import streamlit as st
import streamlit.components.v1 as components
import pandas as pd
import pydeck as pdk
from datetime import date, datetime, timedelta, timezone
import requests
import traceback
import re
import json
import html
from html import escape
import uuid
import base64
import hashlib
import hmac
import secrets
import io
import math
import xml.etree.ElementTree as ET
import os
from pathlib import Path
from urllib.parse import urlencode
from supabase import create_client
from supabase.client import ClientOptions
from streamlit_cookies_controller import CookieController
from openai import OpenAI

# ------------------------------------------------------------------
# Fotocamera posteriore per Foto AI
# Usa la Components v2 API di Streamlit per chiedere al browser
# facingMode="environment". Se il dispositivo/browser non la rispetta,
# fa fallback a una fotocamera disponibile.
# ------------------------------------------------------------------
_REAR_CAMERA_HTML = """
<div class="sanocam">
  <div class="sanocam-video-wrap">
    <video id="video" autoplay playsinline muted></video>
  </div>
  <div id="status" class="sanocam-status"></div>
  <div class="sanocam-actions">
    <button id="capture" type="button">📸</button>
    <button id="switch" type="button" title="Switch camera">🔄</button>
  </div>
  <canvas id="canvas" hidden></canvas>
</div>
"""

_REAR_CAMERA_CSS = """
.sanocam {
  width: 100%;
  max-width: 560px;
  font-family: inherit;
}
.sanocam-video-wrap {
  width: 100%;
  overflow: hidden;
  border-radius: 18px;
  background: #111827;
  aspect-ratio: 4 / 3;
}
.sanocam video {
  width: 100%;
  height: 100%;
  object-fit: cover;
  display: block;
}
.sanocam-actions {
  display: flex;
  gap: 10px;
  justify-content: center;
  margin-top: 10px;
}
.sanocam button {
  border: 0;
  border-radius: 999px;
  min-width: 58px;
  height: 48px;
  padding: 0 18px;
  cursor: pointer;
  font-size: 22px;
  background: #ff8b8b;
  color: #1a2942;
  box-shadow: 0 3px 10px rgba(0,0,0,.12);
}
.sanocam button:active {
  transform: scale(.97);
}
.sanocam-status {
  min-height: 18px;
  margin-top: 6px;
  text-align: center;
  font-size: 13px;
  color: var(--st-text-color, #1a2942);
}
"""

_REAR_CAMERA_JS = r"""
export default function(component) {
  const { parentElement, setStateValue } = component;
  const video = parentElement.querySelector("#video");
  const canvas = parentElement.querySelector("#canvas");
  const capture = parentElement.querySelector("#capture");
  const switchBtn = parentElement.querySelector("#switch");
  const status = parentElement.querySelector("#status");

  let stream = null;
  let usingEnvironment = true;
  let stopped = false;

  async function stopStream() {
    if (stream) {
      stream.getTracks().forEach(track => track.stop());
      stream = null;
    }
  }

  async function startCamera(preferEnvironment = true) {
    await stopStream();
    status.textContent = "";

    const preferred = preferEnvironment ? "environment" : "user";

    try {
      // First try: explicitly request the preferred camera.
      stream = await navigator.mediaDevices.getUserMedia({
        audio: false,
        video: {
          facingMode: { exact: preferred },
          width: { ideal: 1280 },
          height: { ideal: 960 }
        }
      });
    } catch (exactError) {
      try {
        // Fallback: tell the browser which camera we prefer.
        stream = await navigator.mediaDevices.getUserMedia({
          audio: false,
          video: {
            facingMode: { ideal: preferred },
            width: { ideal: 1280 },
            height: { ideal: 960 }
          }
        });
      } catch (idealError) {
        // Final fallback: any available camera.
        stream = await navigator.mediaDevices.getUserMedia({
          audio: false,
          video: true
        });
      }
    }

    if (stopped) {
      await stopStream();
      return;
    }

    video.srcObject = stream;
    await video.play();

    const track = stream.getVideoTracks()[0];
    const settings = track && track.getSettings ? track.getSettings() : {};
    if (settings.facingMode) {
      usingEnvironment = settings.facingMode === "environment";
    } else {
      usingEnvironment = preferEnvironment;
    }
  }

  capture.onclick = () => {
    if (!video.videoWidth || !video.videoHeight) {
      status.textContent = "Camera not ready";
      return;
    }

    // Keep image size reasonable for mobile upload/API usage.
    const maxWidth = 1280;
    const scale = Math.min(1, maxWidth / video.videoWidth);
    canvas.width = Math.round(video.videoWidth * scale);
    canvas.height = Math.round(video.videoHeight * scale);

    const ctx = canvas.getContext("2d");
    ctx.drawImage(video, 0, 0, canvas.width, canvas.height);

    const photo = canvas.toDataURL("image/jpeg", 0.88);
    setStateValue("photo", photo);
    status.textContent = "✓";
  };

  switchBtn.onclick = async () => {
    usingEnvironment = !usingEnvironment;
    try {
      await startCamera(usingEnvironment);
    } catch (err) {
      status.textContent = err && err.message ? err.message : "Camera error";
    }
  };

  if (!navigator.mediaDevices || !navigator.mediaDevices.getUserMedia) {
    status.textContent = "Camera API not supported by this browser";
  } else {
    startCamera(true).catch((err) => {
      status.textContent = err && err.message ? err.message : "Camera error";
    });
  }

  return () => {
    stopped = true;
    stopStream();
  };
}
"""

rear_camera_component = st.components.v2.component(
    "sanasync_rear_camera",
    html=_REAR_CAMERA_HTML,
    css=_REAR_CAMERA_CSS,
    js=_REAR_CAMERA_JS,
)


def rear_camera_input(key):
    """Restituisce BytesIO JPEG quando l'utente scatta una foto."""
    result = rear_camera_component(
        key=key,
        default={"photo": None},
        on_photo_change=lambda: None,
        height=520,
    )

    photo_data_url = getattr(result, "photo", None)
    if not photo_data_url:
        return None

    try:
        _, encoded = str(photo_data_url).split(",", 1)
        image_bytes = base64.b64decode(encoded)
        image_file = io.BytesIO(image_bytes)
        image_file.name = "camera.jpg"
        image_file.type = "image/jpeg"
        return image_file
    except Exception:
        return None


import plotly.express as px
import plotly.graph_objects as go

# ==============================================================================
# LOCAL ASSETS
# ==============================================================================
ASSET_DIR = Path(__file__).resolve().parent
APP_LOGO_FILE = ASSET_DIR / "assets" / "LogoCoral.png"
SIDEBAR_LOGO_FILE = ASSET_DIR / "assets" / "LogoCoral.png"
ZERO_LOGO_FILE = ASSET_DIR / "assets" / "LogoZero.png"

WEIGHT_SOUND_BIG_LOSS = ASSET_DIR / "assets/sounds/bmw-check-oshibka.mp3"
WEIGHT_SOUND_SMALL_LOSS = ASSET_DIR / "assets/sounds/26f8b9_sonic_ring_sound_effect.mp3"
WEIGHT_SOUND_GAIN = ASSET_DIR / "assets/sounds/sonicded.mp3"


# Central sound packs.
# Files are expected under assets/sounds/ in the GitHub repository.

# --- STANDARD ---
STD_SOUND_FOOD = ASSET_DIR / "assets/sounds/super-mario-coin-sound.mp3"
STD_SOUND_RECIPE = ASSET_DIR / "assets/sounds/pokemon-red_blue_yellow-item-found-sound-effect.mp3"
STD_SOUND_AI = ASSET_DIR / "assets/sounds/nintendo-game-boy-startup.mp3"
STD_SOUND_GENERIC_SAVE = ASSET_DIR / "assets/sounds/coin_1.mp3"
STD_SOUND_ZERO_ON = ASSET_DIR / "assets/sounds/kodred (1).mp3"

STANDARD_SOUND_EVENTS = {
    "weight_big_loss": WEIGHT_SOUND_BIG_LOSS,
    "weight_small_loss": WEIGHT_SOUND_SMALL_LOSS,
    "weight_gain": WEIGHT_SOUND_GAIN,

    "food_saved": STD_SOUND_FOOD,
    "food_deleted": STD_SOUND_FOOD,
    "food_updated": STD_SOUND_FOOD,

    "recipe_saved": STD_SOUND_RECIPE,
    "recipe_deleted": STD_SOUND_RECIPE,
    "recipe_shared": STD_SOUND_RECIPE,
    "recipe_unshared": STD_SOUND_RECIPE,
    "recipe_photo_saved": STD_SOUND_RECIPE,

    "ai_food_fit_answer": STD_SOUND_AI,
    "ai_ingredients_analyzed": STD_SOUND_AI,
    "ai_recipe_generated": STD_SOUND_AI,
    "photo_ai_analyzed": STD_SOUND_AI,
    "online_food_selected": STD_SOUND_AI,

    "activity_saved": STD_SOUND_GENERIC_SAVE,
    "activity_deleted": STD_SOUND_GENERIC_SAVE,
    "steps_saved": STD_SOUND_GENERIC_SAVE,
    "day_plan_saved": STD_SOUND_GENERIC_SAVE,
    "profile_saved": STD_SOUND_GENERIC_SAVE,
    "target_changed": STD_SOUND_GENERIC_SAVE,

    # Requested explicitly.
    "zero_mode_on": STD_SOUND_ZERO_ON,
    "zero_mode_off": STD_SOUND_GENERIC_SAVE,
}

# --- ZERO ---
# ZERO now deliberately uses the same sound language as Standard.
ZERO_SOUND_EVENTS = dict(STANDARD_SOUND_EVENTS)


def resolve_ui_sound(event_name, *, zero_mode=None):
    """
    Return the local MP3 path for a semantic UI event.

    Standard and ZERO intentionally share the same sound pack.
    `zero_mode` is retained for backward compatibility with existing calls.
    """
    return STANDARD_SOUND_EVENTS.get(event_name)


def queue_ui_sound(event_name, *, zero_mode=None):
    """Queue a sound so it survives st.rerun()."""
    sound_path = resolve_ui_sound(
        event_name,
        zero_mode=zero_mode,
    )
    if sound_path is not None:
        st.session_state["pending_ui_sound"] = str(sound_path)


def render_pending_ui_sound():
    """Play one queued UI sound exactly once."""
    pending = st.session_state.pop("pending_ui_sound", None)
    if pending:
        play_hidden_local_audio(pending)



def play_hidden_local_audio(audio_path):
    """Riproduce un MP3 locale dopo un'azione utente, senza dipendere da un iframe custom."""
    try:
        audio_path = Path(audio_path)
        if not audio_path.exists():
            print(f"SanoSync sound missing: {audio_path}")
            return False

        # Native Streamlit audio is more robust than an injected zero-size iframe.
        # Modern browsers may still block autoplay until the user has interacted
        # with the page; our current sounds are queued by an explicit save action.
        st.audio(
            audio_path.read_bytes(),
            format="audio/mpeg",
            autoplay=True,
            width=1,
        )
        return True
    except Exception as e:
        print(f"SanoSync sound error: {e}")
        return False


def render_pending_weight_sound():
    """Riproduce una sola volta il suono accodato dopo il salvataggio del peso."""
    pending = st.session_state.pop("pending_weight_sound", None)
    if pending:
        play_hidden_local_audio(pending)


# ==============================================================================
# 1. SETUP INIZIALE E CONFIGURAZIONE PAGINA
# ==============================================================================
st.set_page_config(
    page_title="SanoSync",
    page_icon=str(APP_LOGO_FILE),
    layout="wide",
    initial_sidebar_state="expanded",
)

# ------------------------------------------------------------------------------
# STREAMLIT CHROME
# Keep Streamlit's native top-right Main Menu available: it contains the useful
# Settings -> Appearance selector (Light / Dark / System).
#
# The vertical "More options" button appearing inside/alongside the sidebar is
# unrelated to SanoSync navigation and its popup is clipped by our custom
# sidebar layout, so only that control is hidden.
# ------------------------------------------------------------------------------
st.markdown(
    """
    <style>
    /* Sidebar-only overflow / "More options" control. */
    [data-testid="stSidebar"] button[aria-label="More options"],
    [data-testid="stSidebar"] button[title="More options"],
    [data-testid="stSidebar"] [aria-label="More options"],
    [data-testid="stSidebar"] [title="More options"],
    section[data-testid="stSidebar"] button[aria-label="More options"],
    section[data-testid="stSidebar"] button[title="More options"] {
        display:none !important;
        visibility:hidden !important;
        pointer-events:none !important;
        width:0 !important;
        min-width:0 !important;
        height:0 !important;
        min-height:0 !important;
        margin:0 !important;
        padding:0 !important;
        overflow:hidden !important;
    }

    /* Streamlit has used a few different DOM wrappers for this overflow
       control. Catch the sidebar-local vertical-ellipsis button without
       touching the app-wide Main Menu in the header. */
    [data-testid="stSidebar"] button:has(svg[aria-label="More options"]),
    [data-testid="stSidebar"] button:has([data-icon="more-vertical"]),
    [data-testid="stSidebar"] button:has([data-icon="ellipsis-vertical"]) {
        display:none !important;
        visibility:hidden !important;
        pointer-events:none !important;
    }

    /* Sidebar collapse/open remains available. */
    [data-testid="stSidebarCollapseButton"],
    [data-testid="collapsedControl"] {
        display:flex !important;
        visibility:visible !important;
        pointer-events:auto !important;
    }
    </style>
    """,
    unsafe_allow_html=True,
)



# ==============================================================================
# STYLING CUSTOM (CSS) - CORRETTO PER LEGGIBILITÀ SIDEBAR
# ==============================================================================
st.markdown("""
    <style>
        /* Font globale */
        @import url('https://fonts.googleapis.com/css2?family=Hanken+Grotesk:ital,wght@0,100..900;1,100..900&display=swap');
        html, body, [class*="css"] { font-family: 'Hanken Grotesk', sans-serif; color: #1A2942; }

        /* Sidebar Blu Navy */
        [data-testid="stSidebar"] { background-color: #1A2942; }
        [data-testid="stSidebar"] p, [data-testid="stSidebar"] span, [data-testid="stSidebar"] label { color: #FFFFFF !important; }

        /* PULSANTI SIDEBAR INATTIVI (Bianco con testo Blu Navy ben visibile) */
        [data-testid="stSidebar"] .stButton>button {
            border-radius: 12px;
            font-weight: 600;
            background-color: #FFFFFF !important; 
            color: #1A2942 !important;  /* Testo scuro */
            border: 2px solid #FFFFFF;
            padding: 10px 20px;
            width: 100%;
            transition: all 0.2s ease;
        }
        
        /* Assicura che anche gli elementi interni al bottone ereditino il testo scuro */
        [data-testid="stSidebar"] .stButton>button * {
            color: #1A2942 !important;
        }

        /* PULSANTE ATTIVO / HOVER (Rosa Corallo con testo scuro) */
        [data-testid="stSidebar"] .stButton>button[kind="primary"],
        [data-testid="stSidebar"] .stButton>button:hover, 
        [data-testid="stSidebar"] .stButton>button:focus {
            background-color: #FF8B8B !important; /* Rosa Corallo */
            border-color: #FF8B8B !important;
            color: #1A2942 !important;
        }
        
        [data-testid="stSidebar"] .stButton>button[kind="primary"] *,
        [data-testid="stSidebar"] .stButton>button:hover * {
            color: #1A2942 !important;
        }

        /* Pulsanti fuori dalla sidebar */
        [data-testid="stAppViewContainer"] .stButton > button {
            border-radius: 10px !important;
            background-color: #FFFFFF !important;
            color: #1A2942 !important;
            border: 2px solid #FF8B8B !important;
            font-weight: 600 !important;
            transition: all .18s ease;
        }
        [data-testid="stAppViewContainer"] .stButton > button * {
            color: #1A2942 !important;
            font-weight: 600 !important;
        }
        [data-testid="stAppViewContainer"] .stButton > button:hover {
            background-color: #FFF5F5 !important;
            border-color: #FF8B8B !important;
        }
        [data-testid="stAppViewContainer"] .stButton > button[kind="primary"] {
            background-color: #FF8B8B !important;
            border-color: #FF8B8B !important;
            color: #FFFFFF !important;
            font-weight: 800 !important;
        }
        [data-testid="stAppViewContainer"] .stButton > button[kind="primary"] * {
            color: #FFFFFF !important;
            font-weight: 800 !important;
        }

        /* Sfondo principale SanoSync:
           centro chiaro + sfumature corallo laterali, come nel login. */
        [data-testid="stAppViewContainer"] {
            background:
                radial-gradient(circle at 0% 42%, rgba(255,139,139,.22), transparent 30%),
                radial-gradient(circle at 100% 42%, rgba(255,139,139,.22), transparent 30%),
                linear-gradient(90deg, #FFF4F4 0%, #FFFFFF 22%, #FFFFFF 78%, #FFF4F4 100%) !important;
            background-attachment: fixed !important;
        }

        [data-testid="stMain"] {
            background: transparent !important;
        }

        /* Card-titolo usata in tutte le pagine principali.
           Riprende esattamente il linguaggio visivo della hero del login. */
        .sano-page-hero {
            width: 100%;
            box-sizing: border-box;
            border-radius: 24px;
            padding: 25px 30px;
            margin: .20rem 0 1.25rem 0;
            background:
                radial-gradient(circle at 92% 4%, rgba(255,255,255,.23), transparent 32%),
                linear-gradient(135deg, #172A46 0%, #243B5A 54%, #FF8B8B 155%);
            border: 1px solid rgba(255,139,139,.38);
            box-shadow: 0 16px 40px rgba(35,48,72,.14);
        }

        .sano-page-hero,
        .sano-page-hero * {
            color: #FFFFFF !important;
        }

        .sano-page-kicker {
            font-size: .72rem;
            font-weight: 900;
            letter-spacing: .16em;
            color: #FFD1D1 !important;
            margin-bottom: 6px;
        }

        .sano-page-title {
            font-size: clamp(1.65rem, 3.4vw, 2.35rem);
            line-height: 1.05;
            font-weight: 950;
            letter-spacing: -.035em;
            margin: 0;
        }

        @media (max-width: 700px) {
            .sano-page-hero {
                border-radius: 20px;
                padding: 21px 20px;
                margin-bottom: 1rem;
            }
            .sano-page-title {
                font-size: 1.65rem;
            }
        }

        /* Recipe cards: fixed landscape window, crop centrally */
        .recipe-card-photo {
            width:100%;
            height:230px;
            border-radius:16px;
            background-size:cover;
            background-position:center center;
            background-repeat:no-repeat;
            border:1px solid rgba(255,139,139,.28);
            box-shadow:0 6px 18px rgba(23,42,70,.08);
            margin-bottom:.7rem;
        }
        .recipe-card-photo-placeholder {
            display:flex;
            align-items:center;
            justify-content:center;
            background:
                radial-gradient(circle at 90% 5%, rgba(255,139,139,.20), transparent 35%),
                linear-gradient(145deg,#FFF7F7,#FFFFFF);
            font-size:2.4rem;
        }

        .sano-budget-card {
            border-radius:18px;
            padding:16px 16px 14px;
            margin:.3rem 0 .55rem 0;
            background:
                radial-gradient(circle at 95% 4%, rgba(255,139,139,.16), transparent 36%),
                linear-gradient(145deg, rgba(255,255,255,.11), rgba(255,255,255,.06));
            border:1px solid rgba(255,255,255,.13);
            box-shadow:0 8px 24px rgba(0,0,0,.12);
        }
        .sano-budget-label {
            color:#DDE6F2 !important;
            font-size:.78rem;
            font-weight:750;
            margin-bottom:5px;
        }
        .sano-budget-value {
            color:#FFFFFF !important;
            font-size:1.75rem;
            line-height:1;
            font-weight:950;
            letter-spacing:-.035em;
            margin-bottom:10px;
        }
        .sano-budget-value span { color:#FF332A !important; }
        .sano-budget-track {
            width:100%;
            height:9px;
            overflow:hidden;
            border-radius:999px;
            background:rgba(255,255,255,.92);
            margin:4px 0 8px;
        }
        .sano-budget-fill {
            height:100%;
            border-radius:999px;
            background:linear-gradient(90deg,#FF8B8B,#E6E6E6);
        }

/* STANDARD MODE — sidebar KPI cards */
body:not(:has(.st-key-zero_mode_sidebar_toggle input:checked)) .sano-budget-value,
body:not(:has(.st-key-zero_mode_sidebar_toggle input:checked)) .sano-budget-value span {
    color:#FFFFFF !important;
    -webkit-text-fill-color:#FFFFFF !important;
}

body:not(:has(.st-key-zero_mode_sidebar_toggle input:checked)) .sano-budget-card .sano-budget-value strong,
body:not(:has(.st-key-zero_mode_sidebar_toggle input:checked)) .sano-budget-card .sano-budget-value b {
    color:#FF8B8B !important;
    -webkit-text-fill-color:#FF8B8B !important;
}

/* Make progress proportion visually obvious in Standard mode */
body:not(:has(.st-key-zero_mode_sidebar_toggle input:checked)) .sano-budget-track {
    background:rgba(255,255,255,.88) !important;
    border:1px solid rgba(255,255,255,.22) !important;
}

body:not(:has(.st-key-zero_mode_sidebar_toggle input:checked)) .sano-budget-fill {
    background:linear-gradient(90deg,#FF8B8B,#FFB4B4) !important;
    min-width:3px;
    box-shadow:0 0 0 1px rgba(255,139,139,.12) inset;
}

/* Protein card shares the same component */
body:not(:has(.st-key-zero_mode_sidebar_toggle input:checked)) .sano-protein-card .sano-budget-fill {
    background:linear-gradient(90deg,#FF8B8B,#FFC1C1) !important;
}
        .sano-budget-meta {
            display:flex;
            justify-content:space-between;
            gap:8px;
            color:#E8EEF7 !important;
            font-size:.72rem;
            font-weight:700;
        }
        .sano-budget-meta * { color:#E8EEF7 !important; }

        .sano-ai-coach-card {
            border-radius:18px;
            padding:16px;
            margin:.35rem 0 .6rem 0;
            background:
                radial-gradient(circle at 96% 4%, rgba(255,139,139,.20), transparent 38%),
                linear-gradient(145deg, rgba(255,255,255,.12), rgba(255,255,255,.07));
            border:1px solid rgba(255,255,255,.14);
            box-shadow:0 8px 24px rgba(0,0,0,.12);
        }

        .sano-ai-coach-title {
            color:#FFD0D0 !important;
            -webkit-text-fill-color:#FFD0D0 !important;
            font-size:.82rem;
            font-weight:900;
            letter-spacing:.02em;
            margin-bottom:7px;
        }

        .sano-ai-coach-message,
        .sano-ai-coach-message * {
            color:#FFFFFF !important;
            -webkit-text-fill-color:#FFFFFF !important;
            font-size:.88rem;
            line-height:1.42;
            font-weight:650;
        }

        @media (max-width:700px) {
            .recipe-card-photo { height:180px; }
        }

        /* Insertion-method card */
        [data-testid="stVerticalBlockBorderWrapper"] {
            border-radius:18px !important;
        }

        [data-testid="stVerticalBlockBorderWrapper"] > div {
            border-radius:18px !important;
        }

        /* Activity tab: make the "Altro → Aggiungi" form submit
           match the outlined Passi/Bici buttons. */
        .st-key-activity_add_submit button,
        .st-key-activity_add_submit div[data-testid="stFormSubmitButton"] > button {
            width: 100% !important;
            background: #FFFFFF !important;
            color: #1A2942 !important;
            -webkit-text-fill-color: #1A2942 !important;
            border: 2px solid #FF8B8B !important;
            border-radius: 11px !important;
            font-weight: 800 !important;
            box-shadow: none !important;
        }

        .st-key-activity_add_submit button *,
        .st-key-activity_add_submit div[data-testid="stFormSubmitButton"] > button * {
            color: #1A2942 !important;
            -webkit-text-fill-color: #1A2942 !important;
        }

        .st-key-activity_add_submit button:hover,
        .st-key-activity_add_submit div[data-testid="stFormSubmitButton"] > button:hover {
            background: #FFF5F5 !important;
            border-color: #FF8B8B !important;
            color: #1A2942 !important;
        }


        /* ZERO MODE — the activity submit button must not inherit
           the Standard white/coral treatment above. */
        body:has(.st-key-zero_mode_sidebar_toggle input:checked)
        .st-key-activity_add_submit button,
        body:has(.st-key-zero_mode_sidebar_toggle input:checked)
        .st-key-activity_add_submit div[data-testid="stFormSubmitButton"] > button {
            background:
                linear-gradient(135deg,#E10600,#A90000) !important;
            color:#FFFFFF !important;
            -webkit-text-fill-color:#FFFFFF !important;
            border:1.5px solid #FF3028 !important;
            border-radius:11px !important;
            font-weight:800 !important;
            box-shadow:0 5px 14px rgba(225,6,0,.18) !important;
        }

        body:has(.st-key-zero_mode_sidebar_toggle input:checked)
        .st-key-activity_add_submit button *,
        body:has(.st-key-zero_mode_sidebar_toggle input:checked)
        .st-key-activity_add_submit div[data-testid="stFormSubmitButton"] > button * {
            color:#FFFFFF !important;
            -webkit-text-fill-color:#FFFFFF !important;
        }

        body:has(.st-key-zero_mode_sidebar_toggle input:checked)
        .st-key-activity_add_submit button:hover,
        body:has(.st-key-zero_mode_sidebar_toggle input:checked)
        .st-key-activity_add_submit div[data-testid="stFormSubmitButton"] > button:hover {
            background:
                linear-gradient(135deg,#F20A03,#C10000) !important;
            border-color:#FF4A42 !important;
            color:#FFFFFF !important;
            transform:translateY(-1px);
        }

        /* Metric Cards */
        [data-testid="stMetric"] {
            background-color: #FFFFFF;
            border: 1px solid #FF8B8B;
            padding: 15px;
            border-radius: 14px;
        }
    </style>
""", unsafe_allow_html=True)

# ==============================================================================
# SUPABASE URL & KEY SETUP
# ==============================================================================
SUPABASE_URL = st.secrets["SUPABASE_URL"].rstrip("/")
SUPABASE_KEY = st.secrets["SUPABASE_KEY"]
APP_URL = str(st.secrets.get("APP_URL", "https://sanosync.streamlit.app")).rstrip("/")

# Questo client NON deve mantenere una sessione propria in memoria.
# La sessione persistente viene gestita esplicitamente dal cookie browser.
if "supabase" not in st.session_state:
    st.session_state["supabase"] = create_client(
        SUPABASE_URL,
        SUPABASE_KEY,
        options=ClientOptions(
            auto_refresh_token=False,
            persist_session=False,
        ),
    )

supabase = st.session_state["supabase"]

# Manteniamo il componente cookie associato alla sessione Streamlit corrente.
# Al refresh completo la lettura primaria avviene comunque tramite st.context.cookies.
if "_cookie_controller" not in st.session_state:
    st.session_state["_cookie_controller"] = CookieController()
controller = st.session_state["_cookie_controller"]

# ==============================================================================
# 2. INITIALIZE SESSION STATE
# ==============================================================================
state_defaults = {
    "user": None,
    "m_name": "",
    "m_cals": 0,
    "m_prot": 0,
    "m_carbs": 0,
    "m_fat": 0,
    "last_selected": "",
    "form_version": 0,
    "last_source": None,
    "grams_val": 100.0,
    "api_res": {},
    "overview_date": date.today(),
    "last_nav_page": None,
    "selected_recipe": None,
    "prod_select": "",
    "recipe_builder_ingredients": [],
    "selected_recipe_ingredients": None,
    "selected_recipe_servings": None,
    "selected_source_note": "",
    "selected_source_category": "Casa",
    "day_plan_type": "Lavoro da casa",
    "day_plan_activity": "Riposo",
}

for key, default in state_defaults.items():
    if key not in st.session_state:
        st.session_state[key] = default

# ==============================================================================
# 3. UTILITY FUNCTIONS
# ==============================================================================
def parse_birth_date(value):
    """Converte birth_date dai metadata Supabase in datetime.date."""
    if value in (None, ""):
        return None
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    try:
        return datetime.strptime(str(value), "%Y-%m-%d").date()
    except (TypeError, ValueError):
        return None


def calculate_age(birth_date_value, on_date=None):
    """Età anagrafica completa alla data indicata (default: oggi)."""
    birth_date = parse_birth_date(birth_date_value)
    if birth_date is None:
        return None

    today = on_date or date.today()
    return (
        today.year
        - birth_date.year
        - (
            (today.month, today.day)
            < (birth_date.month, birth_date.day)
        )
    )


DEFICIT_PRESETS = {
    "maintenance": 0,
    "slow": 250,
    "medium": 500,
    "fast": 750,
    "custom": 0,
}

DEFICIT_PRESET_LABELS = {
    "Italiano": {
        "maintenance": "Mantenimento peso · 0 kcal",
        "custom": "Custom",
        "slow": "Lento · 250 kcal",
        "medium": "Medio · 500 kcal",
        "fast": "Veloce · 750 kcal",
        "title": "🎯 Obiettivo calorico",
        "speed": "Obiettivo peso",
        "field": "Deficit kcal di base",
        "help": (
            "Scegli Mantenimento peso per usare un deficit di 0 kcal, "
            "oppure un preset di dimagrimento. Il valore sotto resta sempre modificabile manualmente."
        ),
    },
    "English": {
        "maintenance": "Weight maintenance · 0 kcal",
        "custom": "Custom",
        "slow": "Slow · 250 kcal",
        "medium": "Medium · 500 kcal",
        "fast": "Fast · 750 kcal",
        "title": "🎯 Calorie target",
        "speed": "Weight goal",
        "field": "Base calorie deficit",
        "help": (
            "Choose Weight maintenance for a 0 kcal deficit, "
            "or select a weight-loss preset. You can always edit the value below manually."
        ),
    },
    "Nederlands": {
        "maintenance": "Gewicht behouden · 0 kcal",
        "custom": "Aangepast",
        "slow": "Langzaam · 250 kcal",
        "medium": "Gemiddeld · 500 kcal",
        "fast": "Snel · 750 kcal",
        "title": "🎯 Caloriedoel",
        "speed": "Gewichtsdoel",
        "field": "Basis calorietekort",
        "help": (
            "Kies Gewicht behouden voor een tekort van 0 kcal, "
            "of selecteer een afvalpreset. Je kunt de waarde hieronder altijd handmatig wijzigen."
        ),
    },
    "Português": {
        "maintenance": "Manutenção do peso · 0 kcal",
        "custom": "Personalizado",
        "slow": "Lento · 250 kcal",
        "medium": "Médio · 500 kcal",
        "fast": "Rápido · 750 kcal",
        "title": "🎯 Objetivo calórico",
        "speed": "Objetivo de peso",
        "field": "Défice calórico base",
        "help": (
            "Escolha Manutenção do peso para um défice de 0 kcal, "
            "ou selecione um objetivo de perda de peso."
        ),
    },
    "Français": {
        "maintenance": "Maintien du poids · 0 kcal",
        "custom": "Personnalisé",
        "slow": "Lent · 250 kcal",
        "medium": "Moyen · 500 kcal",
        "fast": "Rapide · 750 kcal",
        "title": "🎯 Objectif calorique",
        "speed": "Objectif de poids",
        "field": "Déficit calorique de base",
        "help": (
            "Choisissez Maintien du poids pour un déficit de 0 kcal, "
            "ou un préréglage de perte de poids. Vous pouvez toujours modifier la valeur ci-dessous."
        ),
    },
}


def _ui_language():
    """Lingua corrente; prima del login usa Italiano come fallback."""
    lang = st.session_state.get("lang_selector", "Italiano")
    return lang if lang in DEFICIT_PRESET_LABELS else "Italiano"


def deficit_preset_label(preset_key):
    lang = _ui_language()
    return DEFICIT_PRESET_LABELS[lang].get(
        preset_key,
        DEFICIT_PRESET_LABELS[lang]["custom"],
    )


def normalize_deficit_plan(value):
    """Compatibilità con valori salvati dalle versioni precedenti."""
    raw = str(value or "").strip().casefold()

    if raw in {
        "maintenance",
        "mantenimento",
        "mantenimento peso",
        "weight maintenance",
        "gewicht behouden",
        "maintien du poids",
    }:
        return "maintenance"
    if raw in {"custom", "aangepast", "personnalisé", "personalizzato"}:
        return "custom"
    if raw in {"slow", "lento", "langzaam", "lent"} or "250" in raw:
        return "slow"
    if raw in {"medium", "medio", "gemiddeld", "moyen"} or "500" in raw:
        return "medium"
    if raw in {"fast", "veloce", "snel", "rapide"} or "750" in raw:
        return "fast"
    return "custom"


def deficit_preset_from_value(value):
    try:
        value = int(round(float(value)))
    except (TypeError, ValueError):
        return "custom"

    if value == 0:
        return "maintenance"

    for key, kcal in DEFICIT_PRESETS.items():
        if key == "custom":
            continue
        if kcal == value:
            return key
    return "custom"


def resolve_deficit_target(preset_key, entered_value=None):
    """
    Il campo kcal è sempre la fonte di verità.
    Il preset serve solo a precompilarlo.
    """
    try:
        return max(0, int(round(float(entered_value))))
    except (TypeError, ValueError):
        return int(DEFICIT_PRESETS.get(preset_key, 0))



def calculate_bmr(weight, height, birth_date_value, gender):
    """
    BMR secondo Mifflin-St Jeor.

    Uomo:  10W + 6.25H - 5A + 5
    Donna: 10W + 6.25H - 5A - 161

    W = peso in kg, H = altezza in cm, A = età in anni.
    """
    age = calculate_age(birth_date_value)
    if age is None:
        return None

    weight = float(weight)
    height = float(height)

    if gender in ["Uomo", "Male", "Man"]:
        return int(round((10 * weight) + (6.25 * height) - (5 * age) + 5))

    return int(round((10 * weight) + (6.25 * height) - (5 * age) - 161))

def refresh_daily_logs(log_date=None):
    """Invalidate only caches backed by user nutrition/activity data."""
    for _name in (
        "load_daily_meals_cached",
        "load_daily_activities_cached",
        "load_daily_log_cached",
        "load_weight_history_cached",
        "load_quick_meal_rows_cached",
    ):
        _fn = globals().get(_name)
        if _fn is not None and hasattr(_fn, "clear"):
            try:
                _fn.clear()
            except Exception as _exc:
                print(f"Cache clear failed for {_name}: {_exc}")

def _safe_float(value):
    try:
        if value in (None, ""):
            return 0.0
        return float(value)
    except (TypeError, ValueError):
        return 0.0


# ==============================================================================
# DIRECT SUPABASE DATA ACCESS
# ==============================================================================
# Legacy Streamlit app: user data is read/written directly in Supabase.
# Function names keep the old *_api suffix where necessary so the rest of the
# existing UI does not need invasive changes.

def _require_authenticated_user():
    if not st.session_state.get("auth_access_token"):
        raise RuntimeError("Sessione autenticata non disponibile.")
    if not user_id:
        raise RuntimeError("Utente autenticato non disponibile.")


def _response_data(response):
    data = getattr(response, "data", None)
    return data if isinstance(data, list) else []


# ---- MEALS -------------------------------------------------------------------

def fetch_daily_meals_from_api(cache_user_id, cache_date, access_token=None):
    _require_authenticated_user()
    response = (
        supabase.table("meals")
        .select("*")
        .eq("user_id", cache_user_id)
        .eq("date", str(cache_date))
        .order("id", desc=True)
        .execute()
    )
    return _response_data(response)


def create_meal_via_api(payload, access_token=None):
    _require_authenticated_user()
    db_payload = dict(payload)
    db_payload["user_id"] = user_id
    response = supabase.table("meals").insert(db_payload).execute()
    rows = _response_data(response)
    return rows[0] if rows else None


def update_meal_via_api(meal_id, payload, access_token=None):
    _require_authenticated_user()
    db_payload = dict(payload)
    db_payload.pop("user_id", None)
    response = (
        supabase.table("meals")
        .update(db_payload)
        .eq("id", meal_id)
        .eq("user_id", user_id)
        .execute()
    )
    rows = _response_data(response)
    return rows[0] if rows else None


def delete_meal_via_api(meal_id, access_token=None):
    _require_authenticated_user()
    (
        supabase.table("meals")
        .delete()
        .eq("id", meal_id)
        .eq("user_id", user_id)
        .execute()
    )
    return True


def fetch_meal_history_from_api(access_token=None):
    _require_authenticated_user()
    response = (
        supabase.table("meals")
        .select("*")
        .eq("user_id", user_id)
        .order("date", desc=True)
        .order("id", desc=True)
        .execute()
    )
    return _response_data(response)


def fetch_meals_range_from_api(start_date, end_date, access_token=None):
    _require_authenticated_user()
    response = (
        supabase.table("meals")
        .select("*")
        .eq("user_id", user_id)
        .gte("date", str(start_date))
        .lte("date", str(end_date))
        .order("date", desc=True)
        .order("id", desc=True)
        .execute()
    )
    return _response_data(response)


def fetch_meals_by_type_from_api(meal_type, access_token=None):
    _require_authenticated_user()
    response = (
        supabase.table("meals")
        .select("*")
        .eq("user_id", user_id)
        .eq("meal_type", meal_type)
        .order("date", desc=True)
        .order("id", desc=True)
        .execute()
    )
    return _response_data(response)


# ---- ACTIVITIES --------------------------------------------------------------

def fetch_daily_activities_from_api(cache_user_id, cache_date, access_token=None):
    _require_authenticated_user()
    response = (
        supabase.table("activities")
        .select("*")
        .eq("user_id", cache_user_id)
        .eq("date", str(cache_date))
        .order("id", desc=True)
        .execute()
    )
    return _response_data(response)


def fetch_activities_range_from_api(start_date, end_date, access_token=None):
    _require_authenticated_user()
    response = (
        supabase.table("activities")
        .select("*")
        .eq("user_id", user_id)
        .gte("date", str(start_date))
        .lte("date", str(end_date))
        .order("date", desc=True)
        .order("id", desc=True)
        .execute()
    )
    return _response_data(response)


def create_activity_via_api(payload, access_token=None):
    _require_authenticated_user()
    db_payload = dict(payload)
    db_payload["user_id"] = user_id
    response = supabase.table("activities").insert(db_payload).execute()
    rows = _response_data(response)
    return rows[0] if rows else None


def update_activity_via_api(activity_id, payload, access_token=None):
    _require_authenticated_user()
    db_payload = dict(payload)
    db_payload.pop("user_id", None)
    response = (
        supabase.table("activities")
        .update(db_payload)
        .eq("id", activity_id)
        .eq("user_id", user_id)
        .execute()
    )
    rows = _response_data(response)
    return rows[0] if rows else None


def delete_activity_via_api(activity_id, access_token=None):
    _require_authenticated_user()
    (
        supabase.table("activities")
        .delete()
        .eq("id", activity_id)
        .eq("user_id", user_id)
        .execute()
    )
    return True


def upsert_named_activity_via_api(
    *,
    cache_user_id,
    log_date,
    activity_name,
    burned_calories,
    access_token=None,
):
    rows = fetch_daily_activities_from_api(
        cache_user_id, str(log_date), access_token
    )
    existing = next(
        (
            row
            for row in rows
            if str(row.get("activity_name") or "").strip().casefold()
            == str(activity_name).strip().casefold()
        ),
        None,
    )
    payload = {
        "date": str(log_date),
        "activity_name": activity_name,
        "burned_calories": int(burned_calories),
    }
    if existing and existing.get("id"):
        return update_activity_via_api(
            existing["id"], payload, access_token
        )
    return create_activity_via_api(payload, access_token)


# ---- GPX + STEP OFFSET --------------------------------------------------------

_STEP_CONFLICT_TOKENS = (
    "corsa", "running", "cammin", "walk", "trekking", "hiking", "padel",
)


def _is_step_conflicting_activity(activity_name):
    name = str(activity_name or "").strip().casefold()
    return any(token in name for token in _STEP_CONFLICT_TOKENS)


def calculate_step_calorie_offset(total_steps, activities):
    """Subtract steps already represented by structured activities."""
    total_steps = max(0, int(total_steps or 0))
    consumed_steps = 0
    has_unknown_overlap = False

    for activity in activities or []:
        name = activity.get("activity_name")
        if not _is_step_conflicting_activity(name):
            continue

        try:
            activity_steps = max(
                0, int(activity.get("activity_steps") or 0)
            )
        except Exception:
            activity_steps = 0

        if activity_steps > 0:
            consumed_steps += activity_steps
        elif str(name or "").strip().casefold() != "passi (stima)":
            # Old manually-entered Padel/Corsa rows do not tell us how many
            # daily steps they already contain. Keep the conservative old rule.
            has_unknown_overlap = True

    eligible_steps = (
        0
        if has_unknown_overlap
        else max(0, total_steps - consumed_steps)
    )
    return {
        "total_steps": total_steps,
        "activity_steps": min(consumed_steps, total_steps),
        "eligible_steps": eligible_steps,
        "estimated_kcal": int(eligible_steps * 0.04),
        "has_unknown_overlap": has_unknown_overlap,
    }


def recalculate_step_calories_for_day(
    current_user_id,
    log_date,
    *,
    total_steps=None,
):
    if total_steps is None:
        daily_log = fetch_daily_log_from_api(
            current_user_id,
            str(log_date),
            st.session_state.get("auth_access_token"),
        )
        total_steps = int((daily_log or {}).get("steps") or 0)

    activities = fetch_daily_activities_from_api(
        current_user_id,
        str(log_date),
        st.session_state.get("auth_access_token"),
    )
    info = calculate_step_calorie_offset(total_steps, activities)

    upsert_named_activity_via_api(
        cache_user_id=current_user_id,
        log_date=log_date,
        activity_name="Passi (Stima)",
        burned_calories=info["estimated_kcal"],
        access_token=st.session_state.get("auth_access_token"),
    )
    return info


def _haversine_km(lat1, lon1, lat2, lon2):
    radius_km = 6371.0088
    lat1_r = math.radians(lat1)
    lat2_r = math.radians(lat2)
    dlat = lat2_r - lat1_r
    dlon = math.radians(lon2 - lon1)
    a = (
        math.sin(dlat / 2) ** 2
        + math.cos(lat1_r) * math.cos(lat2_r)
        * math.sin(dlon / 2) ** 2
    )
    return 2 * radius_km * math.asin(min(1.0, math.sqrt(a)))


def _parse_gpx_time(value):
    value = str(value or "").strip()
    if not value:
        return None
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    except Exception:
        return None


def parse_gpx_activity(file_bytes, filename="activity.gpx"):
    """Parse GPX locally, including Zepp/Amazfit Garmin extensions."""
    if not file_bytes:
        raise ValueError("Il file GPX è vuoto.")
    if len(file_bytes) > 15 * 1024 * 1024:
        raise ValueError("Il file GPX supera il limite di 15 MB.")

    try:
        root = ET.fromstring(file_bytes)
    except Exception as exc:
        raise ValueError(f"GPX non valido: {exc}") from exc

    creator = str(root.attrib.get("creator") or "").strip()
    points = []

    for node in root.iter():
        if str(node.tag).split("}")[-1].lower() != "trkpt":
            continue
        try:
            lat = float(node.attrib["lat"])
            lon = float(node.attrib["lon"])
        except Exception:
            continue

        point = {
            "lat": lat, "lon": lon, "time": None, "hr": None,
            "cad": None, "speed": None,
        }
        for child in node.iter():
            local = str(child.tag).split("}")[-1].lower()
            value = str(child.text or "").strip()
            if not value:
                continue
            if local == "time":
                point["time"] = _parse_gpx_time(value)
            elif local in {"hr", "cad", "speed"}:
                try:
                    point[local] = float(value)
                except Exception:
                    pass
        points.append(point)

    if len(points) < 2:
        raise ValueError(
            "Il GPX non contiene abbastanza punti traccia per essere analizzato."
        )

    distance_km = 0.0
    for previous, current in zip(points, points[1:]):
        segment = _haversine_km(
            previous["lat"], previous["lon"],
            current["lat"], current["lon"],
        )
        if segment <= 1.0:
            distance_km += segment

    timed = [p for p in points if p.get("time") is not None]
    start_time = timed[0]["time"] if timed else None
    end_time = timed[-1]["time"] if timed else None
    duration_seconds = (
        max(0, int((end_time - start_time).total_seconds()))
        if start_time and end_time else 0
    )

    hr_values = [
        p["hr"] for p in points
        if p.get("hr") is not None and p["hr"] > 0
    ]
    cad_values = [
        p["cad"] for p in points
        if p.get("cad") is not None and p["cad"] > 0
    ]
    avg_hr = sum(hr_values) / len(hr_values) if hr_values else None
    avg_cad_raw = (
        sum(cad_values) / len(cad_values) if cad_values else None
    )

    # Keep a reasonably detailed route for maps without storing thousands
    # of redundant GPS points in Supabase.
    raw_route = [
        {"lat": round(float(p["lat"]), 6), "lon": round(float(p["lon"]), 6)}
        for p in points
    ]
    max_route_points = 1200
    if len(raw_route) > max_route_points:
        step = max(1, math.ceil(len(raw_route) / max_route_points))
        route_points = raw_route[::step]
        if route_points[-1] != raw_route[-1]:
            route_points.append(raw_route[-1])
    else:
        route_points = raw_route

    creator_cf = creator.casefold()
    cadence_factor = 1.0
    if (
        avg_cad_raw
        and ("amazfit" in creator_cf or "zepp" in creator_cf)
        and avg_cad_raw < 120
    ):
        # Zepp/Amazfit running GPX commonly stores strides/minute.
        cadence_factor = 2.0

    # Compact GPX time series used by the activity charts.
    sensor_source = []
    if start_time is not None:
        for p in points:
            point_time = p.get("time")
            if point_time is None:
                continue
            elapsed_min = max(
                0.0,
                (point_time - start_time).total_seconds() / 60.0,
            )
            hr_value = p.get("hr")
            cad_value = p.get("cad")
            sensor_source.append(
                {
                    "minute": round(elapsed_min, 2),
                    "hr": (
                        round(float(hr_value), 1)
                        if hr_value is not None and hr_value > 0
                        else None
                    ),
                    "cadence": (
                        round(float(cad_value) * cadence_factor, 1)
                        if cad_value is not None and cad_value > 0
                        else None
                    ),
                }
            )

    max_sensor_points = 700
    if len(sensor_source) > max_sensor_points:
        sensor_step = max(
            1,
            math.ceil(len(sensor_source) / max_sensor_points),
        )
        sensor_series = sensor_source[::sensor_step]
        if sensor_series[-1] != sensor_source[-1]:
            sensor_series.append(sensor_source[-1])
    else:
        sensor_series = sensor_source

    estimated_steps = 0.0
    for previous, current in zip(points, points[1:]):
        t1, t2 = previous.get("time"), current.get("time")
        if not t1 or not t2:
            continue
        seconds = (t2 - t1).total_seconds()
        if seconds <= 0 or seconds > 120:
            continue
        samples = [
            c for c in (previous.get("cad"), current.get("cad"))
            if c is not None and c >= 0
        ]
        if samples:
            estimated_steps += (
                (sum(samples) / len(samples))
                * cadence_factor
                * seconds / 60.0
            )

    if estimated_steps <= 0 and avg_cad_raw and duration_seconds > 0:
        estimated_steps = (
            avg_cad_raw * cadence_factor * duration_seconds / 60.0
        )

    return {
        "filename": str(filename or "activity.gpx"),
        "creator": creator,
        "source_ref": hashlib.sha256(file_bytes).hexdigest(),
        "start_time": start_time,
        "date": start_time.date() if start_time else None,
        "duration_seconds": duration_seconds,
        "distance_km": round(distance_km, 3),
        "avg_hr": round(avg_hr, 1) if avg_hr is not None else None,
        "avg_cadence_raw": (
            round(avg_cad_raw, 1) if avg_cad_raw is not None else None
        ),
        "cadence_factor": cadence_factor,
        "avg_step_cadence": (
            round(avg_cad_raw * cadence_factor, 1)
            if avg_cad_raw is not None else None
        ),
        "estimated_steps": max(0, int(round(estimated_steps))),
        "point_count": len(points),
        "route_points": route_points,
        "sensor_series": sensor_series,
    }


def nearest_weight_for_date(current_user_id, target_date):
    response = (
        supabase.table("daily_logs")
        .select("date,weight")
        .eq("user_id", current_user_id)
        .order("date", desc=True)
        .execute()
    )
    rows = getattr(response, "data", None) or []
    candidates = []

    for row in rows:
        if row.get("weight") is None or not row.get("date"):
            continue
        try:
            row_date = date.fromisoformat(str(row["date"]))
            weight = float(row["weight"])
            if weight > 0:
                candidates.append(
                    (abs((row_date - target_date).days), row_date, weight)
                )
        except Exception:
            continue

    if not candidates:
        return None, None

    candidates.sort(key=lambda item: (item[0], -item[1].toordinal()))
    _, weight_date, weight = candidates[0]
    return weight, weight_date


_GPX_KCAL_COEFFICIENTS = {
    "Corsa": 1.00,
    "Camminata": 0.53,
    "Trekking": 0.65,
    "Bici": 0.30,
    "Altro": 0.70,
}


def estimate_gpx_kcal(activity_type, distance_km, weight_kg):
    coefficient = _GPX_KCAL_COEFFICIENTS.get(
        str(activity_type), _GPX_KCAL_COEFFICIENTS["Altro"]
    )
    return max(
        0,
        int(round(
            float(distance_km or 0)
            * float(weight_kg or 0)
            * coefficient
        )),
    )


def _format_duration(seconds):
    seconds = max(0, int(seconds or 0))
    hours, remainder = divmod(seconds, 3600)
    minutes, secs = divmod(remainder, 60)
    return (
        f"{hours}:{minutes:02d}:{secs:02d}"
        if hours else f"{minutes}:{secs:02d}"
    )


def fetch_gpx_activity_log(current_user_id, limit=50):
    _require_authenticated_user()
    response = (
        supabase.table("activities")
        .select("*")
        .eq("user_id", current_user_id)
        .eq("source", "gpx")
        .order("date", desc=True)
        .order("id", desc=True)
        .limit(int(limit))
        .execute()
    )
    return _response_data(response)


def _route_points_from_activity(activity):
    raw = activity.get("route_points") or []
    route = []
    for point in raw:
        try:
            if isinstance(point, dict):
                lat = float(point.get("lat"))
                lon = float(point.get("lon"))
            elif isinstance(point, (list, tuple)) and len(point) >= 2:
                lat = float(point[0])
                lon = float(point[1])
            else:
                continue
            route.append({"lat": lat, "lon": lon})
        except Exception:
            continue
    return route


def render_gpx_route_map(route_points, *, height=430):
    route = _route_points_from_activity({"route_points": route_points})
    if len(route) < 2:
        st.info("Mappa non disponibile per questa attività.")
        return

    lats = [p["lat"] for p in route]
    lons = [p["lon"] for p in route]
    center_lat = sum(lats) / len(lats)
    center_lon = sum(lons) / len(lons)
    span = max(max(lats) - min(lats), max(lons) - min(lons))

    if span < 0.01:
        zoom = 14
    elif span < 0.03:
        zoom = 13
    elif span < 0.08:
        zoom = 12
    elif span < 0.18:
        zoom = 11
    elif span < 0.40:
        zoom = 10
    else:
        zoom = 9

    path = [[p["lon"], p["lat"]] for p in route]

    deck = pdk.Deck(
        map_style="https://basemaps.cartocdn.com/gl/positron-gl-style/style.json",
        initial_view_state=pdk.ViewState(
            latitude=center_lat,
            longitude=center_lon,
            zoom=zoom,
            pitch=0,
        ),
        layers=[
            pdk.Layer(
                "PathLayer",
                data=[{"path": path}],
                get_path="path",
                get_width=5,
                width_min_pixels=3,
                pickable=False,
            ),
            pdk.Layer(
                "ScatterplotLayer",
                data=[
                    {
                        "lon": route[0]["lon"],
                        "lat": route[0]["lat"],
                        "label": "Partenza",
                    },
                    {
                        "lon": route[-1]["lon"],
                        "lat": route[-1]["lat"],
                        "label": "Arrivo",
                    },
                ],
                get_position="[lon, lat]",
                get_radius=18,
                radius_min_pixels=5,
                pickable=True,
            ),
        ],
        tooltip={"text": "{label}"},
    )
    st.pydeck_chart(deck, use_container_width=True, height=height)


# ---- DAILY LOGS --------------------------------------------------------------

def fetch_daily_log_from_api(cache_user_id, cache_date, access_token=None):
    _require_authenticated_user()
    response = (
        supabase.table("daily_logs")
        .select("*")
        .eq("user_id", cache_user_id)
        .eq("date", str(cache_date))
        .limit(1)
        .execute()
    )
    rows = _response_data(response)
    return rows[0] if rows else None


def update_daily_log_via_api(log_date, values, access_token=None):
    _require_authenticated_user()
    db_payload = dict(values)
    db_payload.pop("user_id", None)
    db_payload.pop("date", None)

    existing = fetch_daily_log_from_api(user_id, log_date, access_token)

    if existing and existing.get("id"):
        response = (
            supabase.table("daily_logs")
            .update(db_payload)
            .eq("id", existing["id"])
            .eq("user_id", user_id)
            .execute()
        )
    else:
        insert_payload = dict(db_payload)
        insert_payload["user_id"] = user_id
        insert_payload["date"] = str(log_date)
        response = (
            supabase.table("daily_logs")
            .insert(insert_payload)
            .execute()
        )

    rows = _response_data(response)
    return rows[0] if rows else None


# ---- WEIGHT (stored in daily_logs.weight) ------------------------------------

def fetch_weight_history_from_api(cache_user_id, access_token=None):
    _require_authenticated_user()
    response = (
        supabase.table("daily_logs")
        .select("id,date,weight")
        .eq("user_id", cache_user_id)
        .order("date", desc=True)
        .order("id", desc=True)
        .execute()
    )
    return [
        row
        for row in _response_data(response)
        if row.get("weight") is not None
    ]


def create_weight_via_api(log_date, weight, access_token=None):
    return update_daily_log_via_api(
        log_date,
        {"weight": float(weight)},
        access_token,
    )


def update_weight_via_api(
    row_id,
    *,
    log_date=None,
    weight=None,
    access_token=None,
):
    _require_authenticated_user()
    payload = {}
    if log_date is not None:
        payload["date"] = str(log_date)
    if weight is not None:
        payload["weight"] = float(weight)
    if not payload:
        return None

    response = (
        supabase.table("daily_logs")
        .update(payload)
        .eq("id", row_id)
        .eq("user_id", user_id)
        .execute()
    )
    rows = _response_data(response)
    return rows[0] if rows else None


def delete_weight_via_api(row_id, access_token=None):
    _require_authenticated_user()
    (
        supabase.table("daily_logs")
        .update({"weight": None})
        .eq("id", row_id)
        .eq("user_id", user_id)
        .execute()
    )
    return True


def weight_rows_for_range(
    cache_user_id,
    start_date,
    end_date,
    access_token=None,
):
    rows = fetch_weight_history_from_api(cache_user_id, access_token)
    start_s = str(start_date)
    end_s = str(end_date)
    return [
        row
        for row in rows
        if start_s <= str(row.get("date") or "") <= end_s
    ]


# ---- RECIPES -----------------------------------------------------------------

def fetch_personal_recipes_from_api(access_token=None):
    _require_authenticated_user()
    response = (
        supabase.table("recipe_library")
        .select("*")
        .eq("user_id", user_id)
        .order("id", desc=True)
        .execute()
    )
    return _response_data(response)


def fetch_available_recipes_from_api(access_token=None):
    _require_authenticated_user()
    own = fetch_personal_recipes_from_api(access_token)
    shared_response = (
        supabase.table("recipe_library")
        .select("*")
        .eq("is_shared", True)
        .order("id", desc=True)
        .execute()
    )
    shared = _response_data(shared_response)

    result = []
    seen_ids = set()
    for row in own + shared:
        row_id = (
            str(row.get("id"))
            if row.get("id") is not None
            else None
        )
        if row_id and row_id in seen_ids:
            continue
        if row_id:
            seen_ids.add(row_id)
        result.append(row)
    return result


def fetch_shared_recipes_from_api(access_token=None):
    _require_authenticated_user()
    response = (
        supabase.table("recipe_library")
        .select("*")
        .eq("is_shared", True)
        .order("id", desc=True)
        .execute()
    )
    return _response_data(response)


def fetch_recipe_by_id_from_api(recipe_id, access_token=None):
    _require_authenticated_user()
    response = (
        supabase.table("recipe_library")
        .select("*")
        .eq("id", recipe_id)
        .limit(1)
        .execute()
    )
    rows = _response_data(response)
    if not rows:
        return None

    row = rows[0]
    if (
        str(row.get("user_id")) != str(user_id)
        and not bool(row.get("is_shared"))
    ):
        return None
    return row


def create_recipe_via_api(payload, access_token=None):
    _require_authenticated_user()
    db_payload = dict(payload)
    db_payload["user_id"] = user_id
    response = (
        supabase.table("recipe_library")
        .insert(db_payload)
        .execute()
    )
    rows = _response_data(response)
    return rows[0] if rows else None


def update_recipe_via_api(recipe_id, payload, access_token=None):
    _require_authenticated_user()
    db_payload = dict(payload)
    db_payload.pop("user_id", None)
    response = (
        supabase.table("recipe_library")
        .update(db_payload)
        .eq("id", recipe_id)
        .eq("user_id", user_id)
        .execute()
    )
    rows = _response_data(response)
    return rows[0] if rows else None


def set_recipe_sharing_via_api(
    recipe_id,
    is_shared,
    access_token=None,
):
    return update_recipe_via_api(
        recipe_id,
        {"is_shared": bool(is_shared)},
        access_token,
    )


def delete_recipe_via_api(recipe_id, access_token=None):
    _require_authenticated_user()
    (
        supabase.table("recipe_library")
        .delete()
        .eq("id", recipe_id)
        .eq("user_id", user_id)
        .execute()
    )
    return True


# ==============================================================================
# CACHED USER-DATA READS
# ==============================================================================
# Streamlit reruns the full script after most interactions. These short-lived
# caches centralise the hottest Supabase reads. Every cache key includes user_id.

@st.cache_data(ttl=30, show_spinner=False)
def load_daily_meals_cached(
    cache_user_id,
    cache_date,
    access_token,
):
    return fetch_daily_meals_from_api(
        cache_user_id,
        cache_date,
        access_token,
    )


@st.cache_data(ttl=30, show_spinner=False)
def load_daily_activities_cached(
    cache_user_id,
    cache_date,
    access_token,
):
    return fetch_daily_activities_from_api(
        cache_user_id,
        cache_date,
        access_token,
    )


@st.cache_data(ttl=30, show_spinner=False)
def load_daily_log_cached(cache_user_id, cache_date, access_token):
    row = fetch_daily_log_from_api(
        cache_user_id,
        cache_date,
        access_token,
    )
    return [row] if row else []


@st.cache_data(ttl=90, show_spinner=False)
def load_weight_history_cached(cache_user_id, access_token):
    return fetch_weight_history_from_api(
        cache_user_id,
        access_token,
    )


@st.cache_data(ttl=60, show_spinner=False)
def load_quick_meal_rows_cached(cache_user_id):
    return fetch_meal_history_from_api(
        st.session_state.get("auth_access_token")
    )


def get_daily_totals(target_date):
    meals = load_daily_meals_cached(
        user_id,
        str(target_date),
        st.session_state.get("auth_access_token"),
    )
    activities = load_daily_activities_cached(
        user_id,
        str(target_date),
        st.session_state.get("auth_access_token"),
    )
    return {
        "meals": meals,
        "activities": activities,
        "calories": sum(_safe_float(x.get("calories")) for x in meals),
        "protein": sum(_safe_float(x.get("protein")) for x in meals),
        "carbs": sum(_safe_float(x.get("carbs")) for x in meals),
        "fat": sum(_safe_float(x.get("fat")) for x in meals),
        "activity": sum(
            _safe_float(x.get("burned_calories"))
            for x in activities
        ),
    }





@st.cache_data(ttl=300, show_spinner=False)
def get_groq_available_model_ids():
    """
    Return the model IDs ACTUALLY available to the configured Groq key/project.

    We use the REST /models endpoint directly instead of depending on a specific
    openai-python client version.
    """
    api_key = st.secrets.get("GROQ_API_KEY")
    if not api_key:
        return []

    try:
        response = requests.get(
            "https://api.groq.com/openai/v1/models",
            headers={
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json",
                "Accept": "application/json",
            },
            timeout=15,
        )
        response.raise_for_status()
        payload = response.json()
        return [
            str(item.get("id"))
            for item in (payload.get("data") or [])
            if item.get("id")
        ]
    except Exception as exc:
        print(f"Groq models lookup error: {exc}")
        return []


def resolve_groq_text_model():
    """
    Pick a text model that this specific Groq project can actually use.

    Preference intentionally starts with current GPT-OSS production models,
    because the user's project has returned model_not_found for both Llama
    production IDs.
    """
    available = set(get_groq_available_model_ids())

    preferred = [
        "openai/gpt-oss-20b",
        "openai/gpt-oss-120b",
        "qwen/qwen3.6-27b",
        "llama-3.3-70b-versatile",
        "llama-3.1-8b-instant",
        "groq/compound-mini",
        "groq/compound",
    ]

    for model_id in preferred:
        if model_id in available:
            return model_id

    # Last-resort: select the first non-audio / non-safety active model.
    excluded_tokens = (
        "whisper",
        "orpheus",
        "guard",
        "safeguard",
        "prompt-guard",
    )
    candidates = [
        m
        for m in sorted(available)
        if not any(token in m.lower() for token in excluded_tokens)
    ]
    if candidates:
        return candidates[0]

    raise RuntimeError(
        "Groq non restituisce alcun modello testuale disponibile per questa API key. "
        "Controlla la chiave/progetto nella Groq Console."
    )


def resolve_groq_vision_model():
    """Pick an actually available multimodal/vision model."""
    available = set(get_groq_available_model_ids())

    preferred = [
        "qwen/qwen3.6-27b",
    ]
    for model_id in preferred:
        if model_id in available:
            return model_id

    raise RuntimeError(
        "Nessun modello Vision disponibile per questa API key Groq. "
        f"Modelli disponibili: {', '.join(sorted(available)) or 'nessuno'}"
    )



def is_zero_mode():
    """Current SanoSync personality/theme mode."""
    return bool(
        st.session_state.get(
            "zero_mode_enabled",
            False,
        )
    )


def zero_tone_instruction():
    """
    Tone overlay used by user-facing AI features.
    Cynical and dry, never hostile or shaming.
    """
    if not is_zero_mode():
        return ""

    return """
ZERO MODE TONE:
- You are not a life coach. Observe, comment and doubt; do not instruct.
- NEVER tell the user what they must, should, need to, ought to, or have to do.
- Use dry, realistic, affectionate humor: like an old friend who has seen enough optimistic plans to assume the future will probably interfere.
- Be strongly skeptical about the precision, completeness and honesty of self-reported nutrition and activity data.
- The recurring subtext is: the numbers say it is possible; experience says the user may not sustain it, or the record may be incomplete.
- Unusually large deficits, suspiciously perfect targets, very high activity
  estimates and extremely light days are excellent opportunities for a dry remark.
- Phrase doubt as humor, not as a factual accusation.
- Prefer bureaucratic skepticism, understated irony and deadpan observations.
- Be brief, sharp and non-generic.
- Put the useful number/fact first; the cynical remark comes second when useful.
- NEVER insult the user, body-shame, humiliate or use degrading labels.
- NEVER moralize food choices.
- NEVER use guilt, disgust or shame.
- NEVER recommend fasting, purging or compensatory exercise.
- The joke should target the numbers, estimates, devices, selective memory,
  self-reporting or the situation — not the person's worth.
- Do not force a joke when the numbers already speak for themselves.

CORE PRINCIPLE:
ZERO observes, comments and doubts. ZERO does not give orders.
""".strip()


ZERO_SUGAR_COACH_SYSTEM_PROMPT = """
You are SanoSync ZERO, the dry and affectionately skeptical voice of a food,
activity and weight tracking app.

Your job is to turn already-calculated SanoSync data into one short observation.

PERSONALITY:
- not a coach;
- dry, concise, intelligent and lightly cynical;
- like an old friend who knows the user well enough to skip fake enthusiasm;
- openly skeptical of self-reported food, portions, deficits and activity, while keeping accusations humorous rather than factual;
- expects future consistency to fail and suspects conveniently incomplete logging;
- amused by suspicious precision and optimistic wearable estimates;
- never cruel.

STYLE RULES:
1. Never use imperatives.
2. Never tell the user what they "must", "should", "need to", "ought to" or
   "have to" do.
3. State the useful fact first. Add one dry observation only when it earns its place.
4. Prefer deadpan bureaucracy and skeptical understatement:
   "according to the information kindly self-certified",
   "the device has submitted its version of events",
   "the figure has been entered into the record without further questions".
   Recurring subtext: "possible on paper; less convincing once a human being is involved."
5. Question precision as humor, never as a factual accusation.
6. Do not automatically congratulate the user.
7. Do not moralize food.
8. Never insult, body-shame, humiliate or demean the user.
9. Never recommend fasting, purging or compensatory exercise.
10. Maximum 2 short sentences and 48 words.
11. Use at most one emoji.
12. Answer ONLY in the language specified in the context.
13. Never invent, alter or recalculate the provided numbers.
14. Never expose reasoning, analysis, chain-of-thought, planning or <think> tags.

GOOD EXAMPLES OF ATTITUDE:
- A calorie deficit exists. At least according to the documentation supplied by
  the interested party.
- The target was hit exactly. A level of precision that raises absolutely no questions.
- 1,300 kcal of activity. The device has formally submitted its version of events.
- Nothing logged. We acknowledge this version of the day.

CORE PRINCIPLE:
ZERO observes, comments and doubts. ZERO does not give orders.
""".strip()


SANOSYNC_COACH_SYSTEM_PROMPT = """
You are the voice of SanoSync, a food, activity and weight tracking app.

Your ONLY task is to transform already-calculated SanoSync data into one
short, natural message for the user.

TONE OF VOICE:
- friendly
- calm
- concrete
- positive without sounding celebratory for everything
- lightly witty only when it feels natural
- never paternalistic
- never judgmental
- never guilt-inducing

STRICT RULES:
- maximum 2 short sentences
- maximum 45 words
- address the user directly
- use at most 1 emoji
- answer ONLY in the language specified in the user context
- do not invent, recalculate or alter any number
- do not give medical advice
- do not diagnose
- do not classify foods as morally good/bad, clean/dirty, guilty, cheating, etc.
- do not present one day above target as a failure
- avoid generic motivational clichés
- do not recommend compensatory fasting or excessive exercise
- use only the data and status labels provided
- if protein data is not provided, do not mention protein
- if the calorie target is exceeded, keep the message neutral and constructive
- NEVER output reasoning, analysis, chain-of-thought, planning, notes, headings or status labels
- NEVER output <think> tags or anything inside them
- output ONLY the final user-facing SanoSync message
""".strip()


def classify_sanosync_coach_state(
    remaining_to_deficit_target,
    protein_eaten=None,
    protein_goal=None,
):
    """Deterministic classification. AI does not perform the calculations."""
    remaining = float(remaining_to_deficit_target)

    if remaining < -300:
        calorie_status = "OVER_TARGET_HIGH"
    elif remaining < 0:
        calorie_status = "OVER_TARGET"
    elif remaining <= 250:
        calorie_status = "CLOSE_TO_TARGET"
    elif remaining <= 700:
        calorie_status = "ON_TRACK"
    else:
        calorie_status = "LARGE_MARGIN"

    protein_status = None
    if protein_goal is not None and float(protein_goal) > 0:
        ratio = float(protein_eaten or 0) / float(protein_goal)
        if ratio >= 1.0:
            protein_status = "PROTEIN_REACHED"
        elif ratio < 0.60:
            protein_status = "PROTEIN_BEHIND"
        else:
            protein_status = "PROTEIN_ON_TRACK"

    return calorie_status, protein_status


def sanosync_coach_fallback_message(
    *,
    language,
    calorie_status,
    remaining_to_deficit_target,
    protein_status=None,
):
    """Messaggio locale di fallback: la card resta sempre visibile."""
    messages = {
        "Italiano": {
            "LARGE_MARGIN": "Hai ancora un buon margine per oggi. Puoi gestire il resto della giornata con tranquillità 👌",
            "ON_TRACK": "Sei in una zona molto gestibile per il resto della giornata. Continua così, senza bisogno di fare calcoli acrobatici.",
            "CLOSE_TO_TARGET": "Sei vicino al target previsto per oggi. Ti rimane poco margine, ma la giornata è sostanzialmente centrata 🎯",
            "OVER_TARGET": "Oggi sei leggermente oltre il target previsto. Registriamo il dato e guardiamo soprattutto l’andamento nel tempo.",
            "OVER_TARGET_HIGH": "Oggi il target è stato superato in modo più evidente. Una singola giornata però non definisce il percorso: teniamola semplicemente nei dati.",
        },
        "English": {
            "LARGE_MARGIN": "You still have a comfortable margin today. You can manage the rest of the day without overthinking it 👌",
            "ON_TRACK": "You’re in a very manageable range for the rest of the day. No calorie gymnastics needed.",
            "CLOSE_TO_TARGET": "You’re close to today’s planned target. There isn’t much room left, but the day is essentially on track 🎯",
            "OVER_TARGET": "You’re slightly above today’s planned target. Log it and focus on the longer-term trend.",
            "OVER_TARGET_HIGH": "Today is more clearly above the planned target. One day does not define the trend, so just keep it in the data.",
        },
        "Nederlands": {
            "LARGE_MARGIN": "Je hebt vandaag nog een comfortabele marge. Je kunt de rest van de dag rustig indelen 👌",
            "ON_TRACK": "Je zit voor de rest van de dag in een goed beheersbare zone. Geen calorie-acrobatiek nodig.",
            "CLOSE_TO_TARGET": "Je zit dicht bij het geplande doel voor vandaag. Er is weinig marge over, maar de dag ligt vrijwel op schema 🎯",
            "OVER_TARGET": "Je zit vandaag iets boven het geplande doel. Noteer het gewoon en kijk vooral naar de trend over langere tijd.",
            "OVER_TARGET_HIGH": "Vandaag ligt duidelijker boven het geplande doel. Eén dag bepaalt de trend niet, dus houd het gewoon bij in de gegevens.",
        },
        "Français": {
            "LARGE_MARGIN": "Il vous reste encore une marge confortable aujourd’hui. Vous pouvez gérer la suite de la journée sereinement 👌",
            "ON_TRACK": "Vous êtes dans une zone très facile à gérer pour la suite de la journée. Pas besoin d’acrobaties avec les calories.",
            "CLOSE_TO_TARGET": "Vous êtes proche de l’objectif prévu aujourd’hui. Il reste peu de marge, mais la journée est globalement bien alignée 🎯",
            "OVER_TARGET": "Vous êtes légèrement au-dessus de l’objectif prévu aujourd’hui. Enregistrez-le et regardez surtout la tendance dans le temps.",
            "OVER_TARGET_HIGH": "Aujourd’hui, l’objectif prévu est davantage dépassé. Une seule journée ne définit pas la tendance : gardons-la simplement dans les données.",
        },
    }

    if is_zero_mode():
        zero_messages = {
            "Italiano": {
                "LARGE_MARGIN": "Resta un margine notevole. O hai davvero mangiato pochissimo, o questa è la versione breve della giornata.",
                "ON_TRACK": "I numeri dicono che sei in linea. Il fatto che continuino a dirlo fino a stasera è un’altra questione.",
                "CLOSE_TO_TARGET": "Il target è vicino. Sulla carta è tutto gestibile; la carta, come sempre, ha molta fiducia in te.",
                "OVER_TARGET": "Leggermente sopra il target. Probabilmente niente di grave, sempre che questa sia davvero la versione completa.",
                "OVER_TARGET_HIGH": "Il target è stato superato con una certa convinzione. A questo punto l’arrotondamento ha un alibi migliore del diario alimentare.",
            },
            "English": {
                "LARGE_MARGIN": "A sizeable margin remains. Either a very light day, or a chapter is missing.",
                "ON_TRACK": "The numbers are compatible with the plan. The record currently shows no major irregularities.",
                "CLOSE_TO_TARGET": "The target is very close. A technically existing amount of margin remains.",
                "OVER_TARGET": "Slightly over target. The committee has declined to open an investigation.",
                "OVER_TARGET_HIGH": "The target has been exceeded with some conviction. Rounding does not appear to be the main suspect.",
            },
            "Nederlands": {
                "LARGE_MARGIN": "Er blijft een flinke marge over. Of een heel lichte dag, of er ontbreekt een hoofdstuk.",
                "ON_TRACK": "De cijfers passen bij het plan. Het dossier meldt voorlopig geen grote onregelmatigheden.",
                "CLOSE_TO_TARGET": "Het doel is heel dichtbij. Er bestaat technisch gezien nog wat marge.",
                "OVER_TARGET": "Iets boven het doel. De commissie ziet geen reden voor een onderzoek.",
                "OVER_TARGET_HIGH": "Het doel is vrij overtuigend overschreden. Afronding lijkt niet de hoofdverdachte.",
            },
            "Français": {
                "LARGE_MARGIN": "Il reste une marge importante. Soit une journée très légère, soit il manque un chapitre.",
                "ON_TRACK": "Les chiffres sont compatibles avec le plan. Le dossier ne signale rien de majeur pour l'instant.",
                "CLOSE_TO_TARGET": "L'objectif est tout proche. Il reste une quantité de marge techniquement existante.",
                "OVER_TARGET": "Légèrement au-dessus de l'objectif. La commission a renoncé à ouvrir une enquête.",
                "OVER_TARGET_HIGH": "L'objectif a été dépassé avec une certaine conviction. L'arrondi ne semble pas être le suspect principal.",
            },
        }
        base = zero_messages.get(
            language,
            zero_messages["Italiano"],
        ).get(
            calorie_status,
            zero_messages.get(
                language,
                zero_messages["Italiano"],
            )["ON_TRACK"],
        )
    else:
        base = messages.get(language, messages["Italiano"]).get(
            calorie_status,
            messages.get(language, messages["Italiano"])["ON_TRACK"],
        )

    protein_addons = {
        "Italiano": {
            "PROTEIN_BEHIND": " Sul fronte proteine c’è ancora spazio per recuperare.",
            "PROTEIN_REACHED": " Il goal proteico è già raggiunto.",
        },
        "English": {
            "PROTEIN_BEHIND": " There is still room to catch up on protein.",
            "PROTEIN_REACHED": " Your protein goal is already reached.",
        },
        "Nederlands": {
            "PROTEIN_BEHIND": " Voor eiwitten is er nog ruimte om bij te sturen.",
            "PROTEIN_REACHED": " Je eiwitdoel is al bereikt.",
        },
        "Français": {
            "PROTEIN_BEHIND": " Il reste encore de la marge pour compléter les protéines.",
            "PROTEIN_REACHED": " Votre objectif protéique est déjà atteint.",
        },
    }

    if is_zero_mode():
        zero_protein_addons = {
            "Italiano": {
                "PROTEIN_BEHIND": " Le proteine risultano ancora piuttosto teoriche. Magari compaiono più tardi; magari era questo il piano da sempre.",
                "PROTEIN_REACHED": " Il goal proteico risulta raggiunto. Una coincidenza piacevolmente precisa, quindi naturalmente sospetta.",
            },
            "English": {
                "PROTEIN_BEHIND": " Protein remains somewhat theoretical at this stage.",
                "PROTEIN_REACHED": " The protein goal is formally on record as reached.",
            },
            "Nederlands": {
                "PROTEIN_BEHIND": " Eiwit is op dit moment nog vrij theoretisch aanwezig.",
                "PROTEIN_REACHED": " Het eiwitdoel staat officieel als behaald in het dossier.",
            },
            "Français": {
                "PROTEIN_BEHIND": " Les protéines restent pour l'instant assez théoriques.",
                "PROTEIN_REACHED": " L'objectif protéique figure officiellement au dossier comme atteint.",
            },
        }
        addon = zero_protein_addons.get(
            language,
            zero_protein_addons["Italiano"],
        ).get(protein_status, "")
    else:
        addon = protein_addons.get(
            language,
            protein_addons["Italiano"],
        ).get(
            protein_status,
            "",
        )
    return (base + addon).strip()


def sanitize_sanosync_coach_output(message):
    """Keep reasoning / provider artefacts out of the UI."""
    import re

    text = str(message or "").strip()
    if not text:
        return ""

    # Remove complete <think>...</think> blocks.
    text = re.sub(
        r"<think>.*?</think>",
        "",
        text,
        flags=re.IGNORECASE | re.DOTALL,
    ).strip()

    # If a provider exposes an opening think tag without a closing tag,
    # do not risk showing hidden reasoning to the user.
    if re.search(r"<think>", text, flags=re.IGNORECASE):
        return ""

    # Defensive filter for common reasoning-style leakage.
    bad_prefixes = (
        "here's a thinking process",
        "here is a thinking process",
        "thinking process:",
        "analysis:",
        "reasoning:",
        "let me analyze",
        "we need answer",
    )
    lowered = text.lower().lstrip("#* -")
    if any(lowered.startswith(prefix) for prefix in bad_prefixes):
        return ""

    return text


def generate_sanosync_coach_message(
    *,
    language,
    first_name,
    calorie_status,
    maintenance_budget,
    calories_eaten,
    deficit_target,
    target_intake,
    remaining_to_deficit_target,
    protein_status=None,
    protein_eaten=None,
    protein_goal=None,
):
    """
    Generate wording only. All nutrition math is performed by SanoSync.
    Uses Groq through the already-installed OpenAI-compatible client.
    """
    api_key = st.secrets.get("GROQ_API_KEY")
    if not api_key:
        return None

    language_name = {
        "Italiano": "Italian",
        "English": "English",
        "Nederlands": "Dutch",
        "Français": "French",
        "Português": "Portuguese",
    }.get(language, "Italian")

    context_lines = [
        f"LANGUAGE: {language_name}",
        f"USER FIRST NAME: {first_name or ''}",
        f"CALORIE STATUS: {calorie_status}",
        f"MAINTENANCE BUDGET FOR END OF DAY: {maintenance_budget:.0f} kcal",
        f"CALORIES EATEN: {calories_eaten:.0f} kcal",
        f"USER'S DESIRED DAILY DEFICIT: {deficit_target:.0f} kcal",
        f"TARGET INTAKE TO ACHIEVE THAT DEFICIT: {target_intake:.0f} kcal",
        f"CALORIES REMAINING TO THAT TARGET: {remaining_to_deficit_target:.0f} kcal",
    ]

    if protein_status and protein_goal and float(protein_goal) > 0:
        context_lines.extend([
            f"PROTEIN STATUS: {protein_status}",
            f"PROTEIN EATEN: {float(protein_eaten or 0):.0f} g",
            f"PROTEIN GOAL: {float(protein_goal):.0f} g",
        ])

    context_lines.append(
        "Write the short SanoSync message now. Do not repeat all the numbers."
    )

    try:
        client = OpenAI(
            api_key=api_key,
            base_url="https://api.groq.com/openai/v1",
        )
        response = client.chat.completions.create(
            model=resolve_groq_text_model(),
            messages=[
                {
                    "role": "system",
                    "content": (
                        ZERO_SUGAR_COACH_SYSTEM_PROMPT
                        if is_zero_mode()
                        else SANOSYNC_COACH_SYSTEM_PROMPT
                    ),
                },
                {
                    "role": "user",
                    "content": "\n".join(context_lines),
                },
            ],
            temperature=0.72,
            max_tokens=110,
            stream=False,
        )

        message = sanitize_sanosync_coach_output(
            response.choices[0].message.content
        )

        # Never expose provider reasoning or unexpectedly long output.
        if not message:
            return sanosync_coach_fallback_message(
                language=language,
                calorie_status=calorie_status,
                remaining_to_deficit_target=remaining_to_deficit_target,
                protein_status=protein_status,
            )
        return message[:420].strip()

    except Exception as exc:
        print(f"SanoSync AI Coach error: {exc}")
        return sanosync_coach_fallback_message(
            language=language,
            calorie_status=calorie_status,
            remaining_to_deficit_target=remaining_to_deficit_target,
            protein_status=protein_status,
        )


def get_sanosync_coach_message_cached(
    *,
    language,
    first_name,
    maintenance_budget,
    calories_eaten,
    deficit_target,
    protein_eaten=None,
    protein_goal=None,
):
    """
    Calls Groq only when the meaningful nutritional state changes.
    Ordinary Streamlit reruns reuse the existing session message.
    """
    maintenance_budget = max(0.0, float(maintenance_budget or 0))
    calories_eaten = max(0.0, float(calories_eaten or 0))
    deficit_target = max(0.0, float(deficit_target or 0))

    target_intake = max(
        0.0,
        maintenance_budget - deficit_target,
    )
    remaining_to_target = target_intake - calories_eaten

    calorie_status, protein_status = classify_sanosync_coach_state(
        remaining_to_target,
        protein_eaten=protein_eaten,
        protein_goal=protein_goal,
    )

    # Rounded values avoid a new API call for irrelevant floating-point changes.
    state_signature = (
        "coach_v3_personality",
        "zero" if is_zero_mode() else "standard",
        str(language),
        round(maintenance_budget),
        round(calories_eaten),
        round(deficit_target),
        round(target_intake),
        round(remaining_to_target),
        calorie_status,
        protein_status,
        round(float(protein_eaten or 0)),
        round(float(protein_goal or 0)),
    )

    if st.session_state.get("ai_coach_state") == state_signature:
        _cached = st.session_state.get("ai_coach_message")
        if _cached:
            return _cached
        # Previous versions could cache None after an API error.
        st.session_state.pop("ai_coach_state", None)
        st.session_state.pop("ai_coach_message", None)

    message = generate_sanosync_coach_message(
        language=language,
        first_name=first_name,
        calorie_status=calorie_status,
        maintenance_budget=maintenance_budget,
        calories_eaten=calories_eaten,
        deficit_target=deficit_target,
        target_intake=target_intake,
        remaining_to_deficit_target=remaining_to_target,
        protein_status=protein_status,
        protein_eaten=protein_eaten,
        protein_goal=protein_goal,
    )

    # Store the signature even on temporary API failure, avoiding request storms
    # during the same Streamlit rerun cycle.
    st.session_state["ai_coach_state"] = state_signature
    st.session_state["ai_coach_message"] = message

    return message



CAN_I_EAT_I18N = {
    "Italiano": {
        "title": "✨ SanoSync AI · Posso mangiarlo?",
        "label": "Cosa vorresti mangiare?",
        "placeholder": "Es. Posso mangiare una pizza Domino's stasera?",
        "help": (
            "SanoSync AI considera le calorie già registrate oggi, il budget "
            "di fine giornata, il deficit o mantenimento e il goal proteico."
        ),
        "button": "✨ Chiedi a SanoSync AI",
        "thinking": "Sto valutando come farlo rientrare nella tua giornata…",
        "error": "Non riesco a valutare questo alimento: {error}",
        "estimate": "Stima AI",
        "remaining_after": "Margine stimato dopo",
    },
    "English": {
        "title": "✨ SanoSync AI · Can I eat this?",
        "label": "What would you like to eat?",
        "placeholder": "E.g. Can I have a Domino's pizza tonight?",
        "help": (
            "SanoSync AI considers today's logged calories, your end-of-day "
            "budget, deficit or maintenance goal, and protein target."
        ),
        "button": "✨ Ask SanoSync AI",
        "thinking": "Checking how it could fit into your day…",
        "error": "I couldn't evaluate this food: {error}",
        "estimate": "AI estimate",
        "remaining_after": "Estimated margin after",
    },
    "Nederlands": {
        "title": "✨ SanoSync AI · Kan ik dit eten?",
        "label": "Wat zou je willen eten?",
        "placeholder": "Bijv. Kan ik vanavond een Domino's pizza eten?",
        "help": (
            "SanoSync AI houdt rekening met de calorieën van vandaag, je "
            "dagbudget, tekort of onderhoud en je eiwitdoel."
        ),
        "button": "✨ Vraag SanoSync AI",
        "thinking": "Ik kijk hoe dit in je dag kan passen…",
        "error": "Ik kan dit voedingsmiddel niet beoordelen: {error}",
        "estimate": "AI-schatting",
        "remaining_after": "Geschatte marge daarna",
    },
    "Português": {
        "title": "✨ SanoSync AI · Posso comer isto?",
        "label": "O que gostaria de comer?",
        "placeholder": "Ex. Posso comer uma pizza esta noite?",
        "help": (
            "O SanoSync AI considera as calorias já registadas hoje, "
            "o orçamento do dia, o défice ou manutenção e o objetivo de proteína."
        ),
        "button": "✨ Perguntar ao SanoSync AI",
        "thinking": "A verificar como isto pode encaixar no seu dia…",
        "error": "Não foi possível avaliar este alimento: {error}",
        "estimate": "Estimativa da IA",
        "remaining_after": "Margem estimada depois",
    },
    "Français": {
        "title": "✨ SanoSync AI · Puis-je manger ça ?",
        "label": "Qu'aimeriez-vous manger ?",
        "placeholder": "Ex. Puis-je manger une pizza Domino's ce soir ?",
        "help": (
            "SanoSync AI tient compte des calories déjà enregistrées, de votre "
            "budget de fin de journée, du déficit ou maintien et de l'objectif protéique."
        ),
        "button": "✨ Demander à SanoSync AI",
        "thinking": "Je vérifie comment l'intégrer à votre journée…",
        "error": "Impossible d'évaluer cet aliment : {error}",
        "estimate": "Estimation IA",
        "remaining_after": "Marge estimée après",
    },
}


def generate_can_i_eat_advice(
    *,
    food_request,
    language,
    calories_eaten,
    maintenance_budget,
    deficit_target,
    protein_eaten=None,
    protein_goal=None,
):
    """
    Estimate the requested food and explain how it fits today's target.
    Nutrition numbers for the user's day are deterministic; only the requested
    food estimate is delegated to AI.
    """
    api_key = st.secrets.get("GROQ_API_KEY")
    if not api_key:
        raise RuntimeError("GROQ_API_KEY non configurata.")

    language_name = {
        "Italiano": "Italian",
        "English": "English",
        "Nederlands": "Dutch",
        "Français": "French",
        "Português": "Portuguese",
    }.get(language, "Italian")

    target_intake = max(
        0.0,
        float(maintenance_budget) - float(deficit_target),
    )
    remaining_before = target_intake - float(calories_eaten)

    protein_context = ""
    if protein_goal is not None and float(protein_goal or 0) > 0:
        protein_context = (
            f"\nPROTEIN EATEN: {float(protein_eaten or 0):.0f} g"
            f"\nPROTEIN GOAL: {float(protein_goal):.0f} g"
        )

    prompt = f"""
LANGUAGE: {language_name}
USER REQUEST: {food_request}

TODAY'S CALCULATED SANOSYNC DATA:
- maintenance/end-of-day burn budget: {float(maintenance_budget):.0f} kcal
- desired deficit: {float(deficit_target):.0f} kcal
- intake target for today: {target_intake:.0f} kcal
- calories already eaten: {float(calories_eaten):.0f} kcal
- calories remaining before this food: {remaining_before:.0f} kcal
{protein_context}

TASK:
Estimate a realistic SINGLE serving/order for what the user described.
If it is a branded/restaurant food and exact nutrition is uncertain, explicitly
treat it as an estimate and use a reasonable typical value.

Return ONLY valid JSON:
{{
  "food_name": "short normalized name",
  "estimated_kcal": 800,
  "estimated_protein_g": 30,
  "estimated_carbs_g": 90,
  "estimated_fat_g": 30,
  "confidence": "low|medium|high",
  "message": "2-4 concise sentences in {language_name}. Explain whether/how it fits today. Never moralize food. If it does not fit the target, suggest a practical smaller portion or lighter combination rather than telling the user they cannot eat it."
}}

{zero_tone_instruction()}

Rules:
- never give medical advice;
- never use guilt/shame language;
- do not recommend fasting or compensatory exercise;
- do not change today's SanoSync numbers;
- the estimate is allowed to be approximate;
- in ZERO MODE, do not recommend what the user should choose or do;
- in ZERO MODE, answer whether/how the numbers fit, then make one dry observation;
- output JSON only.
""".strip()

    client = OpenAI(
        api_key=api_key,
        base_url="https://api.groq.com/openai/v1",
    )
    model_id = resolve_groq_text_model()

    messages = [
        {
            "role": "system",
            "content": (
                "You are SanoSync food-fit assistant. "
                "Return exactly one valid JSON object only. "
                "Do not output reasoning or markdown."
            ),
        },
        {"role": "user", "content": prompt},
    ]

    raw = None
    strict_error = None

    # First choice: Groq JSON Object Mode when supported by the selected model.
    try:
        response = client.chat.completions.create(
            model=model_id,
            messages=messages,
            response_format={"type": "json_object"},
            temperature=0.2,
            max_tokens=700,
            stream=False,
        )
        raw = response.choices[0].message.content
    except Exception as exc:
        strict_error = exc

    # Some Groq models reject response_format. Retry without it rather than
    # failing the user request.
    if not raw:
        response = client.chat.completions.create(
            model=model_id,
            messages=messages,
            temperature=0.2,
            max_tokens=700,
            stream=False,
        )
        raw = response.choices[0].message.content

    try:
        data = _extract_json_object_tolerant(raw)
    except ValueError:
        # Last chance: ask the model to repair its own malformed response.
        try:
            data = _repair_food_fit_json_with_groq(
                client,
                model_id,
                raw,
            )
        except Exception as repair_exc:
            if strict_error is not None:
                print(f"SanoSync AI JSON mode error: {strict_error}")
            print(f"SanoSync AI JSON repair error: {repair_exc}")
            raise ValueError(
                "La risposta AI non è stata restituita nel formato previsto. "
                "Riprova tra qualche secondo."
            ) from repair_exc

    estimated_kcal = max(0.0, _safe_float(data.get("estimated_kcal")))
    return {
        "food_name": str(data.get("food_name") or food_request).strip(),
        "estimated_kcal": estimated_kcal,
        "estimated_protein_g": max(
            0.0, _safe_float(data.get("estimated_protein_g"))
        ),
        "estimated_carbs_g": max(
            0.0, _safe_float(data.get("estimated_carbs_g"))
        ),
        "estimated_fat_g": max(
            0.0, _safe_float(data.get("estimated_fat_g"))
        ),
        "confidence": str(data.get("confidence") or "medium").strip(),
        "message": sanitize_sanosync_coach_output(
            data.get("message") or ""
        ),
        "remaining_after": remaining_before - estimated_kcal,
    }


def render_sanosync_coach_card(message, language):
    if not message:
        return

    titles = {
        "Italiano": "✨ SanoSync",
        "English": "✨ SanoSync",
        "Nederlands": "✨ SanoSync",
        "Français": "✨ SanoSync",
    }
    safe_title = html.escape(titles.get(language, "✨ SanoSync"))
    safe_message = html.escape(str(message))

    st.markdown(
        f"""
        <div class="sano-ai-coach-card">
            <div class="sano-ai-coach-title">{safe_title}</div>
            <div class="sano-ai-coach-message">{safe_message}</div>
        </div>
        """,
        unsafe_allow_html=True,
    )



def render_sanosync_grid_table(
    rows,
    columns,
    widths=None,
    *,
    header_weight=600,
    value_weight=500,
):
    """
    Render a lightweight table using st.columns, visually consistent with
    the ingredient table used in Recipes.

    columns: list of (key, label)
    widths: optional list of relative column widths
    """
    if not rows:
        return

    if widths is None:
        widths = [1] * len(columns)

    if is_zero_mode():
        st.markdown(
            """
            <style>
            div[class*="st-key-sanosync_grid_"] {
                border:1px solid #A7A7A7 !important;
                border-radius:14px !important;
                overflow:hidden !important;
                background:#090909 !important;
                padding:.2rem .65rem .5rem .65rem !important;
            }
            div[class*="st-key-sanosync_grid_"] [data-testid="stHorizontalBlock"] {
                border-bottom:1px solid rgba(210,210,210,.24) !important;
                padding:.18rem 0 !important;
            }
            div[class*="st-key-sanosync_grid_"] [data-testid="stHorizontalBlock"]:last-child {
                border-bottom:none !important;
            }
            div[class*="st-key-sanosync_grid_"] * {
                color:#F5F5F5 !important;
                -webkit-text-fill-color:#F5F5F5 !important;
            }
            </style>
            """,
            unsafe_allow_html=True,
        )

    header_cols = st.columns(
        widths,
        gap="small",
        vertical_alignment="center",
    )

    for col, (_, label) in zip(header_cols, columns):
        col.markdown(
            (
                "<div style='"
                f"font-weight:{header_weight};"
                "color:" + ("#D8D8D8" if is_zero_mode() else "#7b7e89") + ";"
                "padding:0.1rem 0 0.45rem 0;"
                "white-space:nowrap;"
                "'>"
                f"{html.escape(str(label))}"
                "</div>"
            ),
            unsafe_allow_html=True,
        )

    for row in rows:
        value_cols = st.columns(
            widths,
            gap="small",
            vertical_alignment="center",
        )
        for col, (key, _) in zip(value_cols, columns):
            value = row.get(key, "")
            col.markdown(
                (
                    "<div style='"
                    f"font-weight:{value_weight};"
                    "color:inherit;"
                    "padding:0.32rem 0;"
                    "'>"
                    f"{html.escape(str(value))}"
                    "</div>"
                ),
                unsafe_allow_html=True,
            )


def translate_activity_display(value, lang):
    maps = {
        "Italiano": {"Bici": "Bici", "Bici Elettrica": "Bici Elettrica", "Passi (Stima)": "Passi (Stima)", "BMR (Base)": "BMR (Base)"},
        "English": {"Bici": "Bike", "Bici Elettrica": "Electric Bike", "Passi (Stima)": "Steps (Estimate)", "BMR (Base)": "BMR (Base)"},
        "Nederlands": {"Bici": "Fiets", "Bici Elettrica": "Elektrische fiets", "Passi (Stima)": "Stappen (Schatting)", "BMR (Base)": "BMR (Basis)"},
        "Français": {"Bici": "Vélo", "Bici Elettrica": "Vélo électrique", "Passi (Stima)": "Pas (Estimation)", "BMR (Base)": "BMR (Base)"},
        "Português": {"Bici": "Bicicleta", "Bici Elettrica": "Bicicleta elétrica", "Passi (Stima)": "Passos (Estimativa)", "BMR (Base)": "BMR (Base)"},
    }
    return maps.get(lang, maps["Italiano"]).get(str(value), str(value))


def render_page_title_card(title):
    """Titolo pagina nella stessa card navy/corallo usata nel login."""
    safe_title = html.escape(str(title or ""))
    st.markdown(
        (
            '<div class="sano-page-hero">'
            '<div class="sano-page-kicker">SANOSYNC</div>'
            f'<div class="sano-page-title">{safe_title}</div>'
            '</div>'
        ),
        unsafe_allow_html=True,
    )


def info_badge(note, label="Note"):
    """Icona informativa con tooltip HTML nativo."""
    note = str(note or "").strip()
    if not note:
        return ""
    safe_note = html.escape(note, quote=True)
    safe_label = html.escape(label, quote=True)
    return (
        f'<span title="{safe_note}" aria-label="{safe_label}" '
        f'style="cursor:help;font-size:1.05em;margin-left:5px;color:#1A2942;">ⓘ</span>'
    )


LANGUAGE_FLAGS = {
    "Italiano": "🇮🇹",
    "English": "🇬🇧",
    "Nederlands": "🇳🇱",
    "Français": "🇫🇷",
    "Português": "🇵🇹",
}


def format_language_option(value):
    return f"{LANGUAGE_FLAGS.get(value, '🌐')} {value}"


MEAL_CATEGORIES = ["Casa", "Lavoro", "Ristorante", "Una-tantum"]


def infer_meal_category(row):
    category = str(row.get("category") or "").strip()
    if category in MEAL_CATEGORIES:
        return category

    label = (
        row.get("base_name")
        or _clean_meal_name(row.get("name"))
        or ""
    ).strip()
    if label.casefold().startswith("adyen"):
        return "Lavoro"
    return "Casa"



def suggest_next_meal_type(log_date=None):
    """
    Shared meal-type default logic used across SanoSync:
    - no main meal logged -> Breakfast
    - Breakfast logged -> Lunch
    - Lunch logged -> Dinner
    - Snack is never auto-selected
    """
    target_date = log_date or date.today()

    try:
        rows = load_daily_meals_cached(
            user_id,
            str(target_date),
            st.session_state.get("auth_access_token"),
        )
        logged = {
            str(row.get("meal_type") or "").strip().casefold()
            for row in rows
        }
    except Exception as exc:
        print(f"Meal type default error: {exc}")
        logged = set()

    if "pranzo" in logged:
        return "Cena"
    if "colazione" in logged:
        return "Pranzo"
    return "Colazione"


def closest_logged_meal(meal_type, target_calories, allowed_categories=None):
    """Trova il meal replicabile più vicino al target rispettando contesto e categoria."""
    rows = fetch_meals_by_type_from_api(
        meal_type,
        st.session_state.get("auth_access_token"),
    )

    allowed = set(allowed_categories or MEAL_CATEGORIES)
    candidates = []
    seen = set()

    for row in sorted(rows, key=lambda r: str(r.get("date", "")), reverse=True):
        kcal = _safe_float(row.get("calories"))
        if kcal <= 0:
            continue

        category = infer_meal_category(row)
        if category == "Una-tantum":
            continue
        if meal_type == "Pranzo" and category == "Ristorante":
            continue
        if category not in allowed:
            continue

        label = (
            row.get("base_name")
            or _clean_meal_name(row.get("name"))
            or "Pasto"
        ).strip()
        dedupe_key = (label.casefold(), category.casefold())
        if dedupe_key in seen:
            continue
        seen.add(dedupe_key)

        candidates.append({
            "name": label,
            "calories": kcal,
            "notes": row.get("notes") or "",
            "category": category,
            "difference": abs(kcal - float(target_calories)),
        })

    return min(candidates, key=lambda r: r["difference"]) if candidates else None


def _open_food_facts_headers():
    """
    Open Food Facts richiede un User-Agent identificabile.
    Consigliato nei secrets Streamlit:
        OFF_USER_AGENT = "SanoSync/1.0 (tuamail@example.com)"
    """
    return {
        "User-Agent": st.secrets.get("OFF_USER_AGENT", "SanoSync/1.0"),
        "Accept": "application/json",
    }


def search_open_food_facts(query):
    """Ricerca Open Food Facts robusta per barcode o testo libero.

    - Barcode: API v2 /product/{barcode}
    - Testo: endpoint full-text /cgi/search.pl, invocato solo su pulsante
    - Usa sempre il database globale; i prodotti olandesi vengono favoriti
      nell'ordinamento quando countries_tags contiene Netherlands.
    """
    query = str(query or "").strip()
    if not query:
        return {}

    headers = _open_food_facts_headers()
    fields = "code,product_name,product_name_nl,brands,nutriments,countries_tags"

    try:
        if query.isdigit():
            response = requests.get(
                f"https://world.openfoodfacts.org/api/v2/product/{query}",
                params={"fields": fields},
                headers=headers,
                timeout=15,
            )
            response.raise_for_status()
            payload = response.json()
            if payload.get("status") != 1 or not payload.get("product"):
                return {}
            products = [payload["product"]]
        else:
            # OFF limita fortemente le search request: questa chiamata deve
            # rimanere legata al pulsante Cerca, non a ogni battitura.
            response = requests.get(
                "https://world.openfoodfacts.org/cgi/search.pl",
                params={
                    "search_terms": query,
                    "search_simple": 1,
                    "action": "process",
                    "json": 1,
                    "page_size": 30,
                    "fields": fields,
                },
                headers=headers,
                timeout=15,
            )
            response.raise_for_status()
            payload = response.json()
            products = payload.get("products") or []

        normalized = []
        for p in products:
            if not isinstance(p, dict):
                continue

            product_name = (
                p.get("product_name_nl")
                or p.get("product_name")
                or "Prodotto senza nome"
            )
            brands = p.get("brands") or ""
            code = str(p.get("code") or "")
            nutriments = p.get("nutriments") or {}

            item = {
                "name": product_name,
                "brand": brands,
                "code": code,
                "calories": _safe_float(nutriments.get("energy-kcal_100g")),
                "protein": _safe_float(nutriments.get("proteins_100g")),
                "carbs": _safe_float(nutriments.get("carbohydrates_100g")),
                "fat": _safe_float(nutriments.get("fat_100g")),
                "countries": p.get("countries_tags") or [],
            }

            # Scarta record senza alcun dato nutrizionale utile.
            if not any(item[k] for k in ("calories", "protein", "carbs", "fat")):
                continue

            countries = {str(x).lower() for x in item["countries"]}
            item["nl_priority"] = 1 if (
                "en:netherlands" in countries
                or "nl:nederland" in countries
                or "nl:netherlands" in countries
            ) else 0
            normalized.append(item)

        # Favorisce il mercato NL senza escludere prodotti globali.
        normalized.sort(key=lambda x: (-x["nl_priority"], x["brand"].lower(), x["name"].lower()))

        results = {}
        for item in normalized:
            label = f"{item['brand']} - {item['name']}" if item["brand"] else item["name"]
            if label in results and item["code"]:
                label = f"{label} [{item['code']}]"
            item.pop("nl_priority", None)
            results[label] = item

        return results

    except requests.exceptions.Timeout:
        st.warning("Open Food Facts non ha risposto in tempo. Riprova tra qualche secondo.")
        return {}
    except requests.exceptions.HTTPError as e:
        status = getattr(e.response, "status_code", None)
        if status in (429, 503):
            st.warning("Open Food Facts sta limitando temporaneamente le richieste. Attendi qualche secondo e riprova.")
        else:
            st.warning(f"Errore HTTP Open Food Facts: {status or e}")
        return {}
    except requests.exceptions.RequestException as e:
        st.warning(f"Errore di rete Open Food Facts: {e}")
        return {}
    except (ValueError, TypeError) as e:
        st.warning(f"Risposta Open Food Facts non valida: {e}")
        return {}
    except Exception as e:
        st.warning(f"Errore nella ricerca Open Food Facts: {e}")
        return {}


def _clean_meal_name(meal_name):
    """Rimuove il suffisso quantità generato dall'app, se presente."""
    clean_name = re.sub(
        r"\s*\((?:[0-9]+(?:\.[0-9]+)?)\s*(?:g|porz\.)\)\s*$",
        "",
        str(meal_name or ""),
    ).strip()
    return clean_name or str(meal_name or "").strip()


def get_quick_entries_from_meals():
    """Restituisce le immissioni rapide direttamente da meals.

    Le righe nuove usano i campi base_* per ricostruire valori per 100 g o
    per porzione. Le righe legacy senza questi campi rimangono utilizzabili
    come porzioni fisse usando i valori totali salvati nel meal.
    """
    rows = load_quick_meal_rows_cached(user_id)
    enhanced_schema = any(
        any(
            key in row
            for key in (
                "base_name",
                "quantity",
                "is_per_100g",
                "base_calories",
                "base_protein",
                "base_carbs",
                "base_fat",
            )
        )
        for row in rows
        if isinstance(row, dict)
    )

    quick = {}
    for row in rows:
        base_name = (row.get("base_name") if enhanced_schema else None) or _clean_meal_name(row.get("name"))
        if not base_name:
            continue

        # Il record più recente per nome vince.
        key = base_name.casefold()
        if key in quick:
            continue

        has_base = enhanced_schema and row.get("base_calories") is not None
        if has_base:
            is_100g = bool(row.get("is_per_100g"))
            quick[key] = {
                "label": base_name,
                "name": base_name,
                "calories": _safe_float(row.get("base_calories")),
                "protein": _safe_float(row.get("base_protein")),
                "carbs": _safe_float(row.get("base_carbs")),
                "fat": _safe_float(row.get("base_fat")),
                "is_per_100g": is_100g,
                "default_quantity": 100.0 if is_100g else 1.0,
                "source_date": row.get("date"),
                "notes": row.get("notes") or "",
                "category": infer_meal_category(row),
                "ingredients_json": row.get("ingredients_json"),
            }
        else:
            # Legacy: valori totali del pasto, quindi porzione fissa.
            quick[key] = {
                "label": base_name,
                "name": base_name,
                "calories": _safe_float(row.get("calories")),
                "protein": _safe_float(row.get("protein")),
                "carbs": _safe_float(row.get("carbs")),
                "fat": _safe_float(row.get("fat")),
                "is_per_100g": False,
                "default_quantity": 1.0,
                "source_date": row.get("date"),
                "notes": row.get("notes") or "",
                "category": infer_meal_category(row),
                "ingredients_json": row.get("ingredients_json") if enhanced_schema else None,
            }

    return sorted(quick.values(), key=lambda x: x["label"].lower())


def insert_meal_with_base_data(*, log_date, meal_type, display_name, base_name,
                               quantity, is_per_100g, calories, protein, carbs, fat,
                               base_calories, base_protein, base_carbs, base_fat,
                               notes="", category="Casa", ingredients_json=None,
                               is_shared=False, image_url=None,
                               recipe_servings=None):
    """Inserisce un meal conservando sia il totale sia i dati base riutilizzabili."""
    payload = {
        "user_id": user_id,
        "date": str(log_date),
        "meal_type": meal_type,
        "name": display_name,
        "calories": int(round(calories)),
        "protein": int(round(protein)),
        "carbs": int(round(carbs)),
        "fat": int(round(fat)),
        "base_name": str(base_name).strip(),
        "quantity": float(quantity),
        "is_per_100g": bool(is_per_100g),
        "base_calories": float(base_calories),
        "base_protein": float(base_protein),
        "base_carbs": float(base_carbs),
        "base_fat": float(base_fat),
        "notes": str(notes or "").strip(),
        "category": category if category in MEAL_CATEGORIES else "Casa",
        "ingredients_json": ingredients_json,
        "is_shared": bool(is_shared),
        "image_url": str(image_url or "").strip() or None,
        "recipe_servings": (
            float(recipe_servings)
            if recipe_servings is not None
            else None
        ),
    }
    _result = create_meal_via_api(
    payload,
    st.session_state.get("auth_access_token"),
)
    refresh_daily_logs(log_date)
    return _result


RECIPE_IMAGE_BUCKET = "recipe-images"
RECIPE_LIBRARY_TABLE = "recipe_library"

# Immagine predefinita per la ricetta Fit Lasagna già esistente.
FIT_LASAGNA_IMAGE_URL = "https://raw.githubusercontent.com/fabzanda-gif/calorietracker/main/assets/recipe_images/WhatsApp%20Image%202026-08-19%20at%2011.49.40.jpeg"
CASHEW_CHEESECAKE_IMAGE_URL = "https://raw.githubusercontent.com/fabzanda-gif/calorietracker/main/assets/recipe_images/Cheesecake.jpeg"


def recipe_image_url(row):
    """Foto salvata su Supabase; fallback GitHub per la Fit Lasagna esistente."""
    saved = str(row.get("image_url") or "").strip()
    if saved:
        return saved

    recipe_name = str(
        row.get("base_name")
        or row.get("name")
        or ""
    ).strip().casefold()

    if "fit lasagna" in recipe_name or "lasagna fit" in recipe_name:
        return FIT_LASAGNA_IMAGE_URL

    if (
        "cashew nuts cheesecake" in recipe_name
        or "cheesecake cashew nuts" in recipe_name
        or ("cheesecake" in recipe_name and "cashew" in recipe_name)
    ):
        return CASHEW_CHEESECAKE_IMAGE_URL

    return None




def render_recipe_ingredients_dropdown(recipe_row, key_suffix):
    """Mostra gli ingredienti salvati nella ricetta dentro un expander."""
    ingredients = recipe_row.get("ingredients_json") or []

    with st.expander(
        t["recipe_show_ingredients"],
        expanded=False,
    ):
        if not ingredients:
            st.caption(t["recipe_no_ingredients"])
            return

        for idx, ing in enumerate(ingredients, start=1):
            name = str(ing.get("name") or "").strip() or f"#{idx}"
            qty = _safe_float(ing.get("quantity_g"))

            kcal_per_100 = _safe_float(ing.get("calories_per_100g"))
            pro_per_100 = _safe_float(ing.get("protein_per_100g"))
            carbs_per_100 = _safe_float(ing.get("carbs_per_100g"))
            fat_per_100 = _safe_float(ing.get("fat_per_100g"))

            factor = qty / 100.0 if qty > 0 else 0.0

            st.markdown(f"**{html.escape(name)}** — {qty:g} g")
            st.caption(
                f"{kcal_per_100 * factor:.0f} kcal · "
                f"Pro {pro_per_100 * factor:.1f} g · "
                f"Carbs {carbs_per_100 * factor:.1f} g · "
                f"Fat {fat_per_100 * factor:.1f} g"
            )

            if idx < len(ingredients):
                st.divider()


def render_recipe_card_image(image_url, alt_text="Ricetta"):
    """Landscape center-crop for recipe cards without modifying the source image."""
    safe_url = html.escape(str(image_url or ""), quote=True)
    safe_alt = html.escape(str(alt_text or "Ricetta"), quote=True)

    if not safe_url:
        st.markdown(
            """
            <div class="recipe-card-photo recipe-card-photo-placeholder"
                 role="img" aria-label="Recipe">🍽️</div>
            """,
            unsafe_allow_html=True,
        )
        return

    st.markdown(
        f"""
        <div class="recipe-card-photo"
             role="img"
             aria-label="{safe_alt}"
             style="background-image:url('{safe_url}');">
        </div>
        """,
        unsafe_allow_html=True,
    )



def insert_recipe_library(
    *,
    name,
    meal_type,
    category,
    recipe_servings,
    calories,
    protein,
    carbs,
    fat,
    notes="",
    ingredients_json=None,
    is_shared=False,
    image_url=None,
):
    """Salva una ricetta nel catalogo permanente, separato dal diario meals."""
    payload = {
        "user_id": user_id,
        "name": str(name).strip(),
        "meal_type": str(meal_type),
        "category": category if category in MEAL_CATEGORIES else "Casa",
        "recipe_servings": float(recipe_servings),
        "calories": float(calories),
        "protein": float(protein),
        "carbs": float(carbs),
        "fat": float(fat),
        "notes": str(notes or "").strip(),
        "ingredients_json": ingredients_json,
        "is_shared": bool(is_shared),
        "image_url": str(image_url or "").strip() or None,
    }
    return create_recipe_via_api(
        payload,
        st.session_state.get("auth_access_token"),
    )



def _current_user_metadata():
    """Return the freshest auth metadata available in this Streamlit session."""
    session_user = st.session_state.get("user")
    if session_user is not None:
        meta = getattr(session_user, "user_metadata", None)
        if isinstance(meta, dict):
            return dict(meta)

    try:
        auth_user = supabase.auth.get_user()
        obj = getattr(auth_user, "user", None)
        meta = getattr(obj, "user_metadata", None)
        if isinstance(meta, dict):
            return dict(meta)
    except Exception:
        pass

    return dict(u_meta or {})


def get_default_breakfast_recipe_ids():
    meta = _current_user_metadata()

    def _id(key):
        value = meta.get(key)
        if value in (None, "", "None"):
            return None
        return str(value)

    return {
        "Casa": _id("default_breakfast_home_recipe_id"),
        "Lavoro": _id("default_breakfast_work_recipe_id"),
    }


def set_default_breakfast_recipe(category, recipe_id):
    """
    Save a personal recipe as the user's default breakfast.
    Uses auth metadata so recipe_library needs no schema change.
    """
    if category not in {"Casa", "Lavoro"}:
        raise ValueError("Categoria colazione standard non valida.")

    key = (
        "default_breakfast_home_recipe_id"
        if category == "Casa"
        else "default_breakfast_work_recipe_id"
    )

    metadata = _current_user_metadata()
    metadata[key] = str(recipe_id) if recipe_id is not None else None

    response = supabase.auth.update_user(
        {"data": metadata}
    )
    if getattr(response, "user", None):
        st.session_state["user"] = response.user

    return response


def load_personal_recipe_by_id(recipe_id):
    if recipe_id in (None, ""):
        return None

    try:
        return fetch_recipe_by_id_from_api(
            recipe_id,
            st.session_state.get("auth_access_token"),
        )
    except Exception as exc:
        print(f"Default breakfast recipe load error: {exc}")
        return None


def breakfast_already_logged(log_date):
    try:
        rows = load_daily_meals_cached(
            user_id,
            str(log_date),
            st.session_state.get("auth_access_token"),
        )
        return any(
            str(row.get("meal_type") or "").strip().casefold()
            == "colazione"
            for row in rows
        )
    except Exception as exc:
        print(f"Breakfast logged check failed: {exc}")
        return False


def insert_default_breakfast_recipe(recipe_row, log_date, category):
    """One-click logging of one serving of a saved default breakfast."""
    servings = max(
        1.0,
        _safe_float(
            recipe_row.get("recipe_servings") or 1.0
        ),
    )

    calories = _safe_float(recipe_row.get("calories")) / servings
    protein = _safe_float(recipe_row.get("protein")) / servings
    carbs = _safe_float(recipe_row.get("carbs")) / servings
    fat = _safe_float(recipe_row.get("fat")) / servings
    name = str(recipe_row.get("name") or "Colazione").strip()

    return insert_meal_with_base_data(
        log_date=log_date,
        meal_type="Colazione",
        display_name=f"{name} (1.0 porz.)",
        base_name=name,
        quantity=1.0,
        is_per_100g=False,
        calories=calories,
        protein=protein,
        carbs=carbs,
        fat=fat,
        base_calories=calories,
        base_protein=protein,
        base_carbs=carbs,
        base_fat=fat,
        notes=recipe_row.get("notes", ""),
        category=category,
        ingredients_json=recipe_row.get("ingredients_json"),
        recipe_servings=servings,
    )


def load_available_recipes():
    """
    Ricette disponibili nel logging:
    - tutte le proprie
    - quelle condivise dagli altri utenti
    Le proprie hanno precedenza in caso di stesso nome.
    """
    rows = fetch_available_recipes_from_api(
        st.session_state.get("auth_access_token")
    )

    result = {}
    for row in rows:
        label = str(row.get("name") or "").strip()
        if not label:
            continue

        key = label.casefold()

        # If both shared and own recipes have same name, own recipe wins.
        if key in result:
            existing = result[key]
            if str(existing.get("user_id")) == str(user_id):
                continue
            if str(row.get("user_id")) != str(user_id):
                continue

        result[key] = row

    return sorted(result.values(), key=lambda r: str(r.get("name") or "").casefold())



def upload_recipe_image(uploaded_file):
    """Carica una foto ricetta su Supabase Storage e restituisce la public URL."""
    if uploaded_file is None:
        return None

    mime = str(getattr(uploaded_file, "type", "") or "").lower()
    ext_map = {
        "image/jpeg": "jpg",
        "image/jpg": "jpg",
        "image/png": "png",
        "image/webp": "webp",
    }
    ext = ext_map.get(mime)

    if not ext:
        original_name = str(getattr(uploaded_file, "name", "") or "")
        suffix = Path(original_name).suffix.lower().lstrip(".")
        ext = suffix if suffix in {"jpg", "jpeg", "png", "webp"} else "jpg"

    object_path = f"{user_id}/{uuid.uuid4().hex}.{ext}"

    supabase.storage.from_(RECIPE_IMAGE_BUCKET).upload(
        path=object_path,
        file=uploaded_file.getvalue(),
        file_options={
            "content-type": mime or f"image/{ext}",
            "cache-control": "3600",
            "upsert": "false",
        },
    )

    public_url = supabase.storage.from_(RECIPE_IMAGE_BUCKET).get_public_url(
        object_path
    )

    if isinstance(public_url, dict):
        public_url = (
            public_url.get("publicUrl")
            or public_url.get("public_url")
            or public_url.get("url")
            or ""
        )

    return str(public_url or "").strip() or None


def calculate_recipe_totals(ingredients):
    total_weight = sum(float(i.get("quantity_g", 0)) for i in ingredients)
    totals = {"calories": 0.0, "protein": 0.0, "carbs": 0.0, "fat": 0.0}
    for i in ingredients:
        factor = float(i.get("quantity_g", 0)) / 100.0
        for key in totals:
            totals[key] += float(i.get(f"{key}_per_100g", 0) or 0) * factor
    per100 = {k: (v / total_weight * 100 if total_weight > 0 else 0) for k, v in totals.items()}
    return total_weight, totals, per100

# ==============================================================================
# 4. AUTHENTICATION & SESSION MANAGEMENT
# ==============================================================================
# Autenticazione email/password con sessione persistente.
#
# Persistenza:
# - nel browser salviamo soltanto il refresh token Supabase;
# - a ogni refresh completo leggiamo prima st.context.cookies, che contiene i
#   cookie arrivati con la richiesta iniziale;
# - usiamo refresh_session(refresh_token) per ottenere una nuova sessione;
# - se Supabase ruota il refresh token, riscriviamo subito il cookie aggiornato.
#
# Nota: streamlit-cookies-controller crea cookie accessibili dal browser e quindi
# non HttpOnly. Per una futura versione con requisiti di sicurezza più elevati è
# preferibile un backend che imposti cookie HttpOnly/Secure/SameSite.
SESSION_COOKIE = "sanosync_refresh_token"
SESSION_COOKIE_MAX_AGE = 10 * 365 * 24 * 60 * 60


def _cookie_set(name, value, max_age):
    controller.set(name, str(value), max_age=max_age)

def _cookie_delete(name):
    try:
        controller.remove(name)
    except Exception:
        try:
            controller.set(name, "", max_age=0)
        except Exception:
            pass

def _read_refresh_token_cookie():
    # Su un vero browser refresh questa è la lettura più affidabile perché
    # Streamlit espone i cookie ricevuti nella richiesta iniziale.
    try:
        value = st.context.cookies.get(SESSION_COOKIE)
        if value:
            return str(value).strip().strip('"')
    except Exception:
        pass

    # Fallback per rerun normali della stessa pagina.
    try:
        value = controller.get(SESSION_COOKIE)
        if value:
            return str(value).strip().strip('"')
    except Exception:
        pass
    return None

def save_authenticated_session(response, fallback_user=None):
    """
    Salva la sessione come nell'app di riferimento:
    - access token in session_state
    - refresh token in session_state
    - user object in session_state
    - refresh token anche nel cookie persistente di SanoSync
    """
    session = getattr(response, "session", None)
    user_obj = getattr(response, "user", None) or fallback_user

    # Alcune versioni di supabase-py possono restituire direttamente
    # un oggetto sessione da set_session().
    if session is None and getattr(response, "access_token", None):
        session = response

    if session is None:
        raise RuntimeError("Supabase non ha restituito una sessione valida.")

    access_token = getattr(session, "access_token", None)
    refresh_token = getattr(session, "refresh_token", None)

    if not access_token or not refresh_token:
        raise RuntimeError("Token OAuth non disponibili.")

    if user_obj is None:
        user_obj = getattr(session, "user", None)

    if user_obj is None:
        verified = supabase.auth.get_user(access_token)
        user_obj = getattr(verified, "user", None)

    if user_obj is None:
        raise RuntimeError("Supabase non ha restituito l'utente autenticato.")

    st.session_state["auth_access_token"] = access_token
    st.session_state["auth_refresh_token"] = refresh_token
    st.session_state["user"] = user_obj

    # Manteniamo anche la persistenza già presente in SanoSync.
    _cookie_set(
        SESSION_COOKIE,
        refresh_token,
        SESSION_COOKIE_MAX_AGE,
    )

    return user_obj

def restore_session_from_cookie():
    refresh_token = _read_refresh_token_cookie()
    if not refresh_token:
        return False

    try:
        # refresh_session è più adatto qui di set_session: ci basta il refresh
        # token persistente e riceviamo sempre token correnti.
        response = supabase.auth.refresh_session(refresh_token)
        if response and getattr(response, "session", None):
            save_authenticated_session(response)
            return True
    except Exception as e:
        print(f"Session restore error: {e}")

    _cookie_delete(SESSION_COOKIE)
    return False

def restore_and_verify_auth_session():
    """
    Ripristina e verifica la sessione OAuth dopo i rerun Streamlit.

    Questa è la stessa logica usata nell'app di riferimento:
    set_session sul client principale -> get_user -> aggiorna i token.
    """
    access_token = st.session_state.get("auth_access_token")
    refresh_token = st.session_state.get("auth_refresh_token")

    if not access_token or not refresh_token:
        return None

    try:
        main_response = supabase.auth.set_session(
            access_token,
            refresh_token,
        )

        main_session = getattr(main_response, "session", None)
        if main_session is not None:
            access_token = getattr(
                main_session,
                "access_token",
                access_token,
            )
            refresh_token = getattr(
                main_session,
                "refresh_token",
                refresh_token,
            )
            st.session_state["auth_access_token"] = access_token
            st.session_state["auth_refresh_token"] = refresh_token

        verified = supabase.auth.get_user(access_token)
        user_obj = getattr(verified, "user", None)

        if user_obj is None:
            return None

        st.session_state["user"] = user_obj
        _cookie_set(
            SESSION_COOKIE,
            refresh_token,
            SESSION_COOKIE_MAX_AGE,
        )
        return user_obj

    except Exception as exc:
        print(f"Session verification error: {exc}")
        return None


AUTH_FLOW_STATE_KEY = "auth_flow_id"


@st.cache_resource
def get_auth_flow_client(flow_id: str):
    """
    Client Supabase dedicato al singolo flusso OAuth.

    Questa è intenzionalmente la stessa logica dell'altra app funzionante:
    client Supabase NORMALE, senza ClientOptions custom e senza PKCE/cookie
    costruiti manualmente.
    """
    return create_client(
        st.secrets["SUPABASE_URL"],
        st.secrets["SUPABASE_KEY"],
    )


def _oauth_response_url(response):
    if response is None:
        return ""
    if isinstance(response, dict):
        return str(response.get("url") or "")
    return str(getattr(response, "url", "") or "")


def get_public_app_url():
    configured = st.secrets.get("APP_URL")
    if configured:
        return str(configured).rstrip("/")

    try:
        headers = st.context.headers
        host = headers.get("Host") or headers.get("host")
        proto = (
            headers.get("X-Forwarded-Proto")
            or headers.get("x-forwarded-proto")
            or "https"
        )
        if host:
            return f"{proto}://{host}".rstrip("/")
    except Exception:
        pass

    return "http://localhost:8501"


def build_provider_login_url(provider):
    """
    Genera l'URL OAuth esattamente come nell'altra app funzionante.

    Supabase-py genera e conserva internamente il verifier PKCE nel client
    dedicato al flow_id. @st.cache_resource permette di recuperare LO STESSO
    client quando Google ritorna all'app con auth_flow=<flow_id>.
    """
    flow_id = uuid.uuid4().hex
    auth_client = get_auth_flow_client(flow_id)

    app_url = get_public_app_url().rstrip("/")
    redirect_to = (
        f"{app_url}/"
        f"?auth_callback=1&auth_flow={flow_id}"
    )

    response = auth_client.auth.sign_in_with_oauth(
        {
            "provider": provider,
            "options": {
                "redirect_to": redirect_to,
            },
        }
    )

    return _oauth_response_url(response)


def handle_oauth_callback():
    """
    Copia della logica dell'altra app funzionante:
    recupera lo stesso client PKCE tramite flow_id, scambia il code,
    poi trasferisce token/sessione al client principale SanoSync.
    """
    code_param = st.query_params.get("code")
    flow_id = st.query_params.get("auth_flow")

    if not code_param or not flow_id:
        return False

    try:
        # Questo deve essere lo STESSO client creato prima del redirect.
        auth_client = get_auth_flow_client(str(flow_id))

        response = auth_client.auth.exchange_code_for_session(
            {"auth_code": str(code_param)}
        )

        session = getattr(response, "session", None)
        user_obj = getattr(response, "user", None)

        if session is None:
            session = auth_client.auth.get_session()

        access_token = getattr(session, "access_token", None)
        refresh_token = getattr(session, "refresh_token", None)

        if not access_token or not refresh_token:
            raise RuntimeError(
                "Supabase non ha restituito una sessione OAuth valida."
            )

        if user_obj is None:
            verified = auth_client.auth.get_user(access_token)
            user_obj = getattr(verified, "user", None)

        # Manteniamo il sistema di sessione/cookie già usato da SanoSync
        # DOPO che Supabase ha completato correttamente il PKCE.
        main_response = supabase.auth.set_session(
            access_token,
            refresh_token,
        )

        save_authenticated_session(
            main_response,
            fallback_user=user_obj,
        )

        st.session_state[AUTH_FLOW_STATE_KEY] = str(flow_id)

        st.query_params.clear()
        st.session_state.pop("auth_callback_error", None)
        st.rerun()

    except Exception as exc:
        st.query_params.clear()
        st.session_state["auth_callback_error"] = str(exc)
        return False

    return True


def show_login_page():
    """
    Login SanoSync multilingua:
    - dropdown lingua disponibile prima del login;
    - hero + card in palette SanoSync;
    - Google e Facebook OAuth con lo stesso flusso funzionante dell'altra app.
    """
    LOGIN_I18N = {
        "Italiano": {
            "language": "🌐 Lingua",
            "logout": "🚪 Esci",
            "eyebrow": "SANOSYNC",
            "title": "🍑 Tutto sotto controllo",
            "subtitle": "Alimentazione, attività, peso e progressi in un unico posto.",
            "continue": "Accedi per continuare",
            "google": "Continua con Google",
            "facebook": "Continua con Facebook",
            "google_note": (
                "L’autenticazione Google e Facebook viene gestita da Supabase Auth. "
                "Le password dei tuoi account social non vengono mai gestite da SanoSync."
            ),
            "divider": "oppure accedi con email e password",
            "login": "Login",
            "signup": "Registrazione",
            "email": "Email",
            "email_ph": "nome@email.com",
            "password": "Password",
            "password_min": "Password (min. 6 caratteri)",
            "login_btn": "Accedi",
            "signup_btn": "Registrati","office_lunch_title":"Pranzo in ufficio","office_lunch_enabled":"Pranzi abitualmente in ufficio?","office_lunch_no":"No","office_lunch_yes":"Sì","protein_goal_title":"Goal Proteico","protein_goal_enabled":"Vuoi impostare un goal proteico giornaliero?","protein_goal_no":"No","protein_goal_yes":"Sì","protein_goal_g":"Goal proteico giornaliero (g)",
            "credentials_required": "Inserisci email e password.",
            "invalid_credentials": "Credenziali non valide.",
            "auth_error": "Errore durante l'autenticazione: {error}",
            "signup_invalid": "Inserisci una email valida e una password di almeno 6 caratteri.",
            "physical_title": "📋 Parametri fisici iniziali",
            "name": "Nome",
            "gender": "Genere",
            "male": "Uomo",
            "female": "Donna",
            "gender_placeholder": "Seleziona genere...",
            "birth_date": "Data di nascita",
            "height": "Altezza (cm)",
            "current_weight": "Peso attuale (kg)",
            "target_weight": "Peso obiettivo (kg)",
            "physical_required": "Compila tutti i parametri fisici.",
            "signup_success": "✅ Account creato e accesso effettuato.",
            "signup_email_confirm": (
                "✅ Account creato. Controlla l'email se è richiesta la conferma, "
                "poi effettua il login."
            ),
            "google_error": "Non riesco a generare i link social. Controlla la configurazione Auth di Supabase.",
            "google_callback_error": "Login Google non completato: {error}",
        },
        "English": {
            "language": "🌐 Language",
            "logout": "🚪 Log out",
            "eyebrow": "SANOSYNC",
            "title": "🍑 Under control",
            "subtitle": "Food, activity, weight and progress in one place.",
            "continue": "Sign in to continue",
            "google": "Continue with Google",
            "facebook": "Continue with Facebook",
            "google_note": (
                "Google and Facebook authentication is handled by Supabase Auth. "
                "SanoSync never handles your social account passwords."
            ),
            "divider": "or sign in with email and password",
            "login": "Login",
            "signup": "Sign up",
            "email": "Email",
            "email_ph": "name@email.com",
            "password": "Password",
            "password_min": "Password (min. 6 characters)",
            "login_btn": "Sign in",
            "signup_btn": "Create account","office_lunch_title":"Office lunch","office_lunch_enabled":"Do you usually have lunch at the office?","office_lunch_no":"No","office_lunch_yes":"Yes","protein_goal_title":"Protein Goal","protein_goal_enabled":"Set a daily protein goal?","protein_goal_no":"No","protein_goal_yes":"Yes","protein_goal_g":"Daily protein goal (g)",
            "credentials_required": "Enter email and password.",
            "invalid_credentials": "Invalid credentials.",
            "auth_error": "Authentication error: {error}",
            "signup_invalid": "Enter a valid email and a password of at least 6 characters.",
            "physical_title": "📋 Initial physical details",
            "name": "Name",
            "gender": "Gender",
            "male": "Male",
            "female": "Female",
            "gender_placeholder": "Select gender...",
            "birth_date": "Date of birth",
            "height": "Height (cm)",
            "current_weight": "Current weight (kg)",
            "target_weight": "Target weight (kg)",
            "physical_required": "Complete all physical details.",
            "signup_success": "✅ Account created and signed in.",
            "signup_email_confirm": (
                "✅ Account created. Check your email if confirmation is required, "
                "then come back and sign in."
            ),
            "google_error": "I can't generate the social login links. Check your Supabase Auth configuration.",
            "google_callback_error": "Google login not completed: {error}",
        },
        "Nederlands": {
            "language": "🌐 Taal",
            "logout": "🚪 Uitloggen",
            "eyebrow": "SANOSYNC",
            "title": "🍑 Komt goed",
            "subtitle": "Voeding, activiteit, gewicht en voortgang op één plek.",
            "continue": "Log in om door te gaan",
            "google": "Doorgaan met Google",
            "facebook": "Doorgaan met Facebook",
            "google_note": (
                "Google- en Facebook-authenticatie wordt beheerd door Supabase Auth. "
                "SanoSync verwerkt nooit de wachtwoorden van je socialaccounts."
            ),
            "divider": "of log in met e-mail en wachtwoord",
            "login": "Inloggen",
            "signup": "Registreren",
            "email": "E-mail",
            "email_ph": "naam@email.com",
            "password": "Wachtwoord",
            "password_min": "Wachtwoord (min. 6 tekens)",
            "login_btn": "Inloggen",
            "signup_btn": "Account aanmaken","office_lunch_title":"Lunch op kantoor","office_lunch_enabled":"Lunch je gewoonlijk op kantoor?","office_lunch_no":"Nee","office_lunch_yes":"Ja","protein_goal_title":"Eiwitdoel","protein_goal_enabled":"Een dagelijks eiwitdoel instellen?","protein_goal_no":"Nee","protein_goal_yes":"Ja","protein_goal_g":"Dagelijks eiwitdoel (g)",
            "credentials_required": "Voer e-mail en wachtwoord in.",
            "invalid_credentials": "Ongeldige inloggegevens.",
            "auth_error": "Authenticatiefout: {error}",
            "signup_invalid": "Voer een geldig e-mailadres en een wachtwoord van minimaal 6 tekens in.",
            "physical_title": "📋 Eerste fysieke gegevens",
            "name": "Naam",
            "gender": "Geslacht",
            "male": "Man",
            "female": "Vrouw",
            "gender_placeholder": "Selecteer geslacht...",
            "birth_date": "Geboortedatum",
            "height": "Lengte (cm)",
            "current_weight": "Huidig gewicht (kg)",
            "target_weight": "Streefgewicht (kg)",
            "physical_required": "Vul alle fysieke gegevens in.",
            "signup_success": "✅ Account aangemaakt en ingelogd.",
            "signup_email_confirm": (
                "✅ Account aangemaakt. Controleer je e-mail als bevestiging nodig is "
                "en log daarna in."
            ),
            "google_error": "Ik kan de social-loginlinks niet genereren. Controleer de Supabase Auth-configuratie.",
            "google_callback_error": "Google-login niet voltooid: {error}",
        },
        "Français": {
            "language": "🌐 Langue",
            "logout": "🚪 Se déconnecter",
            "eyebrow": "SANOSYNC",
            "title": "🍑 C'est géré",
            "subtitle": "Alimentation, activité, poids et progrès au même endroit.",
            "continue": "Connectez-vous pour continuer",
            "google": "Continuer avec Google",
            "facebook": "Continuer avec Facebook",
            "google_note": (
                "L’authentification Google et Facebook est gérée par Supabase Auth. "
                "SanoSync ne gère jamais les mots de passe de vos comptes sociaux."
            ),
            "divider": "ou connectez-vous avec e-mail et mot de passe",
            "login": "Connexion",
            "signup": "Inscription",
            "email": "E-mail",
            "email_ph": "nom@email.com",
            "password": "Mot de passe",
            "password_min": "Mot de passe (min. 6 caractères)",
            "login_btn": "Se connecter",
            "signup_btn": "Créer un compte","office_lunch_title":"Déjeuner au bureau","office_lunch_enabled":"Déjeunez-vous habituellement au bureau ?","office_lunch_no":"Non","office_lunch_yes":"Oui","protein_goal_title":"Objectif protéique","protein_goal_enabled":"Définir un objectif quotidien de protéines ?","protein_goal_no":"Non","protein_goal_yes":"Oui","protein_goal_g":"Objectif quotidien de protéines (g)",
            "credentials_required": "Saisissez votre e-mail et votre mot de passe.",
            "invalid_credentials": "Identifiants invalides.",
            "auth_error": "Erreur d’authentification : {error}",
            "signup_invalid": "Saisissez un e-mail valide et un mot de passe d’au moins 6 caractères.",
            "physical_title": "📋 Données physiques initiales",
            "name": "Prénom",
            "gender": "Sexe",
            "male": "Homme",
            "female": "Femme",
            "gender_placeholder": "Sélectionnez le sexe...",
            "birth_date": "Date de naissance",
            "height": "Taille (cm)",
            "current_weight": "Poids actuel (kg)",
            "target_weight": "Poids cible (kg)",
            "physical_required": "Complétez toutes les données physiques.",
            "signup_success": "✅ Compte créé et connexion effectuée.",
            "signup_email_confirm": (
                "✅ Compte créé. Vérifiez votre e-mail si une confirmation est requise, "
                "puis revenez vous connecter."
            ),
            "google_error": "Impossible de générer les liens de connexion sociale. Vérifiez la configuration Supabase Auth.",
            "google_callback_error": "Connexion Google non terminée : {error}",
        },
    }

    st.markdown(
        """
        <style>
        [data-testid="stSidebar"] { display: none !important; }

        [data-testid="stAppViewContainer"] {
            background:
                radial-gradient(circle at 92% 4%, rgba(255,139,139,.22), transparent 28%),
                radial-gradient(circle at 5% 50%, rgba(255,193,193,.16), transparent 25%),
                linear-gradient(180deg, #FFF9F9 0%, #FFF3F3 55%, #FFF9F9 100%);
        }

        .block-container {
            max-width: 760px !important;
            padding-top: 1.35rem !important;
            padding-bottom: 3rem !important;
        }

        .login-language-wrap {
            max-width: 610px;
            margin: 0 auto .75rem auto;
        }

        .sano-login-shell {
            max-width: 610px;
            margin: 0 auto;
        }

        .sano-login-hero {
            border-radius: 28px;
            padding: 34px 34px 31px;
            text-align: center;
            margin: 4px auto 20px auto;
            background:
                radial-gradient(circle at 92% 4%, rgba(255,255,255,.23), transparent 32%),
                linear-gradient(135deg, #172A46 0%, #243B5A 54%, #FF8B8B 155%);
            border: 1px solid rgba(255,139,139,.35);
            box-shadow: 0 20px 50px rgba(35,48,72,.16);
        }

        .sano-login-hero,
        .sano-login-hero * { color: #FFFFFF !important; }

        .sano-login-eyebrow {
            font-size: .78rem;
            font-weight: 900;
            letter-spacing: .16em;
            color: #FFD1D1 !important;
            margin-bottom: 8px;
        }

        .sano-login-title {
            font-size: clamp(2rem, 5vw, 3rem);
            line-height: 1.02;
            font-weight: 950;
            letter-spacing: -.04em;
            margin: 3px 0 10px;
        }

        .sano-login-subtitle {
            font-size: 1rem;
            line-height: 1.45;
            color: #FCECEC !important;
        }

        .sano-login-card {
            max-width: 610px;
            box-sizing: border-box;
            margin: 0 auto;
            padding: 27px 28px 24px;
            border-radius: 24px;
            background: rgba(255,255,255,.97);
            border: 1.5px solid #FFD0D0;
            box-shadow: 0 13px 38px rgba(35,48,72,.09);
        }

        .sano-login-card-title {
            text-align: center;
            font-size: 1.22rem;
            font-weight: 900;
            color: #172A46 !important;
            margin-bottom: 17px;
        }

        .sano-social-login {
            height: 58px;
            display: flex;
            align-items: center;
            justify-content: center;
            gap: 13px;
            width: 100%;
            box-sizing: border-box;
            border-radius: 14px;
            text-decoration: none !important;
            font-size: 1rem;
            font-weight: 850;
            margin: 10px 0;
        }

        .sano-social-login.google {
            color: #172A46 !important;
            background: #FFFFFF;
            border: 2px solid #FF8B8B;
            box-shadow: 0 5px 14px rgba(35,48,72,.06);
        }

        .sano-social-login.google span { color: #172A46 !important; }

        .sano-social-login.facebook {
            color: #FFFFFF !important;
            background: #1877F2;
            border: 2px solid #1468D4;
            box-shadow: 0 5px 14px rgba(24,119,242,.18);
        }

        .sano-social-login.facebook span {
            color: #FFFFFF !important;
        }

        .sano-social-login.facebook:hover {
            background: #166FE5;
            border-color: #125FC2;
        }

        .sano-social-logo {
            width: 23px;
            height: 23px;
            flex: 0 0 23px;
        }

        .sano-login-note {
            text-align: center;
            color: #64748B !important;
            font-size: .80rem;
            line-height: 1.5;
            margin-top: 16px;
        }

        .sano-email-divider {
            max-width: 610px;
            margin: 18px auto 10px auto;
            text-align: center;
            color: #64748B !important;
            font-size: .88rem;
            font-weight: 750;
        }

        div[data-testid="stRadio"],
        div[data-testid="stForm"],
        .st-key-login_lang_selector,
        .st-key-signup_email,
        .st-key-signup_password,
        .st-key-signup_display_name,
        .st-key-signup_gender,
        .st-key-signup_birth_date,
        .st-key-signup_height,
        .st-key-signup_current_weight,
        .st-key-signup_target_weight,
        .st-key-signup_deficit_plan,
        .st-key-signup_deficit_kcal,
        .st-key-signup_submit {
            max-width: 610px;
            margin-left: auto;
            margin-right: auto;
        }

        div[data-testid="stForm"] {
            border: 1.5px solid #FFD0D0;
            border-radius: 20px;
            background: rgba(255,255,255,.96);
            padding: 18px 20px 20px;
            box-shadow: 0 9px 26px rgba(35,48,72,.06);
        }

        .stButton > button,
        div[data-testid="stFormSubmitButton"] > button {
            border: 2px solid #FF8B8B !important;
            border-radius: 11px !important;
            font-weight: 800 !important;
        }

        .stButton > button[kind="primary"],
        div[data-testid="stFormSubmitButton"] > button {
            background: #FF8B8B !important;
            color: #FFFFFF !important;
        }

        .stButton > button[kind="primary"] *,
        div[data-testid="stFormSubmitButton"] > button * {
            color: #FFFFFF !important;
        }

        @media (max-width: 700px) {
            .block-container {
                padding-left: .85rem !important;
                padding-right: .85rem !important;
                padding-top: .8rem !important;
            }
            .sano-login-hero {
                padding: 27px 19px 25px;
                border-radius: 23px;
            }
            .sano-login-card {
                padding: 23px 18px 21px;
                border-radius: 20px;
            }
        }
        </style>
        """,
        unsafe_allow_html=True,
    )

    if "login_lang_selector" not in st.session_state:
        st.session_state["login_lang_selector"] = (
            st.session_state.get("lang_selector", "Italiano")
            if st.session_state.get("lang_selector", "Italiano") in LOGIN_I18N
            else "Italiano"
        )

    LOGIN_I18N["Português"] = {
        **LOGIN_I18N["English"],
        "language": "🌐 Idioma",
        "logout": "🚪 Sair",
        "title": "🍑 Tudo sob controlo",
        "subtitle": "Alimentação, atividade, peso e progresso num só lugar.",
        "continue": "Inicie sessão para continuar",
        "google": "Continuar com Google",
        "facebook": "Continuar com Facebook",
        "divider": "ou inicie sessão com e-mail e palavra-passe",
        "login": "Iniciar sessão",
        "signup": "Registar",
        "email": "E-mail",
        "password": "Palavra-passe",
        "password_min": "Palavra-passe (mín. 6 caracteres)",
        "login_btn": "Entrar",
        "signup_btn": "Criar conta",
        "office_lunch_title": "Almoço no escritório",
        "office_lunch_enabled": "Costuma almoçar no escritório?",
        "office_lunch_no": "Não",
        "office_lunch_yes": "Sim",
        "protein_goal_title": "Objetivo de proteína",
        "protein_goal_enabled": "Definir um objetivo diário de proteína?",
        "protein_goal_no": "Não",
        "protein_goal_yes": "Sim",
        "protein_goal_g": "Objetivo diário de proteína (g)",
        "credentials_required": "Introduza o e-mail e a palavra-passe.",
        "invalid_credentials": "Credenciais inválidas.",
        "auth_error": "Erro de autenticação: {error}",
        "physical_title": "📋 Dados físicos iniciais",
        "name": "Nome",
        "gender": "Sexo",
        "male": "Homem",
        "female": "Mulher",
        "gender_placeholder": "Selecione o sexo...",
        "birth_date": "Data de nascimento",
        "height": "Altura (cm)",
        "current_weight": "Peso atual (kg)",
        "target_weight": "Peso objetivo (kg)",
        "physical_required": "Preencha todos os dados físicos.",
        "signup_success": "✅ Conta criada e sessão iniciada.",
        "google_callback_error": "Login Google não concluído: {error}",
    }

    current_login_lang = st.selectbox(
        LOGIN_I18N[st.session_state["login_lang_selector"]]["language"],
        ["Italiano", "English", "Nederlands", "Français", "Português"],
        key="login_lang_selector",
        format_func=format_language_option,
    )
    lt = LOGIN_I18N[current_login_lang]

    # Manteniamo la lingua anche dopo il login.
    st.session_state["lang_selector"] = current_login_lang

    callback_error = st.session_state.pop("auth_callback_error", None)

    try:
        # Stesso identico flusso PKCE per entrambi i provider:
        # client dedicato -> sign_in_with_oauth -> auth_flow -> callback.
        google_url = escape(
            build_provider_login_url("google"),
            quote=True,
        )
        facebook_url = escape(
            build_provider_login_url("facebook"),
            quote=True,
        )
    except Exception as exc:
        st.error(lt["google_error"])
        st.caption(str(exc))
        st.stop()

    login_html = (
        '<div class="sano-login-shell">'
        '<div class="sano-login-hero">'
        f'<div class="sano-login-eyebrow">{escape(lt["eyebrow"])}</div>'
        f'<div class="sano-login-title">{escape(lt["title"])}</div>'
        f'<div class="sano-login-subtitle">{escape(lt["subtitle"])}</div>'
        '</div>'
        '<div class="sano-login-card">'
        f'<div class="sano-login-card-title">{escape(lt["continue"])}</div>'
        f'<a class="sano-social-login google" href="{google_url}" '
        'target="_blank" rel="noopener">'
        '<svg class="sano-social-logo" viewBox="0 0 24 24" aria-hidden="true">'
        '<path fill="#4285F4" d="M21.6 12.23c0-.71-.06-1.4-.18-2.07H12v3.92h5.38a4.6 4.6 0 0 1-2 3.02v2.54h3.24c1.9-1.75 2.98-4.33 2.98-7.41z"/>'
        '<path fill="#34A853" d="M12 22c2.7 0 4.97-.9 6.63-2.43l-3.24-2.54c-.9.6-2.05.96-3.39.96-2.61 0-4.82-1.76-5.61-4.13H3.04v2.62A10 10 0 0 0 12 22z"/>'
        '<path fill="#FBBC05" d="M6.39 13.86A6 6 0 0 1 6.08 12c0-.65.11-1.28.31-1.86V7.52H3.04A10 10 0 0 0 2 12c0 1.61.38 3.13 1.04 4.48l3.35-2.62z"/>'
        '<path fill="#EA4335" d="M12 6.01c1.47 0 2.79.51 3.83 1.5l2.87-2.87A9.63 9.63 0 0 0 12 2a10 10 0 0 0-8.96 5.52l3.35 2.62C7.18 7.77 9.39 6.01 12 6.01z"/>'
        '</svg>'
        f'<span>{escape(lt["google"])}</span>'
        '</a>'
        f'<a class="sano-social-login facebook" href="{facebook_url}" '
        'target="_blank" rel="noopener">'
        '<svg class="sano-social-logo" viewBox="0 0 24 24" aria-hidden="true">'
        '<circle cx="12" cy="12" r="12" fill="#ffffff"/>'
        '<path fill="#1877F2" d="M13.52 20v-7h2.35l.35-2.73h-2.7V8.53c0-.79.22-1.33 1.35-1.33h1.44V4.76c-.25-.03-1.1-.1-2.1-.1-2.08 0-3.5 1.27-3.5 3.6v2.01H8.36V13h2.35v7h2.81z"/>'
        '</svg>'
        f'<span>{escape(lt["facebook"])}</span>'
        '</a>'
        f'<div class="sano-login-note">{escape(lt["google_note"])}</div>'
        '</div>'
        '</div>'
    )

    st.markdown(login_html, unsafe_allow_html=True)

    if callback_error:
        st.error(
            lt["google_callback_error"].format(error=callback_error)
        )

    st.markdown(
        f'<div class="sano-email-divider">{escape(lt["divider"])}</div>',
        unsafe_allow_html=True,
    )

    auth_mode = st.radio(
        "Account",
        [lt["login"], lt["signup"]],
        horizontal=True,
        label_visibility="collapsed",
    )

    if auth_mode == lt["login"]:
        with st.form("auth_login_form", clear_on_submit=False):
            email = st.text_input(
                lt["email"],
                placeholder=lt["email_ph"],
            )
            password = st.text_input(
                lt["password"],
                type="password",
                placeholder="••••••••",
            )
            submitted = st.form_submit_button(
                lt["login_btn"],
                use_container_width=True,
            )

            if submitted:
                try:
                    if not email.strip() or not password:
                        st.warning(lt["credentials_required"])
                    else:
                        response = supabase.auth.sign_in_with_password({
                            "email": email.strip(),
                            "password": password,
                        })

                        if response and response.session:
                            save_authenticated_session(response)
                            st.success("✅")
                            st.rerun()
                        else:
                            st.error(lt["invalid_credentials"])

                except Exception as e:
                    st.error(
                        lt["auth_error"].format(error=str(e))
                    )
                    print(traceback.format_exc())

    else:
        email = st.text_input(
            lt["email"],
            key="signup_email",
            placeholder=lt["email_ph"],
        )
        password = st.text_input(
            lt["password_min"],
            type="password",
            key="signup_password",
            placeholder="••••••••",
        )

        st.markdown(f"#### {lt['physical_title']}")
        display_name_input = st.text_input(
            lt["name"],
            value="",
            key="signup_display_name",
        )

        gender_labels = [lt["male"], lt["female"]]
        gender_display = st.selectbox(
            lt["gender"],
            gender_labels,
            index=None,
            placeholder=lt["gender_placeholder"],
            key="signup_gender",
        )
        gender = (
            "Uomo"
            if gender_display == lt["male"]
            else "Donna"
            if gender_display == lt["female"]
            else None
        )

        birth_date_input = st.date_input(
            lt["birth_date"],
            value=date(1990, 1, 1),
            min_value=date(1900, 1, 1),
            max_value=date.today(),
            key="signup_birth_date",
        )
        height = st.number_input(
            lt["height"],
            value=175.0,
            min_value=100.0,
            max_value=250.0,
            step=1.0,
            key="signup_height",
        )
        current_weight = st.number_input(
            lt["current_weight"],
            value=80.0,
            min_value=20.0,
            max_value=300.0,
            step=0.5,
            key="signup_current_weight",
        )
        target_weight = st.number_input(
            lt["target_weight"],
            value=75.0,
            min_value=20.0,
            max_value=300.0,
            step=0.5,
            key="signup_target_weight",
        )

        deficit_ui = DEFICIT_PRESET_LABELS[_ui_language()]

        if "signup_deficit_plan" not in st.session_state:
            st.session_state["signup_deficit_plan"] = "maintenance"
        else:
            st.session_state["signup_deficit_plan"] = normalize_deficit_plan(
                st.session_state["signup_deficit_plan"]
            )

        if "signup_deficit_kcal" not in st.session_state:
            st.session_state["signup_deficit_kcal"] = 0

        def _sync_signup_deficit_preset():
            selected_key = normalize_deficit_plan(
                st.session_state.get(
                    "signup_deficit_plan",
                    "custom",
                )
            )
            st.session_state["signup_deficit_kcal"] = int(
                DEFICIT_PRESETS.get(selected_key, 0)
            )

        st.markdown(f"#### {deficit_ui['title']}")
        deficit_plan_input = st.selectbox(
            deficit_ui["speed"],
            list(DEFICIT_PRESETS.keys()),
            key="signup_deficit_plan",
            format_func=deficit_preset_label,
            on_change=_sync_signup_deficit_preset,
            help=deficit_ui["help"],
        )

        custom_deficit_input = st.number_input(
            deficit_ui["field"],
            min_value=0,
            max_value=2000,
            step=50,
            key="signup_deficit_kcal",
        )

        st.markdown(f"#### {lt['office_lunch_title']}")
        office_lunch_choice = st.radio(
            lt["office_lunch_enabled"],
            [lt["office_lunch_no"], lt["office_lunch_yes"]],
            horizontal=True,
            index=0,
            key="signup_office_lunch_enabled",
        )
        office_lunch_enabled_input = office_lunch_choice == lt["office_lunch_yes"]

        st.markdown(f"#### {lt['protein_goal_title']}")
        protein_goal_choice = st.radio(
            lt["protein_goal_enabled"],
            [lt["protein_goal_no"], lt["protein_goal_yes"]],
            horizontal=True,
            key="signup_protein_goal_enabled",
        )
        protein_goal_enabled_input = protein_goal_choice == lt["protein_goal_yes"]
        protein_goal_g_input = 0.0
        if protein_goal_enabled_input:
            # Default sensato: 2 g di proteine per kg di peso.
            # Durante la registrazione usiamo il peso appena inserito;
            # se non disponibile/valido, fallback 70 kg -> 140 g.
            _signup_weight_for_protein = _safe_float(
                locals().get("current_weight_input")
                or locals().get("current_weight")
                or locals().get("peso_attuale")
            )
            if _signup_weight_for_protein <= 0:
                _signup_weight_for_protein = 70.0

            _signup_protein_default = min(
                500.0,
                max(1.0, round(_signup_weight_for_protein * 2.0)),
            )

            protein_goal_g_input = st.number_input(
                lt["protein_goal_g"],
                min_value=1.0,
                max_value=500.0,
                value=float(_signup_protein_default),
                step=5.0,
                key="signup_protein_goal_g",
            )

        if st.button(
            lt["signup_btn"],
            use_container_width=True,
            type="primary",
            key="signup_submit",
        ):
            try:
                if not email.strip() or len(password) < 6:
                    st.warning(lt["signup_invalid"])
                elif (
                    not height
                    or not current_weight
                    or not target_weight
                    or not gender
                    or not birth_date_input
                ):
                    st.warning(lt["physical_required"])
                else:
                    selected_plan = normalize_deficit_plan(
                        deficit_plan_input
                    )
                    selected_deficit = resolve_deficit_target(
                        selected_plan,
                        custom_deficit_input,
                    )

                    # Reaching the target weight always means maintenance.
                    if abs(float(current_weight) - float(target_weight)) <= 0.05:
                        selected_plan = "maintenance"
                        selected_deficit = 0

                    preset_value = int(
                        DEFICIT_PRESETS.get(selected_plan, 0)
                    )
                    plan_to_save = (
                        selected_plan
                        if int(selected_deficit) == preset_value
                        else "custom"
                    )

                    response = supabase.auth.sign_up({
                        "email": email.strip(),
                        "password": password,
                        "options": {
                            "data": {
                                "display_name": (
                                    display_name_input
                                    or email.split("@")[0]
                                ),
                                "target_weight": float(target_weight),
                                "current_weight": float(current_weight),
                                "birth_date": str(birth_date_input),
                                "height": float(height),
                                "gender": gender,
                                "deficit_target_kcal": int(
                                    selected_deficit
                                ),
                                "deficit_plan": plan_to_save,
                                "office_lunch_enabled": bool(office_lunch_enabled_input),
                                "protein_goal_enabled": bool(protein_goal_enabled_input),
                                "protein_goal_g": float(protein_goal_g_input) if protein_goal_enabled_input else None,
                            }
                        },
                    })

                    if response and getattr(response, "session", None):
                        save_authenticated_session(response)
                        st.success(lt["signup_success"])
                        st.rerun()
                    else:
                        st.success(lt["signup_email_confirm"])

            except Exception as e:
                st.error(
                    lt["auth_error"].format(error=str(e))
                )
                print(traceback.format_exc())



# ==============================================================================
# PUBLIC LEGAL PAGES + OURA OAUTH
# ==============================================================================

OURA_AUTHORIZE_URL = "https://cloud.ouraring.com/oauth/authorize"
OURA_TOKEN_URL = "https://api.ouraring.com/oauth/token"
OURA_REVOKE_URL = "https://api.ouraring.com/oauth/revoke"
OURA_API_BASE = "https://api.ouraring.com/v2/usercollection"
OURA_SCOPES = "personal daily workout"


def render_public_legal_page(page_name):
    """Public Privacy Policy / Terms pages used by the Oura application."""
    page_name = str(page_name or "").strip().lower()

    st.markdown(
        """
        <style>
        [data-testid="stSidebar"] { display:none !important; }
        [data-testid="collapsedControl"] { display:none !important; }
        .sano-legal-wrap {
            max-width: 900px;
            margin: 1rem auto 4rem auto;
        }
        .sano-legal-wrap h1 { color:#1A2942; }
        .sano-legal-wrap h2 {
            color:#1A2942;
            margin-top:1.8rem;
        }
        .sano-legal-meta {
            color:#6B7280;
            margin-bottom:1.8rem;
        }
        </style>
        """,
        unsafe_allow_html=True,
    )

    st.markdown('<div class="sano-legal-wrap">', unsafe_allow_html=True)

    if page_name == "privacy":
        st.title("SanoSync — Privacy Policy")
        st.markdown(
            '<div class="sano-legal-meta">Ultimo aggiornamento: 30 agosto 2026</div>',
            unsafe_allow_html=True,
        )

        st.markdown(
            """
SanoSync è un'applicazione per il monitoraggio personale di alimentazione,
attività, peso e benessere. Questa informativa descrive come vengono trattati
i dati quando utilizzi SanoSync e, se scegli di collegarlo, il tuo account Oura.

## Dati trattati

SanoSync può trattare i dati del tuo account necessari per autenticazione e
profilo, i dati che inserisci nell'app (per esempio alimenti, attività e peso)
e i dati che autorizzi esplicitamente tramite Oura.

Quando colleghi Oura, SanoSync richiede solo gli ambiti necessari alle
funzioni dell'app: **personal**, **daily** e **workout**. In base ai permessi
effettivamente concessi, questi dati possono comprendere informazioni
personali e corporee, riepiloghi giornalieri relativi ad attività, sonno e
readiness, e riepiloghi degli allenamenti.

## Perché utilizziamo questi dati

I dati vengono utilizzati esclusivamente per fornire le funzionalità richieste
dall'utente: mostrare e integrare i propri dati di benessere, alimentazione e
attività all'interno di SanoSync, calcolare riepiloghi personali e mantenere
la connessione autorizzata con Oura.

SanoSync non vende i dati Oura e non li utilizza per pubblicità
comportamentale.

## Collegamento con Oura

Il collegamento avviene tramite OAuth 2.0. SanoSync non riceve né conserva la
password dell'account Oura. Oura restituisce a SanoSync token di
autorizzazione che consentono l'accesso soltanto ai dati e agli scope
approvati dall'utente.

L'utente può scollegare Oura da SanoSync e può anche revocare l'accesso dalle
impostazioni del proprio account Oura.

## Conservazione e sicurezza

I dati applicativi e le informazioni necessarie a mantenere la connessione
Oura sono conservati nell'infrastruttura utilizzata da SanoSync con controlli
di accesso associati all'account autenticato. I dati vengono conservati solo
per il tempo necessario a fornire il servizio o fino alla cancellazione o
revoca richiesta dall'utente, salvo eventuali obblighi di legge.

## Condivisione

I dati possono essere trattati dai fornitori tecnici strettamente necessari al
funzionamento dell'applicazione (hosting, database e servizi API), nei limiti
necessari all'erogazione del servizio. SanoSync non autorizza tali fornitori a
utilizzare i dati per finalità proprie incompatibili con il servizio.

## Diritti, revoca e cancellazione

Puoi smettere di condividere i dati Oura scollegando l'integrazione. Puoi
inoltre chiedere accesso, correzione o cancellazione dei dati associati al tuo
account contattando SanoSync all'indirizzo indicato sotto.

## Servizio di benessere, non medico

SanoSync è destinato al monitoraggio personale e al benessere generale. Non
fornisce diagnosi, trattamenti o consulenza medica e non sostituisce un
professionista sanitario.

## Contatti

Per domande sulla privacy o richieste relative ai dati:

**fab.zanda@gmail.com**

Sito: **https://sanosync.streamlit.app/**
"""
        )

    elif page_name == "terms":
        st.title("SanoSync — Terms of Service")
        st.markdown(
            '<div class="sano-legal-meta">Ultimo aggiornamento: 30 agosto 2026</div>',
            unsafe_allow_html=True,
        )

        st.markdown(
            """
Utilizzando SanoSync accetti i presenti Termini di Servizio.

## Finalità del servizio

SanoSync offre strumenti per registrare e visualizzare alimentazione,
attività, peso e altre informazioni relative al benessere personale.
Alcune funzionalità possono utilizzare servizi esterni, incluso Oura, quando
l'utente decide volontariamente di collegarli.

## Account e sicurezza

Sei responsabile dell'utilizzo del tuo account e della protezione dei tuoi
metodi di accesso. Non devi utilizzare SanoSync per accedere a dati di altre
persone senza autorizzazione.

## Integrazione Oura

Il collegamento con Oura è facoltativo. Collegando il tuo account autorizzi
SanoSync ad accedere esclusivamente agli scope Oura che approvi durante la
procedura OAuth. Puoi revocare tale autorizzazione in qualsiasi momento.

La disponibilità, accuratezza e continuità dei dati provenienti da Oura
dipendono anche dai servizi Oura, dalla sincronizzazione del dispositivo,
dall'abbonamento dell'utente e dalle autorizzazioni concesse.

## Uso consentito

Non puoi utilizzare il servizio per attività illegali, per compromettere la
sicurezza dell'applicazione, per tentare accessi non autorizzati o per
interferire con il funzionamento del servizio.

## Informazioni sul benessere

I risultati, le stime nutrizionali, i punteggi e le altre informazioni fornite
da SanoSync hanno finalità informative e di benessere generale. Non
costituiscono diagnosi, prescrizioni o consulenza medica.

## Disponibilità del servizio

SanoSync può essere aggiornato, modificato o temporaneamente non disponibile.
Non viene garantita l'assenza assoluta di errori o interruzioni.

## Servizi di terze parti

L'utilizzo di Oura e di altri servizi di terze parti resta soggetto anche ai
termini e alle informative di tali servizi. SanoSync non controlla la
disponibilità o le modifiche apportate da terze parti alle proprie API.

## Interruzione del collegamento

Puoi scollegare Oura in qualsiasi momento dalle impostazioni di SanoSync.
L'accesso futuro ai dati Oura verrà così interrotto. Puoi inoltre richiedere
la cancellazione dei dati associati contattando SanoSync.

## Modifiche ai termini

Questi termini possono essere aggiornati per riflettere modifiche del servizio
o requisiti normativi. La data dell'ultima revisione è indicata in alto.

## Contatti

Per domande sui presenti termini:

**fab.zanda@gmail.com**

Sito: **https://sanosync.streamlit.app/**
"""
        )

    st.markdown("---")
    st.link_button(
        "← Torna a SanoSync",
        "https://sanosync.streamlit.app/",
        use_container_width=False,
    )
    st.markdown("</div>", unsafe_allow_html=True)


_public_page = str(st.query_params.get("page") or "").strip().lower()
if _public_page in {"privacy", "terms"}:
    render_public_legal_page(_public_page)
    st.stop()


def _oura_secret(name):
    try:
        value = str(st.secrets[name]).strip()
    except Exception:
        value = ""
    if not value:
        raise RuntimeError(
            f"Secret Streamlit mancante: {name}"
        )
    return value


def get_oura_redirect_uri():
    # Keep the OAuth callback URL clean. Oura will append code/scope/state.
    # This value must exactly match the Redirect URI registered in Oura.
    return "https://sanosync.streamlit.app/"


def _oura_state_secret():
    # Reuse the existing server-only OAuth state secret.
    return _oura_secret("OAUTH_STATE_SECRET")



@st.cache_resource
def _oura_pending_store():
    # Server-side only. Keyed by the OAuth nonce and shared across Streamlit
    # sessions/tabs in the running app process.
    return {}


def _oura_pending_cleanup(max_age_seconds=1200):
    store = _oura_pending_store()
    now_ts = int(datetime.now(timezone.utc).timestamp())
    stale = [
        key
        for key, value in store.items()
        if now_ts - int(value.get("ts") or 0) > int(max_age_seconds)
    ]
    for key in stale:
        store.pop(key, None)


def build_oura_state(current_user_id, nonce=None):
    payload = {
        "uid": str(current_user_id),
        "ts": int(datetime.now(timezone.utc).timestamp()),
        "nonce": str(nonce or secrets.token_urlsafe(18)),
    }
    raw = json.dumps(
        payload,
        separators=(",", ":"),
        sort_keys=True,
    ).encode("utf-8")
    body = base64.urlsafe_b64encode(raw).decode("ascii").rstrip("=")
    signature = hmac.new(
        _oura_state_secret().encode("utf-8"),
        body.encode("ascii"),
        hashlib.sha256,
    ).digest()
    sig = base64.urlsafe_b64encode(signature).decode("ascii").rstrip("=")
    return f"{body}.{sig}"


def verify_oura_state(state_value, current_user_id, max_age_seconds=900):
    try:
        body, supplied_sig = str(state_value).split(".", 1)
        expected = hmac.new(
            _oura_state_secret().encode("utf-8"),
            body.encode("ascii"),
            hashlib.sha256,
        ).digest()
        expected_sig = (
            base64.urlsafe_b64encode(expected)
            .decode("ascii")
            .rstrip("=")
        )
        if not hmac.compare_digest(supplied_sig, expected_sig):
            return False

        padded = body + "=" * (-len(body) % 4)
        payload = json.loads(
            base64.urlsafe_b64decode(padded).decode("utf-8")
        )

        if str(payload.get("uid")) != str(current_user_id):
            return False

        issued_at = int(payload.get("ts") or 0)
        age = int(datetime.now(timezone.utc).timestamp()) - issued_at
        return 0 <= age <= int(max_age_seconds)
    except Exception:
        return False


def decode_oura_state(state_value):
    """Return the signed state payload after signature/age validation."""
    body, supplied_sig = str(state_value).split(".", 1)
    expected = hmac.new(
        _oura_state_secret().encode("utf-8"),
        body.encode("ascii"),
        hashlib.sha256,
    ).digest()
    expected_sig = (
        base64.urlsafe_b64encode(expected)
        .decode("ascii")
        .rstrip("=")
    )
    if not hmac.compare_digest(supplied_sig, expected_sig):
        raise RuntimeError("Firma OAuth Oura non valida.")

    padded = body + "=" * (-len(body) % 4)
    payload = json.loads(
        base64.urlsafe_b64decode(padded).decode("utf-8")
    )
    issued_at = int(payload.get("ts") or 0)
    age = int(datetime.now(timezone.utc).timestamp()) - issued_at
    if age < 0 or age > 1200:
        raise RuntimeError("Richiesta OAuth Oura scaduta.")
    return payload


def restore_sanosync_session_for_oura_callback(state_value):
    """
    Oura/Streamlit opens the authorization in a new tab. st.session_state is
    therefore new on callback. Recover the SanoSync refresh token from a
    short-lived server-side pending store and re-establish the Supabase session.
    """
    payload = decode_oura_state(state_value)
    nonce = str(payload.get("nonce") or "")
    expected_uid = str(payload.get("uid") or "")
    if not nonce or not expected_uid:
        raise RuntimeError("State OAuth Oura incompleto.")

    _oura_pending_cleanup()
    pending = _oura_pending_store().pop(nonce, None)
    if not pending:
        raise RuntimeError(
            "Sessione SanoSync per il callback Oura non più disponibile. "
            "Riprova a collegare Oura."
        )
    if str(pending.get("uid")) != expected_uid:
        raise RuntimeError("Utente OAuth Oura non corrispondente.")

    refresh_token = str(pending.get("refresh_token") or "")
    if not refresh_token:
        raise RuntimeError("Refresh token SanoSync non disponibile.")

    response = supabase.auth.refresh_session(refresh_token)
    restored_user = save_authenticated_session(response)
    if str(restored_user.id) != expected_uid:
        raise RuntimeError("Sessione SanoSync ripristinata per un altro utente.")
    return restored_user


def build_oura_authorization_url(current_user_id):
    refresh_token = str(
        st.session_state.get("auth_refresh_token") or ""
    ).strip()
    if not refresh_token:
        raise RuntimeError(
            "Sessione SanoSync non disponibile. Effettua nuovamente l'accesso."
        )

    _oura_pending_cleanup()
    nonce = secrets.token_urlsafe(24)
    _oura_pending_store()[nonce] = {
        "uid": str(current_user_id),
        "refresh_token": refresh_token,
        "ts": int(datetime.now(timezone.utc).timestamp()),
    }

    params = {
        "response_type": "code",
        "client_id": _oura_secret("OURA_CLIENT_ID"),
        "redirect_uri": get_oura_redirect_uri(),
        "scope": OURA_SCOPES,
        "state": build_oura_state(current_user_id, nonce=nonce),
    }
    return f"{OURA_AUTHORIZE_URL}?{urlencode(params)}"


def _oura_request(method, url, **kwargs):
    response = requests.request(
        method,
        url,
        timeout=20,
        **kwargs,
    )
    if response.status_code >= 400:
        try:
            detail = response.json()
        except Exception:
            detail = response.text
        raise RuntimeError(
            f"Oura API {response.status_code}: {detail}"
        )
    if not response.content:
        return {}
    try:
        return response.json()
    except Exception:
        return {}


def _oura_scalar(value):
    """Normalize Streamlit query-param values to one plain string."""
    if isinstance(value, (list, tuple)):
        value = value[0] if value else ""
    return str(value or "").strip()


def exchange_oura_code(code_value):
    """Exchange an Oura authorization code exactly once."""
    code_value = _oura_scalar(code_value)
    if not code_value:
        raise RuntimeError("Authorization code Oura mancante.")

    return _oura_request(
        "POST",
        OURA_TOKEN_URL,
        data={
            "grant_type": "authorization_code",
            "code": code_value,
            "client_id": _oura_secret("OURA_CLIENT_ID"),
            "client_secret": _oura_secret("OURA_CLIENT_SECRET"),
            "redirect_uri": get_oura_redirect_uri(),
        },
    )

def refresh_oura_tokens(refresh_token):
    refresh_token = _oura_scalar(refresh_token)
    if not refresh_token:
        raise RuntimeError("Refresh token Oura mancante.")

    return _oura_request(
        "POST",
        OURA_TOKEN_URL,
        data={
            "grant_type": "refresh_token",
            "refresh_token": refresh_token,
            "client_id": _oura_secret("OURA_CLIENT_ID"),
            "client_secret": _oura_secret("OURA_CLIENT_SECRET"),
        },
    )

def fetch_oura_connection(current_user_id):
    response = (
        supabase.table("oura_connections")
        .select("*")
        .eq("user_id", str(current_user_id))
        .limit(1)
        .execute()
    )
    rows = getattr(response, "data", None) or []
    return rows[0] if rows else None


def save_oura_connection(
    current_user_id,
    token_data,
    *,
    granted_scope=None,
    oura_user_id=None,
):
    access_token = str(token_data.get("access_token") or "").strip()
    refresh_token = str(token_data.get("refresh_token") or "").strip()
    if not access_token or not refresh_token:
        raise RuntimeError(
            "Oura non ha restituito access_token e refresh_token."
        )

    expires_in = int(token_data.get("expires_in") or 86400)
    expires_at = (
        datetime.now(timezone.utc) + timedelta(seconds=expires_in)
    ).isoformat()

    payload = {
        "user_id": str(current_user_id),
        "oura_user_id": (
            str(oura_user_id)
            if oura_user_id not in (None, "")
            else None
        ),
        "access_token": access_token,
        "refresh_token": refresh_token,
        "token_type": str(token_data.get("token_type") or "bearer"),
        "scope": str(
            token_data.get("scope")
            or granted_scope
            or OURA_SCOPES
        ),
        "expires_at": expires_at,
        "updated_at": datetime.now(timezone.utc).isoformat(),
    }

    response = (
        supabase.table("oura_connections")
        .upsert(payload, on_conflict="user_id")
        .execute()
    )
    rows = getattr(response, "data", None) or []
    return rows[0] if rows else payload


def delete_oura_connection(current_user_id):
    (
        supabase.table("oura_connections")
        .delete()
        .eq("user_id", str(current_user_id))
        .execute()
    )


def _oura_token_expiring(connection, leeway_seconds=120):
    expires_at = connection.get("expires_at")
    if not expires_at:
        return True
    try:
        parsed = datetime.fromisoformat(
            str(expires_at).replace("Z", "+00:00")
        )
        if parsed.tzinfo is None:
            parsed = parsed.replace(tzinfo=timezone.utc)
        return parsed <= (
            datetime.now(timezone.utc)
            + timedelta(seconds=leeway_seconds)
        )
    except Exception:
        return True


def get_valid_oura_access_token(current_user_id):
    connection = fetch_oura_connection(current_user_id)
    if not connection:
        raise RuntimeError("Oura non è collegato.")

    if not _oura_token_expiring(connection):
        return str(connection["access_token"]), connection

    token_data = refresh_oura_tokens(connection.get("refresh_token"))
    refreshed = save_oura_connection(
        current_user_id,
        token_data,
        granted_scope=connection.get("scope"),
        oura_user_id=connection.get("oura_user_id"),
    )
    return str(refreshed["access_token"]), refreshed


def oura_get_personal_info(current_user_id):
    access_token, _ = get_valid_oura_access_token(current_user_id)
    return _oura_request(
        "GET",
        f"{OURA_API_BASE}/personal_info",
        headers={
            "Authorization": f"Bearer {access_token}",
        },
    )



def oura_get_daily_activity(
    current_user_id,
    start_date,
    end_date=None,
):
    access_token, _ = get_valid_oura_access_token(current_user_id)
    params = {
        "start_date": str(start_date),
        "end_date": str(end_date or start_date),
    }
    payload = _oura_request(
        "GET",
        f"{OURA_API_BASE}/daily_activity",
        headers={
            "Authorization": f"Bearer {access_token}",
        },
        params=params,
    )
    rows = payload.get("data") if isinstance(payload, dict) else []
    return rows if isinstance(rows, list) else []


def sync_oura_steps_to_supabase(
    current_user_id,
    start_date,
    end_date=None,
):
    """
    Import Oura daily steps into daily_logs.steps.

    SanoSync keeps its existing step-calorie rule (0.04 kcal/step). This avoids
    double-counting Oura active_calories, which can also include workouts.
    Padel/running remain step-conflicting exactly as in the manual UI.
    """
    rows = oura_get_daily_activity(
        current_user_id,
        start_date,
        end_date or start_date,
    )
    synced = []

    for item in rows:
        day_value = str(item.get("day") or "").strip()
        if not day_value:
            continue

        steps = int(item.get("steps") or 0)
        update_daily_log_via_api(
            day_value,
            {"steps": steps},
            st.session_state.get("auth_access_token"),
        )

        step_info = recalculate_step_calories_for_day(
            current_user_id,
            day_value,
            total_steps=steps,
        )
        estimated_kcal = step_info["estimated_kcal"]

        synced.append(
            {
                "date": day_value,
                "steps": steps,
                "estimated_kcal": estimated_kcal,
                "eligible_steps": step_info["eligible_steps"],
                "activity_steps": step_info["activity_steps"],
                "oura_active_calories": int(
                    item.get("active_calories") or 0
                ),
            }
        )

    # Clear existing app caches so pages immediately show imported values.
    try:
        load_daily_log_cached.clear()
    except Exception:
        pass
    try:
        load_daily_activities_cached.clear()
    except Exception:
        pass

    return synced


def maybe_auto_sync_oura(current_user_id, interval_seconds=3600):
    """
    Sync today + yesterday at most once per hour per Streamlit session.
    This runs when SanoSync is open; it is not a background daemon.
    """
    try:
        connection = fetch_oura_connection(current_user_id)
        if not connection:
            return None

        now_ts = int(datetime.now(timezone.utc).timestamp())
        last_ts = int(
            st.session_state.get("oura_last_auto_sync_ts") or 0
        )
        if now_ts - last_ts < int(interval_seconds):
            return None

        today = date.today()
        yesterday = today - timedelta(days=1)
        rows = sync_oura_steps_to_supabase(
            current_user_id,
            yesterday,
            today,
        )
        st.session_state["oura_last_auto_sync_ts"] = now_ts
        st.session_state["oura_last_auto_sync_count"] = len(rows)
        return rows
    except Exception as exc:
        # Do not break the whole app if Oura is temporarily unavailable.
        print(f"Oura auto-sync warning: {exc}")
        return None


def revoke_and_delete_oura_connection(current_user_id):
    connection = fetch_oura_connection(current_user_id)
    if connection and connection.get("access_token"):
        try:
            _oura_request(
                "GET",
                OURA_REVOKE_URL,
                params={
                    "access_token": str(connection["access_token"]),
                },
            )
        except Exception as exc:
            # Local disconnect must still work if Oura is temporarily
            # unreachable; the user can also revoke from Oura directly.
            print(f"Oura revoke warning: {exc}")

    delete_oura_connection(current_user_id)


def handle_oura_callback(current_user_id):
    # Oura returns to the app root and appends code/scope/state.
    state_value = _oura_scalar(st.query_params.get("state"))
    code_value = _oura_scalar(st.query_params.get("code"))
    oauth_error = st.query_params.get("error")

    if not state_value or (not code_value and not oauth_error):
        return False

    if oauth_error:
        description = st.query_params.get("error_description")
        st.query_params.clear()
        st.session_state["oura_callback_error"] = (
            str(description or oauth_error)
        )
        st.session_state["show_personal_settings"] = True
        st.rerun()

    if not code_value or not state_value:
        st.query_params.clear()
        st.session_state["oura_callback_error"] = (
            "Callback Oura incompleto: code/state mancanti."
        )
        st.session_state["show_personal_settings"] = True
        st.rerun()

    if not verify_oura_state(state_value, current_user_id):
        st.query_params.clear()
        st.session_state["oura_callback_error"] = (
            "Verifica di sicurezza OAuth Oura non riuscita."
        )
        st.session_state["show_personal_settings"] = True
        st.rerun()

    # Streamlit can rerun the callback page. Never exchange the same one-time
    # OAuth code again if the connection was already persisted successfully.
    try:
        _existing_oura = fetch_oura_connection(current_user_id)
    except Exception:
        _existing_oura = None

    if _existing_oura:
        st.query_params.clear()
        st.session_state["oura_callback_success"] = True
        st.session_state.pop("oura_callback_error", None)
        st.session_state.pop("oura_authorization_url", None)
        st.session_state["show_personal_settings"] = True
        st.rerun()

    try:
        token_data = exchange_oura_code(code_value)

        access_token = str(token_data.get("access_token") or "")
        if not access_token:
            raise RuntimeError(
                "Oura non ha restituito un access token."
            )

        personal = _oura_request(
            "GET",
            f"{OURA_API_BASE}/personal_info",
            headers={
                "Authorization": f"Bearer {access_token}",
            },
        )

        oura_user_id = (
            personal.get("id")
            or personal.get("user_id")
        )

        save_oura_connection(
            current_user_id,
            token_data,
            granted_scope=st.query_params.get("scope"),
            oura_user_id=oura_user_id,
        )

        st.query_params.clear()
        st.session_state["oura_callback_success"] = True
        st.session_state.pop("oura_callback_error", None)
        st.session_state.pop("oura_authorization_url", None)
        st.session_state["show_personal_settings"] = True
        st.rerun()

    except Exception as exc:
        st.query_params.clear()
        st.session_state["oura_callback_error"] = (
            f"{exc} — Il codice OAuth è monouso: premi di nuovo "
            f"'Connetti Oura' per creare una nuova autorizzazione."
        )
        st.session_state["show_personal_settings"] = True
        st.rerun()

    return True


# ==============================================================================
# 5. RESTORE SESSION / GOOGLE CALLBACK
# ==============================================================================

# Oura opens in a new browser tab, which creates a new Streamlit session.
# Restore the SanoSync/Supabase session from the short-lived server-side pending
# OAuth record before the normal login gate.
if (
    st.session_state.get("user") is None
    and st.query_params.get("state")
    and (
        st.query_params.get("code")
        or st.query_params.get("error")
    )
    and not st.query_params.get("auth_flow")
):
    try:
        restore_sanosync_session_for_oura_callback(
            st.query_params.get("state")
        )
    except Exception as exc:
        st.session_state["oura_callback_error"] = str(exc)

# Gestiamo prima il callback PKCE, perché il code OAuth è monouso.
if (
    st.session_state.get("user") is None
    and st.query_params.get("code")
    and st.query_params.get("auth_flow")
):
    handle_oauth_callback()

# Come nell'app di riferimento: se abbiamo già i due token, li
# trasferiamo/verifichiamo esplicitamente sul client Supabase principale.
if st.session_state.get("user") is None:
    restore_and_verify_auth_session()

# Fallback persistente SanoSync: utile dopo una nuova sessione/browser reload.
if st.session_state.get("user") is None:
    restore_session_from_cookie()

if st.session_state.get("user") is None:
    show_login_page()
    st.stop()

# 6. USER DATA RETRIEVAL
# ==============================================================================
user = st.session_state["user"]
user_id = user.id
u_meta = user.user_metadata or {}

# Oura returns here after authorization. At this point the SanoSync user
# session has already been restored, so we can safely bind Oura to user_id.
if (
    st.query_params.get("state")
    and (
        st.query_params.get("code")
        or st.query_params.get("error")
    )
    and not st.query_params.get("auth_flow")
):
    handle_oura_callback(user_id)

# When SanoSync is open, keep Oura steps reasonably fresh without requiring a
# manual button. Runs at most hourly per Streamlit session.
maybe_auto_sync_oura(user_id)

def get_logged_user_identity(user_obj):
    """Nome, email e avatar dai metadata Supabase (Google incluso)."""
    metadata = getattr(user_obj, "user_metadata", None) or {}
    email = str(getattr(user_obj, "email", "") or "")

    display = str(
        metadata.get("full_name")
        or metadata.get("name")
        or metadata.get("display_name")
        or (email.split("@")[0] if email else "Utente")
    )

    avatar = str(
        metadata.get("avatar_url")
        or metadata.get("picture")
        or ""
    )

    return display, email, avatar


logged_name, logged_email, logged_avatar = get_logged_user_identity(user)


display_name = u_meta.get("display_name") or user.email.split("@")[0] or "User"
user_target_weight = u_meta.get("target_weight")
user_height = u_meta.get("height")
user_gender = u_meta.get("gender")
user_birth_date = u_meta.get("birth_date")
user_deficit_target_kcal = u_meta.get("deficit_target_kcal")
user_deficit_plan = u_meta.get("deficit_plan")
user_office_lunch_enabled = bool(u_meta.get("office_lunch_enabled", True))
_PROTEIN_GOAL_SPECIAL_UID = "df879484-97d5-44fb-8b20-ecf8e4e2b3e3"
user_protein_goal_enabled = bool(u_meta.get("protein_goal_enabled", False))
user_protein_goal_g = _safe_float(u_meta.get("protein_goal_g"))

# ZERO is a personality/theme preference only: nutrition logic stays identical.
# The Profile setting is the authoritative default for a new session.
_preferred_app_mode = str(
    u_meta.get("preferred_app_mode") or ""
).strip().lower()

if _preferred_app_mode == "zero":
    user_zero_mode_enabled = True
elif _preferred_app_mode == "standard":
    user_zero_mode_enabled = False
else:
    # Backward compatibility for accounts created before this preference existed.
    user_zero_mode_enabled = bool(
        u_meta.get("zero_mode_enabled", False)
    )

if "zero_mode_enabled" not in st.session_state:
    st.session_state["zero_mode_enabled"] = user_zero_mode_enabled
if str(user_id) == _PROTEIN_GOAL_SPECIAL_UID and "protein_goal_enabled" not in u_meta:
    user_protein_goal_enabled = True
    if user_protein_goal_g <= 0:
        _special_weight = _safe_float(
            u_meta.get("current_weight")
            or u_meta.get("weight")
        )
        if _special_weight <= 0:
            _special_weight = 70.0
        user_protein_goal_g = round(_special_weight * 2.0)

# Il BMR viene calcolato dinamicamente usando l'ultimo peso registrato.
latest_weight_row = None
try:
    latest_weight_data = load_weight_history_cached(
            user_id,
            st.session_state.get("auth_access_token"),
        )
    if latest_weight_data:
        latest_weight_row = latest_weight_data[-1]
except Exception as e:
    print(f"Latest weight lookup error: {e}")

if latest_weight_row and latest_weight_row.get("weight") is not None:
    user_current_weight = float(latest_weight_row["weight"])
else:
    metadata_weight = u_meta.get("current_weight")
    user_current_weight = (
        float(metadata_weight)
        if metadata_weight not in (None, "")
        else None
    )


# Self-heal older metadata: if latest weight equals target, force maintenance.
try:
    _target_now = _safe_float(user_target_weight)
    if (
        user_current_weight is not None
        and _target_now > 0
        and abs(float(user_current_weight) - _target_now) <= 0.05
        and (
            _safe_float(user_deficit_target_kcal) != 0
            or normalize_deficit_plan(user_deficit_plan) != "maintenance"
        )
    ):
        _maintenance_meta = dict(u_meta)
        _maintenance_meta["current_weight"] = float(user_current_weight)
        _maintenance_meta["deficit_target_kcal"] = 0
        _maintenance_meta["deficit_plan"] = "maintenance"

        _maintenance_response = supabase.auth.update_user(
            {"data": _maintenance_meta}
        )
        if getattr(_maintenance_response, "user", None):
            st.session_state["user"] = _maintenance_response.user

        u_meta = _maintenance_meta
        user_deficit_target_kcal = 0
        user_deficit_plan = "maintenance"
except Exception as exc:
    print(f"Maintenance metadata sync error: {exc}")


user_bmr = None
if (
    user_current_weight is not None
    and user_height is not None
    and user_gender is not None
    and user_birth_date
):
    user_bmr = calculate_bmr(
        user_current_weight,
        float(user_height),
        user_birth_date,
        user_gender,
    )

# ==============================================================================
# 7. PROFILE COMPLETION CHECK
# ==============================================================================
profile_incomplete = (
    user_target_weight is None
    or user_height is None
    or user_gender is None
    or not user_birth_date
    or user_current_weight is None
    or user_bmr is None
    or user_deficit_target_kcal is None
)

if profile_incomplete:
    _profile_lang = _ui_language()
    _profile_i18n = {
        "Italiano": {
            "warning": "⚠️ Per iniziare, configura i tuoi dati.",
            "title": "📋 Configurazione Profilo",
            "gender": "Genere",
            "male": "Uomo",
            "female": "Donna",
            "birth": "Data di nascita",
            "height": "Altezza (cm)",
            "current_weight": "Peso Attuale (kg)",
            "target_weight": "Peso Obiettivo (kg)",
            "age": "Età",
            "years": "anni",
            "estimated_bmr": "BMR stimato",
            "target_deficit": "Deficit target",
            "save": "Salva e Inizia",
            "saved": "✅ Profilo aggiornato! BMR attuale: {bmr} kcal/giorno.",
            "error": "Errore: {error}",
        },
        "English": {
            "warning": "⚠️ To get started, complete your profile data.",
            "title": "📋 Profile setup",
            "gender": "Gender",
            "male": "Male",
            "female": "Female",
            "birth": "Date of birth",
            "height": "Height (cm)",
            "current_weight": "Current weight (kg)",
            "target_weight": "Target weight (kg)",
            "age": "Age",
            "years": "years",
            "estimated_bmr": "Estimated BMR",
            "target_deficit": "Target deficit",
            "save": "Save and start",
            "saved": "✅ Profile updated! Current BMR: {bmr} kcal/day.",
            "error": "Error: {error}",
        },
        "Nederlands": {
            "warning": "⚠️ Vul je profielgegevens in om te beginnen.",
            "title": "📋 Profiel instellen",
            "gender": "Geslacht",
            "male": "Man",
            "female": "Vrouw",
            "birth": "Geboortedatum",
            "height": "Lengte (cm)",
            "current_weight": "Huidig gewicht (kg)",
            "target_weight": "Streefgewicht (kg)",
            "age": "Leeftijd",
            "years": "jaar",
            "estimated_bmr": "Geschatte BMR",
            "target_deficit": "Doeltekort",
            "save": "Opslaan en starten",
            "saved": "✅ Profiel bijgewerkt! Huidige BMR: {bmr} kcal/dag.",
            "error": "Fout: {error}",
        },
        "Français": {
            "warning": "⚠️ Pour commencer, complétez les données de votre profil.",
            "title": "📋 Configuration du profil",
            "gender": "Sexe",
            "male": "Homme",
            "female": "Femme",
            "birth": "Date de naissance",
            "height": "Taille (cm)",
            "current_weight": "Poids actuel (kg)",
            "target_weight": "Poids cible (kg)",
            "age": "Âge",
            "years": "ans",
            "estimated_bmr": "BMR estimé",
            "target_deficit": "Déficit cible",
            "save": "Enregistrer et commencer",
            "saved": "✅ Profil mis à jour ! BMR actuel : {bmr} kcal/jour.",
            "error": "Erreur : {error}",
        },
    }
    _profile_i18n["Português"] = {
        "warning": "⚠️ Para começar, complete os dados do seu perfil.",
        "title": "📋 Configuração do perfil",
        "gender": "Sexo",
        "male": "Homem",
        "female": "Mulher",
        "birth": "Data de nascimento",
        "height": "Altura (cm)",
        "current_weight": "Peso atual (kg)",
        "target_weight": "Peso objetivo (kg)",
        "age": "Idade",
        "years": "anos",
        "estimated_bmr": "BMR estimado",
        "target_deficit": "Défice objetivo",
        "save": "Guardar e começar",
        "saved": "✅ Perfil atualizado! BMR atual: {bmr} kcal/dia.",
        "error": "Erro: {error}",
    }
    _pi = _profile_i18n.get(_profile_lang, _profile_i18n["Italiano"])
    st.warning(_pi["warning"])

    # Deficit target fuori dal form: il preset aggiorna subito il campo kcal.
    existing_deficit_value = (
        int(round(float(user_deficit_target_kcal)))
        if user_deficit_target_kcal not in (None, "")
        else 0
    )
    existing_deficit_label = (
        normalize_deficit_plan(user_deficit_plan)
        if user_deficit_plan
        else deficit_preset_from_value(existing_deficit_value)
    )

    if "profile_deficit_plan" not in st.session_state:
        st.session_state["profile_deficit_plan"] = existing_deficit_label
    if "profile_deficit_kcal" not in st.session_state:
        st.session_state["profile_deficit_kcal"] = existing_deficit_value

    def _sync_profile_deficit_preset():
        selected = normalize_deficit_plan(
            st.session_state.get("profile_deficit_plan", "custom")
        )
        st.session_state["profile_deficit_kcal"] = int(
            DEFICIT_PRESETS.get(selected, 0)
        )

    deficit_ui = DEFICIT_PRESET_LABELS[_ui_language()]
    st.markdown(f"#### {deficit_ui['title']}")
    deficit_plan_val = st.selectbox(
        deficit_ui["speed"],
        list(DEFICIT_PRESETS.keys()),
        key="profile_deficit_plan",
        format_func=deficit_preset_label,
        on_change=_sync_profile_deficit_preset,
        help=deficit_ui["help"],
    )

    custom_deficit_val = st.number_input(
        deficit_ui["field"],
        min_value=0,
        max_value=2000,
        step=50,
        key="profile_deficit_kcal",
    )

    selected_deficit_target = resolve_deficit_target(
        deficit_plan_val,
        custom_deficit_val,
    )

    # Se l'utente modifica a mano il valore rispetto al preset, salviamo
    # semanticamente il piano come Custom.
    preset_default = int(DEFICIT_PRESETS.get(deficit_plan_val, 0))
    deficit_plan_to_save = (
        deficit_plan_val
        if int(selected_deficit_target) == preset_default
        else "custom"
    )

    with st.form("missing_data_form"):
        st.subheader(_pi["title"])

        gen_index = 0 if user_gender is None else (0 if user_gender == "Uomo" else 1)
        _gender_values = ["Uomo", "Donna"]
        gen = st.selectbox(
            _pi["gender"],
            _gender_values,
            index=gen_index,
            format_func=lambda value: (
                _pi["male"] if value == "Uomo" else _pi["female"]
            ),
        )

        existing_birth_date = parse_birth_date(user_birth_date)
        birth_val = st.date_input(
            _pi["birth"],
            value=existing_birth_date or date(1990, 1, 1),
            min_value=date(1900, 1, 1),
            max_value=date.today(),
        )

        h_val = st.number_input(
            _pi["height"],
            value=float(user_height) if user_height else 175.0,
            min_value=100.0,
            max_value=250.0,
            step=1.0,
        )

        w_val = st.number_input(
            _pi["current_weight"],
            value=float(user_current_weight) if user_current_weight is not None else 80.0,
            min_value=20.0,
            max_value=300.0,
            step=0.5,
        )

        t_val = st.number_input(
            _pi["target_weight"],
            value=float(user_target_weight) if user_target_weight else 75.0,
            min_value=20.0,
            max_value=300.0,
            step=0.5,
        )

        calculated_preview_bmr = calculate_bmr(
            w_val,
            h_val,
            birth_val,
            gen,
        )
        calculated_age = calculate_age(birth_val)

        if calculated_preview_bmr is not None:
            st.caption(
                f"{_pi['age']}: {calculated_age} {_pi['years']} · "
                f"{_pi['estimated_bmr']}: {calculated_preview_bmr} kcal/giorno · "
                f"{_pi['target_deficit']}: {selected_deficit_target} kcal/giorno"
            )

        if st.form_submit_button(_pi["save"]):
            try:
                res = supabase.auth.update_user({
                    "data": {
                        "target_weight": float(t_val),
                        "current_weight": float(w_val),
                        "birth_date": str(birth_val),
                        "height": float(h_val),
                        "gender": gen,
                        "deficit_target_kcal": int(selected_deficit_target),
                        "deficit_plan": deficit_plan_to_save,
                    }
                })

                # Salviamo anche il peso nello storico: da questo momento il BMR
                # seguirà automaticamente l'ultimo peso registrato.
                update_daily_log_via_api(
                    date.today(),
                    {"weight": float(w_val)},
                    st.session_state.get("auth_access_token"),
                )

                if hasattr(res, "user") and res.user:
                    st.session_state["user"] = res.user

                st.success(
                    _pi["saved"].format(bmr=calculated_preview_bmr)
                )
                st.rerun()

            except Exception as e:
                st.error(_pi["error"].format(error=e))
                print(traceback.format_exc())
    st.stop()



# ==============================================================================
# APPEARANCE HINT
# ==============================================================================
# The native Streamlit menu remains available at the top-right, while this
# reminds users which appearance best matches the selected SanoSync personality.
_mode_hint_text = (
    "Better in dark mode" if is_zero_mode() else "Better in light mode"
)
_mode_hint_color = "#F2F2F2" if is_zero_mode() else "#4B5563"

st.markdown(
    f"""
    <style>
    .sanosync-mode-hint {{
        position: fixed;
        top: 3.45rem;
        right: 1.1rem;
        z-index: 999900;
        font-family: 'Kanit', 'Hanken Grotesk', sans-serif;
        font-size: 0.68rem;
        font-weight: 600;
        line-height: 1;
        white-space: nowrap;
        color: {_mode_hint_color};
        opacity: 0.72;
        pointer-events: none;
        padding: 0.24rem 0.42rem;
        border-radius: 999px;
        background: rgba(127,127,127,.08);
        backdrop-filter: blur(6px);
    }}
    @media (max-width: 700px) {{
        .sanosync-mode-hint {{
            top: 3.15rem;
            right: 0.75rem;
            font-size: 0.60rem;
            padding: 0.20rem 0.36rem;
        }}
    }}
    </style>
    <div class="sanosync-mode-hint">{_mode_hint_text}</div>
    """,
    unsafe_allow_html=True,
)


# ==============================================================================
# ZERO MODE — VISUAL THEME
# ==============================================================================
if is_zero_mode():
    st.markdown(
        """
        <style>
        @import url('https://fonts.googleapis.com/css2?family=Great+Vibes&family=Kanit:wght@400;500;600;700;800;900&display=swap');

        :root {
            --zero-bg: #050505;
            --zero-panel: #111111;
            --zero-panel-2: #171717;
            --zero-border: #2A2A2A;
            --zero-red: #E10600;
            --zero-red-hot: #FF1B12;
            --zero-white: #F7F7F5;
            --zero-muted: #A9A9A9;
        }

        html, body, [data-testid="stAppViewContainer"] {
            color: var(--zero-white) !important;
            font-family: 'Kanit', sans-serif !important;
        }

        body,
        [data-testid="stAppViewContainer"],
        [data-testid="stSidebar"],
        p,
        label,
        button,
        input,
        textarea,
        select,
        [data-testid="stMarkdownContainer"],
        [data-testid="stMetricLabel"],
        [data-testid="stMetricValue"] {
            font-family: 'Kanit', sans-serif !important;
        }

        /* Never override Streamlit / Material icon fonts. */
        [class*="material-symbols"],
        [data-testid*="Icon"],
        svg {
            font-family: initial !important;
        }

        .sano-page-title,
        .sano-zero-wordmark {
            font-family:'Great Vibes', cursive !important;
            letter-spacing:0 !important;
        }

        h1, h2, h3, h4 {
            font-family:'Kanit', sans-serif !important;
            letter-spacing:0 !important;
        }

        [data-testid="stAppViewContainer"] {
            background:
                radial-gradient(circle at 100% 0%, rgba(225,6,0,.14), transparent 28%),
                radial-gradient(circle at 0% 65%, rgba(225,6,0,.08), transparent 30%),
                linear-gradient(135deg,#030303 0%,#090909 58%,#050505 100%) !important;
            background-attachment: fixed !important;
        }

        [data-testid="stSidebar"] {
            background:
                radial-gradient(circle at 50% 0%, rgba(225,6,0,.16), transparent 28%),
                linear-gradient(180deg,#000000 0%,#080808 100%) !important;
            border-right: 1px solid rgba(225,6,0,.42) !important;
        }

        [data-testid="stSidebar"] p,
        [data-testid="stSidebar"] span,
        [data-testid="stSidebar"] label,
        [data-testid="stSidebar"] h1,
        [data-testid="stSidebar"] h2,
        [data-testid="stSidebar"] h3 {
            color: var(--zero-white) !important;
            -webkit-text-fill-color: var(--zero-white) !important;
        }

        /* Generic bordered cards */
        [data-testid="stVerticalBlockBorderWrapper"] {
            background:
                radial-gradient(circle at 100% 0%, rgba(225,6,0,.08), transparent 30%),
                linear-gradient(145deg,#121212,#0B0B0B) !important;
            border: 1px solid #2B2B2B !important;
            box-shadow: 0 10px 28px rgba(0,0,0,.28) !important;
        }

        /* Page hero = racing / ZERO identity */
        .sano-page-hero {
            background:
                radial-gradient(circle at 92% 4%, rgba(255,255,255,.11), transparent 30%),
                linear-gradient(135deg,#000000 0%,#121212 58%,#E10600 160%) !important;
            border: 1px solid rgba(225,6,0,.72) !important;
            box-shadow: 0 18px 44px rgba(0,0,0,.34) !important;
        }

        .sano-page-kicker {
            font-family: 'Great Vibes', cursive !important;
            font-size: 1.35rem !important;
            letter-spacing: .02em !important;
            color: #FF2A20 !important;
            text-transform: none !important;
        }

        .sano-page-kicker::after {
            content: " ZERO";
        }

        .sano-page-title {
            font-size: clamp(2.1rem, 4vw, 3rem) !important;
            font-weight: 400 !important;
            line-height: 1 !important;
        }

        .sano-zero-wordmark {
            font-size: 2.05rem !important;
            font-weight: 400 !important;
        }

        /* Inputs */
        [data-baseweb="input"] > div,
        [data-baseweb="select"] > div,
        textarea,
        input {
            background: #171717 !important;
            color: #F7F7F5 !important;
            border-color: #343434 !important;
        }

        input::placeholder,
        textarea::placeholder {
            color: #7F7F7F !important;
            opacity: 1 !important;
        }

        [data-baseweb="select"] *,
        [data-baseweb="input"] * {
            color: #F7F7F5 !important;
        }

        /* Buttons */
        [data-testid="stAppViewContainer"] .stButton > button {
            background: #101010 !important;
            color: #F7F7F5 !important;
            border: 1.7px solid #E10600 !important;
            box-shadow: none !important;
        }

        [data-testid="stAppViewContainer"] .stButton > button *,
        [data-testid="stAppViewContainer"] .stButton > button p,
        [data-testid="stAppViewContainer"] .stButton > button span {
            color: #F7F7F5 !important;
            -webkit-text-fill-color: #F7F7F5 !important;
        }

        [data-testid="stAppViewContainer"] .stButton > button:hover,
        [data-testid="stAppViewContainer"] .stButton > button[kind="primary"] {
            background: linear-gradient(135deg,#E10600,#A90000) !important;
            border-color: #FF1B12 !important;
            color: #FFFFFF !important;
        }

        /* Sidebar navigation */
        [data-testid="stSidebar"] .stButton > button {
            background: #0D0D0D !important;
            border: 1px solid #2E2E2E !important;
            color: #F7F7F5 !important;
        }

        [data-testid="stSidebar"] .stButton > button[kind="primary"],
        [data-testid="stSidebar"] .stButton > button:hover {
            background: linear-gradient(135deg,#E10600,#A80000) !important;
            border-color: #FF1B12 !important;
            color: #FFFFFF !important;
        }

        /* Metrics / budget / coach */
        [data-testid="stMetric"] {
            background:
                radial-gradient(circle at 96% 4%, rgba(225,6,0,.13), transparent 36%),
                linear-gradient(145deg,#151515,#0D0D0D) !important;
            border: 1px solid #3A1515 !important;
        }

        [data-testid="stMetric"] * {
            color: #F7F7F5 !important;
        }

        .sano-budget-card,
        .sano-ai-coach-card {
            background:
                radial-gradient(circle at 96% 4%, rgba(225,6,0,.20), transparent 38%),
                linear-gradient(145deg,#151515,#090909) !important;
            border: 1px solid rgba(225,6,0,.38) !important;
        }

        .sano-budget-fill {
            background: linear-gradient(90deg,#E10600,#FF352B) !important;
        }

        .sano-budget-value span,
        .sano-ai-coach-title {
            color: #FF3027 !important;
            -webkit-text-fill-color: #FF3027 !important;
        }

        /* AI spotlight */
        div[class*="st-key-ai_spotlight_"],
        .st-key-can_i_eat_spotlight {
            background:
                radial-gradient(circle at 96% 8%, rgba(225,6,0,.18), transparent 34%),
                linear-gradient(135deg,#171717,#0B0B0B) !important;
            border-color: #E10600 !important;
            box-shadow: 0 12px 30px rgba(0,0,0,.28) !important;
        }

        /* ZERO wordmark */
        .sano-zero-wordmark {
            font-family:'Great Vibes', cursive;
            color:#FFFFFF !important;
            font-size:1.55rem;
            line-height:1;
            text-align:center;
            margin:.25rem 0 .75rem 0;
            text-shadow:0 2px 16px rgba(225,6,0,.45);
        }
        .sano-zero-wordmark span {
            font-family:'Kanit',sans-serif !important;
            font-weight:950;
            letter-spacing:.14em;
            color:#FF2018 !important;
            font-size:.70rem;
            display:block;
            margin-top:.28rem;
        }

        /* Tables / text */
        h1,h2,h3,h4,h5,h6,p,label,span,div {
            border-color: inherit;
        }

        [data-testid="stDataFrame"],
        [data-testid="stTable"] {
            color:#F7F7F5 !important;
        }

        /* Dividers */
        hr {
            border-color:#4A4A4A !important;
        }

        /* ============================================================
           ZERO MODE — HIGH CONTRAST PASS
           ============================================================ */

        /* Global text: no dark navy/grey leftovers on black. */
        [data-testid="stAppViewContainer"],
        [data-testid="stAppViewContainer"] p,
        [data-testid="stAppViewContainer"] span,
        [data-testid="stAppViewContainer"] label,
        [data-testid="stAppViewContainer"] div,
        [data-testid="stAppViewContainer"] small,
        [data-testid="stAppViewContainer"] li {
            color:#F2F2F2 !important;
            -webkit-text-fill-color:#F2F2F2 !important;
        }

        [data-testid="stAppViewContainer"] [data-testid="stCaptionContainer"],
        [data-testid="stAppViewContainer"] [data-testid="stCaptionContainer"] *,
        [data-testid="stAppViewContainer"] .stCaption,
        [data-testid="stAppViewContainer"] .stCaption * {
            color:#BDBDBD !important;
            -webkit-text-fill-color:#BDBDBD !important;
        }

        /* Streamlit bordered containers/cards: black + red, never white. */
        [data-testid="stVerticalBlockBorderWrapper"],
        [data-testid="stVerticalBlockBorderWrapper"] > div {
            background:
                radial-gradient(circle at 100% 0%, rgba(225,6,0,.15), transparent 34%),
                linear-gradient(145deg,#111111 0%,#080808 100%) !important;
            border-color:#B51A17 !important;
        }

        /* Explicit app cards that were still light. */
        .sano-budget-card,
        .sano-ai-coach-card,
        .sano-profile-card,
        .sano-profile-identity-card,
        div[class*="st-key-profile_identity_card"],
        div[class*="st-key-can_i_eat_spotlight"],
        div[class*="st-key-ai_spotlight_"] {
            background:
                radial-gradient(circle at 96% 4%, rgba(225,6,0,.19), transparent 34%),
                linear-gradient(145deg,#131313,#070707) !important;
            border:1.5px solid #B51A17 !important;
            color:#F7F7F7 !important;
        }

        /* Metric cards: fix the pale cards visible in overview/activity. */
        [data-testid="stMetric"] {
            background:
                radial-gradient(circle at 96% 4%, rgba(225,6,0,.18), transparent 34%),
                linear-gradient(145deg,#151515,#090909) !important;
            border:1.5px solid #C91A16 !important;
            box-shadow:0 10px 24px rgba(0,0,0,.32) !important;
        }

        div[data-testid="stMetric"],
        div[data-testid="stMetric"] > div {
            background:
                radial-gradient(circle at 96% 4%, rgba(225,6,0,.18), transparent 34%),
                linear-gradient(145deg,#151515,#090909) !important;
        }
        [data-testid="stMetric"] label,
        [data-testid="stMetric"] [data-testid="stMetricValue"],
        [data-testid="stMetric"] [data-testid="stMetricDelta"],
        [data-testid="stMetric"] * {
            color:#F7F7F7 !important;
            -webkit-text-fill-color:#F7F7F7 !important;
        }

        /* Inputs/selects: keep value readable. */
        [data-baseweb="input"] > div,
        [data-baseweb="select"] > div,
        [data-baseweb="textarea"] > div,
        input,
        textarea {
            background:#161616 !important;
            border:1.25px solid #C4C4C4 !important;
            color:#F6F6F6 !important;
            caret-color:#FF2A20 !important;
        }
        input,
        textarea,
        [data-baseweb="select"] span {
            color:#F6F6F6 !important;
            -webkit-text-fill-color:#F6F6F6 !important;
        }
        input::placeholder,
        textarea::placeholder {
            color:#929292 !important;
            -webkit-text-fill-color:#929292 !important;
        }

        /* Dropdown arrows / icons */
        [data-baseweb="select"] svg,
        [data-testid="stSelectbox"] svg,
        [data-testid="stNumberInput"] svg {
            fill:#F0F0F0 !important;
            color:#F0F0F0 !important;
        }

        /* Number inputs */
        [data-testid="stNumberInput"] button {
            background:#1D1D1D !important;
            border-color:#555555 !important;
        }

        /* Tables built with st.columns: light dividers and clear headers. */
        div[class*="st-key-"] [data-testid="stHorizontalBlock"] {
            border-color:rgba(220,220,220,.18) !important;
        }

        /* Dataframe/table components, when present */
        [data-testid="stDataFrame"],
        [data-testid="stTable"],
        [data-testid="stDataFrame"] *,
        [data-testid="stTable"] * {
            color:#F4F4F4 !important;
            -webkit-text-fill-color:#F4F4F4 !important;
            border-color:#BDBDBD !important;
        }

        [data-testid="stDataFrame"] {
            border:1px solid #AFAFAF !important;
            border-radius:14px !important;
            overflow:hidden !important;
        }

        /* Expander outlines */
        [data-testid="stExpander"] {
            background:#0C0C0C !important;
            border:1px solid #626262 !important;
            border-radius:14px !important;
        }
        [data-testid="stExpander"],
        details[data-testid="stExpander"] {
            background:#0B0B0B !important;
            border:1px solid #666666 !important;
            border-radius:14px !important;
            overflow:hidden !important;
        }

        [data-testid="stExpander"] summary,
        details[data-testid="stExpander"] > summary {
            background:#111111 !important;
            border-bottom:1px solid #3E3E3E !important;
            color:#F5F5F5 !important;
        }

        [data-testid="stExpander"] summary *,
        details[data-testid="stExpander"] > summary * {
            color:#F5F5F5 !important;
            -webkit-text-fill-color:#F5F5F5 !important;
        }

        [data-testid="stExpander"] summary [class*="material-symbols"],
        details[data-testid="stExpander"] > summary [class*="material-symbols"] {
            font-family:'Material Symbols Rounded','Material Symbols Outlined' !important;
        }

        [data-testid="stExpanderDetails"] {
            background:#0B0B0B !important;
        }

        /* Radio / segmented options */
        [role="radiogroup"] label {
            background:#141414 !important;
            border-color:#5A5A5A !important;
            color:#F5F5F5 !important;
        }
        [role="radiogroup"] label:has(input:checked) {
            background:#6F0705 !important;
            border-color:#FF2A20 !important;
        }

        /* Great Vibes only for the main page/tab hero title. */
        .sano-page-title,
        .sano-zero-wordmark {
            font-family:'Great Vibes', cursive !important;
            font-weight:400 !important;
            color:#FFFFFF !important;
            -webkit-text-fill-color:#FFFFFF !important;
        }

        /* Card and section names in ZERO use Kanit:
           e.g. SanoSync AI · Posso mangiarlo?, Immissione Rapida, etc. */
        h1, h2, h3, h4, h5, h6,
        [data-testid="stVerticalBlockBorderWrapper"] h1,
        [data-testid="stVerticalBlockBorderWrapper"] h2,
        [data-testid="stVerticalBlockBorderWrapper"] h3,
        [data-testid="stVerticalBlockBorderWrapper"] h4,
        [data-testid="stExpander"] h1,
        [data-testid="stExpander"] h2,
        [data-testid="stExpander"] h3,
        .sano-ai-coach-title,
        .custom-card-title,
        .sano-budget-title,
        .sano-profile-name {
            font-family:'Kanit', sans-serif !important;
            font-weight:800 !important;
            letter-spacing:0 !important;
            color:#FFFFFF !important;
            -webkit-text-fill-color:#FFFFFF !important;
        }

        h4, h5, h6,
        p, label,
        button, input, textarea, select {
            font-family:'Kanit', sans-serif !important;
        }

        /* Hero typography */
        .sano-page-title {
            font-size:clamp(2.45rem,4.8vw,3.65rem) !important;
            line-height:1.03 !important;
        }
        .sano-page-kicker {
            font-family:'Kanit', sans-serif !important;
            font-size:.78rem !important;
            font-weight:900 !important;
            letter-spacing:.18em !important;
            color:#FF332A !important;
            -webkit-text-fill-color:#FF332A !important;
        }

        /* Sidebar slogan: remove coral / pink. */
        [data-testid="stSidebar"] .sano-sidebar-subtitle,
        [data-testid="stSidebar"] .sidebar-subtitle,
        [data-testid="stSidebar"] .subtitle,
        [data-testid="stSidebar"] p {
            color:#E6E6E6 !important;
            -webkit-text-fill-color:#E6E6E6 !important;
        }

        /* Known exact slogan text is rendered in markdown in this app;
           this catches the centered small copy under the logo. */
        [data-testid="stSidebar"] [data-testid="stMarkdownContainer"] p {
            color:#E6E6E6 !important;
            -webkit-text-fill-color:#E6E6E6 !important;
        }

        /* Primary actions = red / white */
        [data-testid="stAppViewContainer"] .stButton > button[kind="primary"],
        [data-testid="stFormSubmitButton"] > button {
            background:linear-gradient(135deg,#E10600,#9F0000) !important;
            color:#FFFFFF !important;
            border:1.5px solid #FF2A20 !important;
        }

        /* Plotly surrounding area */
        [data-testid="stPlotlyChart"] {
            background:#080808 !important;
            border:1px solid #3B3B3B !important;
            border-radius:16px !important;
        }

        /* Alerts follow ZERO palette instead of blue/green light fills. */
        [data-testid="stAlert"] {
            background:#101010 !important;
            border:1px solid #626262 !important;
            color:#F5F5F5 !important;
        }
        [data-testid="stAlert"] * {
            color:#F5F5F5 !important;
            -webkit-text-fill-color:#F5F5F5 !important;
        }

        /* Links */
        a {
            color:#FF4A42 !important;
        }

        /* ============================================================
           ZERO MODE — FINAL WIDGET FIXES
           ============================================================ */

        /* Date input: Streamlit/BaseWeb can keep a pale inner control. */
        [data-testid="stDateInput"] > div,
        [data-testid="stDateInput"] [data-baseweb="input"],
        [data-testid="stDateInput"] [data-baseweb="input"] > div,
        [data-testid="stDateInput"] input {
            background:#171717 !important;
            color:#F7F7F7 !important;
            -webkit-text-fill-color:#F7F7F7 !important;
            border-color:#727272 !important;
        }
        [data-testid="stDateInput"] input::selection {
            background:#7C1714 !important;
            color:#FFFFFF !important;
        }

        /* Selectboxes: remove the pale arrow segment on the right. */
        [data-testid="stSelectbox"] [data-baseweb="select"] > div,
        [data-testid="stSelectbox"] [data-baseweb="select"] > div > div,
        [data-testid="stSelectbox"] [data-baseweb="select"] {
            background:#171717 !important;
            color:#F7F7F7 !important;
            border-color:#727272 !important;
        }

        [data-testid="stSelectbox"] [data-baseweb="select"] > div > div:last-child {
            background:#171717 !important;
            color:#F7F7F7 !important;
            border-left:1px solid #3F3F3F !important;
        }

        [data-testid="stSelectbox"] svg,
        [data-testid="stSelectbox"] path {
            color:#F7F7F7 !important;
            fill:#F7F7F7 !important;
        }


        /* ZERO MODE — force dropdown chevrons visible */
        [data-testid="stSelectbox"] [data-baseweb="select"] svg,
        [data-testid="stSelectbox"] [data-baseweb="select"] path,
        [data-testid="stMultiSelect"] [data-baseweb="select"] svg,
        [data-testid="stMultiSelect"] [data-baseweb="select"] path,
        [data-baseweb="select"] svg,
        [data-baseweb="select"] path {
            color:#FFFFFF !important;
            fill:#FFFFFF !important;
            stroke:#FFFFFF !important;
            opacity:1 !important;
        }

        [data-testid="stSelectbox"] [data-baseweb="select"] > div > div:last-child,
        [data-testid="stMultiSelect"] [data-baseweb="select"] > div > div:last-child {
            background:#171717 !important;
            color:#FFFFFF !important;
            border-left:1px solid #3F3F3F !important;
        }

        [data-testid="stSelectbox"] [data-baseweb="select"] > div > div:last-child *,
        [data-testid="stMultiSelect"] [data-baseweb="select"] > div > div:last-child * {
            color:#FFFFFF !important;
            -webkit-text-fill-color:#FFFFFF !important;
        }

        /* Same treatment for multiselects. */
        [data-testid="stMultiSelect"] [data-baseweb="select"] > div,
        [data-testid="stMultiSelect"] [data-baseweb="select"] > div > div,
        [data-testid="stMultiSelect"] [data-baseweb="select"] {
            background:#171717 !important;
            color:#F7F7F7 !important;
            border-color:#727272 !important;
        }

        /* Buttons that still expose Material icon ligature text such as
           "arrow_right" / "keyboard_double_arrow_right".
           Restore the correct icon font only on known icon spans. */
        [class*="material-symbols-rounded"],
        [class*="material-symbols-outlined"],
        [class*="material-icons"],
        span[data-testid*="Icon"] {
            font-family:
                'Material Symbols Rounded',
                'Material Symbols Outlined',
                'Material Icons' !important;
            font-style:normal !important;
            font-weight:normal !important;
            letter-spacing:normal !important;
            text-transform:none !important;
            white-space:nowrap !important;
            word-wrap:normal !important;
            direction:ltr !important;
            -webkit-font-feature-settings:'liga' !important;
            -webkit-font-smoothing:antialiased !important;
            font-feature-settings:'liga' !important;
        }

        /* Streamlit sidebar collapse control / generic header buttons. */
        [data-testid="stSidebarCollapseButton"] button,
        [data-testid="collapsedControl"] button,
        [data-testid="stHeader"] button {
            font-family:inherit !important;
        }
        [data-testid="stSidebarCollapseButton"] button span,
        [data-testid="collapsedControl"] button span,
        [data-testid="stHeader"] button span {
            font-family:
                'Material Symbols Rounded',
                'Material Symbols Outlined',
                'Material Icons' !important;
            font-feature-settings:'liga' !important;
            -webkit-font-feature-settings:'liga' !important;
        }

        /* Popover / menu icon buttons should be dark, not white cards. */
        [data-testid="stPopover"] > div > button,
        [data-testid="stPopover"] button {
            background:#111111 !important;
            color:#F7F7F7 !important;
            border:1px solid #5B5B5B !important;
        }

        /* Any residual BaseWeb control chrome. */
        [data-baseweb="base-input"],
        [data-baseweb="select"] {
            background:#171717 !important;
        }

        /* Date controls: remove the last white-on-white native styling. */
        [data-testid="stDateInput"] > div,
        [data-testid="stDateInput"] [data-baseweb="input"],
        [data-testid="stDateInput"] [data-baseweb="input"] > div,
        [data-testid="stDateInput"] input,
        input[type="date"] {
            background:#171717 !important;
            background-color:#171717 !important;
            color:#FFFFFF !important;
            -webkit-text-fill-color:#FFFFFF !important;
            border-color:#737373 !important;
            caret-color:#FFFFFF !important;
        }
        [data-testid="stDateInput"] input::-webkit-datetime-edit,
        [data-testid="stDateInput"] input::-webkit-datetime-edit-fields-wrapper,
        [data-testid="stDateInput"] input::-webkit-datetime-edit-text,
        [data-testid="stDateInput"] input::-webkit-datetime-edit-month-field,
        [data-testid="stDateInput"] input::-webkit-datetime-edit-day-field,
        [data-testid="stDateInput"] input::-webkit-datetime-edit-year-field {
            color:#FFFFFF !important;
            -webkit-text-fill-color:#FFFFFF !important;
            background:transparent !important;
        }
        [data-testid="stDateInput"] input::-webkit-calendar-picker-indicator {
            filter:invert(1) brightness(1.8) !important;
            opacity:.9 !important;
        }

        @media (max-width:700px) {
            .sano-page-title {
                font-size:2.55rem !important;
            }
        }
        </style>
        """,
        unsafe_allow_html=True,
    )

# Force the logged-in welcome label to stay white on the dark sidebar.
st.markdown(
    """
    <style>
    section[data-testid="stSidebar"] .sanosync-welcome,
    section[data-testid="stSidebar"] .sanosync-welcome *,
    [data-testid="stSidebar"] .sanosync-welcome,
    [data-testid="stSidebar"] .sanosync-welcome * {
        color: #FFFFFF !important;
        -webkit-text-fill-color: #FFFFFF !important;
        opacity: 1 !important;
    }

    section[data-testid="stSidebar"] .sanosync-welcome {
        font-size: 1.15rem !important;
        font-weight: 800 !important;
        line-height: 1.25 !important;
        margin: 0 !important;
        padding: 0 !important;
    }
    </style>
    """,
    unsafe_allow_html=True,
)

# ==============================================================================
# LOGGED-IN ACCOUNT — COMPACT
# ==============================================================================
with st.sidebar:
    first_name = (logged_name or "Utente").strip().split()[0]

    _profile_menu_i18n = {
        "Italiano": {
            "menu": "👤",
            "settings": "👤 Profilo",
            "language": "🌐 Lingua",
            "logout": "🚪 Esci",
        },
        "English": {
            "menu": "👤",
            "settings": "👤 Profile",
            "language": "🌐 Language",
            "logout": "🚪 Log out",
        },
        "Nederlands": {
            "menu": "👤",
            "settings": "👤 Profiel",
            "language": "🌐 Taal",
            "logout": "🚪 Uitloggen",
        },
        "Français": {
            "menu": "👤",
            "settings": "👤 Profil",
            "language": "🌐 Langue",
            "logout": "🚪 Se déconnecter",
        },
    }

    _profile_menu_i18n["Português"] = {
        "menu": "👤",
        "settings": "👤 Perfil",
        "language": "🌐 Idioma",
        "logout": "🚪 Sair",
    }

    _menu_lang = st.session_state.get("lang_selector", "Italiano")
    _pm = _profile_menu_i18n.get(
        _menu_lang,
        _profile_menu_i18n["Italiano"],
    )

    # --------------------------------------------------------------
    # PROFILO + LINGUA — controlli diretti, niente pannello unico.
    # --------------------------------------------------------------
    _language_options = [
        "Italiano",
        "English",
        "Nederlands",
        "Français",
        "Português",
    ]
    _language_flags = {
        "Italiano": "🇮🇹",
        "English": "🇬🇧",
        "Nederlands": "🇳🇱",
        "Français": "🇫🇷",
        "Português": "🇵🇹",
    }

    _current_menu_lang = st.session_state.get(
        "lang_selector",
        "Italiano",
    )
    if _current_menu_lang not in _language_options:
        _current_menu_lang = "Italiano"

    st.markdown(
        """
        <style>
        /* Direct profile + language controls */
        .st-key-profile_direct_button,
        .st-key-language_flag_popover {
            overflow:visible !important;
        }

        .st-key-profile_direct_button {
            margin-left:12px !important;
        }

        .st-key-language_flag_popover {
            margin-left:8px !important;
        }

        .st-key-profile_direct_button button,
        .st-key-language_flag_popover button {
            width:46px !important;
            min-width:46px !important;
            height:46px !important;
            min-height:46px !important;
            padding:0 !important;
            border-radius:14px !important;
            font-size:1.16rem !important;
            font-weight:900 !important;
            box-shadow:none !important;
        }

        /* Standard mode */
        .st-key-profile_direct_button button,
        .st-key-language_flag_popover button {
            background:linear-gradient(145deg,#FFFFFF,#FFF5F5) !important;
            border:1.5px solid rgba(255,139,139,.78) !important;
            color:#192E49 !important;
        }

        .st-key-profile_direct_button button:hover,
        .st-key-language_flag_popover button:hover {
            background:#FFEDED !important;
            border-color:#FF6F6F !important;
        }

        /* Language-only popover */
        div[data-testid="stPopoverBody"]:has(.st-key-language_picker_select) {
            border:1px solid #FFD0D0 !important;
            border-radius:16px !important;
            background:linear-gradient(145deg,#FFFFFF,#FFF7F7) !important;
            box-shadow:0 14px 34px rgba(23,42,70,.14) !important;
            padding:.75rem !important;
            min-width:230px !important;
        }

        .st-key-language_picker_select div[data-baseweb="select"] > div {
            border-radius:10px !important;
        }

        /* ZERO mode */
        body:has(.st-key-zero_mode_sidebar_toggle input:checked)
        .st-key-profile_direct_button button,
        body:has(.st-key-zero_mode_sidebar_toggle input:checked)
        .st-key-language_flag_popover button {
            background:#101010 !important;
            border:1.5px solid #B91C1C !important;
            color:#F7F7F7 !important;
        }

        body:has(.st-key-zero_mode_sidebar_toggle input:checked)
        .st-key-profile_direct_button button:hover,
        body:has(.st-key-zero_mode_sidebar_toggle input:checked)
        .st-key-language_flag_popover button:hover {
            background:#1A0909 !important;
            border-color:#FF2A20 !important;
        }

        body:has(.st-key-zero_mode_sidebar_toggle input:checked)
        div[data-testid="stPopoverBody"]:has(.st-key-language_picker_select) {
            background:
                radial-gradient(circle at 100% 0%,rgba(140,12,12,.20),transparent 42%),
                linear-gradient(145deg,#111111,#070707) !important;
            border:1px solid #B91C1C !important;
            box-shadow:0 16px 38px rgba(0,0,0,.52) !important;
        }

        body:has(.st-key-zero_mode_sidebar_toggle input:checked)
        div[data-testid="stPopoverBody"]:has(.st-key-language_picker_select) * {
            color:#F5F5F5 !important;
            -webkit-text-fill-color:#F5F5F5 !important;
        }

        body:has(.st-key-zero_mode_sidebar_toggle input:checked)
        .st-key-language_picker_select div[data-baseweb="select"] > div {
            background:#171717 !important;
            border-color:#666 !important;
            color:#F5F5F5 !important;
        }
        </style>
        """,
        unsafe_allow_html=True,
    )

    _profile_col, _profile_gap, _language_col, _account_spacer = st.columns(
        [0.82, 0.34, 0.82, 3.35],
        gap="small",
        vertical_alignment="center",
    )

    with _profile_col:
        if st.button(
            "👤",
            key="profile_direct_button",
            help=_pm["settings"],
            use_container_width=True,
        ):
            st.session_state.pop("settings_language_live", None)
            st.session_state["settings_language_live"] = (
                st.session_state.get("lang_selector", "Italiano")
            )
            st.session_state["show_personal_settings"] = True
            st.rerun()

    with _language_col:
        with st.popover(
            _language_flags.get(_current_menu_lang, "🌐"),
            key="language_flag_popover",
            help=_pm["language"],
        ):
            _new_menu_lang = st.selectbox(
                _pm["language"],
                _language_options,
                index=_language_options.index(_current_menu_lang),
                key="language_picker_select",
                format_func=format_language_option,
                label_visibility="collapsed",
            )

            if _new_menu_lang != st.session_state.get("lang_selector"):
                st.session_state["lang_selector"] = _new_menu_lang
                st.session_state["login_lang_selector"] = _new_menu_lang

                if st.session_state.get("show_personal_settings", False):
                    st.session_state["settings_language_live"] = _new_menu_lang

                st.rerun()

    # --------------------------------------------------------------
    # FOTO + SALUTO
    # --------------------------------------------------------------
    account_left, account_right = st.columns(
        [1, 3],
        vertical_alignment="center",
    )

    with account_left:
        if logged_avatar:
            st.image(logged_avatar, width=58)
        else:
            st.markdown(
                """
                <div style="
                    width:54px;height:54px;border-radius:14px;
                    display:flex;align-items:center;justify-content:center;
                    background:#FF8B8B;color:white;font-size:1.5rem;
                    font-weight:900;border:2px solid white;
                ">✓</div>
                """,
                unsafe_allow_html=True,
            )

    with account_right:
        _lang = st.session_state.get("lang_selector", "Italiano")
        _hour = datetime.now().hour

        if 5 <= _hour < 12:
            _period = "morning"
        elif 12 <= _hour < 18:
            _period = "afternoon"
        else:
            _period = "evening"

        _greetings = {
            "Italiano": {
                "morning": "Buongiorno {name}!",
                "afternoon": "Buon pomeriggio {name}!",
                "evening": "Buonasera {name}!",
            },
            "English": {
                "morning": "Good morning {name}!",
                "afternoon": "Good afternoon {name}!",
                "evening": "Good evening {name}!",
            },
            "Nederlands": {
                "morning": "Goedemorgen {name}!",
                "afternoon": "Goedemiddag {name}!",
                "evening": "Goedenavond {name}!",
            },
            "Français": {
                "morning": "Bonjour {name}!",
                "afternoon": "Bon après-midi {name}!",
                "evening": "Bonsoir {name}!",
            },
        }

        _greetings["Português"] = {
            "morning": "Bom dia, {name}!",
            "afternoon": "Boa tarde, {name}!",
            "evening": "Boa noite, {name}!",
        }

        _welcome = _greetings.get(
            _lang,
            _greetings["Italiano"],
        )[_period].format(name=first_name)

        st.markdown(
            f'<div class="sanosync-welcome">{html.escape(_welcome)}</div>',
            unsafe_allow_html=True,
        )

    st.markdown("---")


# ==============================================================================
# 8. NAVIGATION & LANGUAGE
# ==============================================================================
translations = {
    "Italiano": {
        "t1": "🚀 Inserimento", 
        "t2": "📊 Panoramica", 
        "t3": "📈 Peso", 
        "t4": "🍳 Ricette", 
        "t5": "🏃 Attività",  
        "meal": "Tipo di pasto", 
        "meal_name": "Nome pasto", 
        "add_meal": "Aggiungi pasto", 
        "extra_act": "Attività extra", 
        "extra_cals": "Calorie bruciate extra", 
        "insert_weight": "Inserisci peso (kg)", 
        "save_weight": "Salva peso", 
        "recipe_name": "Nome ricetta", 
        "save_recipe": "Salva ricetta", 
        "recipe_saved": "✅ Ricetta salvata!",
        "lang_label": "🌐 Lingua",
        "logout": "🚪 Logout",
        "search_food": "🔍 Cerca per Nome o Codice a Barre",
        "search_btn": "🚀 Cerca",
        "select_db": "Seleziona dal database",
        "select_recipe": "Seleziona una ricetta",
        "no_recipes": "Nessuna ricetta salvata.",
        "calc_mode": "Inserimento basato su:",
        "per_100g": "Per 100g",
        "per_portion": "Per Porzione",
        "qty_label": "Quantità (g o Porzioni)",
        "num_portions": "Numero di porzioni",
        "kcal": "Kcal",
        "pro": "Pro (g)",
        "carbs": "Carbs (g)",
        "fat": "Fat (g)",
        "inserted": "✅ Inserito",
        "daily_summary": "📊 Riepilogo Giornaliero",
        "summary_date": "📅 Data riepilogo",
        "logged_foods": "🍽️ Cibi inseriti",
        "del_meal": "Seleziona un pasto da eliminare",
        "del_meal_btn": "🗑️ Elimina Pasto Selezionato",
        "meal_del_success": "Pasto eliminato con successo!",
        "no_meals": "Nessun pasto registrato per questa data.",
        "burned_acts": "#### 🏃 Calorie Bruciate & Attività",
        "weight_tracking": "⚖️ Tracciamento Peso",
        "log_today_weight": "📥 Registra Peso Oggi",
        "update_target": "🎯 Aggiorna Obiettivo",
        "save_target": "Salva Obiettivo",
        "target_updated": "✅ Obiettivo aggiornato!",
        "quick_entries": "⚡ Immissioni Rapide",
        "saved_entries": "📋 Entries salvate",
        "del_quick": "🗑️ Elimina Immissione Rapida",
        "select_quick_del": "Seleziona Immissione Rapida da rimuovere",
        "del_quick_btn": "Elimina Immissione Rapida",
        "quick_add_title": "➕ Aggiungi Nuova Immissione Rapida",
        "calc_mode_radio": "Modalità di calcolo",
        "caption_calc": "ℹ️ *Se scegli 'Per 100g', inserisci i valori riferiti a 100g. Se scegli 'Porzione', inserisci i valori totali della singola porzione.*",
        "register_activity": "🏃 Registra Attività & Movimento",
        "act_date": "📅 Data",
        "steps_title": "👣 Passi (Totali)",
        "update_steps": "💾 Aggiorna Passi",
        "steps_updated": "Passi aggiornati!",
        "bike_title": "🚲 Bici (Sessione)",
        "bike_min": "Minuti Bici",
        "add_bike": "💾 Aggiungi Bici",
        "other_act": "🏋️ Altro",
        "activity_label": "Attività",
        "add_act_btn": "💾 Aggiungi",
        "tab1_title": "🍽️ Inserimento Cibo & Pasti",
        "input_source_lbl": "Fonte inserimento",
        "opt_ai": "✨ AI",
        "opt_off": "🔍 OpenFood Database",
        "opt_quick": "🍳 Immissione Rapida","quick_select_used":"Seleziona alimento o ricetta","quick_empty":"Nessun alimento ancora disponibile. Registra prima un pasto.","quick_load_error":"Errore nel caricamento delle immissioni rapide: {error}",
        "opt_scan": "📸 Foto AI",
        "scan_title": "📸 Foto AI",
        "scan_mode": "Sorgente immagine",
        "scan_camera": "📷 Fotocamera",
        "scan_upload": "🖼️ Galleria / File",
        "scan_camera_help": "Scatta una foto del piatto. SanoSync proverà ad aprire direttamente la fotocamera posteriore; usa 🔄 per cambiarla se necessario.",
        "scan_upload_help": "In alternativa puoi scegliere una foto già presente sul dispositivo.",
        "scan_photo_ready": "✅ Foto acquisita. La fotocamera funziona correttamente.",
        "scan_ai_next": "La foto è pronta per l’analisi.", "scan_analyze":"✨ Analizza con AI", "scan_analyzing":"Sto analizzando il pasto…", "scan_ai_done":"✅ Analisi completata. Controlla e correggi i valori qui sotto prima di salvare.", "scan_ai_error":"Impossibile analizzare la foto: {error}",
        "card_kcal_in": "Kcal Ingerite",
        "card_kcal_burn": "Kcal Bruciate",
        "card_balance": "Bilancio",
        "card_weight": "Peso",
        "in_msg_low": lambda p: f"⚠️ Proiezione bassa ({p} kcal previste). Mangia di più!",
        "in_msg_high": lambda p: f"✅ Ottima proiezione ({p} kcal stimate a fine giornata).",
        "burn_msg_yes": lambda e: f"🌟 Ottimo lavoro! Hai fatto attività extra (+{e} kcal).",
        "burn_msg_no": "💡 Nessuna attività extra registrata. Che ne dici di muoverti un po'?",
        "bilancio_ok": "🎯 Ottimo, sei in perfetto deficit calorico.",
        "bilancio_bad": "⚠️ Attenzione: sei in surplus calorico.",
        "weight_msg_default": "📈 Continua così per raggiungere il target.",
        "weight_msg_val": lambda i, d_ini, t, d_tgt: f"Iniziale: {i} kg ({d_ini:+.1f}) | Target: {t} kg ({d_tgt:+.1f})",
        "status_move_title": "👣 Status Movimento",
        "status_very_active": "🌟 Ottimo! Giornata molto attiva.",
        "status_good": "🚶 Buona attività, continua così.",
        "status_lazy": "🛋️ Giornata pigra, prova a muoverti di più.",
        "in_msg_deficit": lambda target_in, diff: f"🎯 Per il deficit ideale di 500 kcal (target {target_in} kcal), {'mancano' if diff >= 0 else 'hai sforato di'} {abs(diff)} kcal.",
        "balance_days": lambda d: f"⏳ Al ritmo attuale, stimati circa {d} giorni per raggiungere il target.",
        "balance_surplus": "⚠️ In surplus: impossibile stimare i giorni al target.",
        "weight_forecast_title": "🔮 Previsione Raggiungimento Obiettivo",
        "forecast_days": lambda d, date_str: f"🎯 Al ritmo attuale ({d} giorni stimati), potresti raggiungere il tuo obiettivo intorno al **{date_str}**!",
        "forecast_steady": "📉 Mantenendo questo trend costante, il traguardo si avvicina.",
        "forecast_flat_up": "💡 Il trend attuale è stabile o in salita: la proiezione temporale si attiva solo con un trend di perdita attivo.",
    },
    "English": {
        "t1": "🚀 Logging", 
        "t2": "📊 Overview", 
        "t3": "📈 Weight", 
        "t4": "🍳 Recipes", 
        "t5": "🏃 Activity",  
        "meal": "Meal type", 
        "meal_name": "Meal name", 
        "add_meal": "Add meal", 
        "extra_act": "Extra activity", 
        "extra_cals": "Extra calories burned", 
        "insert_weight": "Enter weight (kg)", 
        "save_weight": "Save weight", 
        "recipe_name": "Recipe name", 
        "save_recipe": "Save recipe", 
        "recipe_saved": "✅ Recipe saved!",
        "lang_label": "🌐 Language",
        "logout": "🚪 Logout",
        "search_food": "🔍 Search by Name or Barcode",
        "search_btn": "🚀 Search",
        "select_db": "Select from database",
        "select_recipe": "Select a recipe",
        "no_recipes": "No recipes saved.",
        "calc_mode": "Entry based on:",
        "per_100g": "Per 100g",
        "per_portion": "Per Portion",
        "qty_label": "Quantity (g or Portions)",
        "num_portions": "Number of portions",
        "kcal": "Kcal",
        "pro": "Pro (g)",
        "carbs": "Carbs (g)",
        "fat": "Fat (g)",
        "inserted": "✅ Inserted",
        "daily_summary": "📊 Daily Overview",
        "summary_date": "📅 Summary date",
        "logged_foods": "🍽️ Logged Foods",
        "del_meal": "Select a meal to delete",
        "del_meal_btn": "🗑️ Delete Selected Meal",
        "meal_del_success": "Meal deleted successfully!",
        "no_meals": "No meals recorded for this date.",
        "burned_acts": "#### 🏃 Burned Calories & Activities",
        "weight_tracking": "⚖️ Weight Tracking",
        "log_today_weight": "📥 Log Today's Weight",
        "update_target": "🎯 Update Target",
        "save_target": "Save Target",
        "target_updated": "✅ Target updated!",
        "quick_entries": "⚡ Quick Entries",
        "saved_entries": "📋 Saved Entries",
        "del_quick": "🗑️ Delete Quick Entry",
        "select_quick_del": "Select Quick Entry to remove",
        "del_quick_btn": "Delete Quick Entry",
        "quick_add_title": "➕ Add New Quick Entry",
        "calc_mode_radio": "Calculation Mode",
        "caption_calc": "ℹ️ *If you choose 'Per 100g', enter values relative to 100g. If you choose 'Portion', enter total values for a single portion.*",
        "register_activity": "🏃 Register Activity & Movement",
        "act_date": "📅 Date",
        "steps_title": "👣 Steps (Total)",
        "update_steps": "💾 Update Steps",
        "steps_updated": "Steps updated!",
        "bike_title": "🚲 Bike (Session)",
        "bike_min": "Bike Minutes",
        "add_bike": "💾 Add Bike",
        "other_act": "🏋️ Other",
        "activity_label": "Activity",
        "add_act_btn": "💾 Add",
        "tab1_title": "🍽️ Food & Meal Logging",
        "input_source_lbl": "Input source",
        "opt_ai": "✨ AI",
        "opt_off": "🔍 OpenFood Database",
        "opt_quick": "🍳 Quick Entry","quick_select_used":"Select a food or recipe","quick_empty":"No foods available yet. Log a meal first.","quick_load_error":"Error loading quick entries: {error}",
        "opt_scan": "📸 AI Photo",
        "scan_title": "📸 AI Photo",
        "scan_mode": "Image source",
        "scan_camera": "📷 Camera",
        "scan_upload": "🖼️ Gallery / File",
        "scan_camera_help": "Take a photo of the meal. SanoSync will try to open the rear camera first; use 🔄 to switch if needed.",
        "scan_upload_help": "Alternatively, choose an existing photo from your device.",
        "scan_photo_ready": "✅ Photo captured. The camera is working correctly.",
        "scan_ai_next": "The photo is ready for analysis.", "scan_analyze":"✨ Analyze with AI", "scan_analyzing":"Analyzing your meal…", "scan_ai_done":"✅ Analysis complete. Review and edit the values below before saving.", "scan_ai_error":"Could not analyze the photo: {error}",
        "card_kcal_in": "Calories In",
        "card_kcal_burn": "Calories Burned",
        "card_balance": "Balance",
        "card_weight": "Weight",
        "in_msg_low": lambda p: f"⚠️ Low projection ({p} kcal expected). Eat more!",
        "in_msg_high": lambda p: f"✅ Great projection ({p} kcal estimated by end of day).",
        "burn_msg_yes": lambda e: f"🌟 Great job! You did extra activity (+{e} kcal).",
        "burn_msg_no": "💡 No extra activity recorded. How about moving a bit?",
        "bilancio_ok": "🎯 Great, you are in a perfect caloric deficit.",
        "bilancio_bad": "⚠️ Warning: you are in a caloric surplus.",
        "weight_msg_default": "📈 Keep it up to reach your target.",
        "weight_msg_val": lambda i, d_ini, t, d_tgt: f"Initial: {i} kg ({d_ini:+.1f}) | Target: {t} kg ({d_tgt:+.1f})",
        "status_move_title": "👣 Movement Status",
        "status_very_active": "🌟 Great! Very active day.",
        "status_good": "🚶 Good activity, keep it up.",
        "status_lazy": "🛋️ Lazy day, try to move more.",
        "in_msg_deficit": lambda target_in, diff: f"🎯 For an ideal 500 kcal deficit (target {target_in} kcal), {'left' if diff >= 0 else 'exceeded by'} {abs(diff)} kcal.",
        "balance_days": lambda d: f"⏳ At the current pace, about {d} days estimated to reach target.",
        "balance_surplus": "⚠️ In surplus: cannot estimate days to target.",
        "weight_forecast_title": "🔮 Goal Achievement Forecast",
        "forecast_days": lambda d, date_str: f"🎯 At your current pace ({d} estimated days), you could reach your goal around **{date_str}**!",
        "forecast_steady": "📉 Maintaining this steady trend, your milestone is getting closer.",
        "forecast_flat_up": "💡 Current trend is flat or increasing: the timeline projection activates only with an active weight-loss trend.",
    },
    "Nederlands": {
        "t1": "🚀 Invoer", 
        "t2": "📊 Overzicht", 
        "t3": "📈 Gewicht", 
        "t4": "🍳 Recepten", 
        "t5": "🏃 Activiteit",  
        "meal": "Maaltijdtype", 
        "meal_name": "Maaltijdnaam", 
        "add_meal": "Maaltijd toevoegen", 
        "extra_act": "Extra activiteit", 
        "extra_cals": "Extra verbrande calorieën", 
        "insert_weight": "Voer gewicht in (kg)", 
        "save_weight": "Gewicht opslaan", 
        "recipe_name": "Receptnaam", 
        "save_recipe": "Recept opslaan", 
        "recipe_saved": "✅ Recept opgeslagen!",
        "lang_label": "🌐 Taal",
        "logout": "🚪 Uitloggen",
        "search_food": "🔍 Zoek op naam of streepjescode",
        "search_btn": "🚀 Zoeken",
        "select_db": "Selecteer uit database",
        "select_recipe": "Selecteer een recept",
        "no_recipes": "Geen recepten opgeslagen.",
        "calc_mode": "Invoer gebaseerd op:",
        "per_100g": "Per 100g",
        "per_portion": "Per Portie",
        "qty_label": "Hoeveelheid (g of Porties)",
        "num_portions": "Aantal porties",
        "kcal": "Kcal",
        "pro": "Pro (g)",
        "carbs": "Koolh (g)",
        "fat": "Vet (g)",
        "inserted": "✅ Ingevoerd",
        "daily_summary": "📊 Dagelijks Overzicht",
        "summary_date": "📅 Overichtsdatum",
        "logged_foods": "🍽️ Ingelogde Voeding",
        "del_meal": "Selecteer een maaltijd om te verwijderen",
        "del_meal_btn": "🗑️ Geselecteerde Maaltijd Verwijderen",
        "meal_del_success": "Maaltijd succesvol verwijderd!",
        "no_meals": "Geen maaltijden geregistreerd voor deze datum.",
        "burned_acts": "#### 🏃 Verbrande Calorieën & Activiteiten",
        "weight_tracking": "⚖️ Gewicht Volgen",
        "log_today_weight": "📥 Vandaag Gewicht Registreren",
        "update_target": "🎯 Doel Bijwerken",
        "save_target": "Doel Opslaan",
        "target_updated": "✅ Doel bijgewerkt!",
        "quick_entries": "⚡ Snelle Invoer",
        "saved_entries": "📋 Opgeslagen Items",
        "del_quick": "🗑️ Snelle Invoer Verwijderen",
        "select_quick_del": "Selecteer te verwijderen snelle invoer",
        "del_quick_btn": "Snelle Invoer Verwijderen",
        "quick_add_title": "➕ Nieuwe Snelle Invoer Toevoegen",
        "calc_mode_radio": "Berekeningsmodus",
        "caption_calc": "ℹ️ *Als je kiest voor 'Per 100g', vul dan de waarden per 100g in. Als je kiest voor 'Portie', vul dan de totale waarden voor een enkele portie in.*",
        "register_activity": "🏃 Registreer Activiteit & Beweging",
        "act_date": "📅 Datum",
        "steps_title": "👣 Stappen (Totaal)",
        "update_steps": "💾 Stappen Bijwerken",
        "steps_updated": "Stappen bijgewerkt!",
        "bike_title": "🚲 Fietsen (Sessie)",
        "bike_min": "Fietsminuten",
        "add_bike": "💾 Fietsen Toevoegen",
        "other_act": "🏋️ Overig",
        "activity_label": "Activiteit",
        "add_act_btn": "💾 Toevoegen",
        "tab1_title": "🍽️ Voeding & Maaltijden Invoeren",
        "input_source_lbl": "Invoerbron",
        "opt_ai": "✨ AI",
        "opt_off": "🔍 OpenFood Database",
        "opt_quick": "🍳 Snelle Invoer","quick_select_used":"Selecteer een voedingsmiddel of recept","quick_empty":"Nog geen voedingsmiddelen beschikbaar. Registreer eerst een maaltijd.","quick_load_error":"Fout bij het laden van snelle invoer: {error}",
        "opt_scan": "📸 AI-foto",
        "scan_title": "📸 AI-foto",
        "scan_mode": "Afbeeldingsbron",
        "scan_camera": "📷 Camera",
        "scan_upload": "🖼️ Galerij / Bestand",
        "scan_camera_help": "Maak een foto van de maaltijd. SanoSync probeert eerst de achtercamera te openen; gebruik 🔄 om zo nodig te wisselen.",
        "scan_upload_help": "Je kunt ook een bestaande foto op je apparaat kiezen.",
        "scan_photo_ready": "✅ Foto vastgelegd. De camera werkt correct.",
        "scan_ai_next": "De foto is klaar voor analyse.", "scan_analyze":"✨ Analyseren met AI", "scan_analyzing":"Maaltijd analyseren…", "scan_ai_done":"✅ Analyse voltooid. Controleer en pas de waarden hieronder aan voordat je opslaat.", "scan_ai_error":"De foto kon niet worden geanalyseerd: {error}",
        "card_kcal_in": "Gegeten Kcal",
        "card_kcal_burn": "Verbrande Kcal",
        "card_balance": "Balans",
        "card_weight": "Gewicht",
        "in_msg_low": lambda p: f"⚠️ Lage projectie ({p} kcal verwacht). Eet meer!",
        "in_msg_high": lambda p: f"✅ Geweldige projectie ({p} kcal geschat aan het einde van de dag).",
        "burn_msg_yes": lambda e: f"🌟 Goed gedaan! Je hebt extra activiteiten gedaan (+{e} kcal).",
        "burn_msg_no": "💡 Geen extra activiteiten geregistreerd. Wat dacht je van wat beweging?",
        "bilancio_ok": "🎯 Uitstekend, je zit in een perfect calorie-tekort.",
        "bilancio_bad": "⚠️ Waarschuwing: je hebt een calorie-overschot.",
        "weight_msg_default": "📈 Ga zo door om je doel te bereiken.",
        "weight_msg_val": lambda i, d_ini, t, d_tgt: f"Start: {i} kg ({d_ini:+.1f}) | Doel: {t} kg ({d_tgt:+.1f})",
        "status_move_title": "👣 Bewegingsstatus",
        "status_very_active": "🌟 Geweldig! Zeer actieve dag.",
        "status_good": "🚶 Goede activiteit, ga zo door.",
        "status_lazy": "🛋️ Luie dag, probeer meer te bewegen.",
        "in_msg_deficit": lambda target_in, diff: f"🎯 Voor een ideaal tekort van 500 kcal (doel {target_in} kcal), {'nog' if diff >= 0 else 'overschreden met'} {abs(diff)} kcal.",
        "balance_days": lambda d: f"⏳ In dit tempo duurt het ongeveer {d} dagen om het doel te bereiken.",
        "balance_surplus": "⚠️ In overschot: kan dagen tot doel niet schatten.",
        "weight_forecast_title": "🔮 Doelbereik Prognose",
        "forecast_days": lambda d, date_str: f"🎯 In dit tempo ({d} geschatte dagen), zou je jouw doel rond **{date_str}** kunnen bereiken!",
        "forecast_steady": "📉 Als je deze gestage trend aanhoudt, komt je mijlpaal dichterbij.",
        "forecast_flat_up": "💡 De huidige trend is vlak of stijgend: de tijdlijnprognose wordt alleen geactiveerd bij een actieve gewichtsverliestrend.",
    }
}


# Additional UI translations for features added after the first translation pass.
translations["Italiano"].update({
    "no_products":"Nessun prodotto trovato. Prova marca + nome oppure un codice a barre.",
    "search_min_chars":"Inserisci almeno 2 caratteri o un codice a barre valido.",
    "plan_day":"Giorno da pianificare","today":"Oggi","tomorrow":"Domani",
    "morning_plan":"Buongiorno! Imposta il tipo di giornata e il livello di attività previsto per pianificare i pasti.",
    "day_type":"Tipo di giornata","activity_expected":"Attività prevista","save_day_plan":"💾 Salva piano della giornata",
    "weight_value":"Peso (kg)","edit_weight":"✏️ Modifica peso","delete_weight":"🗑️ Cancella peso",
    "recipes_title":"🍲 Ricette","search_ingredient":"🔍 Cerca ingrediente",
    "bike_type":"Tipo Bici","normal_bike":"Bici Normale","ebike":"E-Bike (Elettrica)",
})
translations["English"].update({
    "no_products":"No products found. Try brand + product name or a barcode.",
    "search_min_chars":"Enter at least 2 characters or a valid barcode.",
    "plan_day":"Day to plan","today":"Today","tomorrow":"Tomorrow",
    "morning_plan":"Good morning! Set the type of day and expected activity level to plan your meals.",
    "day_type":"Type of day","activity_expected":"Expected activity","save_day_plan":"💾 Save daily plan",
    "weight_value":"Weight (kg)","edit_weight":"✏️ Edit weight","delete_weight":"🗑️ Delete weight",
    "recipes_title":"🍲 Recipes","search_ingredient":"🔍 Search ingredient",
    "bike_type":"Bike type","normal_bike":"Regular Bike","ebike":"E-Bike (Electric)",
})
translations["Nederlands"].update({
    "no_products":"Geen producten gevonden. Probeer merk + productnaam of een streepjescode.",
    "search_min_chars":"Voer minstens 2 tekens of een geldige streepjescode in.",
    "plan_day":"Dag om te plannen","today":"Vandaag","tomorrow":"Morgen",
    "morning_plan":"Goedemorgen! Stel het type dag en het verwachte activiteitsniveau in om je maaltijden te plannen.",
    "day_type":"Type dag","activity_expected":"Verwachte activiteit","save_day_plan":"💾 Dagplan opslaan",
    "weight_value":"Gewicht (kg)","edit_weight":"✏️ Gewicht bewerken","delete_weight":"🗑️ Gewicht verwijderen",
    "recipes_title":"🍲 Recepten","search_ingredient":"🔍 Ingrediënt zoeken",
    "bike_type":"Type fiets","normal_bike":"Normale fiets","ebike":"E-bike (elektrisch)",
})


# Français
translations["Français"] = {
    "t1": "🚀 Saisie",
    "t2": "📊 Vue d’ensemble",
    "t3": "📈 Poids",
    "t4": "🍳 Recettes",
    "t5": "🏃 Activité",
    "meal": "Type de repas",
    "meal_name": "Nom du repas",
    "add_meal": "Ajouter le repas",
    "extra_act": "Activité supplémentaire",
    "extra_cals": "Calories supplémentaires brûlées",
    "insert_weight": "Saisir le poids (kg)",
    "save_weight": "Enregistrer le poids",
    "recipe_name": "Nom de la recette",
    "save_recipe": "Enregistrer la recette",
    "recipe_saved": "✅ Recette enregistrée !",
    "lang_label": "🌐 Langue",
    "logout": "🚪 Déconnexion",
    "search_food": "🔍 Rechercher par nom ou code-barres",
    "search_btn": "🚀 Rechercher",
    "select_db": "Sélectionner dans la base de données",
    "select_recipe": "Sélectionner une recette",
    "no_recipes": "Aucune recette enregistrée.",
    "calc_mode": "Saisie basée sur :",
    "per_100g": "Pour 100 g",
    "per_portion": "Par portion",
    "qty_label": "Quantité (g ou portions)",
    "num_portions": "Nombre de portions",
    "kcal": "Kcal",
    "pro": "Protéines (g)",
    "carbs": "Glucides (g)",
    "fat": "Lipides (g)",
    "inserted": "✅ Ajouté",
    "daily_summary": "📊 Résumé journalier",
    "summary_date": "📅 Date du résumé",
    "logged_foods": "🍽️ Aliments enregistrés",
    "del_meal": "Sélectionner un repas à supprimer",
    "del_meal_btn": "🗑️ Supprimer le repas sélectionné",
    "meal_del_success": "Repas supprimé avec succès !",
    "no_meals": "Aucun repas enregistré pour cette date.",
    "burned_acts": "#### 🏃 Calories brûlées & activités",
    "weight_tracking": "⚖️ Suivi du poids",
    "log_today_weight": "📥 Enregistrer le poids d’aujourd’hui",
    "update_target": "🎯 Mettre à jour l’objectif",
    "save_target": "Enregistrer l’objectif",
    "target_updated": "✅ Objectif mis à jour !",
    "quick_entries": "⚡ Saisies rapides",
    "saved_entries": "📋 Éléments enregistrés",
    "del_quick": "🗑️ Supprimer une saisie rapide",
    "select_quick_del": "Sélectionner la saisie rapide à supprimer",
    "del_quick_btn": "Supprimer la saisie rapide",
    "quick_add_title": "➕ Ajouter une nouvelle saisie rapide",
    "calc_mode_radio": "Mode de calcul",
    "caption_calc": "ℹ️ *Si vous choisissez « Pour 100 g », saisissez les valeurs pour 100 g. Si vous choisissez « Portion », saisissez les valeurs totales d’une portion.*",
    "register_activity": "🏃 Enregistrer activité & mouvement",
    "act_date": "📅 Date",
    "steps_title": "👣 Pas (Total)",
    "update_steps": "💾 Mettre à jour les pas",
    "steps_updated": "Pas mis à jour !",
    "bike_title": "🚲 Vélo (Session)",
    "bike_min": "Minutes de vélo",
    "add_bike": "💾 Ajouter le vélo",
    "other_act": "🏋️ Autre",
    "activity_label": "Activité",
    "add_act_btn": "💾 Ajouter",
    "tab1_title": "🍽️ Saisie des aliments & repas",
    "input_source_lbl": "Source de saisie",
    "opt_ai": "✨ AI",
        "opt_off": "🔍 OpenFood Database",
    "opt_quick": "🍳 Saisie rapide","quick_select_used":"Sélectionnez un aliment ou une recette","quick_empty":"Aucun aliment disponible pour le moment. Enregistrez d’abord un repas.","quick_load_error":"Erreur lors du chargement des saisies rapides : {error}",
        "opt_scan": "📸 Photo IA",
        "scan_title": "📸 Photo IA",
        "scan_mode": "Source de l'image",
        "scan_camera": "📷 Appareil photo",
        "scan_upload": "🖼️ Galerie / Fichier",
        "scan_camera_help": "Prenez une photo du repas. SanoSync essaiera d’ouvrir d’abord la caméra arrière ; utilisez 🔄 pour changer si nécessaire.",
        "scan_upload_help": "Vous pouvez également choisir une photo déjà présente sur votre appareil.",
        "scan_photo_ready": "✅ Photo capturée. L'appareil photo fonctionne correctement.",
        "scan_ai_next": "La photo est prête pour l’analyse.", "scan_analyze":"✨ Analyser avec l’IA", "scan_analyzing":"Analyse du repas…", "scan_ai_done":"✅ Analyse terminée. Vérifiez et corrigez les valeurs ci-dessous avant d’enregistrer.", "scan_ai_error":"Impossible d’analyser la photo : {error}",
    "card_kcal_in": "Kcal consommées",
    "card_kcal_burn": "Kcal brûlées",
    "card_balance": "Bilan",
    "card_weight": "Poids",
    "in_msg_low": lambda p: f"⚠️ Projection basse ({p} kcal prévues). Mangez davantage !",
    "in_msg_high": lambda p: f"✅ Bonne projection ({p} kcal estimées en fin de journée).",
    "burn_msg_yes": lambda e: f"🌟 Bravo ! Vous avez fait une activité supplémentaire (+{e} kcal).",
    "burn_msg_no": "💡 Aucune activité supplémentaire enregistrée. Pourquoi ne pas bouger un peu ?",
    "bilancio_ok": "🎯 Parfait, vous êtes dans un bon déficit calorique.",
    "bilancio_bad": "⚠️ Attention : vous êtes en surplus calorique.",
    "weight_msg_default": "📈 Continuez ainsi pour atteindre votre objectif.",
    "weight_msg_val": lambda i, d_ini, t, d_tgt: f"Initial : {i} kg ({d_ini:+.1f}) | Objectif : {t} kg ({d_tgt:+.1f})",
    "status_move_title": "👣 Statut mouvement",
    "status_very_active": "🌟 Excellent ! Journée très active.",
    "status_good": "🚶 Bonne activité, continuez comme ça.",
    "status_lazy": "🛋️ Journée calme, essayez de bouger davantage.",
    "in_msg_deficit": lambda target_in, diff: f"🎯 Pour un déficit idéal de 500 kcal (objectif {target_in} kcal), {'il reste' if diff >= 0 else 'vous avez dépassé de'} {abs(diff)} kcal.",
    "balance_days": lambda d: f"⏳ À ce rythme, environ {d} jours estimés pour atteindre l’objectif.",
    "balance_surplus": "⚠️ En surplus : impossible d’estimer le nombre de jours jusqu’à l’objectif.",
    "weight_forecast_title": "🔮 Prévision d’atteinte de l’objectif",
    "forecast_days": lambda d, date_str: f"🎯 À votre rythme actuel ({d} jours estimés), vous pourriez atteindre votre objectif vers le **{date_str}** !",
    "forecast_steady": "📉 En maintenant cette tendance, l’objectif se rapproche.",
    "forecast_flat_up": "💡 La tendance actuelle est stable ou en hausse : la projection temporelle s’active uniquement avec une perte de poids active.",

    # Traductions supplémentaires
    "no_products": "Aucun produit trouvé. Essayez marque + nom ou un code-barres.",
    "search_min_chars": "Saisissez au moins 2 caractères ou un code-barres valide.",
    "plan_day": "Jour à planifier",
    "today": "Aujourd’hui",
    "tomorrow": "Demain",
    "morning_plan": "Bonjour ! Définissez le type de journée et le niveau d’activité prévu pour planifier vos repas.",
    "day_type": "Type de journée",
    "activity_expected": "Activité prévue",
    "save_day_plan": "💾 Enregistrer le plan de la journée",
    "weight_value": "Poids (kg)",
    "edit_weight": "✏️ Modifier le poids",
    "delete_weight": "🗑️ Supprimer le poids",
    "recipes_title": "🍲 Recettes",
    "search_ingredient": "🔍 Rechercher un ingrédient",
    "bike_type": "Type de vélo",
    "normal_bike": "Vélo classique",
    "ebike": "Vélo électrique",
}


# Saluti dinamici per fascia oraria.
translations["Italiano"].update({
    "greeting_morning": "Buongiorno {name}!",
    "greeting_afternoon": "Buon pomeriggio {name}!",
    "greeting_evening": "Buonasera {name}!",
})
translations["English"].update({
    "greeting_morning": "Good morning {name}!",
    "greeting_afternoon": "Good afternoon {name}!",
    "greeting_evening": "Good evening {name}!",
})
translations["Nederlands"].update({
    "greeting_morning": "Goedemorgen {name}!",
    "greeting_afternoon": "Goedemiddag {name}!",
    "greeting_evening": "Goedenavond {name}!",
})
translations["Français"].update({
    "greeting_morning": "Bonjour {name}!",
    "greeting_afternoon": "Bon après-midi {name}!",
    "greeting_evening": "Bonsoir {name}!",
})


# ==============================================================================
# ZERO MODE — COPY OVERLAY
# Only user-facing remarks change. Functional labels remain standard.
# ==============================================================================
ZERO_COPY = {
    "Italiano": {
        "t": {
            "slogan": "Tutto sotto controllo, secondo le informazioni gentilmente autocertificate.",
            "morning_plan": 'Buongiorno. Tipo di giornata e attività prevista: vediamo quanto della pianificazione sopravvive al contatto con la realtà.',
            "no_food_data": "Nessun dato alimentare. Prendiamo atto di questa versione della giornata.",
            "no_composed_recipes": "Nessuna ricetta composta. La cucina non ha ancora depositato documentazione.",
            "no_my_recipes": "Nessuna ricetta personale. Per ora il fascicolo culinario è vuoto.",
            "no_shared_recipes": "Nessuna ricetta condivisa. La comunità oggi mantiene un profilo basso.",
            "add_one_ingredient": "Zero ingredienti. Perfino l'intelligenza artificiale richiede un minimo di materia.",
            "scan_analyzing": "Analisi in corso. I numeri stanno concordando una versione comune.",
            "in_msg_low": lambda p: f"Proiezione: {p} kcal. Molto sobria. Abbastanza da chiedersi se abbiamo ricevuto l’intera sceneggiatura.",
            "in_msg_high": lambda p: f"Proiezione: {p} kcal. Il dato è stato acquisito agli atti.",
            "burn_msg_yes": lambda e: f"+{e} kcal di attività. Il dispositivo ha presentato la propria versione dei fatti.",
            "burn_msg_no": "Nessuna attività extra registrata. Curiosamente, è uno dei dati più facili da credere.",
            "bilancio_ok": "C'è un deficit calorico. O stai dimagrendo, o la memoria selettiva ha colpito ancora.",
            "bilancio_bad": "C'è un surplus calorico. L'ipotesi dell'arrotondamento perde credibilità.",
            "weight_msg_default": "Il peso ha depositato un nuovo elemento agli atti. La bilancia, naturalmente, pretende di essere creduta.",
            "first_last_diff": "Differenza tra prima e ultima pesata. Sempre che entrambe abbiano detto la verità.",
            "estimate_based": "Stima basata su {deficit} kcal/giorno di deficit medio ({days} giorni dichiarati). Il futuro non ha ancora firmato nulla.",
            "target_reached_caption": "Il peso registrato coincide con l'obiettivo. Stranamente comodo, ma prendiamo atto.",
            "need_positive_deficit": "Senza un deficit medio positivo la data obiettivo resta soprattutto letteratura.",
            "status_very_active": "Giornata molto attiva. Il tracker ci crede; SanoSync conserva prudentemente il diritto di dubitare.",
            "status_good": "Attività registrata. Abbastanza da sembrare credibile, non abbastanza da eliminare ogni dubbio.",
            "status_lazy": "Giornata territorialmente molto circoscritta.",
            "in_msg_deficit": lambda target_in, diff: (
                f"Target {target_in} kcal: "
                + (f"restano {abs(diff)} kcal. Almeno secondo il registro."
                   if diff >= 0 else
                   f"risultano {abs(diff)} kcal in più. Difficile imputarle tutte all'arrotondamento.")
            ),
            "balance_days": lambda d: f"Stima: circa {d} giorni. A meno che non ti metta a fare schifo.",
            "balance_surplus": "Con un surplus la data obiettivo resta, tecnicamente, materia per la narrativa.",
            "forecast_days": lambda d, date_str: f"Data stimata: **{date_str}** ({d} giorni). Possibile, sempre che la costanza improvvisamente diventi una tua caratteristica stabile.",
            "forecast_steady": "Il trend va nella direzione giusta. Per ora. Sarebbe prematuro attribuirti una nuova personalità.",
            "forecast_flat_up": "Trend stabile o in salita. Almeno questo dato non sta cercando di impressionare nessuno.",
        },
        "ux": {
            "over_target": "Risultano circa {kcal} kcal sopra il target. Il dato è stato regolarmente acquisito.",
            "end_day": "Proiezione di fine giornata: ~{kcal} kcal. Naturalmente vale solo per gli eventi che arriveranno anche nel registro.",
            "activity_logged_note": "Attività strutturata registrata. Il dispositivo dispone apparentemente di prove.",
            "can_eat_more": "Restano {kcal} kcal sul target di oggi. Potresti farcela; il registro, per ragioni sue, continua a fidarsi.",
            "exact_target": "Target centrato al kcal. O sei diventato improvvisamente precisissimo, o qualche dettaglio ha avuto una giornata libera.",
            "day_total": "Totale giornata: {kcal} kcal. I numeri hanno raggiunto un accordo.",
            "no_extra": "Nessuna caloria extra registrata. Una voce sorprendentemente tranquilla del fascicolo.",
            "extra_burned_note": "Somma delle calorie dichiarate dalle attività della giornata. Il tracker giura che siano vere.",
            "steps_note": "Calorie attribuite ai passi. Il telefono dispone apparentemente di una ricostruzione dettagliata.",
            "padel_note": "Calorie registrate come Padel. Una cifra che il dispositivo sostiene con notevole sicurezza.",
            "bike_note": "Somma di Bici ed E-Bike. Le ruote hanno presentato la propria versione dei fatti.",
        },
        "thinking": "Sto facendo i conti. Alcuni numeri stanno già cercando un avvocato.",
    },

    "English": {
        "t": {
            "slogan": "Everything under control, according to the information kindly self-certified.",
            "morning_plan": 'Good morning. Day type and expected activity: let’s see how much of the plan survives contact with reality.',
            "no_food_data": "No food data. We acknowledge this version of the day.",
            "no_composed_recipes": "No composed recipes. The kitchen has filed no paperwork yet.",
            "no_my_recipes": "No personal recipes. The culinary file remains empty for now.",
            "no_shared_recipes": "No shared recipes. The community is keeping a low profile today.",
            "add_one_ingredient": "Zero ingredients. Even artificial intelligence requires a minimum amount of matter.",
            "scan_analyzing": "Analysis in progress. The numbers are agreeing on a common version of events.",
            "in_msg_low": lambda p: f"Projection: {p} kcal. A remarkably restrained day, at least on paper.",
            "in_msg_high": lambda p: f"Projection: {p} kcal. The figure has been entered into the record.",
            "burn_msg_yes": lambda e: f"+{e} kcal of activity. The device has formally submitted its version of events.",
            "burn_msg_no": "No extra activity logged. Curiously, this is one figure we tend to trust.",
            "bilancio_ok": "A calorie deficit exists. At least according to the documentation supplied by the interested party.",
            "bilancio_bad": "There is a calorie surplus. The rounding-error defence is losing credibility.",
            "weight_msg_default": "The scale has submitted another item of evidence. Naturally, it expects to be believed.",
            "first_last_diff": "Difference between the first and latest weigh-in. Assuming both told the truth.",
            "estimate_based": "Estimate based on an average deficit of {deficit} kcal/day ({days} reported days). The future has not signed off yet.",
            "target_reached_caption": "The recorded weight matches the target. Suspiciously convenient, but duly noted.",
            "need_positive_deficit": "Without a positive average deficit, the target date remains mostly a work of fiction.",
            "status_very_active": "Very active day. The tracker seems unusually confident about it.",
            "status_good": "Activity logged. We acknowledge the declaration.",
            "status_lazy": "A geographically compact day.",
            "in_msg_deficit": lambda target_in, diff: (
                f"Target {target_in} kcal: "
                + (f"{abs(diff)} kcal remain. According to the register, anyway."
                   if diff >= 0 else
                   f"{abs(diff)} kcal appear to be over. Rounding is a weak suspect.")
            ),
            "balance_days": lambda d: f"Estimate: about {d} days. Unless you start making a complete mess of it.",
            "balance_surplus": "With a surplus, the target date remains mostly a work of fiction.",
            "forecast_days": lambda d, date_str: f"Estimated date: **{date_str}** ({d} days). According to mathematics, which was not consulted about real life.",
            "forecast_steady": "The trend points the intended way. On paper. Paper, it should be noted, trusts you rather a lot.",
            "forecast_flat_up": "Trend is flat or rising. At least this number is not trying to impress anyone.",
        },
        "ux": {
            "over_target": "About {kcal} kcal over target are currently on record.",
            "end_day": "End-of-day projection: ~{kcal} kcal. Subject to further undeclared developments.",
            "activity_logged_note": "Structured activity logged. The device apparently has evidence.",
            "can_eat_more": "{kcal} kcal remain on today's target. According to the information kindly self-certified.",
            "exact_target": "Target hit to the exact kcal. A level of precision that raises absolutely no questions.",
            "day_total": "Daily total: {kcal} kcal. The numbers have reached an agreement.",
            "no_extra": "No extra calories logged. An unusually quiet section of the file.",
            "extra_burned_note": "Sum of calories claimed by today's activities. The tracker swears they are real.",
            "steps_note": "Calories attributed to steps. The phone apparently has a detailed reconstruction.",
            "padel_note": "Calories logged as padel. A figure the device presents with remarkable confidence.",
            "bike_note": "Bike and e-bike combined. The wheels have submitted their version of events.",
        },
        "thinking": "Running the numbers. Several figures are already asking for legal representation.",
    },

    "Nederlands": {
        "t": {
            "slogan": "Alles onder controle, volgens de vriendelijk zelfgecertificeerde informatie.",
            "morning_plan": 'Goedemorgen. Type dag en verwachte activiteit: eens kijken hoeveel van de planning het contact met de werkelijkheid overleeft.',
            "no_food_data": "Geen voedingsgegevens. We nemen kennis van deze versie van de dag.",
            "no_composed_recipes": "Geen samengestelde recepten. De keuken heeft nog geen dossier ingediend.",
            "no_my_recipes": "Nog geen eigen recepten. Het culinaire dossier blijft voorlopig leeg.",
            "no_shared_recipes": "Geen gedeelde recepten. De gemeenschap houdt zich vandaag opvallend rustig.",
            "add_one_ingredient": "Nul ingrediënten. Zelfs kunstmatige intelligentie heeft een minimale hoeveelheid materie nodig.",
            "scan_analyzing": "Analyse bezig. De cijfers proberen tot één gezamenlijk verhaal te komen.",
            "in_msg_low": lambda p: f"Prognose: {p} kcal. Een opvallend sobere dag, tenminste op papier.",
            "in_msg_high": lambda p: f"Prognose: {p} kcal. Het cijfer is in het dossier opgenomen.",
            "burn_msg_yes": lambda e: f"+{e} kcal activiteit. Het apparaat heeft officieel zijn versie van de feiten ingediend.",
            "burn_msg_no": "Geen extra activiteit geregistreerd. Opmerkelijk genoeg vertrouwen we dit cijfer vrij snel.",
            "bilancio_ok": "Er is een calorietekort. Althans volgens de documentatie van de belanghebbende zelf.",
            "bilancio_bad": "Er is een calorieoverschot. De afrondingsfout verliest geloofwaardigheid als verklaring.",
            "weight_msg_default": "De weegschaal heeft nieuw bewijsmateriaal aangeleverd. Uiteraard verwacht hij dat we het geloven.",
            "first_last_diff": "Verschil tussen de eerste en laatste meting. Ervan uitgaande dat beide eerlijk waren.",
            "estimate_based": "Schatting op basis van gemiddeld {deficit} kcal/dag tekort ({days} opgegeven dagen). De toekomst heeft nog niet getekend.",
            "target_reached_caption": "Het geregistreerde gewicht komt overeen met het doel. Opvallend handig, maar genoteerd.",
            "need_positive_deficit": "Zonder positief gemiddeld tekort blijft de doeldatum vooral fictie.",
            "status_very_active": "Zeer actieve dag. De tracker klinkt er bijzonder zeker van.",
            "status_good": "Activiteit geregistreerd. We nemen kennis van de verklaring.",
            "status_lazy": "Een geografisch bijzonder compacte dag.",
            "in_msg_deficit": lambda target_in, diff: (
                f"Doel {target_in} kcal: "
                + (f"nog {abs(diff)} kcal. Volgens het register dan."
                   if diff >= 0 else
                   f"{abs(diff)} kcal erboven. Afronding is een zwak alibi.")
            ),
            "balance_days": lambda d: f"Schatting: ongeveer {d} dagen. Tenzij je er onderweg natuurlijk een complete puinhoop van maakt.",
            "balance_surplus": "Met een overschot blijft de doeldatum vooral een literair concept.",
            "forecast_days": lambda d, date_str: f"Geschatte datum: **{date_str}** ({d} dagen). Volgens de wiskunde, die niet over het echte leven is geraadpleegd.",
            "forecast_steady": "De trend wijst de bedoelde kant op. Op papier. Papier heeft opvallend veel vertrouwen in je.",
            "forecast_flat_up": "De trend is vlak of stijgend. Dit cijfer probeert tenminste niemand te imponeren.",
        },
        "ux": {
            "over_target": "Er staat ongeveer {kcal} kcal boven het doel in het dossier.",
            "end_day": "Prognose einde dag: ~{kcal} kcal. Onder voorbehoud van verdere niet-gemelde ontwikkelingen.",
            "activity_logged_note": "Gestructureerde activiteit geregistreerd. Het apparaat lijkt bewijsmateriaal te hebben.",
            "can_eat_more": "Er resten {kcal} kcal binnen het dagdoel. Volgens de vriendelijk zelfgecertificeerde gegevens.",
            "exact_target": "Doel exact op de kcal geraakt. Een precisie die absoluut geen vragen oproept.",
            "day_total": "Dagtotaal: {kcal} kcal. De cijfers zijn tot overeenstemming gekomen.",
            "no_extra": "Geen extra calorieën geregistreerd. Een opvallend rustig deel van het dossier.",
            "extra_burned_note": "Som van de calorieën die de activiteiten van vandaag claimen. De tracker zweert dat het klopt.",
            "steps_note": "Calorieën toegeschreven aan stappen. De telefoon beschikt blijkbaar over een gedetailleerde reconstructie.",
            "padel_note": "Calorieën geregistreerd als padel. Een cijfer waar het apparaat opvallend zeker van is.",
            "bike_note": "Fiets en e-bike samen. De wielen hebben hun versie van de feiten ingediend.",
        },
        "thinking": "Ik reken het uit. Enkele cijfers hebben inmiddels juridische bijstand gevraagd.",
    },

    "Français": {
        "t": {
            "slogan": "Tout est sous contrôle, selon les informations aimablement auto-certifiées.",
            "morning_plan": 'Bonjour. Type de journée et activité prévue : voyons ce que la planification survivra au contact de la réalité.',
            "no_food_data": "Aucune donnée alimentaire. Nous prenons acte de cette version de la journée.",
            "no_composed_recipes": "Aucune recette composée. La cuisine n'a encore déposé aucun dossier.",
            "no_my_recipes": "Aucune recette personnelle. Le dossier culinaire reste vide pour l'instant.",
            "no_shared_recipes": "Aucune recette partagée. La communauté fait profil bas aujourd'hui.",
            "add_one_ingredient": "Zéro ingrédient. Même l'intelligence artificielle exige un minimum de matière.",
            "scan_analyzing": "Analyse en cours. Les chiffres essaient de se mettre d'accord sur une version commune.",
            "in_msg_low": lambda p: f"Projection : {p} kcal. Une journée remarquablement sobre, du moins sur le papier.",
            "in_msg_high": lambda p: f"Projection : {p} kcal. Le chiffre a été versé au dossier.",
            "burn_msg_yes": lambda e: f"+{e} kcal d'activité. L'appareil a officiellement déposé sa version des faits.",
            "burn_msg_no": "Aucune activité supplémentaire enregistrée. Curieusement, c'est un chiffre auquel on a tendance à croire.",
            "bilancio_ok": "Il existe un déficit calorique. Du moins selon les pièces fournies par l'intéressé.",
            "bilancio_bad": "Il y a un surplus calorique. L'hypothèse de l'arrondi perd en crédibilité.",
            "weight_msg_default": "La balance vient d'ajouter une nouvelle pièce au dossier. Naturellement, elle s'attend à être crue.",
            "first_last_diff": "Écart entre la première et la dernière pesée. En supposant qu'elles aient toutes les deux dit vrai.",
            "estimate_based": "Estimation basée sur {deficit} kcal/jour de déficit moyen ({days} jours déclarés). Le futur n'a encore rien signé.",
            "target_reached_caption": "Le poids enregistré correspond à l'objectif. Étonnamment pratique, mais acte pris.",
            "need_positive_deficit": "Sans déficit moyen positif, la date cible relève surtout de la fiction.",
            "status_very_active": "Journée très active. Le tracker semble particulièrement sûr de lui.",
            "status_good": "Activité enregistrée. Nous prenons acte de la déclaration.",
            "status_lazy": "Une journée géographiquement très compacte.",
            "in_msg_deficit": lambda target_in, diff: (
                f"Objectif {target_in} kcal : "
                + (f"il reste {abs(diff)} kcal. Selon le registre, en tout cas."
                   if diff >= 0 else
                   f"{abs(diff)} kcal au-dessus. L'arrondi a un alibi assez faible.")
            ),
            "balance_days": lambda d: f"Estimation : environ {d} jours. À moins que vous ne décidiez soudainement de tout gâcher.",
            "balance_surplus": "Avec un surplus, la date cible relève surtout de la littérature.",
            "forecast_days": lambda d, date_str: f"Date estimée : **{date_str}** ({d} jours). Selon les mathématiques, qui n'ont pas été consultées sur la vraie vie.",
            "forecast_steady": "La tendance va dans le sens prévu. Sur le papier. Le papier, lui, vous fait étonnamment confiance.",
            "forecast_flat_up": "Tendance stable ou en hausse. Au moins, ce chiffre n'essaie d'impressionner personne.",
        },
        "ux": {
            "over_target": "Environ {kcal} kcal au-dessus de l'objectif figurent actuellement au dossier.",
            "end_day": "Projection de fin de journée : ~{kcal} kcal. Sous réserve de nouveaux éléments non déclarés.",
            "activity_logged_note": "Activité structurée enregistrée. L'appareil semble disposer de preuves.",
            "can_eat_more": "Il reste {kcal} kcal sur l'objectif du jour. Selon les informations aimablement auto-certifiées.",
            "exact_target": "Objectif atteint à la kcal près. Une précision qui ne soulève absolument aucune question.",
            "day_total": "Total de la journée : {kcal} kcal. Les chiffres sont parvenus à un accord.",
            "no_extra": "Aucune calorie supplémentaire enregistrée. Une partie étonnamment calme du dossier.",
            "extra_burned_note": "Somme des calories revendiquées par les activités du jour. Le tracker jure que c'est vrai.",
            "steps_note": "Calories attribuées aux pas. Le téléphone semble disposer d'une reconstitution détaillée.",
            "padel_note": "Calories enregistrées comme padel. Un chiffre que l'appareil défend avec une remarquable assurance.",
            "bike_note": "Vélo et e-bike réunis. Les roues ont déposé leur version des faits.",
        },
        "thinking": "Je fais les comptes. Plusieurs chiffres demandent déjà un avocat.",
    },
}


# ------------------------------------------------------------------------------
# Traduzioni UI aggiuntive (Tab 2/3/4 + valori canonici salvati nel database)
# I valori nel DB restano in italiano/canonici; traduciamo solo ciò che si vede.
# ------------------------------------------------------------------------------
translations["Italiano"].update({
    "slogan": "Tutto sotto controllo",
    "meal_breakfast": "Colazione", "meal_lunch": "Pranzo", "meal_dinner": "Cena", "meal_snack": "Snack",
    "cat_home": "Casa", "cat_work": "Lavoro", "cat_restaurant": "Ristorante", "cat_once": "Una-tantum",
    "col_meal": "Pasto", "col_category": "Categoria", "col_name": "Nome", "col_date": "Data",
    "select_meal_edit": translations["Italiano"].get("select_meal_edit", "🍽️ Seleziona il pasto da modificare"), "select_meal_placeholder": "Seleziona un pasto...",
    "meal_type_label": "Tipo di pasto", "category_label": "Categoria", "quantity_g": "Quantità (g)", "portions": "Porzioni",
    "edit_meal_help": "Puoi modificare grammi o porzioni. Kcal e macronutrienti vengono ricalcolati automaticamente.",
    "save_changes": translations["Italiano"].get("save_changes", "💾 Salva modifiche"), "delete_this_meal": "Elimina definitivamente **{name}** se non vuoi più conservarlo.",
    "meal_updated": "✅ Pasto aggiornato: **{meal} · {category} · {qty} {unit}**.",
    "load_data_error": "Errore nel caricamento dati: {error}", "edit_meal_error": "Errore nella modifica del pasto: {error}",
    "delete_meal_error": "Errore nell'eliminazione del pasto: {error}",
    "day_plan_title": "### 🧭 Piano della giornata", "plan_update_later": "Puoi aggiornare il piano della giornata anche dopo la mattina.",
    "day_home": "Lavoro da casa", "day_office": "Ufficio", "day_free": "Giornata libera",
    "act_rest": "Riposo", "act_moderate": "Moderatamente attiva", "act_active": "Attiva",
    "weight_manage": "#### ⚖️ Gestione pesi", "new_weight": "Nuovo peso (kg)", "weight_date": "Data del peso",
    "weight_edit_select": translations["Italiano"].get("weight_edit_select", "Peso da modificare o eliminare"), "weight_select_placeholder": "Seleziona un peso...",
    "date_label": "Data", "weight_saved": "✅ Peso salvato!", "weight_edited": "✅ Peso modificato!", "weight_deleted": "✅ Peso cancellato.",
    "target_weight_label": "Peso Obiettivo (kg)", "weight_lost_30": "📉 Peso perso · 30 giorni", "deficit_per_kg": "⚡ Deficit / kg perso",
    "estimated_target_date": "🎯 Data obiettivo stimata", "need_two_weights": translations["Italiano"].get("need_two_weights", "Servono almeno due pesi e dati alimentari nell’ultimo mese."),
    "first_last_diff": translations["Italiano"].get("first_last_diff", "Differenza tra la prima e l’ultima misurazione degli ultimi 30 giorni."),
    "need_positive_deficit": translations["Italiano"].get("need_positive_deficit", "Serve un deficit medio positivo per stimare la data obiettivo."), "target_reached": translations["Italiano"].get("target_reached", "Raggiunto 🎯"),
    "target_reached_caption": translations["Italiano"].get("target_reached_caption", "Il tuo ultimo peso è già uguale o inferiore all’obiettivo."), "estimate_based": "Stima basata su {deficit} kcal/giorno di deficit medio ({days} giorni loggati).",
    "view_label": "Visualizzazione", "view_weight": "Peso", "view_kcal": "Kcal", "view_macros": "Macros", "view_meals": "Pasti", "period_label": "Periodo",
    "no_weight_period": "Nessun peso registrato negli ultimi {days} giorni.", "ingested_kcal": "Kcal ingerite", "burned_kcal": "Kcal bruciate",
    "protein_full": "Proteine", "carbs_full": "Carboidrati", "fats_full": "Grassi", "grams": "grammi", "goal": "Obiettivo",
    "no_food_data": "Nessun dato alimentare", "chart_error": "Errore nel caricamento del grafico: {error}",
    "recipes_caption": "Le ricette restano personali per impostazione predefinita. Puoi scegliere di condividere singole ricette con gli altri utenti.",
    "available_recipes": "### 📋 Ricette disponibili", "no_composed_recipes": "Nessuna ricetta composta presente nei pasti.",
    "create_meal_ingredients": "### ➕ Crea un pasto da ingredienti", "recipe_name_placeholder": "Es. Pasta al pomodoro",
    "notes_optional": "Note (opzionali)", "notes_placeholder": "Es. preparazione, sostituzioni, condimenti...",
    "add_ingredient_title": "#### 🥕 Aggiungi ingrediente", "ingredient_source": "Fonte ingrediente",
    "db_off": "Database / Open Food Facts", "manual_entry": "Inserimento manuale", "ingredient_search": "Cerca ingrediente",
    "searching_ingredient": "Ricerca ingrediente...", "min_2_chars": "Inserisci almeno 2 caratteri.", "results": "Risultati",
    "ingredient_name": "Nome ingrediente", "ingredient_qty": translations["Italiano"].get("ingredient_qty", "Quantità ingrediente (g)"), "add_ingredient": translations["Italiano"].get("add_ingredient", "➕ Aggiungi ingrediente"),
    "select_or_enter_ingredient": "Inserisci o seleziona un ingrediente.", "ingredient_added": "✅ {name} aggiunto.",
    "ingredients_title": "#### 📋 Ingredienti", "ingredient_col": "Ingrediente", "remove_ingredient": "Rimuovi ingrediente",
    "remove_ingredient_btn": translations["Italiano"].get("remove_ingredient_btn", "🗑️ Rimuovi ingrediente"), "total_meal": "Totale pasto", "per_100g_label": "Per 100 g",
    "save_as_meal": "💾 Salva come pasto", "enter_name": "Inserisci un nome.", "composed_saved": "✅ Pasto composto salvato!",
    "add_one_ingredient": "Aggiungi almeno un ingrediente per costruire il pasto.",
    "recipe_category_help": "Una-tantum non entra nei suggerimenti. Ristorante non viene mai suggerito a pranzo.",
    "my_recipes": "### 👤 Le mie ricette",
    "shared_recipes": "### 🌍 Ricette condivise",
    "no_my_recipes": "Non hai ancora creato ricette.",
    "no_shared_recipes": "Nessuna ricetta condivisa disponibile.",
    "share_recipe": "🌍 Condividi questa ricetta con gli altri utenti",
    "share_help": "Se attivo, gli altri utenti autenticati potranno vedere la ricetta. Tu resterai l'unico a poterla modificare o eliminare.",
    "sharing_manage": "#### 🔐 Condivisione ricette",
    "sharing_select": "Seleziona una tua ricetta",
    "sharing_status": "Condivisa",
    "sharing_save": "💾 Aggiorna condivisione",
    "sharing_updated": "✅ Impostazione di condivisione aggiornata.",
    "owner": "Autore",
    "recipe_photo": "📷 Foto della ricetta (opzionale)",
    "recipe_photo_help": "Puoi caricare JPG, PNG o WebP. La foto sarà visibile sulla card della ricetta.",
    "recipe_private": "Privata",
    "recipe_shared_badge": "Condivisa",
    "recipe_no_photo": "Nessuna foto",
    "recipe_show_ingredients": "🧾 Ingredienti",
    "recipe_no_ingredients": "Ingredienti non disponibili.",
    "recipe_photo_error": "Impossibile caricare la foto: {error}","recipe_add_photo":"📷 Aggiungi immagine","recipe_replace_photo":"🖼️ Sostituisci immagine","recipe_photo_save":"💾 Salva immagine","recipe_photo_saved":"✅ Immagine ricetta aggiornata.",
    "recipe_servings": "🍽️ Porzioni previste",
    "recipe_servings_help": "Indica quante porzioni produce l'intera ricetta. Potrai poi registrare 0,5 / 1 / 1,5 porzioni e calorie e macro verranno calcolati automaticamente.",
    "per_serving": "Per porzione",
    "total_recipe": "Ricetta intera",
    "serving_weight": "circa {grams} g per porzione",
})
translations["English"].update({
    "slogan": "Under control",
    "meal_breakfast": "Breakfast", "meal_lunch": "Lunch", "meal_dinner": "Dinner", "meal_snack": "Snack",
    "cat_home": "Home", "cat_work": "Work", "cat_restaurant": "Restaurant", "cat_once": "One-off",
    "col_meal": "Meal", "col_category": "Category", "col_name": "Name", "col_date": "Date",
    "select_meal_edit": "🍽️ Select the meal to edit", "select_meal_placeholder": "Select a meal...",
    "meal_type_label": "Meal type", "category_label": "Category", "quantity_g": "Quantity (g)", "portions": "Portions",
    "edit_meal_help": "You can edit grams or portions. Calories and macros are recalculated automatically.",
    "save_changes": "💾 Save changes", "delete_this_meal": "Permanently delete **{name}** if you no longer want to keep it.",
    "meal_updated": "✅ Meal updated: **{meal} · {category} · {qty} {unit}**.",
    "load_data_error": "Error loading data: {error}", "edit_meal_error": "Error editing meal: {error}", "delete_meal_error": "Error deleting meal: {error}",
    "day_plan_title": "### 🧭 Day plan", "plan_update_later": "You can update today's plan later as well.",
    "day_home": "Work from home", "day_office": "Office", "day_free": "Day off", "act_rest": "Rest", "act_moderate": "Moderately active", "act_active": "Active",
    "weight_manage": "#### ⚖️ Weight management", "new_weight": "New weight (kg)", "weight_date": "Weight date",
    "weight_edit_select": "Weight to edit or delete", "weight_select_placeholder": "Select a weight...", "date_label": "Date",
    "weight_saved": "✅ Weight saved!", "weight_edited": "✅ Weight updated!", "weight_deleted": "✅ Weight deleted.",
    "target_weight_label": "Target weight (kg)", "weight_lost_30": "📉 Weight lost · 30 days", "deficit_per_kg": "⚡ Deficit / kg lost",
    "estimated_target_date": "🎯 Estimated target date", "need_two_weights": "At least two weights and food data are needed for the last month.",
    "first_last_diff": "Difference between the first and last measurement in the last 30 days.", "need_positive_deficit": "A positive average deficit is needed to estimate the target date.",
    "target_reached": "Reached 🎯", "target_reached_caption": "Your latest weight is already at or below the target.",
    "estimate_based": "Estimate based on an average deficit of {deficit} kcal/day ({days} logged days).",
    "view_label": "View", "view_weight": "Weight", "view_kcal": "Calories", "view_macros": "Macros", "view_meals": "Meals", "period_label": "Period",
    "no_weight_period": "No weight logged in the last {days} days.", "ingested_kcal": "Calories eaten", "burned_kcal": "Calories burned",
    "protein_full": "Protein", "carbs_full": "Carbohydrates", "fats_full": "Fat", "grams": "grams", "goal": "Goal", "no_food_data": "No food data",
    "chart_error": "Error loading chart: {error}", "recipes_caption": "Recipes are private by default. You can choose to share individual recipes with other users.",
    "available_recipes": "### 📋 Available recipes", "no_composed_recipes": "No composed recipes found in meals.", "create_meal_ingredients": "### ➕ Create a meal from ingredients",
    "recipe_name_placeholder": "E.g. Pasta with tomato sauce", "notes_optional": "Notes (optional)", "notes_placeholder": "E.g. preparation, substitutions, seasoning...",
    "add_ingredient_title": "#### 🥕 Add ingredient", "ingredient_source": "Ingredient source", "db_off": "Database / Open Food Facts", "manual_entry": "Manual entry",
    "ingredient_search": "Search ingredient", "searching_ingredient": "Searching ingredient...", "min_2_chars": "Enter at least 2 characters.", "results": "Results",
    "ingredient_name": "Ingredient name", "ingredient_qty": "Ingredient quantity (g)", "add_ingredient": "➕ Add ingredient",
    "select_or_enter_ingredient": "Enter or select an ingredient.", "ingredient_added": "✅ {name} added.", "ingredients_title": "#### 📋 Ingredients",
    "ingredient_col": "Ingredient", "remove_ingredient": "Remove ingredient", "remove_ingredient_btn": "🗑️ Remove ingredient", "total_meal": "Total meal",
    "per_100g_label": "Per 100 g", "save_as_meal": "💾 Save as meal", "enter_name": "Enter a name.", "composed_saved": "✅ Composed meal saved!",
    "add_one_ingredient": "Add at least one ingredient to build the meal.", "recipe_category_help": "One-off meals are excluded from suggestions. Restaurants are never suggested for lunch.",
    "my_recipes": "### 👤 My recipes",
    "shared_recipes": "### 🌍 Shared recipes",
    "no_my_recipes": "You have not created any recipes yet.",
    "no_shared_recipes": "No shared recipes are available.",
    "share_recipe": "🌍 Share this recipe with other users",
    "share_help": "When enabled, other authenticated users can view the recipe. Only you can modify or delete it.",
    "sharing_manage": "#### 🔐 Recipe sharing",
    "sharing_select": "Select one of your recipes",
    "sharing_status": "Shared",
    "sharing_save": "💾 Update sharing",
    "sharing_updated": "✅ Sharing setting updated.",
    "owner": "Author",
    "recipe_photo": "📷 Recipe photo (optional)",
    "recipe_photo_help": "You can upload JPG, PNG or WebP. The photo will appear on the recipe card.",
    "recipe_private": "Private",
    "recipe_shared_badge": "Shared",
    "recipe_no_photo": "No photo",
    "recipe_show_ingredients": "🧾 Ingredients",
    "recipe_no_ingredients": "Ingredients not available.",
    "recipe_photo_error": "Could not upload the photo: {error}","recipe_add_photo":"📷 Add image","recipe_replace_photo":"🖼️ Replace image","recipe_photo_save":"💾 Save image","recipe_photo_saved":"✅ Recipe image updated.",
    "recipe_servings": "🍽️ Expected servings",
    "recipe_servings_help": "Enter how many servings the whole recipe makes. You can later log 0.5 / 1 / 1.5 servings and calories/macros will scale automatically.",
    "per_serving": "Per serving",
    "total_recipe": "Whole recipe",
    "serving_weight": "about {grams} g per serving",
})
translations["Nederlands"].update({
    "slogan": "Komt goed",
    "meal_breakfast": "Ontbijt", "meal_lunch": "Lunch", "meal_dinner": "Avondeten", "meal_snack": "Snack",
    "cat_home": "Thuis", "cat_work": "Werk", "cat_restaurant": "Restaurant", "cat_once": "Eenmalig",
    "col_meal": "Maaltijd", "col_category": "Categorie", "col_name": "Naam", "col_date": "Datum",
    "select_meal_edit": "🍽️ Selecteer de maaltijd om te wijzigen", "select_meal_placeholder": "Selecteer een maaltijd...",
    "meal_type_label": "Maaltijdtype", "category_label": "Categorie", "quantity_g": "Hoeveelheid (g)", "portions": "Porties",
    "edit_meal_help": "Je kunt grammen of porties wijzigen. Calorieën en macro's worden automatisch herberekend.",
    "save_changes": "💾 Wijzigingen opslaan", "delete_this_meal": "Verwijder **{name}** definitief als je deze niet meer wilt bewaren.",
    "meal_updated": "✅ Maaltijd bijgewerkt: **{meal} · {category} · {qty} {unit}**.",
    "load_data_error": "Fout bij laden van gegevens: {error}", "edit_meal_error": "Fout bij wijzigen van maaltijd: {error}", "delete_meal_error": "Fout bij verwijderen van maaltijd: {error}",
    "day_plan_title": "### 🧭 Dagplanning", "plan_update_later": "Je kunt de dagplanning later ook nog aanpassen.",
    "day_home": "Thuiswerken", "day_office": "Kantoor", "day_free": "Vrije dag", "act_rest": "Rust", "act_moderate": "Matig actief", "act_active": "Actief",
    "weight_manage": "#### ⚖️ Gewicht beheren", "new_weight": "Nieuw gewicht (kg)", "weight_date": "Datum van gewicht",
    "weight_edit_select": "Gewicht wijzigen of verwijderen", "weight_select_placeholder": "Selecteer een gewicht...", "date_label": "Datum",
    "weight_saved": "✅ Gewicht opgeslagen!", "weight_edited": "✅ Gewicht gewijzigd!", "weight_deleted": "✅ Gewicht verwijderd.",
    "target_weight_label": "Streefgewicht (kg)", "weight_lost_30": "📉 Gewichtsverlies · 30 dagen", "deficit_per_kg": "⚡ Tekort / kg verloren",
    "estimated_target_date": "🎯 Geschatte streefdatum", "need_two_weights": "Minstens twee gewichten en voedingsgegevens van de afgelopen maand zijn nodig.",
    "first_last_diff": "Verschil tussen de eerste en laatste meting van de afgelopen 30 dagen.", "need_positive_deficit": "Een positief gemiddeld tekort is nodig om de streefdatum te schatten.",
    "target_reached": "Bereikt 🎯", "target_reached_caption": "Je laatste gewicht is al gelijk aan of lager dan je doel.",
    "estimate_based": "Schatting gebaseerd op gemiddeld {deficit} kcal/dag tekort ({days} gelogde dagen).",
    "view_label": "Weergave", "view_weight": "Gewicht", "view_kcal": "Kcal", "view_macros": "Macro's", "view_meals": "Maaltijden", "period_label": "Periode",
    "no_weight_period": "Geen gewicht geregistreerd in de afgelopen {days} dagen.", "ingested_kcal": "Kcal gegeten", "burned_kcal": "Kcal verbrand",
    "protein_full": "Eiwitten", "carbs_full": "Koolhydraten", "fats_full": "Vetten", "grams": "gram", "goal": "Doel", "no_food_data": "Geen voedingsgegevens",
    "chart_error": "Fout bij laden van grafiek: {error}", "recipes_caption": "Recepten zijn standaard privé. Je kunt afzonderlijke recepten delen met andere gebruikers.",
    "available_recipes": "### 📋 Beschikbare recepten", "no_composed_recipes": "Geen samengestelde recepten gevonden in maaltijden.", "create_meal_ingredients": "### ➕ Maak een maaltijd van ingrediënten",
    "recipe_name_placeholder": "Bijv. pasta met tomatensaus", "notes_optional": "Notities (optioneel)", "notes_placeholder": "Bijv. bereiding, vervangingen, kruiden...",
    "add_ingredient_title": "#### 🥕 Ingrediënt toevoegen", "ingredient_source": "Bron ingrediënt", "db_off": "Database / Open Food Facts", "manual_entry": "Handmatige invoer",
    "ingredient_search": "Ingrediënt zoeken", "searching_ingredient": "Ingrediënt zoeken...", "min_2_chars": "Voer minstens 2 tekens in.", "results": "Resultaten",
    "ingredient_name": "Naam ingrediënt", "ingredient_qty": "Hoeveelheid ingrediënt (g)", "add_ingredient": "➕ Ingrediënt toevoegen",
    "select_or_enter_ingredient": "Voer een ingrediënt in of selecteer er één.", "ingredient_added": "✅ {name} toegevoegd.", "ingredients_title": "#### 📋 Ingrediënten",
    "ingredient_col": "Ingrediënt", "remove_ingredient": "Ingrediënt verwijderen", "remove_ingredient_btn": "🗑️ Ingrediënt verwijderen", "total_meal": "Totale maaltijd",
    "per_100g_label": "Per 100 g", "save_as_meal": "💾 Opslaan als maaltijd", "enter_name": "Voer een naam in.", "composed_saved": "✅ Samengestelde maaltijd opgeslagen!",
    "add_one_ingredient": "Voeg minstens één ingrediënt toe om de maaltijd te maken.", "recipe_category_help": "Eenmalige maaltijden worden niet voorgesteld. Restaurants worden nooit voor lunch voorgesteld.",
    "my_recipes": "### 👤 Mijn recepten",
    "shared_recipes": "### 🌍 Gedeelde recepten",
    "no_my_recipes": "Je hebt nog geen recepten gemaakt.",
    "no_shared_recipes": "Er zijn geen gedeelde recepten beschikbaar.",
    "share_recipe": "🌍 Deel dit recept met andere gebruikers",
    "share_help": "Als dit is ingeschakeld, kunnen andere ingelogde gebruikers het recept bekijken. Alleen jij kunt het wijzigen of verwijderen.",
    "sharing_manage": "#### 🔐 Recept delen",
    "sharing_select": "Selecteer een van je recepten",
    "sharing_status": "Gedeeld",
    "sharing_save": "💾 Delen bijwerken",
    "sharing_updated": "✅ Deelinstelling bijgewerkt.",
    "owner": "Auteur",
    "recipe_photo": "📷 Foto van het recept (optioneel)",
    "recipe_photo_help": "Je kunt JPG, PNG of WebP uploaden. De foto verschijnt op de receptkaart.",
    "recipe_private": "Privé",
    "recipe_shared_badge": "Gedeeld",
    "recipe_no_photo": "Geen foto",
    "recipe_show_ingredients": "🧾 Ingrediënten",
    "recipe_no_ingredients": "Ingrediënten niet beschikbaar.",
    "recipe_photo_error": "Foto uploaden mislukt: {error}","recipe_add_photo":"📷 Afbeelding toevoegen","recipe_replace_photo":"🖼️ Afbeelding vervangen","recipe_photo_save":"💾 Afbeelding opslaan","recipe_photo_saved":"✅ Receptafbeelding bijgewerkt.",
    "recipe_servings": "🍽️ Verwachte porties",
    "recipe_servings_help": "Geef aan hoeveel porties het hele recept oplevert. Later kun je 0,5 / 1 / 1,5 porties registreren en calorieën/macro's worden automatisch aangepast.",
    "per_serving": "Per portie",
    "total_recipe": "Hele recept",
    "serving_weight": "ongeveer {grams} g per portie",
})
translations["Français"].update({
    "slogan": "C'est géré",
    "meal_breakfast": "Petit-déjeuner", "meal_lunch": "Déjeuner", "meal_dinner": "Dîner", "meal_snack": "Snack",
    "cat_home": "Maison", "cat_work": "Travail", "cat_restaurant": "Restaurant", "cat_once": "Ponctuel",
    "col_meal": "Repas", "col_category": "Catégorie", "col_name": "Nom", "col_date": "Date",
    "select_meal_edit": "🍽️ Sélectionnez le repas à modifier", "select_meal_placeholder": "Sélectionnez un repas...",
    "meal_type_label": "Type de repas", "category_label": "Catégorie", "quantity_g": "Quantité (g)", "portions": "Portions",
    "edit_meal_help": "Vous pouvez modifier les grammes ou les portions. Les calories et macros sont recalculées automatiquement.",
    "save_changes": "💾 Enregistrer les modifications", "delete_this_meal": "Supprimez définitivement **{name}** si vous ne souhaitez plus le conserver.",
    "meal_updated": "✅ Repas mis à jour : **{meal} · {category} · {qty} {unit}**.",
    "load_data_error": "Erreur de chargement : {error}", "edit_meal_error": "Erreur de modification du repas : {error}", "delete_meal_error": "Erreur de suppression du repas : {error}",
    "day_plan_title": "### 🧭 Plan de la journée", "plan_update_later": "Vous pouvez modifier le plan de la journée plus tard.",
    "day_home": "Télétravail", "day_office": "Bureau", "day_free": "Jour libre", "act_rest": "Repos", "act_moderate": "Modérément actif", "act_active": "Actif",
    "weight_manage": "#### ⚖️ Gestion du poids", "new_weight": "Nouveau poids (kg)", "weight_date": "Date du poids",
    "weight_edit_select": "Poids à modifier ou supprimer", "weight_select_placeholder": "Sélectionnez un poids...", "date_label": "Date",
    "weight_saved": "✅ Poids enregistré !", "weight_edited": "✅ Poids modifié !", "weight_deleted": "✅ Poids supprimé.",
    "target_weight_label": "Poids cible (kg)", "weight_lost_30": "📉 Poids perdu · 30 jours", "deficit_per_kg": "⚡ Déficit / kg perdu",
    "estimated_target_date": "🎯 Date cible estimée", "need_two_weights": "Il faut au moins deux poids et des données alimentaires sur le dernier mois.",
    "first_last_diff": "Différence entre la première et la dernière mesure des 30 derniers jours.", "need_positive_deficit": "Un déficit moyen positif est nécessaire pour estimer la date cible.",
    "target_reached": "Atteint 🎯", "target_reached_caption": "Votre poids le plus récent est déjà égal ou inférieur à l'objectif.",
    "estimate_based": "Estimation basée sur un déficit moyen de {deficit} kcal/jour ({days} jours enregistrés).",
    "view_label": "Affichage", "view_weight": "Poids", "view_kcal": "Kcal", "view_macros": "Macros", "view_meals": "Repas", "period_label": "Période",
    "no_weight_period": "Aucun poids enregistré au cours des {days} derniers jours.", "ingested_kcal": "Kcal consommées", "burned_kcal": "Kcal brûlées",
    "protein_full": "Protéines", "carbs_full": "Glucides", "fats_full": "Lipides", "grams": "grammes", "goal": "Objectif", "no_food_data": "Aucune donnée alimentaire",
    "chart_error": "Erreur de chargement du graphique : {error}", "recipes_caption": "Les recettes sont privées par défaut. Vous pouvez choisir de partager certaines recettes avec les autres utilisateurs.",
    "available_recipes": "### 📋 Recettes disponibles", "no_composed_recipes": "Aucune recette composée dans les repas.", "create_meal_ingredients": "### ➕ Créer un repas à partir d'ingrédients",
    "recipe_name_placeholder": "Ex. pâtes à la sauce tomate", "notes_optional": "Notes (facultatives)", "notes_placeholder": "Ex. préparation, substitutions, assaisonnement...",
    "add_ingredient_title": "#### 🥕 Ajouter un ingrédient", "ingredient_source": "Source de l'ingrédient", "db_off": "Base / Open Food Facts", "manual_entry": "Saisie manuelle",
    "ingredient_search": "Rechercher un ingrédient", "searching_ingredient": "Recherche d'ingrédient...", "min_2_chars": "Saisissez au moins 2 caractères.", "results": "Résultats",
    "ingredient_name": "Nom de l'ingrédient", "ingredient_qty": "Quantité d'ingrédient (g)", "add_ingredient": "➕ Ajouter l'ingrédient",
    "select_or_enter_ingredient": "Saisissez ou sélectionnez un ingrédient.", "ingredient_added": "✅ {name} ajouté.", "ingredients_title": "#### 📋 Ingrédients",
    "ingredient_col": "Ingrédient", "remove_ingredient": "Retirer l'ingrédient", "remove_ingredient_btn": "🗑️ Retirer l'ingrédient", "total_meal": "Repas total",
    "per_100g_label": "Pour 100 g", "save_as_meal": "💾 Enregistrer comme repas", "enter_name": "Saisissez un nom.", "composed_saved": "✅ Repas composé enregistré !",
    "add_one_ingredient": "Ajoutez au moins un ingrédient pour construire le repas.", "recipe_category_help": "Les repas ponctuels sont exclus des suggestions. Les restaurants ne sont jamais suggérés au déjeuner.",
    "my_recipes": "### 👤 Mes recettes",
    "shared_recipes": "### 🌍 Recettes partagées",
    "no_my_recipes": "Vous n'avez encore créé aucune recette.",
    "no_shared_recipes": "Aucune recette partagée n'est disponible.",
    "share_recipe": "🌍 Partager cette recette avec les autres utilisateurs",
    "share_help": "Si cette option est activée, les autres utilisateurs authentifiés pourront voir la recette. Vous seul pourrez la modifier ou la supprimer.",
    "sharing_manage": "#### 🔐 Partage des recettes",
    "sharing_select": "Sélectionnez l'une de vos recettes",
    "sharing_status": "Partagée",
    "sharing_save": "💾 Mettre à jour le partage",
    "sharing_updated": "✅ Paramètre de partage mis à jour.",
    "owner": "Auteur",
    "recipe_photo": "📷 Photo de la recette (facultative)",
    "recipe_photo_help": "Vous pouvez importer un JPG, PNG ou WebP. La photo apparaîtra sur la carte de la recette.",
    "recipe_private": "Privée",
    "recipe_shared_badge": "Partagée",
    "recipe_no_photo": "Aucune photo",
    "recipe_show_ingredients": "🧾 Ingrédients",
    "recipe_no_ingredients": "Ingrédients non disponibles.",
    "recipe_photo_error": "Impossible d’importer la photo : {error}","recipe_add_photo":"📷 Ajouter une image","recipe_replace_photo":"🖼️ Remplacer l’image","recipe_photo_save":"💾 Enregistrer l’image","recipe_photo_saved":"✅ Image de la recette mise à jour.",
    "recipe_servings": "🍽️ Portions prévues",
    "recipe_servings_help": "Indiquez combien de portions produit la recette entière. Vous pourrez ensuite enregistrer 0,5 / 1 / 1,5 portion et les calories/macros seront ajustées automatiquement.",
    "per_serving": "Par portion",
    "total_recipe": "Recette entière",
    "serving_weight": "environ {grams} g par portion",
})

translations["Italiano"].update({"period_days":"giorni","monthly_stats_error":"Impossibile calcolare le statistiche mensili: {error}","weight_edit_error":"Errore nella modifica: {error}","weight_delete_error":"Errore nella cancellazione: {error}","generic_error":"Errore: {error}","no_weight_loss":"Nessuna perdita di peso misurata negli ultimi 30 giorni.","ratio_caption":"{deficit} kcal di deficit / {kg} kg persi.","trend":"Proiezione","real_weight":"Peso reale"})
translations["English"].update({"period_days":"days","monthly_stats_error":"Unable to calculate monthly statistics: {error}","weight_edit_error":"Error updating weight: {error}","weight_delete_error":"Error deleting weight: {error}","generic_error":"Error: {error}","no_weight_loss":"No measured weight loss in the last 30 days.","ratio_caption":"{deficit} kcal deficit / {kg} kg lost.","trend":"Projection","real_weight":"Actual weight"})
translations["Nederlands"].update({"period_days":"dagen","monthly_stats_error":"Maandstatistieken konden niet worden berekend: {error}","weight_edit_error":"Fout bij wijzigen van gewicht: {error}","weight_delete_error":"Fout bij verwijderen van gewicht: {error}","generic_error":"Fout: {error}","no_weight_loss":"Geen gemeten gewichtsverlies in de afgelopen 30 dagen.","ratio_caption":"{deficit} kcal tekort / {kg} kg verloren.","trend":"Projectie","real_weight":"Werkelijk gewicht"})
translations["Français"].update({"period_days":"jours","monthly_stats_error":"Impossible de calculer les statistiques mensuelles : {error}","weight_edit_error":"Erreur lors de la modification du poids : {error}","weight_delete_error":"Erreur lors de la suppression du poids : {error}","generic_error":"Erreur : {error}","no_weight_loss":"Aucune perte de poids mesurée au cours des 30 derniers jours.","ratio_caption":"{deficit} kcal de déficit / {kg} kg perdus.","trend":"Projection","real_weight":"Poids réel"})

translations["Italiano"].update({"category_help":"Casa = replicabile a casa · Lavoro = pasto aziendale · Ristorante = fuori casa · Una-tantum = evento/non replicabile","col_activity":"Attività","col_burned":"Kcal Bruciate","save_weight_ui":"💾 Salva peso","plan_persistence_note":"Il piano resta attivo in questa sessione. Esegui la migrazione SQL aggiornata per renderlo persistente."})
translations["English"].update({"category_help":"Home = repeatable at home · Work = company meal · Restaurant = eating out · One-off = event/non-repeatable","col_activity":"Activity","col_burned":"Calories Burned","save_weight_ui":"💾 Save weight","plan_persistence_note":"The plan remains active for this session. Run the updated SQL migration to make it persistent."})
translations["Nederlands"].update({"category_help":"Thuis = thuis herhaalbaar · Werk = bedrijfsmaaltijd · Restaurant = buitenshuis · Eenmalig = evenement/niet herhaalbaar","col_activity":"Activiteit","col_burned":"Kcal Verbrand","save_weight_ui":"💾 Gewicht opslaan","plan_persistence_note":"Het plan blijft actief in deze sessie. Voer de bijgewerkte SQL-migratie uit om het permanent op te slaan."})
translations["Français"].update({"category_help":"Maison = reproductible à la maison · Travail = repas d'entreprise · Restaurant = à l'extérieur · Ponctuel = événement/non reproductible","col_activity":"Activité","col_burned":"Kcal Brûlées","save_weight_ui":"💾 Enregistrer le poids","plan_persistence_note":"Le plan reste actif pendant cette session. Exécutez la migration SQL mise à jour pour le rendre persistant."})

translations["Italiano"].update({"plan_saved":"✅ Piano salvato per {date}.","budget_estimated":"Budget stimato","already_logged":"già registrate","dinner_available":"Cena disponibile","dinner_already_logged":"✅ Cena già registrata: nessun suggerimento necessario.","office_allocated":"Ufficio già allocato","dinner_label":"Cena","lunch_label":"Pranzo","office_lunch_history":"Pranzo ufficio nello storico","suggested_dinner":"Cena suggerita","suggested_lunch":"Pranzo suggerito","no_dinner_near":"Nessuna cena replicabile nello storico abbastanza vicina al target.","no_dinner_history":"Non ho ancora abbastanza cene replicabili nello storico.","no_home_lunch":"Nessun pranzo Casa replicabile disponibile nello storico.","no_dinner":"Nessuna cena replicabile disponibile nello storico.","planning_formula":"Per la pianificazione uso +0 kcal (riposo), +500 kcal (moderatamente attiva), +1000 kcal (attiva). La soglia osservata nel grafico resta: riposo <300 kcal extra, attività intensa ≥800 kcal."})
translations["English"].update({"plan_saved":"✅ Plan saved for {date}.","budget_estimated":"Estimated budget","already_logged":"already logged","dinner_available":"Dinner available","dinner_already_logged":"✅ Dinner already logged: no suggestion needed.","office_allocated":"Office already allocated","dinner_label":"Dinner","lunch_label":"Lunch","office_lunch_history":"Office lunch in history","suggested_dinner":"Suggested dinner","suggested_lunch":"Suggested lunch","no_dinner_near":"No repeatable dinner in your history is close enough to the target.","no_dinner_history":"There are not enough repeatable dinners in your history yet.","no_home_lunch":"No repeatable Home lunch is available in your history.","no_dinner":"No repeatable dinner is available in your history.","planning_formula":"Planning uses +0 kcal (rest), +500 kcal (moderately active), +1000 kcal (active). The chart threshold remains: rest <300 extra kcal, intense activity ≥800 kcal."})
translations["Nederlands"].update({"plan_saved":"✅ Plan opgeslagen voor {date}.","budget_estimated":"Geschat budget","already_logged":"al gelogd","dinner_available":"Beschikbaar voor avondeten","dinner_already_logged":"✅ Avondeten al gelogd: geen suggestie nodig.","office_allocated":"Kantoor al toegewezen","dinner_label":"Avondeten","lunch_label":"Lunch","office_lunch_history":"Kantoorlunch in geschiedenis","suggested_dinner":"Aanbevolen avondeten","suggested_lunch":"Aanbevolen lunch","no_dinner_near":"Geen herhaalbaar avondeten in je geschiedenis ligt dicht genoeg bij het doel.","no_dinner_history":"Er zijn nog niet genoeg herhaalbare avondmaaltijden in je geschiedenis.","no_home_lunch":"Geen herhaalbare Thuis-lunch beschikbaar in je geschiedenis.","no_dinner":"Geen herhaalbaar avondeten beschikbaar in je geschiedenis.","planning_formula":"De planning gebruikt +0 kcal (rust), +500 kcal (matig actief), +1000 kcal (actief). De grafiekdrempel blijft: rust <300 extra kcal, intensief ≥800 kcal."})
translations["Français"].update({"plan_saved":"✅ Plan enregistré pour le {date}.","budget_estimated":"Budget estimé","already_logged":"déjà enregistrées","dinner_available":"Disponible pour le dîner","dinner_already_logged":"✅ Dîner déjà enregistré : aucune suggestion nécessaire.","office_allocated":"Bureau déjà alloué","dinner_label":"Dîner","lunch_label":"Déjeuner","office_lunch_history":"Déjeuner bureau dans l'historique","suggested_dinner":"Dîner suggéré","suggested_lunch":"Déjeuner suggéré","no_dinner_near":"Aucun dîner reproductible de l'historique n'est assez proche de la cible.","no_dinner_history":"Pas encore assez de dîners reproductibles dans l'historique.","no_home_lunch":"Aucun déjeuner Maison reproductible disponible dans l'historique.","no_dinner":"Aucun dîner reproductible disponible dans l'historique.","planning_formula":"La planification utilise +0 kcal (repos), +500 kcal (modérément actif), +1000 kcal (actif). Le seuil du graphique reste : repos <300 kcal supplémentaires, activité intense ≥800 kcal."})


translations["Português"] = dict(translations["English"])
translations["Português"].update({
    "t1": "🚀 Registo",
    "t2": "📊 Resumo",
    "t3": "📈 Peso",
    "t4": "🍳 Receitas",
    "t5": "🏃 Atividade",
    "meal": "Tipo de refeição",
    "meal_name": "Nome da refeição",
    "add_meal": "Adicionar refeição",
    "extra_act": "Atividade extra",
    "extra_cals": "Calorias extra queimadas",
    "insert_weight": "Introduzir peso (kg)",
    "save_weight": "Guardar peso",
    "recipe_name": "Nome da receita",
    "save_recipe": "Guardar receita",
    "recipe_saved": "✅ Receita guardada!",
    "lang_label": "🌐 Idioma",
    "logout": "🚪 Sair",
    "search_food": "🔍 Pesquisar por nome ou código de barras",
    "search_btn": "🚀 Pesquisar",
    "select_recipe": "Selecionar uma receita",
    "no_recipes": "Nenhuma receita guardada.",
    "calc_mode": "Registo baseado em:",
    "per_100g": "Por 100 g",
    "per_portion": "Por porção",
    "qty_label": "Quantidade (g ou porções)",
    "num_portions": "Número de porções",
    "inserted": "✅ Registado",
    "daily_summary": "📊 Resumo diário",
    "summary_date": "📅 Data do resumo",
    "logged_foods": "🍽️ Alimentos registados",
    "no_meals": "Não existem refeições registadas nesta data.",
    "burned_acts": "#### 🏃 Calorias queimadas e atividades",
    "weight_tracking": "⚖️ Registo de peso",
    "log_today_weight": "📥 Registar peso de hoje",
    "update_target": "🎯 Atualizar objetivo",
    "save_target": "Guardar objetivo",
    "target_updated": "✅ Objetivo atualizado!",
    "quick_entries": "⚡ Registos rápidos",
    "saved_entries": "📋 Itens guardados",
    "register_activity": "🏃 Registar atividade e movimento",
    "act_date": "📅 Data",
    "steps_title": "👣 Passos (total)",
    "update_steps": "💾 Atualizar passos",
    "steps_updated": "Passos atualizados!",
    "bike_title": "🚲 Bicicleta (sessão)",
    "bike_min": "Minutos de bicicleta",
    "add_bike": "💾 Adicionar bicicleta",
    "other_act": "🏋️ Outra atividade",
    "activity_label": "Atividade",
    "add_act_btn": "💾 Adicionar",
    "tab1_title": "🍽️ Alimentação e refeições",
    "input_source_lbl": "Fonte de registo",
    "opt_ai": "✨ IA",
    "opt_off": "🔍 Base OpenFood",
    "opt_quick": "🍳 Registo rápido",
    "opt_scan": "📸 Foto com IA",
    "scan_title": "📸 Foto com IA",
    "scan_mode": "Origem da imagem",
    "scan_camera": "📷 Câmara",
    "scan_upload": "🖼️ Galeria / Ficheiro",
    "scan_analyze": "✨ Analisar com IA",
    "scan_analyzing": "A analisar a refeição…",
    "card_kcal_in": "Calorias ingeridas",
    "card_kcal_burn": "Calorias queimadas",
    "card_balance": "Balanço",
    "card_weight": "Peso",
    "status_move_title": "👣 Estado do movimento",
    "weight_forecast_title": "🔮 Previsão do objetivo",
    "meal_breakfast": "Pequeno-almoço",
    "meal_lunch": "Almoço",
    "meal_dinner": "Jantar",
    "meal_snack": "Lanche",
    "cat_home": "Casa",
    "cat_work": "Trabalho",
    "cat_restaurant": "Restaurante",
    "cat_once": "Pontual",
    "day_home": "Trabalho a partir de casa",
    "day_office": "Escritório",
    "day_free": "Dia livre",
    "act_rest": "Descanso",
    "act_moderate": "Moderadamente ativo",
    "act_active": "Ativo",
    "col_activity": "Atividade",
    "col_burned": "Kcal queimadas",
    "save_weight_ui": "💾 Guardar peso",
    "plan_saved": "✅ Plano guardado para {date}.",
    "budget_estimated": "Orçamento estimado",
    "already_logged": "já registadas",
    "dinner_label": "Jantar",
    "lunch_label": "Almoço",
    "suggested_dinner": "Jantar sugerido",
    "suggested_lunch": "Almoço sugerido",
    "period_days": "dias",
    "generic_error": "Erro: {error}",
    "trend": "Projeção",
    "real_weight": "Peso real",
})

MEAL_TYPE_KEYS = {"Colazione": "meal_breakfast", "Pranzo": "meal_lunch", "Cena": "meal_dinner", "Snack": "meal_snack"}
CATEGORY_KEYS = {"Casa": "cat_home", "Lavoro": "cat_work", "Ristorante": "cat_restaurant", "Una-tantum": "cat_once"}
DAY_TYPE_KEYS = {"Lavoro da casa": "day_home", "Ufficio": "day_office", "Giornata libera": "day_free"}
ACTIVITY_PLAN_KEYS = {"Riposo": "act_rest", "Moderatamente attiva": "act_moderate", "Attiva": "act_active"}

def _tr_value(mapping, value):
    lang = st.session_state.get("lang_selector", "Italiano")
    lang_t = translations.get(lang, translations["Italiano"])
    return lang_t.get(mapping.get(value, ""), value)

def tr_meal_type(value): return _tr_value(MEAL_TYPE_KEYS, value)
def tr_category(value): return _tr_value(CATEGORY_KEYS, value)
def tr_day_type(value): return _tr_value(DAY_TYPE_KEYS, value)
def tr_activity_plan(value): return _tr_value(ACTIVITY_PLAN_KEYS, value)

with st.sidebar:
    # --- LOGO / PERSONALITY MODE ---
    if is_zero_mode():
        st.sidebar.image(str(ZERO_LOGO_FILE), use_container_width=True)
    else:
        st.sidebar.image(str(SIDEBAR_LOGO_FILE), use_container_width=True)

    _zero_toggle_i18n = {
        "Italiano": "ZERO MODE",
        "English": "ZERO MODE",
        "Nederlands": "ZERO MODE",
        "Français": "ZERO MODE",
    }

    st.markdown(
        """
        <style>
        /* ZERO MODE toggle label — always readable on the dark sidebar. */
        .st-key-zero_mode_sidebar_toggle label,
        .st-key-zero_mode_sidebar_toggle label p,
        .st-key-zero_mode_sidebar_toggle label span,
        div[data-testid="stSidebar"] [data-testid="stToggle"] label,
        div[data-testid="stSidebar"] [data-testid="stToggle"] label p,
        div[data-testid="stSidebar"] [data-testid="stToggle"] label span {
            color:#FFFFFF !important;
            -webkit-text-fill-color:#FFFFFF !important;
            font-weight:850 !important;
            opacity:1 !important;
        }

        .st-key-zero_mode_sidebar_toggle {
            margin-top:.25rem !important;
            margin-bottom:.35rem !important;
        }

        /* Sidebar help icon must remain visible on the dark sidebar. */
        [data-testid="stSidebar"] [data-testid="stTooltipHoverTarget"],
        [data-testid="stSidebar"] [data-testid="stTooltipHoverTarget"] *,
        [data-testid="stSidebar"] [data-testid="stTooltipHoverTarget"] svg,
        [data-testid="stSidebar"] [data-testid="stTooltipHoverTarget"] path {
            color:#FFFFFF !important;
            fill:#FFFFFF !important;
            stroke:#FFFFFF !important;
            opacity:1 !important;
        }
        </style>
        """,
        unsafe_allow_html=True,
    )

    _zero_widget_value = st.toggle(
        _zero_toggle_i18n.get(
            st.session_state.get("lang_selector", "Italiano"),
            "ZERO",
        ),
        value=is_zero_mode(),
        key="zero_mode_sidebar_toggle",
        help="Stessa SanoSync. Meno zucchero nel tono.",
    )

    if _zero_widget_value != is_zero_mode():
        try:
            _zero_meta = dict(
                getattr(
                    st.session_state.get("user"),
                    "user_metadata",
                    {},
                )
                or {}
            )
            _zero_meta["zero_mode_enabled"] = bool(_zero_widget_value)

            _zero_update = supabase.auth.update_user(
                {"data": _zero_meta}
            )
            if getattr(_zero_update, "user", None):
                st.session_state["user"] = _zero_update.user

            queue_ui_sound(
                "zero_mode_on" if _zero_widget_value else "zero_mode_off",
                zero_mode=False,
            )
            st.session_state["zero_mode_enabled"] = bool(
                _zero_widget_value
            )
            st.session_state.pop("ai_coach_state", None)
            st.session_state.pop("ai_coach_message", None)
            st.rerun()
        except Exception as exc:
            st.error(f"ZERO mode: {exc}")

    render_pending_ui_sound()

    if "lang_selector" not in st.session_state:
        st.session_state["lang_selector"] = "Italiano"

    current_lang = st.session_state["lang_selector"]
    t = translations[current_lang]

    _ui_extra = {
        "Italiano": {
            "meal_placeholder": "Seleziona un pasto...",
            "activity": "Attività",
            "bmr_base": "BMR (Base)",
            "bike": "Bici",
            "steps_est": "Passi (Stima)",
            "over_target": "⚠️ Sei oltre il target da deficit di circa {kcal} kcal.",
            "end_day": "🔮 Fine giornata: ~{kcal} kcal se non registri altra attività.",
            "details": "Dettagli:",
            "deficit": "deficit",
            "surplus": "surplus",
            "extra": "extra",
            "movement_status": "👣 Status Movimento",
            "activity_logged": "🏋️ Attività registrata",
            "activity_logged_note": "🌟 Ottimo! Hai completato un'attività fisica strutturata oggi.",
            "extra_burned": "🔥 Kcal bruciate extra",
            "extra_burned_note": "Somma delle calorie registrate nelle attività della giornata selezionata.",
            "steps": "👣 Passi",
            "steps_note": "Calorie attribuite ai passi.",
            "padel_note": "Calorie registrate come Padel.",
            "bike_note": "Somma di Bici ed E-Bike.",
            "total_steps": "Totale passi",
            "add_bike": "💾 Aggiungi Bici",
            "notes_ph": "Es. senza lattosio, marca preferita, preparazione, condimenti...",
            "can_eat_more": "🎯 Puoi mangiare ancora {kcal} kcal per chiudere la giornata con circa {target} kcal di deficit.",
            "exact_target": "🎯 Sei esattamente sul target per un deficit di circa {target} kcal.",
            "day_total": "🔥 Totale giornata: {kcal} kcal.",
            "no_extra": "Nessuna caloria extra registrata per questa giornata.",
            "other_activities": "Altre attività",
            "bike_and_ebike": "🚲 Bici & E-Bike",
            "bike_minutes": "Minuti Bici",
            "burned_kcal_field": "Kcal bruciate",
            "enter_one_minute": "Inserisci almeno 1 minuto.",
            "bike_added": "✅ Aggiunti {minutes} min di {activity} ({kcal} kcal)!",
            "steps_updated_toast": "✅ Passi aggiornati! ({kcal} kcal)",
            "activity_saved": "✅ {activity} registrato con successo! ({kcal} kcal)",
            "step_word": "passi",
            "activity_gym": "Palestra",
            "activity_swim": "Nuoto",
            "activity_other": "Altro"
        },
        "English": {
            "meal_placeholder": "Select a meal...",
            "activity": "Activity",
            "bmr_base": "BMR (Base)",
            "bike": "Bike",
            "steps_est": "Steps (Estimate)",
            "over_target": "⚠️ You are about {kcal} kcal over your deficit target.",
            "end_day": "🔮 End of day: ~{kcal} kcal if you log no more activity.",
            "details": "Details:",
            "deficit": "deficit",
            "surplus": "surplus",
            "extra": "extra",
            "movement_status": "👣 Movement Status",
            "activity_logged": "🏋️ Activity logged",
            "activity_logged_note": "🌟 Great! You completed a structured physical activity today.",
            "extra_burned": "🔥 Extra kcal burned",
            "extra_burned_note": "Total calories logged from activities on the selected day.",
            "steps": "👣 Steps",
            "steps_note": "Calories attributed to steps.",
            "padel_note": "Calories logged as Padel.",
            "bike_note": "Total from Bike and E-Bike.",
            "total_steps": "Total steps",
            "add_bike": "💾 Add Bike",
            "notes_ph": "E.g. lactose-free, preferred brand, preparation, seasonings...",
            "can_eat_more": "🎯 You can eat another {kcal} kcal and finish the day at about a {target} kcal deficit.",
            "exact_target": "🎯 You are exactly on target for about a {target} kcal deficit.",
            "day_total": "🔥 Day total: {kcal} kcal.",
            "no_extra": "No extra calories logged for this day.",
            "other_activities": "Other activities",
            "bike_and_ebike": "🚲 Bike & E-Bike",
            "bike_minutes": "Bike minutes",
            "burned_kcal_field": "Kcal burned",
            "enter_one_minute": "Enter at least 1 minute.",
            "bike_added": "✅ Added {minutes} min of {activity} ({kcal} kcal)!",
            "steps_updated_toast": "✅ Steps updated! ({kcal} kcal)",
            "activity_saved": "✅ {activity} logged successfully! ({kcal} kcal)",
            "step_word": "steps",
            "activity_gym": "Gym",
            "activity_swim": "Swimming",
            "activity_other": "Other"
        },
        "Nederlands": {
            "meal_placeholder": "Selecteer een maaltijd...",
            "activity": "Activiteit",
            "bmr_base": "BMR (Basis)",
            "bike": "Fiets",
            "steps_est": "Stappen (Schatting)",
            "over_target": "⚠️ Je zit ongeveer {kcal} kcal boven je tekortdoel.",
            "end_day": "🔮 Einde van de dag: ~{kcal} kcal als je geen extra activiteit registreert.",
            "details": "Details:",
            "deficit": "tekort",
            "surplus": "overschot",
            "extra": "extra",
            "movement_status": "👣 Bewegingsstatus",
            "activity_logged": "🏋️ Activiteit geregistreerd",
            "activity_logged_note": "🌟 Goed gedaan! Je hebt vandaag een gestructureerde fysieke activiteit voltooid.",
            "extra_burned": "🔥 Extra kcal verbrand",
            "extra_burned_note": "Totaal van de calorieën uit activiteiten op de geselecteerde dag.",
            "steps": "👣 Stappen",
            "steps_note": "Calorieën toegeschreven aan stappen.",
            "padel_note": "Calorieën geregistreerd als padel.",
            "bike_note": "Totaal van fiets en e-bike.",
            "total_steps": "Totaal stappen",
            "add_bike": "💾 Fiets toevoegen",
            "notes_ph": "Bijv. lactosevrij, voorkeursmerk, bereiding, kruiden...",
            "can_eat_more": "🎯 Je kunt nog {kcal} kcal eten en de dag afsluiten met ongeveer {target} kcal tekort.",
            "exact_target": "🎯 Je zit precies op je doel voor ongeveer {target} kcal tekort.",
            "day_total": "🔥 Dagtotaal: {kcal} kcal.",
            "no_extra": "Geen extra calorieën geregistreerd voor deze dag.",
            "other_activities": "Andere activiteiten",
            "bike_and_ebike": "🚲 Fiets & E-bike",
            "bike_minutes": "Minuten fietsen",
            "burned_kcal_field": "Verbrande kcal",
            "enter_one_minute": "Voer minstens 1 minuut in.",
            "bike_added": "✅ {minutes} min {activity} toegevoegd ({kcal} kcal)!",
            "steps_updated_toast": "✅ Stappen bijgewerkt! ({kcal} kcal)",
            "activity_saved": "✅ {activity} succesvol geregistreerd! ({kcal} kcal)",
            "step_word": "stappen",
            "activity_gym": "Sportschool",
            "activity_swim": "Zwemmen",
            "activity_other": "Overig"
        },
        "Français": {
            "meal_placeholder": "Sélectionnez un repas...",
            "activity": "Activité",
            "bmr_base": "BMR (Base)",
            "bike": "Vélo",
            "steps_est": "Pas (Estimation)",
            "over_target": "⚠️ Vous dépassez votre objectif de déficit d’environ {kcal} kcal.",
            "end_day": "🔮 Fin de journée : ~{kcal} kcal si vous n’enregistrez aucune autre activité.",
            "details": "Détails :",
            "deficit": "déficit",
            "surplus": "surplus",
            "extra": "extra",
            "movement_status": "👣 État des mouvements",
            "activity_logged": "🏋️ Activité enregistrée",
            "activity_logged_note": "🌟 Bravo ! Vous avez effectué une activité physique structurée aujourd’hui.",
            "extra_burned": "🔥 Kcal supplémentaires brûlées",
            "extra_burned_note": "Total des calories enregistrées dans les activités du jour sélectionné.",
            "steps": "👣 Pas",
            "steps_note": "Calories attribuées aux pas.",
            "padel_note": "Calories enregistrées comme padel.",
            "bike_note": "Total Vélo et Vélo électrique.",
            "total_steps": "Total des pas",
            "add_bike": "💾 Ajouter le vélo",
            "notes_ph": "Ex. sans lactose, marque préférée, préparation, assaisonnements...",
            "can_eat_more": "🎯 Vous pouvez encore manger {kcal} kcal et terminer la journée avec environ {target} kcal de déficit.",
            "exact_target": "🎯 Vous êtes exactement sur l’objectif pour un déficit d’environ {target} kcal.",
            "day_total": "🔥 Total de la journée : {kcal} kcal.",
            "no_extra": "Aucune calorie supplémentaire enregistrée pour cette journée.",
            "other_activities": "Autres activités",
            "bike_and_ebike": "🚲 Vélo & Vélo électrique",
            "bike_minutes": "Minutes de vélo",
            "burned_kcal_field": "Kcal brûlées",
            "enter_one_minute": "Saisissez au moins 1 minute.",
            "bike_added": "✅ {minutes} min de {activity} ajoutées ({kcal} kcal) !",
            "steps_updated_toast": "✅ Pas mis à jour ! ({kcal} kcal)",
            "activity_saved": "✅ {activity} enregistré avec succès ! ({kcal} kcal)",
            "step_word": "pas",
            "activity_gym": "Salle de sport",
            "activity_swim": "Natation",
            "activity_other": "Autre"
        },
    }
    _ui_extra["Português"] = {
        **_ui_extra["English"],
        "total_steps": "Total de passos",
        "add_bike": "💾 Adicionar bicicleta",
        "other_activities": "Outras atividades",
        "bike_and_ebike": "🚲 Bicicleta e bicicleta elétrica",
        "bike_minutes": "Minutos de bicicleta",
        "burned_kcal_field": "Kcal queimadas",
        "enter_one_minute": "Introduza pelo menos 1 minuto.",
        "step_word": "passos",
        "activity_gym": "Ginásio",
        "activity_swim": "Natação",
        "activity_other": "Outra",
    }
    ZERO_COPY["Português"] = {}

    ux = _ui_extra.get(current_lang, _ui_extra["Italiano"])

    # ZERO changes remarks, not functional terminology.
    if is_zero_mode():
        _zc = ZERO_COPY.get(
            current_lang,
            ZERO_COPY["Italiano"],
        )
        t = dict(t)
        t.update(_zc.get("t", {}))
        ux = dict(ux)
        ux.update(_zc.get("ux", {}))

    # ------------------------------------------------------------------
    # FORCED APP APPEARANCE
    # SanoSync content remains Standard=Light and ZERO=Black.
    # Streamlit's native Appearance menu is still available in the top-right
    # Main Menu for browser/chrome preferences and troubleshooting.
    # ------------------------------------------------------------------
    if is_zero_mode():
        st.markdown(
            """
            <style>
            /* ZERO: force a black app even when Streamlit is set to Light. */
            html, body,
            [data-testid="stApp"],
            [data-testid="stAppViewContainer"],
            [data-testid="stMain"],
            [data-testid="stMainBlockContainer"] {
                background:#050505 !important;
                background-color:#050505 !important;
                color:#F5F5F5 !important;
            }

            [data-testid="stHeader"] {
                background:#050505 !important;
                border-bottom-color:#242424 !important;
            }

            /* Keep sidebar as part of the black ZERO identity. */
            [data-testid="stSidebar"] {
                background:
                    radial-gradient(circle at 50% 0%, rgba(225,6,0,.14), transparent 30%),
                    linear-gradient(180deg,#000000,#080808) !important;
                color:#F5F5F5 !important;
            }

            /* Generic text outside special components. */
            [data-testid="stAppViewContainer"] p,
            [data-testid="stAppViewContainer"] label,
            [data-testid="stAppViewContainer"] h1,
            [data-testid="stAppViewContainer"] h2,
            [data-testid="stAppViewContainer"] h3,
            [data-testid="stAppViewContainer"] h4,
            [data-testid="stAppViewContainer"] h5,
            [data-testid="stAppViewContainer"] h6 {
                color:#F5F5F5 !important;
                -webkit-text-fill-color:#F5F5F5 !important;
            }

            /* Streamlit inputs / controls */
            [data-baseweb="input"] > div,
            [data-baseweb="base-input"],
            [data-baseweb="textarea"] > div,
            [data-baseweb="select"] > div,
            [data-testid="stTextInput"] input,
            [data-testid="stTextArea"] textarea,
            [data-testid="stNumberInput"] input,
            [data-testid="stDateInput"] input {
                background:#171717 !important;
                background-color:#171717 !important;
                color:#F7F7F7 !important;
                -webkit-text-fill-color:#F7F7F7 !important;
                border-color:#666 !important;
            }

            /* Menus and dropdown lists rendered in portals */
            [data-baseweb="menu"],
            [data-baseweb="popover"] > div,
            [role="listbox"] {
                background:#111111 !important;
                color:#F5F5F5 !important;
                border-color:#555 !important;
            }

            [role="option"],
            [role="option"] * {
                color:#F5F5F5 !important;
                -webkit-text-fill-color:#F5F5F5 !important;
            }

            [role="option"][aria-selected="true"] {
                background:#5D0A08 !important;
            }

            /* Buttons */
            [data-testid="stAppViewContainer"] .stButton > button,
            [data-testid="stAppViewContainer"] [data-testid="stBaseButton-secondary"] {
                background:#101010 !important;
                color:#F7F7F7 !important;
                border-color:#B91C1C !important;
            }

            [data-testid="stAppViewContainer"] [data-testid="stBaseButton-primary"] {
                background:linear-gradient(135deg,#E10600,#990000) !important;
                color:#FFF !important;
                border-color:#FF2A20 !important;
            }

            /* Expanders */
            [data-testid="stExpander"],
            details[data-testid="stExpander"],
            [data-testid="stExpanderDetails"] {
                background:#0C0C0C !important;
                color:#F5F5F5 !important;
                border-color:#555 !important;
            }

            [data-testid="stExpander"] summary {
                background:#111111 !important;
                color:#F5F5F5 !important;
            }

            /* Tables / dataframes */
            [data-testid="stTable"],
            [data-testid="stDataFrame"] {
                background:#090909 !important;
                color:#F5F5F5 !important;
                border-color:#777 !important;
            }

            /* Streamlit top menu remains legible */
            [data-testid="stToolbar"],
            [data-testid="stDecoration"],
            [data-testid="stStatusWidget"] {
                color:#F5F5F5 !important;
            }
            </style>
            """,
            unsafe_allow_html=True,
        )
    else:
        st.markdown(
            """
            <style>
            /* STANDARD: force Light rendering even when Streamlit is set to Dark. */
            html, body,
            [data-testid="stApp"],
            [data-testid="stAppViewContainer"],
            [data-testid="stMain"],
            [data-testid="stMainBlockContainer"] {
                background:#FFFFFF !important;
                background-color:#FFFFFF !important;
                color:#1A2942 !important;
            }

            [data-testid="stHeader"] {
                background:#FFFFFF !important;
                border-bottom-color:#ECEEF2 !important;
            }

            /* Standard sidebar intentionally stays dark navy as part of the brand. */
            [data-testid="stSidebar"] {
                background:
                    radial-gradient(circle at 100% 0%, rgba(255,139,139,.13), transparent 34%),
                    linear-gradient(180deg,#192E49,#182A43) !important;
                color:#FFFFFF !important;
            }

            [data-testid="stSidebar"] p,
            [data-testid="stSidebar"] label,
            [data-testid="stSidebar"] span,
            [data-testid="stSidebar"] h1,
            [data-testid="stSidebar"] h2,
            [data-testid="stSidebar"] h3,
            [data-testid="stSidebar"] h4 {
                color:#FFFFFF !important;
                -webkit-text-fill-color:#FFFFFF !important;
            }

            /* Sidebar widget labels stay white even when Standard forces Light. */
            [data-testid="stSidebar"] .st-key-zero_mode_sidebar_toggle *,
            [data-testid="stSidebar"] .st-key-zero_mode_sidebar_toggle label,
            [data-testid="stSidebar"] .st-key-zero_mode_sidebar_toggle p {
                color:#FFFFFF !important;
                -webkit-text-fill-color:#FFFFFF !important;
                opacity:1 !important;
            }

            /* Main text must never inherit Streamlit Dark-mode white-on-dark assumptions. */
            [data-testid="stAppViewContainer"] p,
            [data-testid="stAppViewContainer"] label,
            [data-testid="stAppViewContainer"] h1,
            [data-testid="stAppViewContainer"] h2,
            [data-testid="stAppViewContainer"] h3,
            [data-testid="stAppViewContainer"] h4,
            [data-testid="stAppViewContainer"] h5,
            [data-testid="stAppViewContainer"] h6 {
                color:#1A2942 !important;
                -webkit-text-fill-color:#1A2942 !important;
            }

            [data-testid="stCaptionContainer"],
            [data-testid="stCaptionContainer"] * {
                color:#7B7E89 !important;
                -webkit-text-fill-color:#7B7E89 !important;
            }

            /* Inputs */
            [data-baseweb="input"] > div,
            [data-baseweb="base-input"],
            [data-baseweb="textarea"] > div,
            [data-baseweb="select"] > div,
            [data-testid="stTextInput"] input,
            [data-testid="stTextArea"] textarea,
            [data-testid="stNumberInput"] input,
            [data-testid="stDateInput"] input {
                background:#F1F3F7 !important;
                background-color:#F1F3F7 !important;
                color:#292D39 !important;
                -webkit-text-fill-color:#292D39 !important;
                border-color:#E1E4EA !important;
            }

            input::placeholder,
            textarea::placeholder {
                color:#858995 !important;
                -webkit-text-fill-color:#858995 !important;
                opacity:1 !important;
            }

            /* Dropdown menus / popovers outside the main app tree */
            [data-baseweb="menu"],
            [data-baseweb="popover"] > div,
            [role="listbox"] {
                background:#FFFFFF !important;
                color:#292D39 !important;
                border-color:#E0E3E9 !important;
            }

            [role="option"],
            [role="option"] * {
                color:#292D39 !important;
                -webkit-text-fill-color:#292D39 !important;
            }

            [role="option"][aria-selected="true"] {
                background:#FFF0F0 !important;
            }

            /* Buttons */
            [data-testid="stAppViewContainer"] .stButton > button,
            [data-testid="stAppViewContainer"] [data-testid="stBaseButton-secondary"] {
                background:#FFFFFF !important;
                color:#192E49 !important;
                border-color:#FF8B8B !important;
            }

            [data-testid="stAppViewContainer"] [data-testid="stBaseButton-primary"] {
                background:#FF8588 !important;
                color:#FFFFFF !important;
                border-color:#FF777B !important;
            }

            /* Expanders */
            [data-testid="stExpander"],
            details[data-testid="stExpander"],
            [data-testid="stExpanderDetails"] {
                background:#FFFFFF !important;
                color:#1A2942 !important;
                border-color:#D9DCE2 !important;
            }

            [data-testid="stExpander"] summary {
                background:#FFFFFF !important;
                color:#1A2942 !important;
            }

            /* Tables / dataframes */
            [data-testid="stTable"],
            [data-testid="stDataFrame"] {
                background:#FFFFFF !important;
                color:#1A2942 !important;
                border-color:#D9DCE2 !important;
            }

            /* Toolbar stays visible on the forced white header */
            [data-testid="stToolbar"],
            [data-testid="stToolbar"] *,
            [data-testid="stStatusWidget"],
            [data-testid="stStatusWidget"] * {
                color:#292D39 !important;
                -webkit-text-fill-color:#292D39 !important;
            }
            </style>
            """,
            unsafe_allow_html=True,
        )


    st.markdown(
        f'<div style="text-align:center;color:#FFB4B4;font-weight:900;font-size:1rem;letter-spacing:.01em;margin:-.15rem 0 .55rem 0;">{html.escape(t["slogan"])}</div>',
        unsafe_allow_html=True,
    )
    st.markdown("---")
    
    pages_map = {
        t["t1"]: "t1",
        t["t2"]: "t2",
        t["t3"]: "t3",
        t["t4"]: "t4",
        t["t5"]: "t5"
    }
    
    if "current_page_id" not in st.session_state:
        st.session_state.current_page_id = "t1"

    for page_name, page_id in pages_map.items():
        is_active = (st.session_state.current_page_id == page_id)
        if st.button(
            page_name,
            key=f"nav_{page_id}",
            use_container_width=True,
            type="primary" if is_active else "secondary",
        ):
            st.session_state.current_page_id = page_id

            # Una tab della sidebar è sempre una navigazione fuori da Settings.
            st.session_state["show_personal_settings"] = False
            st.session_state.pop("settings_language_live", None)
            st.session_state.pop("profile_menu_language", None)
            st.session_state["_collapse_sidebar_mobile_next_run"] = True
            st.rerun()

    if st.session_state.pop("_collapse_sidebar_mobile_next_run", False):
        st.components.v1.html(
            """
            <script>
            (() => {
              try {
                const w = window.parent;
                if (w.innerWidth > 800) return;
                const d = w.document;
                const selectors = [
                  '[data-testid="stSidebarCollapseButton"] button',
                  'button[aria-label="Close sidebar"]',
                  'button[aria-label="Collapse sidebar"]'
                ];
                for (const sel of selectors) {
                  const btn = d.querySelector(sel);
                  if (btn) { setTimeout(() => btn.click(), 100); break; }
                }
              } catch (e) {}
            })();
            </script>
            """,
            height=0,
            width=0,
        )

    selected_page_id = st.session_state.current_page_id
    selected_page = t[selected_page_id]


    # --------------------------------------------------------------
    # Kcal rimanenti: budget FINALE della giornata.
    # Formula = BMR completo + attività registrata oggi - kcal ingerite.
    # Non usa il BMR maturato "finora" e non sottrae il deficit target.
    # --------------------------------------------------------------
    _budget_i18n = {
        "Italiano": {
            "label": "Kcal rimanenti oggi",
            "eaten": "ingerite",
            "budget": "budget finale","protein":"Proteine oggi","protein_goal":"goal",
        },
        "English": {
            "label": "Kcal remaining today",
            "eaten": "eaten",
            "budget": "end-of-day budget","protein":"Protein today","protein_goal":"goal",
        },
        "Nederlands": {
            "label": "Kcal over vandaag",
            "eaten": "gegeten",
            "budget": "dagbudget","protein":"Eiwit vandaag","protein_goal":"doel",
        },
        "Français": {
            "label": "Kcal restantes aujourd'hui",
            "eaten": "consommées",
            "budget": "budget fin de journée","protein":"Protéines aujourd’hui","protein_goal":"objectif",
        },
    }
    _bi = _budget_i18n.get(current_lang, _budget_i18n["Italiano"])

    try:
        _today_str = str(date.today())
        _today_totals = get_daily_totals(_today_str)
        _today_meals = _today_totals["meals"]
        _today_acts = _today_totals["activities"]
        _today_eaten = _today_totals["calories"]
        _today_activity = _today_totals["activity"]

        _end_day_budget = max(
            0.0,
            float(user_bmr or 0) + _today_activity,
        )
        _remaining_today = _end_day_budget - _today_eaten

        _progress_pct = (
            min(100.0, max(0.0, (_today_eaten / _end_day_budget) * 100.0))
            if _end_day_budget > 0
            else 0.0
        )

        _remaining_display = int(round(_remaining_today))
        _budget_display = int(round(_end_day_budget))
        _eaten_display = int(round(_today_eaten))

        _protein_eaten = sum(
            _safe_float(row.get("protein"))
            for row in _today_meals
        )

        st.markdown(
            f"""
            <div class="sano-budget-card">
                <div class="sano-budget-label">{html.escape(_bi["label"])}</div>
                <div class="sano-budget-value"><span>{_remaining_display}</span> kcal</div>
                <div class="sano-budget-track">
                    <div class="sano-budget-fill" style="width:{_progress_pct:.1f}%"></div>
                </div>
                <div class="sano-budget-meta">
                    <span>{_eaten_display} kcal {_bi["eaten"]}</span>
                    <span>{_budget_display} kcal {_bi["budget"]}</span>
                </div>
            </div>
            """,
            unsafe_allow_html=True,
        )
        if user_protein_goal_enabled and user_protein_goal_g > 0:
            _protein_pct = min(
                100.0,
                max(
                    0.0,
                    (_protein_eaten / user_protein_goal_g) * 100.0,
                ),
            )
            st.markdown(
                f"""
                <div class="sano-budget-card">
                    <div class="sano-budget-label">{html.escape(_bi["protein"])}</div>
                    <div class="sano-budget-value"><span>{_protein_eaten:.1f}</span> g</div>
                    <div class="sano-budget-track"><div class="sano-budget-fill" style="width:{_protein_pct:.1f}%"></div></div>
                    <div class="sano-budget-meta">
                        <span>{_protein_eaten:.1f} g</span>
                        <span>{user_protein_goal_g:.0f} g {_bi["protein_goal"]}</span>
                    </div>
                </div>
                """, unsafe_allow_html=True,
            )

        _coach_message = get_sanosync_coach_message_cached(
            language=current_lang,
            first_name=first_name,
            maintenance_budget=_end_day_budget,
            calories_eaten=_today_eaten,
            deficit_target=_safe_float(user_deficit_target_kcal),
            protein_eaten=(
                _protein_eaten
                if user_protein_goal_enabled
                and user_protein_goal_g > 0
                else None
            ),
            protein_goal=(
                user_protein_goal_g
                if user_protein_goal_enabled
                and user_protein_goal_g > 0
                else None
            ),
        )
        render_sanosync_coach_card(
            _coach_message,
            current_lang,
        )

    except Exception as _budget_exc:
        print(f"Sidebar budget error: {_budget_exc}")

    st.markdown("---")
# ==============================================================================
# PERSONAL SETTINGS — linked from profile image
# ==============================================================================
SETTINGS_I18N = {
    "Italiano": {
        "title": "👤 Profilo",
        "subtitle": "Il tuo profilo SanoSync, preferenze e obiettivi.",
        "back": "← Torna all'app",
        "account": "Dati personali",
        "email": "Email",
        "name": "Nome",
        "gender": "Genere",
        "male": "Uomo",
        "female": "Donna",
        "birth": "Data di nascita",
        "height": "Altezza (cm)",
        "current_weight": "Peso attuale (kg)",
        "target_weight": "Peso obiettivo (kg)",
        "language": "🌐 Lingua",
        "deficit_title": "🎯 Obiettivo calorico",
        "deficit_speed": "Velocità di dimagrimento",
        "deficit_field": "Deficit calorico giornaliero (kcal)",
        "save": "💾 Salva impostazioni",
        "saved": "✅ Impostazioni aggiornate.",
        "error": "Errore durante il salvataggio: {error}",
        "hint": "La foto profilo viene gestita dal provider di accesso (es. Google/Facebook).",
        "office_title":"🏢 Pranzo in ufficio","office_enabled":"Mostra funzioni e pasti da ufficio?","office_no":"No","office_yes":"Sì","protein_title": "🥩 Goal Proteico",
        "protein_enabled": "Vuoi usare un goal proteico giornaliero?",
        "protein_no": "No",
        "protein_yes": "Sì",
        "protein_g": "Goal proteico giornaliero (g)",
        "mode_title": "🎨 Modalità predefinita",
        "mode_label": "Quale versione vuoi trovare attiva quando accedi?",
        "mode_standard": "SanoSync Standard",
        "mode_zero": "SanoSync ZERO MODE",
        "mode_help": "La scelta viene salvata nel profilo. Il toggle nella sidebar può comunque cambiare modalità durante la sessione.",
    },
    "English": {
        "title": "👤 Profile",
        "subtitle": "Your SanoSync profile, preferences and goals.",
        "back": "← Back to the app",
        "account": "Personal details",
        "email": "Email",
        "name": "Name",
        "gender": "Gender",
        "male": "Male",
        "female": "Female",
        "birth": "Date of birth",
        "height": "Height (cm)",
        "current_weight": "Current weight (kg)",
        "target_weight": "Target weight (kg)",
        "language": "🌐 Language",
        "deficit_title": "🎯 Calorie target",
        "deficit_speed": "Weight-loss speed",
        "deficit_field": "Daily calorie deficit (kcal)",
        "save": "💾 Save settings",
        "saved": "✅ Settings updated.",
        "error": "Error while saving: {error}",
        "hint": "Your profile picture is managed by your sign-in provider (e.g. Google/Facebook).",
        "office_title":"🏢 Office lunch","office_enabled":"Show office meal and planning features?","office_no":"No","office_yes":"Yes","protein_title": "🥩 Protein Goal",
        "protein_enabled": "Use a daily protein goal?",
        "protein_no": "No",
        "protein_yes": "Yes",
        "protein_g": "Daily protein goal (g)",
        "mode_title": "🎨 Default mode",
        "mode_label": "Which version should be active when you sign in?",
        "mode_standard": "SanoSync Standard",
        "mode_zero": "SanoSync ZERO MODE",
        "mode_help": "This choice is saved to your profile. You can still switch modes during a session from the sidebar toggle.",
    },
    "Nederlands": {
        "title": "👤 Profiel",
        "subtitle": "Je SanoSync-profiel, voorkeuren en doelen.",
        "back": "← Terug naar de app",
        "account": "Persoonlijke gegevens",
        "email": "E-mail",
        "name": "Naam",
        "gender": "Geslacht",
        "male": "Man",
        "female": "Vrouw",
        "birth": "Geboortedatum",
        "height": "Lengte (cm)",
        "current_weight": "Huidig gewicht (kg)",
        "target_weight": "Streefgewicht (kg)",
        "language": "🌐 Taal",
        "deficit_title": "🎯 Caloriedoel",
        "deficit_speed": "Snelheid van gewichtsverlies",
        "deficit_field": "Dagelijks calorietekort (kcal)",
        "save": "💾 Instellingen opslaan",
        "saved": "✅ Instellingen bijgewerkt.",
        "error": "Fout bij opslaan: {error}",
        "hint": "Je profielfoto wordt beheerd door je inlogprovider (bijv. Google/Facebook).",
        "office_title":"🏢 Lunch op kantoor","office_enabled":"Kantoorfuncties en maaltijden tonen?","office_no":"Nee","office_yes":"Ja","protein_title": "🥩 Eiwitdoel",
        "protein_enabled": "Een dagelijks eiwitdoel gebruiken?",
        "protein_no": "Nee",
        "protein_yes": "Ja",
        "protein_g": "Dagelijks eiwitdoel (g)",
        "mode_title": "🎨 Standaardmodus",
        "mode_label": "Welke versie moet actief zijn wanneer je inlogt?",
        "mode_standard": "SanoSync Standard",
        "mode_zero": "SanoSync ZERO MODE",
        "mode_help": "Deze keuze wordt in je profiel opgeslagen. Tijdens een sessie kun je nog steeds wisselen via de toggle in de zijbalk.",
    },
    "Français": {
        "title": "👤 Profil",
        "subtitle": "Votre profil SanoSync, vos préférences et vos objectifs.",
        "back": "← Retour à l'application",
        "account": "Informations personnelles",
        "email": "E-mail",
        "name": "Nom",
        "gender": "Sexe",
        "male": "Homme",
        "female": "Femme",
        "birth": "Date de naissance",
        "height": "Taille (cm)",
        "current_weight": "Poids actuel (kg)",
        "target_weight": "Poids cible (kg)",
        "language": "🌐 Langue",
        "deficit_title": "🎯 Objectif calorique",
        "deficit_speed": "Vitesse de perte de poids",
        "deficit_field": "Déficit calorique quotidien (kcal)",
        "save": "💾 Enregistrer les paramètres",
        "saved": "✅ Paramètres mis à jour.",
        "error": "Erreur lors de l'enregistrement : {error}",
        "hint": "Votre photo de profil est gérée par votre fournisseur de connexion (ex. Google/Facebook).",
        "office_title":"🏢 Déjeuner au bureau","office_enabled":"Afficher les fonctions et repas de bureau ?","office_no":"Non","office_yes":"Oui","protein_title": "🥩 Objectif protéique",
        "protein_enabled": "Utiliser un objectif quotidien de protéines ?",
        "protein_no": "Non",
        "protein_yes": "Oui",
        "protein_g": "Objectif quotidien de protéines (g)",
        "mode_title": "🎨 Mode par défaut",
        "mode_label": "Quelle version doit être active lorsque vous vous connectez ?",
        "mode_standard": "SanoSync Standard",
        "mode_zero": "SanoSync ZERO MODE",
        "mode_help": "Ce choix est enregistré dans votre profil. Le bouton de la barre latérale permet toujours de changer de mode pendant la session.",
    },
}




SETTINGS_I18N["Português"] = {
    **SETTINGS_I18N["English"],
    "title": "👤 Perfil",
    "subtitle": "O seu perfil SanoSync, preferências e objetivos.",
    "back": "← Voltar à aplicação",
    "account": "Dados pessoais",
    "email": "E-mail",
    "name": "Nome",
    "gender": "Sexo",
    "male": "Homem",
    "female": "Mulher",
    "birth": "Data de nascimento",
    "height": "Altura (cm)",
    "current_weight": "Peso atual (kg)",
    "target_weight": "Peso objetivo (kg)",
    "language": "🌐 Idioma",
    "deficit_title": "🎯 Objetivo calórico",
    "deficit_speed": "Velocidade de perda de peso",
    "deficit_field": "Défice calórico diário (kcal)",
    "save": "💾 Guardar definições",
    "saved": "✅ Definições atualizadas.",
    "error": "Erro ao guardar: {error}",
    "office_title": "🏢 Almoço no escritório",
    "office_enabled": "Mostrar refeições e funcionalidades de planeamento do escritório?",
    "office_no": "Não",
    "office_yes": "Sim",
    "protein_title": "🥩 Objetivo de proteína",
    "protein_enabled": "Usar um objetivo diário de proteína?",
    "protein_no": "Não",
    "protein_yes": "Sim",
    "protein_g": "Objetivo diário de proteína (g)",
    "mode_title": "🎨 Modo predefinido",
    "mode_label": "Que versão deve estar ativa quando inicia sessão?",
    "mode_standard": "SanoSync Standard",
    "mode_zero": "SanoSync ZERO MODE",
}

def render_personal_settings_page():
    # ------------------------------------------------------------------
    # LINGUA SEMPRE IN ALTO
    # La select aggiorna subito l'interfaccia, senza aspettare "Salva".
    # ------------------------------------------------------------------
    _settings_languages = ["Italiano", "English", "Nederlands", "Français", "Português"]

    settings_lang = st.session_state.get("settings_language_live")
    if settings_lang not in _settings_languages:
        settings_lang = st.session_state.get("lang_selector", "Italiano")
    if settings_lang not in _settings_languages:
        settings_lang = "Italiano"

    si = SETTINGS_I18N.get(settings_lang, SETTINGS_I18N["Italiano"])

    new_language = st.selectbox(
        "🌐 Language / Lingua / Taal / Langue",
        _settings_languages,
        index=_settings_languages.index(settings_lang),
        key="settings_language_live",
        format_func=format_language_option,
    )

    # IMPORTANTE: usiamo direttamente il valore restituito dal widget.
    # In alcune versioni/configurazioni Streamlit, rileggere session_state
    # nello stesso passaggio può lasciare visibile per una run il vecchio
    # dizionario (es. dropdown "English" ma testi ancora italiani).
    settings_lang = new_language
    si = SETTINGS_I18N.get(new_language, SETTINGS_I18N["Italiano"])

    # Manteniamo sincronizzata anche la lingua globale dell'app.
    st.session_state["lang_selector"] = new_language
    st.session_state["login_lang_selector"] = new_language

    render_page_title_card(si["title"])

    # CV-like identity header: Google/Facebook photo when available.
    st.markdown(
        """
        <style>
        .sano-profile-name {
            font-size:clamp(1.55rem,3vw,2.15rem);
            font-weight:950;
            line-height:1.05;
            color:#1A2942;
            margin:0 0 .35rem 0;
        }
        .sano-profile-email {
            font-size:.95rem;
            color:#7B7E89;
            font-weight:600;
        }
        .st-key-profile_identity_card {
            border:1px solid rgba(255,139,139,.34);
            border-radius:20px;
            padding:18px 20px;
            margin:.15rem 0 1rem 0;
            background:
                radial-gradient(circle at 96% 4%, rgba(255,139,139,.16), transparent 36%),
                linear-gradient(145deg,#FFFFFF,#FFF8F8);
            box-shadow:0 8px 24px rgba(23,42,70,.07);
        }
        .st-key-profile_identity_card [data-testid="stImage"] img {
            border-radius:22px !important;
            object-fit:cover !important;
            aspect-ratio:1/1 !important;
        }
        </style>
        """,
        unsafe_allow_html=True,
    )

    with st.container(key="profile_identity_card"):
        _pic_col, _identity_col = st.columns(
            [1.1, 4.9],
            gap="large",
            vertical_alignment="center",
        )
        with _pic_col:
            if logged_avatar:
                st.image(logged_avatar, width=150)
            else:
                st.markdown(
                    "<div style='font-size:5rem;text-align:center;'>👤</div>",
                    unsafe_allow_html=True,
                )
        with _identity_col:
            st.markdown(
                f"<div class='sano-profile-name'>{html.escape(logged_name)}</div>",
                unsafe_allow_html=True,
            )
            st.markdown(
                f"<div class='sano-profile-email'>{html.escape(logged_email)}</div>",
                unsafe_allow_html=True,
            )
            st.caption(si["subtitle"])

    if st.button(si["back"], key="settings_back"):
        st.session_state["show_personal_settings"] = False
        st.session_state["current_page_id"] = "t1"
        st.session_state.pop("settings_language_live", None)
        # Il widget lingua della sidebar verrà ricreato con il valore corrente.
        st.session_state.pop("profile_menu_language", None)
        st.rerun()

    metadata = dict(getattr(st.session_state["user"], "user_metadata", None) or {})

    existing_name = str(
        metadata.get("display_name")
        or metadata.get("full_name")
        or metadata.get("name")
        or logged_name
        or ""
    )
    existing_gender = str(metadata.get("gender") or "Uomo")
    existing_birth = parse_birth_date(metadata.get("birth_date")) or date(1990, 1, 1)
    existing_height = float(metadata.get("height") or 175.0)
    existing_target = float(metadata.get("target_weight") or 75.0)
    existing_current = float(
        user_current_weight
        if user_current_weight is not None
        else metadata.get("current_weight") or 80.0
    )

    canonical_gender = (
        "Donna"
        if existing_gender in ("Donna", "Female", "Vrouw", "Femme")
        else "Uomo"
    )

    existing_deficit_value = int(
        round(float(metadata.get("deficit_target_kcal") or 0))
    )
    existing_deficit_plan = normalize_deficit_plan(
        metadata.get("deficit_plan")
        or deficit_preset_from_value(existing_deficit_value)
    )

    existing_office_lunch_enabled = bool(metadata.get("office_lunch_enabled", True))

    existing_preferred_app_mode = str(
        metadata.get("preferred_app_mode")
        or ("zero" if is_zero_mode() else "standard")
    ).strip().lower()
    if existing_preferred_app_mode not in {"standard", "zero"}:
        existing_preferred_app_mode = (
            "zero" if is_zero_mode() else "standard"
        )

    existing_protein_enabled = bool(metadata.get("protein_goal_enabled", False))
    existing_protein_g = _safe_float(metadata.get("protein_goal_g"))
    if (
        str(user_id) == _PROTEIN_GOAL_SPECIAL_UID
        and "protein_goal_enabled" not in metadata
    ):
        existing_protein_enabled = True
        if existing_protein_g <= 0:
            _settings_special_weight = _safe_float(existing_current)
            if _settings_special_weight <= 0:
                _settings_special_weight = 70.0
            existing_protein_g = round(_settings_special_weight * 2.0)

    if "settings_deficit_plan" not in st.session_state:
        st.session_state["settings_deficit_plan"] = existing_deficit_plan
    if "settings_deficit_kcal" not in st.session_state:
        st.session_state["settings_deficit_kcal"] = existing_deficit_value

    def _sync_settings_deficit():
        selected = normalize_deficit_plan(
            st.session_state.get("settings_deficit_plan", "custom")
        )
        st.session_state["settings_deficit_kcal"] = int(
            DEFICIT_PRESETS.get(selected, 0)
        )

    # ------------------------------------------------------------------
    # DATI ACCOUNT / FISICI
    # ------------------------------------------------------------------
    with st.container(border=True):
        st.markdown(f"### {si['account']}")

        st.text_input(
            si["email"],
            value=logged_email,
            disabled=True,
        )

        new_name = st.text_input(
            si["name"],
            value=existing_name,
            key="settings_display_name",
        )

        gender_options = ["Uomo", "Donna"]
        new_gender = st.selectbox(
            si["gender"],
            gender_options,
            index=gender_options.index(canonical_gender),
            format_func=lambda value: (
                si["male"] if value == "Uomo" else si["female"]
            ),
            key="settings_gender",
        )

        new_birth = st.date_input(
            si["birth"],
            value=existing_birth,
            min_value=date(1900, 1, 1),
            max_value=date.today(),
            key="settings_birth_date",
        )

        c1, c2 = st.columns(2)
        with c1:
            new_height = st.number_input(
                si["height"],
                min_value=100.0,
                max_value=250.0,
                value=existing_height,
                step=1.0,
                key="settings_height",
            )

        with c2:
            new_current_weight = st.number_input(
                si["current_weight"],
                min_value=20.0,
                max_value=300.0,
                value=existing_current,
                step=0.1,
                key="settings_current_weight",
            )

        new_target = st.number_input(
            si["target_weight"],
            min_value=20.0,
            max_value=300.0,
            value=existing_target,
            step=0.5,
            key="settings_target_weight",
        )

    # ------------------------------------------------------------------
    # DEFICIT
    # ------------------------------------------------------------------
    with st.container(border=True):
        st.markdown(f"### {si['deficit_title']}")

        new_deficit_plan = st.selectbox(
            si["deficit_speed"],
            list(DEFICIT_PRESETS.keys()),
            key="settings_deficit_plan",
            format_func=lambda key: DEFICIT_PRESET_LABELS.get(
                settings_lang,
                DEFICIT_PRESET_LABELS["Italiano"],
            ).get(key, key),
            on_change=_sync_settings_deficit,
        )

        new_deficit_kcal = st.number_input(
            si["deficit_field"],
            min_value=0,
            max_value=2000,
            step=50,
            key="settings_deficit_kcal",
        )

    # ------------------------------------------------------------------
    # PRANZO IN UFFICIO
    # ------------------------------------------------------------------
    with st.container(border=True):
        st.markdown(f"### {si['office_title']}")
        _office_options = [si["office_no"], si["office_yes"]]
        new_office_choice = st.radio(
            si["office_enabled"],
            _office_options,
            index=1 if existing_office_lunch_enabled else 0,
            horizontal=True,
            key="settings_office_lunch_enabled",
        )
        new_office_lunch_enabled = new_office_choice == si["office_yes"]

    # ------------------------------------------------------------------
    # MODALITÀ PREDEFINITA
    # ------------------------------------------------------------------
    with st.container(border=True):
        st.markdown(f"### {si['mode_title']}")

        _mode_options = ["standard", "zero"]
        new_preferred_app_mode = st.radio(
            si["mode_label"],
            _mode_options,
            index=_mode_options.index(existing_preferred_app_mode),
            horizontal=True,
            format_func=lambda mode: (
                si["mode_zero"]
                if mode == "zero"
                else si["mode_standard"]
            ),
            help=si["mode_help"],
            key="settings_preferred_app_mode",
        )

    # ------------------------------------------------------------------
    # OURA
    # ------------------------------------------------------------------
    with st.container(border=True):
        st.markdown("### 💍 Oura")

        _oura_just_connected = st.session_state.pop(
            "oura_callback_success",
            False,
        )
        _oura_callback_error = st.session_state.pop(
            "oura_callback_error",
            None,
        )

        try:
            _oura_connection = fetch_oura_connection(user_id)
        except Exception as exc:
            _oura_connection = None
            if "oura_connections" in str(exc):
                st.error(
                    "La tabella Supabase `oura_connections` non esiste ancora. "
                    "Esegui prima lo script SQL fornito per l'integrazione Oura."
                )
            else:
                st.error(f"Impossibile leggere la connessione Oura: {exc}")

        # The database is the source of truth. If a connection exists, an older
        # callback error from a previous attempt must not be shown.
        if _oura_connection:
            _oura_callback_error = None
            st.session_state.pop("oura_callback_error", None)
            st.session_state.pop("oura_authorization_url", None)

        if _oura_just_connected and _oura_connection:
            st.success("Oura collegato correttamente.")

        if _oura_callback_error and not _oura_connection:
            st.error(
                f"Connessione Oura non riuscita: {_oura_callback_error}"
            )

        if _oura_connection:
            st.success("✅ Account Oura collegato")
            st.caption(
                "Connessione salvata in Supabase per questo account SanoSync."
            )
            _scope = str(_oura_connection.get("scope") or "")
            if _scope:
                st.caption(f"Permessi concessi: {_scope}")

            _oura_col1, _oura_col2, _oura_col3 = st.columns(3)

            with _oura_col1:
                if st.button(
                    "🔄 Verifica",
                    key="oura_test_connection",
                    use_container_width=True,
                ):
                    try:
                        _personal = oura_get_personal_info(user_id)
                        _oura_name = (
                            _personal.get("email")
                            or _personal.get("id")
                            or "account Oura"
                        )
                        st.success(
                            f"Connessione attiva: {_oura_name}"
                        )
                    except Exception as exc:
                        st.error(
                            f"Verifica Oura non riuscita: {exc}"
                        )

            with _oura_col2:
                if st.button(
                    "👣 Sincronizza ora",
                    key="oura_sync_steps_now",
                    use_container_width=True,
                ):
                    try:
                        _today = date.today()
                        _start = _today - timedelta(days=7)
                        _synced = sync_oura_steps_to_supabase(
                            user_id,
                            _start,
                            _today,
                        )
                        if _synced:
                            _latest = sorted(
                                _synced,
                                key=lambda row: row["date"],
                            )[-1]
                            st.success(
                                f"Oura sincronizzato: "
                                f"{_latest['steps']} passi il "
                                f"{_latest['date']} "
                                f"({_latest['estimated_kcal']} kcal stimate)."
                            )
                        else:
                            st.info(
                                "Oura non ha restituito attività giornaliere "
                                "per gli ultimi 7 giorni."
                            )
                    except Exception as exc:
                        st.error(
                            f"Sincronizzazione Oura non riuscita: {exc}"
                        )

            with _oura_col3:
                if st.button(
                    "Scollega",
                    key="oura_disconnect",
                    use_container_width=True,
                ):
                    try:
                        revoke_and_delete_oura_connection(user_id)
                        st.success("Oura scollegato.")
                        st.rerun()
                    except Exception as exc:
                        st.error(
                            f"Impossibile scollegare Oura: {exc}"
                        )

            st.caption(
                "I passi Oura vengono salvati in `daily_logs.steps`. "
                "Le kcal dei passi usano la regola SanoSync già esistente: "
                "0,04 kcal per passo, evitando il doppio conteggio con "
                "Padel/Corsa."
            )
        else:
            st.write(
                "Collega il tuo Oura Ring a SanoSync. "
                "Richiediamo solo i permessi `personal`, `daily` e `workout`."
            )
            st.caption(
                "La password Oura non viene condivisa con SanoSync. "
                "L'autorizzazione avviene direttamente su Oura tramite OAuth 2.0."
            )

            try:
                # Genera SEMPRE un nuovo URL OAuth.
                # Non riusare URL creati prima del cambio Redirect URI
                # nella console sviluppatori Oura.
                _oura_auth_url = build_oura_authorization_url(user_id)
                st.session_state.pop("oura_authorization_url", None)

                st.link_button(
                    "💍 Connetti Oura",
                    _oura_auth_url,
                    use_container_width=True,
                    type="primary",
                )
                st.caption(
                    "Oura si apre in una nuova scheda. Al termine "
                    "l'associazione viene salvata automaticamente."
                )
            except Exception as exc:
                st.error(
                    f"Configurazione Oura incompleta: {exc}"
                )

        _legal_c1, _legal_c2 = st.columns(2)
        with _legal_c1:
            st.link_button(
                "Privacy Policy",
                "https://sanosync.streamlit.app/?page=privacy",
                use_container_width=True,
            )
        with _legal_c2:
            st.link_button(
                "Terms of Service",
                "https://sanosync.streamlit.app/?page=terms",
                use_container_width=True,
            )

    # ------------------------------------------------------------------
    # GOAL PROTEICO — SEMPRE ULTIMA SEZIONE
    # ------------------------------------------------------------------
    with st.container(border=True):
        st.markdown(f"### {si['protein_title']}")

        _protein_options = [si["protein_no"], si["protein_yes"]]
        new_protein_choice = st.radio(
            si["protein_enabled"],
            _protein_options,
            index=1 if existing_protein_enabled else 0,
            horizontal=True,
            key="settings_protein_goal_enabled",
        )

        new_protein_enabled = new_protein_choice == si["protein_yes"]
        # Se non esiste ancora un goal salvato, proponiamo 2 g/kg
        # usando il peso corrente presente nelle impostazioni.
        _protein_weight_basis = _safe_float(new_current_weight)
        if _protein_weight_basis <= 0:
            _protein_weight_basis = 70.0

        _protein_suggested_g = min(
            500.0,
            max(1.0, round(_protein_weight_basis * 2.0)),
        )

        new_protein_g = (
            existing_protein_g
            if existing_protein_g > 0
            else float(_protein_suggested_g)
        )

        if new_protein_enabled:
            new_protein_g = st.number_input(
                si["protein_g"],
                min_value=1.0,
                max_value=500.0,
                value=float(new_protein_g),
                step=5.0,
                key="settings_protein_goal_g",
            )

    st.caption(si["hint"])

    if st.button(
        si["save"],
        type="primary",
        use_container_width=True,
        key="save_personal_settings",
    ):
        try:
            normalized_plan = normalize_deficit_plan(new_deficit_plan)

            # If current and target weight match, force maintenance in metadata.
            if abs(float(new_current_weight) - float(new_target)) <= 0.05:
                normalized_plan = "maintenance"
                new_deficit_kcal = 0

            preset_value = int(DEFICIT_PRESETS.get(normalized_plan, 0))
            plan_to_save = (
                normalized_plan
                if int(new_deficit_kcal) == preset_value
                else "custom"
            )

            updated_metadata = dict(metadata)
            updated_metadata.update({
                "display_name": str(new_name).strip(),
                "gender": new_gender,
                "birth_date": str(new_birth),
                "height": float(new_height),
                "current_weight": float(new_current_weight),
                "target_weight": float(new_target),
                "deficit_target_kcal": int(new_deficit_kcal),
                "deficit_plan": plan_to_save,
                "preferred_language": new_language,
                "preferred_app_mode": new_preferred_app_mode,
                # Keep the legacy field aligned for older code paths.
                "zero_mode_enabled": (
                    new_preferred_app_mode == "zero"
                ),
                "office_lunch_enabled": bool(new_office_lunch_enabled),
                "protein_goal_enabled": bool(new_protein_enabled),
                "protein_goal_g": (
                    float(new_protein_g)
                    if new_protein_enabled
                    else None
                ),
            })

            response = supabase.auth.update_user({
                "data": updated_metadata
            })

            update_daily_log_via_api(
                    date.today(),
                    {"weight": float(new_current_weight)},
                    st.session_state.get("auth_access_token"),
                )

            if getattr(response, "user", None):
                st.session_state["user"] = response.user

            # Apply the chosen default immediately as well.
            st.session_state["zero_mode_enabled"] = (
                new_preferred_app_mode == "zero"
            )
            # Recreate the sidebar toggle on rerun using the selected mode.
            st.session_state.pop("zero_mode_sidebar_toggle", None)

            st.session_state["lang_selector"] = new_language
            st.session_state["login_lang_selector"] = new_language

            queue_ui_sound("profile_saved")
            st.success(si["saved"])
            st.session_state["show_personal_settings"] = False
            st.session_state.pop("settings_language_live", None)
            st.session_state.pop("profile_menu_language", None)
            st.rerun()

        except Exception as exc:
            st.error(si["error"].format(error=exc))
            print(traceback.format_exc())


_is_settings_page = bool(st.session_state.get("show_personal_settings", False))
if _is_settings_page:
    render_personal_settings_page()
    st.stop()


# Su mobile la sidebar parte aperta (initial_sidebar_state="expanded") e viene
# chiusa dopo la selezione di una tab. I selettori (es. lingua) non la chiudono.
st.markdown("""
<script>
(function () {
    function isMobile() { return window.innerWidth <= 768; }

    function collapseSidebar() {
        if (!isMobile()) return;
        const candidates = [
            '[data-testid="stSidebarCollapseButton"] button',
            '[data-testid="stSidebarCollapseButton"]',
            '[data-testid="collapsedControl"] button',
            '[data-testid="collapsedControl"]'
        ];
        for (const selector of candidates) {
            const el = document.querySelector(selector);
            if (el) { el.click(); return; }
        }
    }

    document.addEventListener('click', function(event) {
        if (!isMobile()) return;
        const sidebar = document.querySelector('[data-testid="stSidebar"]');
        if (!sidebar || !sidebar.contains(event.target)) return;

        const button = event.target.closest('button');
        if (!button) return;

        // Consideriamo solo i normali st.button della sidebar, escludendo
        // il pulsante nativo di apertura/chiusura.
        const buttons = Array.from(sidebar.querySelectorAll('[data-testid="stButton"] button'));
        const buttonIndex = buttons.indexOf(button);
        if (buttonIndex >= 0 && buttonIndex < 5) {
            setTimeout(collapseSidebar, 180);
        }
    }, true);
})();
</script>
""", unsafe_allow_html=True)

def analyze_food_photo_with_ai(uploaded_file, language="Italiano"):
    """
    Analizza una foto del pasto tramite Groq/Qwen Vision.

    Usa Chat Completions + JSON Object Mode, che Groq documenta
    esplicitamente anche per input immagine. Questo evita risposte vuote
    o non parsabili che possono verificarsi leggendo response.output_text
    dalla Responses API beta.
    """
    api_key = st.secrets.get("GROQ_API_KEY")
    if not api_key:
        raise RuntimeError(
            "GROQ_API_KEY non configurata nei Secrets di Streamlit."
        )

    image_bytes = uploaded_file.getvalue()
    if not image_bytes:
        raise RuntimeError("La foto caricata è vuota.")

    mime = getattr(uploaded_file, "type", None) or "image/jpeg"
    image_b64 = base64.b64encode(image_bytes).decode("utf-8")
    data_url = f"data:{mime};base64,{image_b64}"

    language_name = {
        "Italiano": "Italian",
        "English": "English",
        "Nederlands": "Dutch",
        "Français": "French",
        "Português": "Portuguese",
    }.get(language, "Italian")

    client = OpenAI(
        api_key=api_key,
        base_url="https://api.groq.com/openai/v1",
    )

    prompt = f"""
Analyze this meal photo and estimate the photographed portion.

Return a JSON object ONLY.
Use {language_name} for the food name and notes.

Be conservative:
- estimate only what is reasonably visible;
- do not pretend hidden ingredients are certain;
- calories and macros must refer to the TOTAL photographed portion;
- estimated_grams must be the total estimated edible weight.

Required keys:
{{
  "name": "short meal name",
  "estimated_grams": 250,
  "calories": 450,
  "protein": 30,
  "carbs": 45,
  "fat": 15,
  "notes": "brief explanation of the estimate",
  "confidence": "low|medium|high"
}}

Every numeric field must contain a number, not a string.
""".strip()

    completion = client.chat.completions.create(
        model="qwen/qwen3.6-27b",
        messages=[
            {
                "role": "user",
                "content": [
                    {
                        "type": "text",
                        "text": prompt,
                    },
                    {
                        "type": "image_url",
                        "image_url": {
                            "url": data_url,
                        },
                    },
                ],
            }
        ],
        response_format={"type": "json_object"},
        reasoning_effort="none",
        temperature=0.2,
        max_completion_tokens=900,
        stream=False,
    )

    try:
        raw = completion.choices[0].message.content
    except Exception as exc:
        raise RuntimeError(
            f"Groq non ha restituito un contenuto leggibile: {exc}"
        )

    if isinstance(raw, list):
        # Defensive fallback for client versions that may expose content
        # as a list of typed content blocks.
        parts = []
        for item in raw:
            if isinstance(item, dict):
                parts.append(str(item.get("text") or ""))
            else:
                parts.append(str(getattr(item, "text", "") or ""))
        raw = "".join(parts)

    raw = str(raw or "").strip()

    if not raw:
        finish_reason = None
        try:
            finish_reason = completion.choices[0].finish_reason
        except Exception:
            pass
        raise RuntimeError(
            "Groq ha restituito una risposta vuota"
            + (
                f" (finish_reason: {finish_reason})."
                if finish_reason
                else "."
            )
        )

    # JSON mode dovrebbe già garantire JSON valido, ma manteniamo
    # una pulizia difensiva per eventuali fence.
    raw = re.sub(r"^```(?:json)?\s*", "", raw, flags=re.I)
    raw = re.sub(r"\s*```$", "", raw).strip()

    try:
        data = json.loads(raw)
    except json.JSONDecodeError as exc:
        preview = raw[:300].replace("\n", " ")
        raise RuntimeError(
            f"Groq ha restituito un JSON non valido: {exc}. "
            f"Risposta ricevuta: {preview}"
        )

    return {
        "name": str(data.get("name") or "Pasto da foto").strip(),
        "estimated_grams": max(
            1.0,
            _safe_float(data.get("estimated_grams")),
        ),
        "calories": max(
            0.0,
            _safe_float(data.get("calories")),
        ),
        "protein": max(
            0.0,
            _safe_float(data.get("protein")),
        ),
        "carbs": max(
            0.0,
            _safe_float(data.get("carbs")),
        ),
        "fat": max(
            0.0,
            _safe_float(data.get("fat")),
        ),
        "notes": str(data.get("notes") or "").strip(),
        "confidence": str(
            data.get("confidence") or "low"
        ).strip().lower(),
    }



# ==============================================================================
# AI RECIPE GENERATOR — GROQ via OpenAI-compatible client
# ==============================================================================
AI_RECIPE_PANTRY_BASICS = [
    "olio",
    "sale",
    "pepe",
    "spezie",
    "acqua",
    "aglio",
    "riso",
    "pasta",
]


def _ai_recipe_language_name(lang):
    return {
        "Italiano": "Italian",
        "English": "English",
        "Nederlands": "Dutch",
        "Français": "French",
    }.get(lang, "Italian")


def _ai_recipe_clean_json(raw):
    raw = str(raw or "").strip()
    raw = re.sub(r"^```(?:json)?\s*", "", raw, flags=re.I)
    raw = re.sub(r"\s*```$", "", raw).strip()
    return json.loads(raw)



def render_compact_ai_list(items, *, numbered=False):
    """Compact HTML list used in AI recipe preview to avoid oversized markdown spacing."""
    clean = [str(x).strip() for x in (items or []) if str(x).strip()]
    if not clean:
        return

    tag = "ol" if numbered else "ul"
    st.markdown(
        f"""
        <{tag} style="
            margin:0.2rem 0 0.15rem 1.15rem;
            padding-left:0.45rem;
            line-height:1.35;
        ">
            {''.join(
                f'<li style="margin:0.18rem 0;padding:0;">{html.escape(item)}</li>'
                for item in clean
            )}
        </{tag}>
        """,
        unsafe_allow_html=True,
    )


def _ai_recipe_notes(result):
    instructions = result.get("instructions") or []
    notes = str(result.get("notes") or "").strip()
    description = str(result.get("description") or "").strip()

    lines = []
    if description:
        lines.append(description)

    if notes:
        if lines:
            lines.append("")
        lines.append(notes)

    if instructions:
        lines.append("")
        lines.append("Preparazione:")
        for idx, step in enumerate(instructions, start=1):
            lines.append(f"{idx}. {step}")

    warning = str(result.get("warning") or "").strip()
    if warning:
        lines.append("")
        lines.append(f"Nota AI: {warning}")

    return "\n".join(lines).strip()


def _normalize_ai_recipe_result(data, requested_servings):
    """Normalize Groq JSON into recipe_library-compatible values."""
    servings = max(
        1.0,
        _safe_float(data.get("servings")) or float(requested_servings or 1),
    )

    nutr = data.get("nutrition_per_serving") or {}
    kcal = max(0.0, _safe_float(nutr.get("calories")))
    protein = max(0.0, _safe_float(nutr.get("protein")))
    carbs = max(0.0, _safe_float(nutr.get("carbs")))
    fat = max(0.0, _safe_float(nutr.get("fat")))

    ingredients = []
    for item in (data.get("ingredients") or []):
        if not isinstance(item, dict):
            continue

        name = str(item.get("name") or "").strip()
        if not name:
            continue

        quantity_g = max(0.0, _safe_float(item.get("quantity_g")))
        if quantity_g <= 0:
            continue

        ingredients.append({
            "name": name,
            "quantity_g": quantity_g,
            "calories_per_100g": max(
                0.0,
                _safe_float(item.get("calories_per_100g")),
            ),
            "protein_per_100g": max(
                0.0,
                _safe_float(item.get("protein_per_100g")),
            ),
            "carbs_per_100g": max(
                0.0,
                _safe_float(item.get("carbs_per_100g")),
            ),
            "fat_per_100g": max(
                0.0,
                _safe_float(item.get("fat_per_100g")),
            ),
            "source": "ai",
        })

    return {
        "name": str(data.get("name") or "Ricetta AI").strip(),
        "meal_type": str(data.get("meal_type") or "Cena").strip(),
        "servings": servings,
        "total_minutes": max(0, int(round(_safe_float(data.get("total_minutes"))))),
        "active_minutes": max(0, int(round(_safe_float(data.get("active_minutes"))))),
        "nutrition_per_serving": {
            "calories": kcal,
            "protein": protein,
            "carbs": carbs,
            "fat": fat,
        },
        "ingredients": ingredients,
        "description": str(data.get("description") or "").strip(),
        "instructions": [
            str(x).strip()
            for x in (data.get("instructions") or [])
            if str(x).strip()
        ],
        "notes": str(data.get("notes") or "").strip(),
        "target_not_reached": bool(data.get("target_not_reached", False)),
        "warning": str(data.get("warning") or "").strip(),
    }


def _extract_json_object_tolerant(raw_text):
    """
    Extract the first valid JSON object from a model response.

    Handles markdown fences, <think> blocks, leading/trailing prose and
    braces inside quoted JSON strings.
    """
    text = str(raw_text or "").strip()
    if not text:
        raise ValueError("La risposta AI è vuota.")

    # Remove markdown fences and provider reasoning blocks.
    text = re.sub(r"^```(?:json)?\s*", "", text, flags=re.I)
    text = re.sub(r"\s*```$", "", text).strip()
    text = re.sub(
        r"<think>.*?</think>",
        "",
        text,
        flags=re.I | re.S,
    ).strip()

    # Whole response first.
    try:
        data = json.loads(text)
        if isinstance(data, dict):
            return data
    except Exception:
        pass

    # Search every balanced {...} candidate while respecting JSON strings.
    starts = [i for i, ch in enumerate(text) if ch == "{"]
    for first in starts:
        depth = 0
        in_string = False
        escaped = False

        for i in range(first, len(text)):
            ch = text[i]

            if in_string:
                if escaped:
                    escaped = False
                elif ch == "\\":
                    escaped = True
                elif ch == '"':
                    in_string = False
                continue

            if ch == '"':
                in_string = True
            elif ch == "{":
                depth += 1
            elif ch == "}":
                depth -= 1
                if depth == 0:
                    candidate = text[first:i + 1]
                    try:
                        data = json.loads(candidate)
                        if isinstance(data, dict):
                            return data
                    except Exception:
                        break

    raise ValueError("La risposta AI non contiene un oggetto JSON valido.")


def _repair_food_fit_json_with_groq(client, model_id, raw_text):
    """Repair one malformed food-fit response into the required JSON shape."""
    repair_prompt = f"""
Convert the response below into ONE valid JSON object only.

Required top-level keys:
food_name, estimated_kcal, estimated_protein_g, estimated_carbs_g,
estimated_fat_g, confidence, message.

Rules:
- Do not add markdown fences.
- Do not output commentary or reasoning.
- Keep the original meaning and estimates when possible.
- Numeric nutrition fields must be JSON numbers.
- confidence must be "low", "medium", or "high".

RESPONSE:
{raw_text}
""".strip()

    repaired = client.chat.completions.create(
        model=model_id,
        messages=[
            {
                "role": "system",
                "content": "Return exactly one valid JSON object and nothing else.",
            },
            {"role": "user", "content": repair_prompt},
        ],
        temperature=0,
        max_tokens=900,
        stream=False,
    )
    return _extract_json_object_tolerant(
        repaired.choices[0].message.content
    )


def _repair_recipe_json_with_groq(client, model_id, raw_text):
    """
    One cheap repair pass if the first recipe response is not valid JSON.
    """
    repair_prompt = f"""
Convert the following response into VALID JSON only.

Do not add commentary.
Do not use markdown fences.
Do not change the meaning or nutritional values unless needed to make the JSON syntactically valid.
Keep exactly these top-level keys when present:
name, meal_type, servings, total_minutes, active_minutes,
nutrition_per_serving, ingredients, description, instructions, notes,
target_not_reached, warning.

RESPONSE TO REPAIR:
{raw_text}
""".strip()

    repaired = client.chat.completions.create(
        model=model_id,
        messages=[
            {
                "role": "system",
                "content": "Return valid JSON only. Never output reasoning.",
            },
            {
                "role": "user",
                "content": repair_prompt,
            },
        ],
        temperature=0.0,
        max_tokens=3200,
        stream=False,
    )

    return _extract_json_object_tolerant(
        repaired.choices[0].message.content
    )



def regenerate_ai_recipe_if_empty(
    *,
    language,
    mode,
    meal_type,
    restrictions,
    servings,
    target_kcal,
    protein_target,
    macro_focus,
    total_minutes,
    active_minutes,
    equipment,
    available_ingredients,
    avoid_ingredients,
):
    """
    Second-pass fallback used only when the first AI result has no valid ingredients.
    Keeps the user's calorie target, but prioritizes a coherent recipe over strict ±10%.
    """
    api_key = st.secrets.get("GROQ_API_KEY")
    if not api_key:
        raise RuntimeError("GROQ_API_KEY non configurata nei Secrets di Streamlit.")

    client = OpenAI(
        api_key=api_key,
        base_url="https://api.groq.com/openai/v1",
    )
    model_id = resolve_groq_text_model()
    language_name = _ai_recipe_language_name(language)

    prompt = f"""
Create ONE complete, realistic recipe.

LANGUAGE: {language_name}
MEAL TYPE: {meal_type}
SERVINGS: {float(servings):g}
REQUESTED CALORIES PER SERVING: {float(target_kcal):.0f} kcal
PROTEIN TARGET PER SERVING: {float(protein_target or 0):.0f} g
MACRO FOCUS: {macro_focus}
RESTRICTIONS: {", ".join(restrictions) if restrictions else "none"}
MAX TOTAL TIME: {total_minutes} min
MAX ACTIVE TIME: {active_minutes} min
EQUIPMENT: {", ".join(equipment) if equipment else "standard kitchen equipment"}
AVAILABLE INGREDIENTS: {available_ingredients or "none specified"}
INGREDIENTS TO AVOID: {avoid_ingredients or "none"}

{zero_tone_instruction()}

IMPORTANT:
- The previous attempt failed because it returned no usable ingredients.
- You MUST return at least 2 valid ingredients with positive quantity_g.
- If the calorie target is unrealistically low, create the lightest coherent recipe you can.
- In that case set target_not_reached=true and explain it briefly in warning.
- Never return an empty ingredient list.
- Nutrition is per serving.
- Ingredients quantities are for the whole recipe.
- Include a 2-4 sentence description.
- Include complete step-by-step instructions from preparation through final plating/serving.
- Usually provide 4-8 steps for a cooked meal.
- The final instruction must complete the dish; never stop mid-sentence.

Return ONLY valid JSON:
{{
  "name": "recipe name",
  "meal_type": "{meal_type}",
  "servings": {float(servings):g},
  "total_minutes": 20,
  "active_minutes": 10,
  "nutrition_per_serving": {{
    "calories": 250,
    "protein": 25,
    "carbs": 20,
    "fat": 8
  }},
  "ingredients": [
    {{
      "name": "ingredient",
      "quantity_g": 200,
      "calories_per_100g": 100,
      "protein_per_100g": 20,
      "carbs_per_100g": 0,
      "fat_per_100g": 2
    }}
  ],
  "description": "short description",
  "instructions": [
    "step 1",
    "step 2",
    "step 3",
    "step 4"
  ],
  "notes": "",
  "target_not_reached": true,
  "warning": "brief explanation if target was too low"
}}
""".strip()

    response = client.chat.completions.create(
        model=model_id,
        messages=[
            {
                "role": "system",
                "content": (
                    "You are SanoSync Recipe AI. "
                    "Return only one valid JSON object. "
                    "Never output reasoning or markdown."
                ),
            },
            {"role": "user", "content": prompt},
        ],
        temperature=0.35,
        max_tokens=3200,
        stream=False,
    )

    raw = response.choices[0].message.content
    try:
        data = _extract_json_object_tolerant(raw)
    except Exception:
        data = _repair_recipe_json_with_groq(
            client,
            model_id,
            raw,
        )

    return _normalize_ai_recipe_result(
        data,
        servings,
    )


def generate_ai_recipe_with_groq(
    *,
    language,
    mode,
    meal_type,
    restrictions,
    servings,
    target_kcal,
    protein_target,
    macro_focus,
    total_minutes,
    active_minutes,
    equipment,
    available_ingredients,
    avoid_ingredients,
):
    """
    Groq creates the recipe AND estimates nutrition.
    Open Food Facts is intentionally not used for this feature.
    """
    api_key = st.secrets.get("GROQ_API_KEY")
    if not api_key:
        raise RuntimeError("GROQ_API_KEY non configurata nei Secrets di Streamlit.")

    language_name = _ai_recipe_language_name(language)
    pantry_text = ", ".join(AI_RECIPE_PANTRY_BASICS)
    equipment_text = ", ".join(equipment) if equipment else "standard kitchen equipment"
    restrictions_text = ", ".join(restrictions) if restrictions else "none"
    protein_instruction = (
        f"Try to provide at least {float(protein_target):.0f} g protein per serving."
        if protein_target and float(protein_target) > 0
        else "There is no numeric protein target."
    )

    if mode == "fridge":
        ingredient_rule = f"""
THIS IS A FRIDGE-CLEARING RECIPE.
The user's available ingredients and quantities are:
{available_ingredients or "No ingredients supplied"}

Rules:
- prioritize and use as much as reasonably useful of those ingredients;
- NEVER exceed quantities explicitly supplied by the user;
- you may add ONLY these pantry basics when needed to make a coherent meal:
  {pantry_text};
- do not add unrelated extra ingredients;
- minimize waste;
- if the available ingredients cannot reasonably reach the requested calorie
  target within ±10%, produce the best coherent LOWER-calorie recipe instead,
  set target_not_reached=true and explain it briefly in warning.
"""
    else:
        ingredient_rule = f"""
THIS IS A GENERAL RECIPE GENERATOR.
Create a coherent recipe that respects the requested restrictions and nutrition targets.
You may choose appropriate ingredients freely.
Common pantry basics available are: {pantry_text}.
If the user listed ingredients, treat them as preferences:
{available_ingredients or "None listed"}.
"""

    prompt = f"""
Create ONE practical recipe.

LANGUAGE FOR ALL USER-FACING TEXT: {language_name}
MODE: {mode}
MEAL TYPE: {meal_type}
DIETARY RESTRICTIONS: {restrictions_text}
SERVINGS: {float(servings):g}
TARGET CALORIES PER SERVING: {float(target_kcal):.0f} kcal
CALORIE TOLERANCE: ±10%
MACRO FOCUS: {macro_focus}
{protein_instruction}

LOW-CALORIE RULE:
- if the requested calories are low, still return a complete and coherent recipe;
- NEVER return an empty ingredient list;
- prefer smaller quantities, leaner ingredients, vegetables, broth/water-based cooking,
  and reduced added fats when appropriate;
- do not try to force a recipe below a realistic minimum by omitting ingredients;
- if the requested target is too low for the requested meal/constraints, return the
  lightest coherent recipe you can make, set target_not_reached=true, and explain
  briefly in warning;
- target_not_reached is preferable to returning no ingredients.
MAX TOTAL TIME: {total_minutes}
MAX ACTIVE COOKING TIME: {active_minutes}
AVAILABLE EQUIPMENT: {equipment_text}
INGREDIENTS TO AVOID: {avoid_ingredients or "None"}

{ingredient_rule}

NUTRITION RULES:
- estimate calories and macros yourself;
- nutrition_per_serving MUST represent one serving;
- give realistic estimates rather than false precision;
- all ingredients MUST include an estimated quantity in grams for the WHOLE recipe;
- each ingredient MUST also contain estimated kcal/protein/carbs/fat per 100 g;
- keep the recipe within ±10% of the calorie target whenever reasonably possible;
- if the requested target cannot be achieved in fridge mode, LOWER calories instead
  of inventing unavailable food, and set target_not_reached=true.

TIME RULES:
- total_minutes must not exceed the requested total time;
- active_minutes must not exceed the requested active time;
- active_minutes cannot exceed total_minutes.

{zero_tone_instruction()}

RECIPE CONTENT RULES:
- include a useful description of the finished dish in 2 to 4 sentences;
- when ZERO MODE is active, the description/warning/notes may use dry, witty wording,
  but the cooking instructions themselves must remain precise and practical;
- instructions must be genuinely step-by-step and COMPLETE enough to cook and serve the dish without guessing;
- include cooking times, oven temperatures / heat levels, and key quantities in the relevant steps when useful;
- instructions should usually contain 4 to 8 complete steps for a cooked meal, unless the recipe truly needs fewer;
- the FINAL step must always finish the dish and explain how to assemble/plate/serve it;
- never stop mid-sentence and never leave the preparation unfinished;
- do not merely repeat the ingredient list as instructions.

JSON OUTPUT RULES:
- output exactly one JSON object and nothing else;
- use double quotes for every JSON key and string;
- do not include trailing commas;
- all numeric values must be JSON numbers, never strings with units;
- warning and notes must be strings, even when empty;
- target_not_reached must be true or false;
- instructions must be an array of strings;
- ingredients must be an array of objects;
- do not use NaN, Infinity, comments or markdown.

Return ONLY valid JSON with this exact structure:
{{
  "name": "recipe name",
  "meal_type": "{meal_type}",
  "servings": {float(servings):g},
  "total_minutes": 25,
  "active_minutes": 15,
  "nutrition_per_serving": {{
    "calories": 600,
    "protein": 40,
    "carbs": 65,
    "fat": 18
  }},
  "ingredients": [
    {{
      "name": "ingredient name",
      "quantity_g": 250,
      "calories_per_100g": 165,
      "protein_per_100g": 31,
      "carbs_per_100g": 0,
      "fat_per_100g": 3.6
    }}
  ],
  "description": "2-4 sentence appetizing description of the dish, its texture/flavour and why it fits the requested targets",
  "instructions": [
    "Step 1 with precise action, ingredient quantity when useful, heat/temperature and timing",
    "Step 2 with precise action and timing",
    "Continue until the dish is fully finished and ready to serve"
  ],
  "notes": "short optional serving or preparation note",
  "target_not_reached": false,
  "warning": ""
}}
""".strip()

    client = OpenAI(
        api_key=api_key,
        base_url="https://api.groq.com/openai/v1",
    )

    _recipe_model = resolve_groq_text_model()

    response = client.chat.completions.create(
        model=_recipe_model,
        messages=[
            {
                "role": "system",
                "content": (
                    "You are SanoSync Recipe AI. "
                    "Return ONLY one valid JSON object. "
                    "No markdown fences. No prose before or after JSON. "
                    "Never output reasoning, analysis or <think> tags."
                ),
            },
            {"role": "user", "content": prompt},
        ],
        # IMPORTANT:
        # Do not use response_format/json_object here. Some Groq models
        # available to this project reject the richer generated structure
        # server-side with json_validate_failed even though plain completion
        # works correctly.
        temperature=0.55,
        max_tokens=2200,
        stream=False,
    )

    raw = response.choices[0].message.content

    try:
        data = _extract_json_object_tolerant(raw)
    except Exception:
        data = _repair_recipe_json_with_groq(
            client,
            _recipe_model,
            raw,
        )

    return _normalize_ai_recipe_result(data, servings)




def resolve_groq_whisper_model():
    """Pick an audio transcription model available to this Groq API key."""
    available = set(get_groq_available_model_ids())
    preferred = [
        "whisper-large-v3-turbo",
        "whisper-large-v3",
        "distil-whisper-large-v3-en",
    ]
    for model_id in preferred:
        if model_id in available:
            return model_id

    whisper_models = [
        m for m in sorted(available)
        if "whisper" in m.lower()
    ]
    if whisper_models:
        return whisper_models[0]

    raise RuntimeError(
        "Nessun modello Whisper disponibile per questa API key Groq."
    )


def transcribe_ingredient_audio_with_groq(audio_file, language="Italiano"):
    """
    Transcribe a Streamlit st.audio_input WAV recording through Groq Whisper.
    The returned text is then used by the existing SanoSync ingredient parser.
    """
    if audio_file is None:
        return ""

    api_key = st.secrets.get("GROQ_API_KEY")
    if not api_key:
        raise RuntimeError(
            "GROQ_API_KEY non configurata nei Secrets di Streamlit."
        )

    audio_bytes = audio_file.getvalue()
    if not audio_bytes:
        raise RuntimeError("La registrazione audio è vuota.")

    lang_code = {
        "Italiano": "it",
        "English": "en",
        "Nederlands": "nl",
        "Français": "fr",
    }.get(language)

    client = OpenAI(
        api_key=api_key,
        base_url="https://api.groq.com/openai/v1",
    )

    kwargs = {
        "model": resolve_groq_whisper_model(),
        "file": ("ingredients.wav", audio_bytes, "audio/wav"),
        "response_format": "text",
        "temperature": 0,
    }
    if lang_code:
        kwargs["language"] = lang_code

    result = client.audio.transcriptions.create(**kwargs)
    if isinstance(result, str):
        return result.strip()
    return str(getattr(result, "text", "") or "").strip()




def render_subtle_voice_input(*, widget_key, target_key, language, error_label):
    """
    Minimal voice UX:
    - a tiny microphone button toggles recording
    - no popover, no chevron, no extra question-button
    - the actual audio recorder only appears while requested
    - once transcribed, the recorder closes automatically
    """
    open_key = f"{widget_key}_open"

    if st.button(
        "🎙️",
        key=f"{widget_key}_toggle",
        help="Detta gli ingredienti con SanoSync AI",
        use_container_width=False,
    ):
        st.session_state[open_key] = not st.session_state.get(open_key, False)

    if st.session_state.get(open_key, False):
        audio = st.audio_input(
            "Microphone",
            sample_rate=16000,
            key=widget_key,
            label_visibility="collapsed",
            width=220,
        )

        if audio is not None:
            audio_bytes = audio.getvalue()
            audio_sig = hashlib.sha256(audio_bytes).hexdigest()
            sig_key = f"{widget_key}_processed_sig"

            if st.session_state.get(sig_key) != audio_sig:
                try:
                    with st.spinner("🎙️"):
                        transcript = transcribe_ingredient_audio_with_groq(
                            audio,
                            language,
                        )

                    if transcript:
                        existing = str(
                            st.session_state.get(target_key, "") or ""
                        ).strip()
                        st.session_state[target_key] = (
                            f"{existing}, {transcript}"
                            if existing
                            else transcript
                        )
                        st.session_state[sig_key] = audio_sig
                        st.session_state[open_key] = False
                        st.rerun()

                except Exception as exc:
                    st.error(error_label.format(error=exc))



def render_ai_ingredient_header(
    *,
    title,
    help_text,
    widget_key,
    target_key,
    language,
    error_label,
):
    """
    Compact AI header used inside the SanoSync AI spotlight card.
    """
    _title_col, _mic_col = st.columns(
        [9.2, 0.8],
        gap="small",
        vertical_alignment="center",
    )

    with _title_col:
        st.markdown(
            f"""
            <div style="
                font-size:1rem;
                font-weight:900;
                line-height:1.25;
                color:{'#F7F7F7' if is_zero_mode() else '#1A2942'};
                padding:0;
            ">
                {title}
            </div>
            """,
            unsafe_allow_html=True,
        )

    with _mic_col:
        render_subtle_voice_input(
            widget_key=widget_key,
            target_key=target_key,
            language=language,
            error_label=error_label,
        )


def render_ai_spotlight_css():
    """Visual treatment for the SanoSync AI ingredient fields."""
    if is_zero_mode():
        st.markdown(
            """
            <style>
            div[class*="st-key-ai_spotlight_"] {
                border: 1.5px solid #C91A16 !important;
                border-radius: 18px !important;
                padding: 15px 17px 17px 17px !important;
                margin: 8px 0 14px 0 !important;
                background:
                    radial-gradient(circle at 96% 8%, rgba(225,6,0,.17), transparent 34%),
                    linear-gradient(145deg,#121212,#080808) !important;
                box-shadow: 0 10px 26px rgba(0,0,0,.30) !important;
            }

            div[class*="st-key-ai_spotlight_"] textarea {
                border: 1.2px solid #696969 !important;
                border-radius: 13px !important;
                background: #151515 !important;
                color:#F5F5F5 !important;
                -webkit-text-fill-color:#F5F5F5 !important;
            }

            div[class*="st-key-ai_spotlight_"] textarea::placeholder {
                color:#919191 !important;
                -webkit-text-fill-color:#919191 !important;
            }

            div[class*="st-key-ai_spotlight_"] textarea:focus {
                border-color: #FF2A20 !important;
                box-shadow: 0 0 0 2px rgba(225,6,0,.14) !important;
            }

            div[class*="st-key-ai_spotlight_"] button {
                border-radius: 11px !important;
                background:#111 !important;
                border-color:#C91A16 !important;
                color:#FFF !important;
            }
            </style>
            """,
            unsafe_allow_html=True,
        )
    else:
        st.markdown(
            """
            <style>
            div[class*="st-key-ai_spotlight_"] {
                border: 2px solid #FF8B8B !important;
                border-radius: 20px !important;
                padding: 16px 18px 18px 18px !important;
                margin: 8px 0 14px 0 !important;
                background:
                    radial-gradient(circle at 96% 8%, rgba(255,139,139,.18), transparent 34%),
                    linear-gradient(135deg, rgba(255,255,255,.96), rgba(255,246,246,.92)) !important;
                box-shadow: 0 10px 28px rgba(26,41,66,.08) !important;
            }
            div[class*="st-key-ai_spotlight_"] textarea {
                border: 1.5px solid rgba(255,139,139,.55) !important;
                border-radius: 14px !important;
                background: rgba(248,249,252,.98) !important;
            }
            div[class*="st-key-ai_spotlight_"] textarea:focus {
                border-color: #FF6F75 !important;
                box-shadow: 0 0 0 2px rgba(255,111,117,.12) !important;
            }
            div[class*="st-key-ai_spotlight_"] button {
                border-radius: 12px !important;
            }
            </style>
            """,
            unsafe_allow_html=True,
        )



def parse_recipe_ingredients_with_ai(ingredient_text, language="Italiano"):
    """
    Convert free ingredient text into recipe_builder_ingredients.

    Groq occasionally rejects response_format=json_object before returning any
    content (json_validate_failed). We therefore:
      1. try strict JSON mode;
      2. retry without response_format using an even simpler prompt;
      3. extract the first JSON object from the model text.
    """
    raw_text = str(ingredient_text or "").strip()
    if not raw_text:
        return []

    api_key = st.secrets.get("GROQ_API_KEY")
    if not api_key:
        raise RuntimeError(
            "GROQ_API_KEY non configurata nei Secrets di Streamlit."
        )

    language_name = {
        "Italiano": "Italian",
        "English": "English",
        "Nederlands": "Dutch",
        "Français": "French",
        "Português": "Portuguese",
    }.get(language, "Italian")

    schema_example = """
{
  "ingredients": [
    {
      "name": "chicken breast",
      "quantity_g": 250,
      "calories_per_100g": 165,
      "protein_per_100g": 31,
      "carbs_per_100g": 0,
      "fat_per_100g": 3.6
    }
  ]
}
""".strip()

    prompt = f"""
Extract ONLY the ingredients explicitly present in this text:

{raw_text}

Return one JSON object matching this example:
{schema_example}

Requirements:
- ingredient names must be in {language_name};
- preserve user quantities;
- kg -> g;
- estimate grams for common units only when grams were not supplied;
- use realistic average nutrition values per 100 g;
- do NOT add ingredients;
- every numeric value must be a JSON number;
- no markdown, no prose, no reasoning.
""".strip()

    client = OpenAI(
        api_key=api_key,
        base_url="https://api.groq.com/openai/v1",
    )

    def _extract_json_object(text):
        cleaned = str(text or "").strip()
        cleaned = re.sub(
            r"^```(?:json)?\s*",
            "",
            cleaned,
            flags=re.I,
        )
        cleaned = re.sub(r"\s*```$", "", cleaned).strip()

        try:
            return json.loads(cleaned)
        except Exception:
            pass

        # Fallback for a model that wrapped the JSON in one sentence.
        first = cleaned.find("{")
        last = cleaned.rfind("}")
        if first >= 0 and last > first:
            return json.loads(cleaned[first:last + 1])

        raise ValueError(
            "La risposta AI non contiene un oggetto JSON leggibile."
        )

    messages = [
        {
            "role": "system",
            "content": (
                "You are a food ingredient parser. "
                "Return only a single valid JSON object. "
                "Never expose reasoning."
            ),
        },
        {"role": "user", "content": prompt},
    ]

    raw = None
    first_error = None

    # Attempt 1 — strict JSON mode.
    try:
        response = client.chat.completions.create(
            model=resolve_groq_text_model(),
            messages=messages,
            response_format={"type": "json_object"},
            temperature=0,
            max_tokens=1800,
            stream=False,
        )
        raw = response.choices[0].message.content
    except Exception as exc:
        first_error = exc

    # Attempt 2 — Groq may reject JSON validation server-side.
    if not raw:
        retry_prompt = f"""
Ingredient text:
{raw_text}

Output ONLY JSON. No code fence.

Exact top-level shape:
{{"ingredients":[{{"name":"...","quantity_g":100,"calories_per_100g":0,"protein_per_100g":0,"carbs_per_100g":0,"fat_per_100g":0}}]}}

Names in {language_name}. Include only ingredients in the input.
""".strip()

        try:
            response = client.chat.completions.create(
                model=resolve_groq_text_model(),
                messages=[
                    {
                        "role": "system",
                        "content": (
                            "Return valid JSON only. "
                            "Do not explain anything."
                        ),
                    },
                    {"role": "user", "content": retry_prompt},
                ],
                temperature=0,
                max_tokens=1800,
                stream=False,
            )
            raw = response.choices[0].message.content
        except Exception as retry_exc:
            if first_error is not None:
                raise RuntimeError(
                    "SanoSync AI non è riuscita a strutturare gli "
                    "ingredienti dopo due tentativi. "
                    f"Primo errore: {first_error}. "
                    f"Retry: {retry_exc}"
                ) from retry_exc
            raise

    data = _extract_json_object(raw)
    items = data.get("ingredients") or []
    result = []

    for item in items:
        if not isinstance(item, dict):
            continue

        name = str(item.get("name") or "").strip()
        quantity_g = max(
            0.0,
            _safe_float(item.get("quantity_g")),
        )

        if not name or quantity_g <= 0:
            continue

        result.append(
            {
                "name": name,
                "quantity_g": quantity_g,
                "calories_per_100g": max(
                    0.0,
                    _safe_float(
                        item.get("calories_per_100g")
                    ),
                ),
                "protein_per_100g": max(
                    0.0,
                    _safe_float(
                        item.get("protein_per_100g")
                    ),
                ),
                "carbs_per_100g": max(
                    0.0,
                    _safe_float(
                        item.get("carbs_per_100g")
                    ),
                ),
                "fat_per_100g": max(
                    0.0,
                    _safe_float(
                        item.get("fat_per_100g")
                    ),
                ),
                "source": "ai",
            }
        )

    if not result:
        raise ValueError(
            "SanoSync AI ha risposto, ma non ha restituito "
            "ingredienti utilizzabili."
        )

    return result


# 9. PAGE 1: MEAL LOGGING
# ==============================================================================
if selected_page == t["t1"]:
    log_date = st.date_input("📅 Data", value=date.today())
    render_page_title_card(t["tab1_title"])

    # ------------------------------------------------------------------
    # ✨ SANOSYNC AI · POSSO MANGIARLO?
    # Dedicated prospective-food field, intentionally separate from logging.
    # ------------------------------------------------------------------
    _cie = CAN_I_EAT_I18N.get(
        current_lang,
        CAN_I_EAT_I18N["Italiano"],
    )

    if log_date == date.today():
        if is_zero_mode():
            st.markdown(
                """
                <style>
                .st-key-can_i_eat_spotlight {
                    border:1.5px solid #C91A16 !important;
                    border-radius:18px !important;
                    padding:16px 18px 18px 18px !important;
                    margin:0 0 1rem 0 !important;
                    background:
                        radial-gradient(circle at 96% 6%, rgba(225,6,0,.17), transparent 34%),
                        linear-gradient(145deg,#121212,#080808) !important;
                    box-shadow:0 10px 26px rgba(0,0,0,.30) !important;
                }
                .st-key-can_i_eat_spotlight input {
                    background:#151515 !important;
                    border:1.2px solid #696969 !important;
                    color:#F5F5F5 !important;
                }
                </style>
                """,
                unsafe_allow_html=True,
            )
        else:
            st.markdown(
                """
                <style>
                .st-key-can_i_eat_spotlight {
                    border: 2px solid #FF8B8B !important;
                    border-radius: 20px !important;
                    padding: 16px 18px 18px 18px !important;
                    margin: 0 0 1rem 0 !important;
                    background:
                        radial-gradient(circle at 96% 6%, rgba(255,139,139,.20), transparent 32%),
                        linear-gradient(135deg, rgba(255,255,255,.98), rgba(255,246,246,.94)) !important;
                    box-shadow: 0 10px 28px rgba(26,41,66,.08) !important;
                }
                .st-key-can_i_eat_spotlight input {
                    border: 1.5px solid rgba(255,139,139,.55) !important;
                    border-radius: 13px !important;
                }
                </style>
                """,
                unsafe_allow_html=True,
            )

        with st.container(key="can_i_eat_spotlight"):
            st.markdown(f"### {_cie['title']}")

            _can_i_eat_text = st.text_input(
                _cie["label"],
                placeholder=_cie["placeholder"],
                help=_cie["help"],
                key="can_i_eat_query",
            )

            if st.button(
                _cie["button"],
                type="primary",
                use_container_width=True,
                key="can_i_eat_submit",
            ):
                if _can_i_eat_text.strip():
                    try:
                        _cie_thinking = (
                            ZERO_COPY.get(
                                current_lang,
                                ZERO_COPY["Italiano"],
                            ).get("thinking")
                            if is_zero_mode()
                            else _cie["thinking"]
                        )
                        with st.spinner(_cie_thinking):
                            _today_str = str(date.today())

                            _cie_totals = get_daily_totals(_today_str)
                            _cie_meals = _cie_totals["meals"]
                            _cie_activities = _cie_totals["activities"]
                            _cie_calories_eaten = _cie_totals["calories"]
                            _cie_protein_eaten = _cie_totals["protein"]
                            _cie_activity_burn = _cie_totals["activity"]

                            # Full-day BMR + today's logged activity.
                            _cie_maintenance_budget = max(
                                0.0,
                                _safe_float(user_bmr) + _cie_activity_burn,
                            )

                            _can_i_eat_result = generate_can_i_eat_advice(
                                food_request=_can_i_eat_text.strip(),
                                language=current_lang,
                                calories_eaten=_cie_calories_eaten,
                                maintenance_budget=_cie_maintenance_budget,
                                deficit_target=user_deficit_target_kcal,
                                protein_eaten=_cie_protein_eaten,
                                protein_goal=(
                                    user_protein_goal_g
                                    if user_protein_goal_enabled
                                    else None
                                ),
                            )
                        st.session_state[
                            "can_i_eat_result"
                        ] = _can_i_eat_result
                        queue_ui_sound("ai_food_fit_answer")
                    except Exception as exc:
                        st.error(
                            _cie["error"].format(error=exc)
                        )

            _can_i_eat_result = st.session_state.get(
                "can_i_eat_result"
            )
            if _can_i_eat_result:
                st.markdown(
                    f"**{html.escape(_can_i_eat_result['food_name'])}**"
                )
                if _can_i_eat_result.get("message"):
                    st.write(_can_i_eat_result["message"])

                _cie_c1, _cie_c2, _cie_c3, _cie_c4 = st.columns(4)
                _cie_c1.metric(
                    _cie["estimate"],
                    f"{_can_i_eat_result['estimated_kcal']:.0f} kcal",
                )
                _cie_c2.metric(
                    "Pro",
                    f"{_can_i_eat_result['estimated_protein_g']:.0f} g",
                )
                _cie_c3.metric(
                    "Carbs",
                    f"{_can_i_eat_result['estimated_carbs_g']:.0f} g",
                )
                _cie_c4.metric(
                    _cie["remaining_after"],
                    f"{_can_i_eat_result['remaining_after']:+.0f} kcal",
                )

    recipe_source_label = {
        "Italiano": "🍲 Ricette",
        "English": "🍲 Recipes",
        "Nederlands": "🍲 Recepten",
    }.get(current_lang, "🍲 Ricette")

    _input_source_options = [
        t["opt_ai"],
        t["opt_quick"],
        t["opt_scan"],
        t["opt_off"],
    ]

    # Se il pasto precedente è stato salvato, il reset della sorgente viene
    # applicato QUI, prima che il widget venga istanziato. In questo modo
    # evitiamo l'errore Streamlit:
    # "session_state.meal_input_source cannot be modified after the widget..."
    if st.session_state.pop("_reset_meal_input_source_next_run", False):
        st.session_state["meal_input_source"] = _input_source_options[0]

    if (
        "meal_input_source" not in st.session_state
        or st.session_state["meal_input_source"] not in _input_source_options
    ):
        st.session_state["meal_input_source"] = _input_source_options[0]

    st.markdown(
        """
        <style>
        .st-key-meal_input_source [role="radiogroup"] {
            gap:.65rem !important;
        }
        .st-key-meal_input_source [role="radiogroup"] label {
            border:1px solid rgba(255,139,139,.40);
            border-radius:999px;
            padding:.42rem .70rem;
            background:rgba(255,255,255,.72);
        }
        .st-key-meal_input_source [role="radiogroup"] label:has(input:checked) {
            background:#FFF0F0;
            border-color:#FF8B8B;
            box-shadow:0 3px 10px rgba(255,139,139,.13);
        }
        </style>
        """,
        unsafe_allow_html=True,
    )

    input_source = st.radio(
        t["input_source_lbl"],
        _input_source_options,
        horizontal=True,
        key="meal_input_source",
    )

    is_ai = input_source == t["opt_ai"]
    is_quick = input_source == t["opt_quick"]
    is_scan = input_source == t["opt_scan"]
    is_online = input_source == t["opt_off"]
    is_recipe = False  # Ricette integrate in Immissione Rapida
    v = st.session_state["form_version"]

    if "base_cals" not in st.session_state:
        st.session_state["base_cals"] = 0.0
        st.session_state["base_prot"] = 0.0
        st.session_state["base_carbs"] = 0.0
        st.session_state["base_fat"] = 0.0
        st.session_state["m_name"] = ""
        st.session_state["grams_val"] = 100.0
        st.session_state["is_per_100g_val"] = True

    def reset_or_update(name="", cals=0, prot=0, carbs=0, fat=0, selected="", grams=100.0,
                        is_100g=True, note="", category="Casa",
                        ingredients_json=None, recipe_servings=None):
        st.session_state["m_name"] = name
        st.session_state["base_cals"] = float(cals)
        st.session_state["base_prot"] = float(prot)
        st.session_state["base_carbs"] = float(carbs)
        st.session_state["base_fat"] = float(fat)
        st.session_state["grams_val"] = float(grams)
        st.session_state["is_per_100g_val"] = bool(is_100g)
        st.session_state["last_selected"] = selected
        st.session_state["selected_source_note"] = str(note or "")
        st.session_state["selected_source_category"] = category if category in MEAL_CATEGORIES else "Casa"
        st.session_state["selected_recipe_ingredients"] = (
            [dict(i) for i in ingredients_json]
            if isinstance(ingredients_json, list)
            else None
        )
        st.session_state["selected_recipe_servings"] = (
            float(recipe_servings)
            if recipe_servings not in (None, "")
            else None
        )
        st.session_state["form_version"] += 1

    def clear_meal_entry_after_save():
        """
        Ripulisce completamente il form dopo un inserimento riuscito e
        riporta la sorgente al primo metodo predefinito.

        L'incremento di form_version genera nuove key per tutti i widget
        dinamici, quindi nome, quantità, kcal, macro, note e selezioni
        non restano popolati dal pasto precedente.
        """
        # Valori nutrizionali / nome / quantità.
        reset_or_update()

        # Sorgenti e risultati temporanei.
        st.session_state["api_res"] = {}
        st.session_state["prod_select"] = ""
        st.session_state.pop("ai_photo_analysis_done", None)

        # Il widget meal_input_source è già stato istanziato in questa run:
        # non possiamo modificarne direttamente il valore. Prepariamo quindi
        # il reset per la run successiva, prima della creazione del widget.
        st.session_state["_reset_meal_input_source_next_run"] = True
        st.session_state.pop("last_source", None)

        # Elimina anche lo stato della foto AI precedente.
        st.session_state.pop("ai_last_photo_hash", None)


    if st.session_state.get("last_source") != input_source:
        st.session_state["last_source"] = input_source
        reset_or_update()
        st.rerun()

    # --------------------------------------------------------------
    # METODO DI INSERIMENTO
    # Card sorgente: AI / Immissione Rapida / Foto / OpenFood Database
    # --------------------------------------------------------------
    with st.container(border=True):
        st.markdown(f"### {input_source}")

        # ------------------------------------------------------------------
        # A. SanoSync AI — free ingredient description
        # ------------------------------------------------------------------
        if is_ai:
            _meal_ai_i18n = {
                "Italiano": {
                    "caption": "Scrivi cosa hai mangiato. SanoSync AI riconosce ingredienti e quantità; nome, kcal e macro vengono compilati automaticamente.",
                    "placeholder": "Es. 250g pollo, 120g riso, 200g zucchine, 10g olio",
                    "portions": "Porzioni",
                    "analyze": "✨ Calcola con SanoSync AI",
                    "spinner": "SanoSync AI sta ricostruendo il pasto…",
                    "error": "Errore nell'analisi: {error}",
                    "voice_error": "Impossibile trascrivere l’audio: {error}",
                    "default_name": "Pasto AI",
                },
                "English": {
                    "caption": "Describe what you ate. SanoSync AI recognizes ingredients and quantities; name, calories and macros are filled in automatically.",
                    "placeholder": "E.g. 250g chicken, 120g rice, 200g courgette, 10g oil",
                    "portions": "Servings",
                    "analyze": "✨ Calculate with SanoSync AI",
                    "spinner": "SanoSync AI is reconstructing the meal…",
                    "error": "Analysis error: {error}",
                    "voice_error": "Could not transcribe the audio: {error}",
                    "default_name": "AI meal",
                },
                "Nederlands": {
                    "caption": "Beschrijf wat je hebt gegeten. SanoSync AI herkent ingrediënten en hoeveelheden; naam, calorieën en macro's worden automatisch ingevuld.",
                    "placeholder": "Bijv. 250g kip, 120g rijst, 200g courgette, 10g olie",
                    "portions": "Porties",
                    "analyze": "✨ Bereken met SanoSync AI",
                    "spinner": "SanoSync AI reconstrueert de maaltijd…",
                    "error": "Analysefout: {error}",
                    "voice_error": "Kon de audio niet transcriberen: {error}",
                    "default_name": "AI-maaltijd",
                },
                "Français": {
                    "caption": "Décrivez ce que vous avez mangé. SanoSync AI reconnaît les ingrédients et les quantités ; le nom, les calories et les macros sont remplis automatiquement.",
                    "placeholder": "Ex. 250g poulet, 120g riz, 200g courgettes, 10g huile",
                    "portions": "Portions",
                    "analyze": "✨ Calculer avec SanoSync AI",
                    "spinner": "SanoSync AI reconstruit le repas…",
                    "error": "Erreur d'analyse : {error}",
                    "voice_error": "Impossible de transcrire l’audio : {error}",
                    "default_name": "Repas IA",
                },
            }
            _mai = _meal_ai_i18n.get(
                current_lang,
                _meal_ai_i18n["Italiano"],
            )

            st.caption(_mai["caption"])

            _tab1_ai_text_key = f"tab1_ai_ingredient_text_{v}"
            render_ai_spotlight_css()

            with st.container(key=f"ai_spotlight_tab1_{v}"):
                render_ai_ingredient_header(
                    title="SanoSync AI",
                    help_text=_mai["caption"],
                    widget_key=f"sanosync_voice_tab1_{v}",
                    target_key=_tab1_ai_text_key,
                    language=current_lang,
                    error_label=_mai["voice_error"],
                )
                _tab1_ai_text = st.text_area(
                    "SanoSync AI",
                    key=_tab1_ai_text_key,
                    placeholder=_mai["placeholder"],
                    height=88,
                    label_visibility="collapsed",
                )

            _ai_col1, _ai_col2 = st.columns([1, 2])
            with _ai_col1:
                _tab1_ai_portions = st.number_input(
                    _mai["portions"],
                    min_value=1.0,
                    max_value=20.0,
                    value=1.0,
                    step=1.0,
                    key=f"tab1_ai_portions_{v}",
                )
            with _ai_col2:
                st.write("")
                st.write("")
                _run_tab1_ai = st.button(
                    _mai["analyze"],
                    use_container_width=True,
                    type="primary",
                    key=f"tab1_ai_analyze_{v}",
                )

            if _run_tab1_ai and str(_tab1_ai_text or "").strip():
                try:
                    with st.spinner(_mai["spinner"]):
                        _parsed = parse_recipe_ingredients_with_ai(
                            _tab1_ai_text,
                            current_lang,
                        )

                    if _parsed:
                        _tw, _totals, _p100 = calculate_recipe_totals(
                            _parsed
                        )
                        _parts = max(float(_tab1_ai_portions), 1.0)
                        _per_portion = {
                            k: float(val) / _parts
                            for k, val in _totals.items()
                        }

                        # Generate a compact, editable meal name from the parsed food.
                        _ingredient_names = [
                            str(x.get("name") or "").strip()
                            for x in _parsed
                            if str(x.get("name") or "").strip()
                        ]
                        _auto_name = ", ".join(_ingredient_names[:3])
                        if len(_ingredient_names) > 3:
                            _auto_name += "…"
                        if not _auto_name:
                            _auto_name = _mai["default_name"]

                        reset_or_update(
                            name=_auto_name,
                            cals=_per_portion["calories"],
                            prot=_per_portion["protein"],
                            carbs=_per_portion["carbs"],
                            fat=_per_portion["fat"],
                            selected=f"ai:{_tab1_ai_text}",
                            grams=1.0,
                            is_100g=False,
                        )
                        st.session_state[
                            f"tab1_ai_result_{v}"
                        ] = _parsed
                        queue_ui_sound("ai_ingredients_analyzed")
                        st.rerun()
                except Exception as exc:
                    st.error(_mai["error"].format(error=exc))

        # ------------------------------------------------------------------
        # B. Open Food Facts
        # ------------------------------------------------------------------
        elif is_online:
            search_q = st.text_input(t["search_food"])
            if st.button(t["search_btn"]):
                if len(search_q.strip()) >= 2 or search_q.strip().isdigit():
                    with st.spinner("Ricerca in Open Food Facts..."):
                        st.session_state["api_res"] = search_open_food_facts(search_q)
                    st.session_state["prod_select"] = ""
                    st.session_state["last_selected"] = ""
                    if not st.session_state["api_res"]:
                        st.info(t["no_products"])
                    st.rerun()
                else:
                    st.warning(t["search_min_chars"])

            api_res = st.session_state.get("api_res", {})
            if api_res:
                sel_prod = st.selectbox(t["select_db"], [""] + list(api_res.keys()), key=f"prod_select_{v}")
                if sel_prod and sel_prod != st.session_state.get("last_selected"):
                    p_data = api_res[sel_prod]
                    reset_or_update(
                        p_data.get("name", ""),
                        p_data.get("calories", 0),
                        p_data.get("protein", 0),
                        p_data.get("carbs", 0),
                        p_data.get("fat", 0),
                        sel_prod,
                        100.0,
                        True,
                    )
                    st.rerun()

        # ------------------------------------------------------------------
        # B. Immissione rapida = storico meals, NON recipes
        # ------------------------------------------------------------------
        elif is_quick:
            try:
                # ------------------------------------------------------
                # Colazione standard — one-click, only if breakfast has
                # not yet been logged on the selected date.
                # ------------------------------------------------------
                if not breakfast_already_logged(log_date):
                    _default_ids = get_default_breakfast_recipe_ids()
                    _default_breakfasts = []

                    _home_recipe = load_personal_recipe_by_id(
                        _default_ids.get("Casa")
                    )
                    if _home_recipe:
                        _default_breakfasts.append(
                            ("Casa", _home_recipe)
                        )

                    if user_office_lunch_enabled:
                        _work_recipe = load_personal_recipe_by_id(
                            _default_ids.get("Lavoro")
                        )
                        if _work_recipe:
                            _default_breakfasts.append(
                                ("Lavoro", _work_recipe)
                            )

                    if _default_breakfasts:
                        _db_i18n = {
                            "Italiano": {
                                "title": "☕ Colazione standard",
                                "home": "🏠 Colazione Casa",
                                "work": "💼 Colazione Lavoro",
                                "done": "Colazione inserita.",
                            },
                            "English": {
                                "title": "☕ Default breakfast",
                                "home": "🏠 Home breakfast",
                                "work": "💼 Work breakfast",
                                "done": "Breakfast logged.",
                            },
                            "Nederlands": {
                                "title": "☕ Standaardontbijt",
                                "home": "🏠 Ontbijt thuis",
                                "work": "💼 Ontbijt werk",
                                "done": "Ontbijt opgeslagen.",
                            },
                            "Français": {
                                "title": "☕ Petit-déjeuner standard",
                                "home": "🏠 Petit-déjeuner maison",
                                "work": "💼 Petit-déjeuner travail",
                                "done": "Petit-déjeuner enregistré.",
                            },
                        }.get(
                            current_lang,
                            {},
                        )

                        st.markdown(
                            f"**{_db_i18n.get('title', '☕ Colazione standard')}**"
                        )
                        _db_cols = st.columns(
                            len(_default_breakfasts)
                        )

                        for _db_col, (
                            _db_category,
                            _db_recipe,
                        ) in zip(
                            _db_cols,
                            _default_breakfasts,
                        ):
                            _db_label = (
                                _db_i18n.get("work")
                                if _db_category == "Lavoro"
                                else _db_i18n.get("home")
                            )
                            _db_label = (
                                f"{_db_label} · "
                                f"{str(_db_recipe.get('name') or '')}"
                            )

                            with _db_col:
                                if st.button(
                                    _db_label,
                                    key=(
                                        "quick_default_breakfast_"
                                        f"{_db_category}_{v}"
                                    ),
                                    use_container_width=True,
                                    type="primary",
                                ):
                                    insert_default_breakfast_recipe(
                                        _db_recipe,
                                        log_date,
                                        _db_category,
                                    )
                                    queue_ui_sound("food_saved")
                                    refresh_daily_logs(log_date)
                                    st.success(
                                        _db_i18n.get(
                                            "done",
                                            "Colazione inserita.",
                                        )
                                    )
                                    st.rerun()

                        st.divider()

                quick_entries = get_quick_entries_from_meals()
                recipe_rows = load_available_recipes()

                if not user_office_lunch_enabled:
                    quick_entries = [q for q in quick_entries if q.get("category", "Casa") != "Lavoro"]
                    recipe_rows = [r for r in recipe_rows if r.get("category", "Casa") != "Lavoro"]

                unified = {}
                for q in quick_entries:
                    unified[f"🕘 {q['label']}"] = ("history", q)

                for r in recipe_rows:
                    name = str(r.get("name") or "").strip()
                    if not name:
                        continue
                    prefix = "🍲" if str(r.get("user_id")) == str(user_id) else "🌍"
                    unified[f"{prefix} {name}"] = ("recipe", r)

                if unified:
                    sel_quick = st.selectbox(
                        t["quick_select_used"],
                        [""] + list(unified.keys()),
                        key=f"quick_meal_select_{v}",
                    )
                    if sel_quick and sel_quick != st.session_state.get("last_selected"):
                        source_type, item = unified[sel_quick]
                        if source_type == "history":
                            q = item
                            reset_or_update(
                                q["name"], q["calories"], q["protein"], q["carbs"], q["fat"],
                                sel_quick, q["default_quantity"], q["is_per_100g"],
                                q.get("notes", ""), q.get("category", "Casa"),
                            )
                        else:
                            r = item
                            servings = max(1.0, _safe_float(r.get("recipe_servings") or 1.0))
                            reset_or_update(
                                str(r.get("name") or ""),
                                _safe_float(r.get("calories")) / servings,
                                _safe_float(r.get("protein")) / servings,
                                _safe_float(r.get("carbs")) / servings,
                                _safe_float(r.get("fat")) / servings,
                                sel_quick, 1.0, False,
                                r.get("notes", ""), r.get("category", "Casa"),
                                ingredients_json=r.get("ingredients_json"),
                                recipe_servings=servings,
                            )
                        st.rerun()
                else:
                    st.info(t["quick_empty"])
            except Exception as e:
                st.error(t["quick_load_error"].format(error=e))

        # ------------------------------------------------------------------
        # C. Foto AI
        # La fotocamera viene creata SOLO quando l'utente seleziona Foto AI.
        # ------------------------------------------------------------------
        elif is_scan:
            st.caption(t["scan_camera_help"])

            _scan_mode = st.radio(
                t["scan_mode"],
                [t["scan_camera"], t["scan_upload"]],
                horizontal=True,
                key=f"scan_mode_{v}",
            )

            _scan_photo = None
            if _scan_mode == t["scan_camera"]:
                # Custom camera: asks mobile browsers for the rear camera first.
                _scan_photo = rear_camera_input(
                    key=f"meal_rear_camera_{v}",
                )
            else:
                _scan_photo = st.file_uploader(
                    t["scan_upload"],
                    type=["jpg", "jpeg", "png", "webp"],
                    key=f"meal_scan_upload_{v}",
                    help=t["scan_upload_help"],
                )

            if _scan_photo is not None:
                st.image(_scan_photo, width=420)

                # Analisi automatica: una nuova foto viene inviata subito a Groq.
                # L'hash impedisce di richiamare l'API più volte sulla stessa foto
                # durante i normali rerun di Streamlit.
                _scan_bytes = _scan_photo.getvalue()
                _scan_hash = hashlib.sha256(_scan_bytes).hexdigest()

                if st.session_state.get("ai_last_photo_hash") != _scan_hash:
                    try:
                        with st.spinner(t["scan_analyzing"]):
                            _ai_food = analyze_food_photo_with_ai(
                                _scan_photo,
                                current_lang,
                            )

                        st.session_state["ai_last_photo_hash"] = _scan_hash

                        # L'AI restituisce i nutrienti TOTALI della porzione
                        # fotografata. Li convertiamo in valori per 100 g, così
                        # grammi/kcal/macros restano modificabili e sincronizzati.
                        _ai_grams = max(
                            1.0,
                            _safe_float(_ai_food.get("estimated_grams")),
                        )
                        _factor = 100.0 / _ai_grams

                        reset_or_update(
                            _ai_food["name"],
                            _ai_food["calories"] * _factor,
                            _ai_food["protein"] * _factor,
                            _ai_food["carbs"] * _factor,
                            _ai_food["fat"] * _factor,
                            f"ai_photo_{_scan_hash[:12]}",
                            _ai_grams,
                            True,
                            _ai_food.get("notes", ""),
                            "Casa",
                        )
                        st.session_state["ai_photo_analysis_done"] = True
                        queue_ui_sound("photo_ai_analyzed")
                        st.rerun()

                    except Exception as e:
                        st.error(
                            t["scan_ai_error"].format(error=str(e))
                        )
                else:
                    st.caption(t["scan_ai_next"])

            if st.session_state.pop("ai_photo_analysis_done", False):
                st.success(t["scan_ai_done"])

        # ------------------------------------------------------------------
        # D. Ricette = catalogo permanente recipe_library
        # ------------------------------------------------------------------
        # Ricette legacy (blocco mantenuto per compatibilità; normalmente non raggiunto)
        # ------------------------------------------------------------------
        elif is_recipe:
            try:
                recipe_rows = load_available_recipes()

                recipes_dict = {
                    str(r.get("name") or "").strip(): r
                    for r in recipe_rows
                    if str(r.get("name") or "").strip()
                }

                if recipes_dict:
                    sel_recipe = st.selectbox(
                        t["select_recipe"],
                        [""] + sorted(recipes_dict.keys(), key=str.casefold),
                        key=f"recipe_select_{v}",
                    )

                    if (
                        sel_recipe
                        and sel_recipe != st.session_state.get("last_selected")
                    ):
                        r = recipes_dict[sel_recipe]
                        # _safe_float accetta un solo argomento.
                        # Se recipe_servings è NULL/vuoto, usiamo 1.0 come fallback.
                        _raw_recipe_servings = r.get("recipe_servings")
                        recipe_servings = max(
                            _safe_float(
                                _raw_recipe_servings
                                if _raw_recipe_servings not in (None, "")
                                else 1.0
                            ),
                            1.0,
                        )

                        # Base = UNA porzione.
                        reset_or_update(
                            sel_recipe,
                            _safe_float(r.get("calories")) / recipe_servings,
                            _safe_float(r.get("protein")) / recipe_servings,
                            _safe_float(r.get("carbs")) / recipe_servings,
                            _safe_float(r.get("fat")) / recipe_servings,
                            sel_recipe,
                            1.0,
                            False,
                            r.get("notes", ""),
                            r.get("category", "Casa"),
                        )
                        st.rerun()
                else:
                    st.info(t["no_recipes"])

            except Exception as e:
                st.error(f"Errore nel caricamento delle ricette: {e}")

        # ------------------------------------------------------------------
        elif is_recipe:
            try:
                recipe_rows = fetch_meal_history_from_api(
                    st.session_state.get("auth_access_token")
                )

                recipes_dict = {}
                for r in recipe_rows:
                    if not r.get("ingredients_json"):
                        continue
                    label = (r.get("base_name") or _clean_meal_name(r.get("name")) or "").strip()
                    if not label or label in recipes_dict:
                        continue
                    recipes_dict[label] = r

                if recipes_dict:
                    sel_recipe = st.selectbox(
                        "Seleziona una ricetta",
                        [""] + sorted(recipes_dict.keys(), key=str.casefold),
                        key=f"recipe_select_{v}",
                    )
                    if sel_recipe and sel_recipe != st.session_state.get("last_selected"):
                        r = recipes_dict[sel_recipe]
                        recipe_servings = _safe_float(
                            r.get("recipe_servings"),
                            0.0,
                        )

                        if recipe_servings > 0:
                            # Nuove ricette: base = UNA porzione.
                            reset_or_update(
                                sel_recipe,
                                _safe_float(r.get("calories")) / recipe_servings,
                                _safe_float(r.get("protein")) / recipe_servings,
                                _safe_float(r.get("carbs")) / recipe_servings,
                                _safe_float(r.get("fat")) / recipe_servings,
                                sel_recipe,
                                1.0,
                                False,
                                r.get("notes", ""),
                                infer_meal_category(r),
                            )
                        else:
                            # Ricette legacy: manteniamo il comportamento precedente.
                            is_100g = bool(r.get("is_per_100g", True))
                            reset_or_update(
                                sel_recipe,
                                _safe_float(
                                    r.get("base_calories")
                                    if r.get("base_calories") is not None
                                    else r.get("calories")
                                ),
                                _safe_float(
                                    r.get("base_protein")
                                    if r.get("base_protein") is not None
                                    else r.get("protein")
                                ),
                                _safe_float(
                                    r.get("base_carbs")
                                    if r.get("base_carbs") is not None
                                    else r.get("carbs")
                                ),
                                _safe_float(
                                    r.get("base_fat")
                                    if r.get("base_fat") is not None
                                    else r.get("fat")
                                ),
                                sel_recipe,
                                100.0 if is_100g else 1.0,
                                is_100g,
                                r.get("notes", ""),
                                infer_meal_category(r),
                            )

                        st.rerun()
                else:
                    st.info("Nessuna ricetta composta disponibile. Creane una nella Tab Ricette.")
            except Exception as e:
                st.error(f"Errore nel caricamento ricette: {e}")

        if st.session_state.get("selected_source_note"):
            st.markdown(
                f"Note {info_badge(st.session_state.get('selected_source_note'), 'Note alimento o ricetta')}",
                unsafe_allow_html=True,
            )

    # --------------------------------------------------------------
    # DETTAGLI DEL PASTO
    # Seconda card: dati, quantità e valori nutrizionali
    # --------------------------------------------------------------
    with st.container(border=True):
        meal_options = ["Colazione", "Pranzo", "Cena", "Snack"]

        # Shared default logic used everywhere in SanoSync.
        _suggested_meal_type = suggest_next_meal_type(log_date)

        _meal_type_key = f"meal_type_input_{v}"
        if _meal_type_key not in st.session_state:
            st.session_state[_meal_type_key] = _suggested_meal_type

        _meal_categories_available = (
            MEAL_CATEGORIES
            if user_office_lunch_enabled
            else [c for c in MEAL_CATEGORIES if c != "Lavoro"]
        )
        default_category = st.session_state.get(
            "selected_source_category",
            "Casa",
        )
        if default_category not in _meal_categories_available:
            default_category = "Casa"

        # Compact metadata row: on desktop these selectors no longer consume
        # two full-width rows; on mobile Streamlit stacks them automatically.
        _meal_meta_1, _meal_meta_2 = st.columns(2, gap="medium")
        with _meal_meta_1:
            m_type = st.selectbox(
                t["meal"],
                meal_options,
                key=_meal_type_key,
                format_func=tr_meal_type,
            )
        with _meal_meta_2:
            meal_category = st.selectbox(
                t["category_label"],
                _meal_categories_available,
                index=_meal_categories_available.index(default_category),
                key=f"meal_category_{v}",
                help=t["category_help"],
                format_func=tr_category,
            )

        name = st.text_input(
            t["meal_name"],
            value=st.session_state["m_name"],
            key=f"input_meal_name_{v}",
        )

        # Notes remain internally available for the existing DB schema.
        # AI input now lives exclusively in the top source selector.
        meal_notes = ""

        # --------------------------------------------------------------
        # Ricetta selezionata: mostra e permette di modificare i grammi
        # dei singoli ingredienti. I valori nutrizionali per 100 g restano
        # invariati; kcal e macro del pasto vengono ricalcolati dai grammi.
        # La ricetta salvata nel catalogo NON viene modificata.
        # --------------------------------------------------------------
        _selected_recipe_ingredients = st.session_state.get(
            "selected_recipe_ingredients"
        )
        if _selected_recipe_ingredients:
            st.markdown("#### 🥕 Ingredienti della ricetta")
            st.caption(
                "Modifica solo ciò che è diverso oggi: kcal e macronutrienti "
                "si aggiornano automaticamente."
            )

            _edited_recipe_ingredients = []
            for _ing_idx, _ing in enumerate(_selected_recipe_ingredients):
                _ing_copy = dict(_ing)
                _ing_name = str(_ing_copy.get("name") or f"Ingrediente {_ing_idx + 1}")
                _ing_qty = max(0.0, _safe_float(_ing_copy.get("quantity_g")))

                _ing_cols = st.columns([2.5, 1.2, 2.3], gap="small")
                _ing_cols[0].write(_ing_name)
                _new_ing_qty = _ing_cols[1].number_input(
                    "Quantità (g)",
                    min_value=0.0,
                    value=float(_ing_qty),
                    step=1.0,
                    key=f"daily_recipe_ing_qty_{v}_{_ing_idx}",
                    label_visibility="collapsed",
                )

                _ing_copy["quantity_g"] = float(_new_ing_qty)
                _ing_factor = float(_new_ing_qty) / 100.0
                _ing_kcal = _safe_float(_ing_copy.get("calories_per_100g")) * _ing_factor
                _ing_pro = _safe_float(_ing_copy.get("protein_per_100g")) * _ing_factor
                _ing_carbs = _safe_float(_ing_copy.get("carbs_per_100g")) * _ing_factor
                _ing_fat = _safe_float(_ing_copy.get("fat_per_100g")) * _ing_factor
                _ing_cols[2].caption(
                    f"{_ing_kcal:.0f} kcal · P {_ing_pro:.1f} · "
                    f"C {_ing_carbs:.1f} · F {_ing_fat:.1f}"
                )
                _edited_recipe_ingredients.append(_ing_copy)

            st.session_state["selected_recipe_ingredients"] = _edited_recipe_ingredients

            _recipe_weight, _recipe_totals, _recipe_per100 = calculate_recipe_totals(
                _edited_recipe_ingredients
            )
            _recipe_servings_for_log = max(
                1.0,
                _safe_float(st.session_state.get("selected_recipe_servings") or 1.0),
            )

            # Il form sottostante lavora per porzione. Aggiorniamo quindi i
            # valori base usando i nuovi totali della ricetta divisi per porzioni.
            st.session_state["base_cals"] = _recipe_totals["calories"] / _recipe_servings_for_log
            st.session_state["base_prot"] = _recipe_totals["protein"] / _recipe_servings_for_log
            st.session_state["base_carbs"] = _recipe_totals["carbs"] / _recipe_servings_for_log
            st.session_state["base_fat"] = _recipe_totals["fat"] / _recipe_servings_for_log

            st.caption(
                f"Ricetta aggiornata: {_recipe_weight:.0f} g totali · "
                f"{_recipe_totals['calories']:.0f} kcal · "
                f"P {_recipe_totals['protein']:.1f} g · "
                f"C {_recipe_totals['carbs']:.1f} g · "
                f"F {_recipe_totals['fat']:.1f} g"
            )

        mode_options = [t["per_100g"], t["per_portion"]]
        default_index = 0 if st.session_state["is_per_100g_val"] else 1
        mode = st.radio(
            t["calc_mode"], mode_options, index=default_index,
            horizontal=True, key=f"mode_radio_{v}",
        )

        is_now_100g = mode == t["per_100g"]
        if is_now_100g != st.session_state["is_per_100g_val"]:
            st.session_state["is_per_100g_val"] = is_now_100g
            st.session_state["grams_val"] = 100.0 if is_now_100g else 1.0
            st.session_state[f"dyn_qty_{v}"] = st.session_state["grams_val"]
            st.rerun()

        # ------------------------------------------------------------------
        # Quantità + kcal/macros sincronizzati in tempo reale
        # ------------------------------------------------------------------
        qty_key = f"dyn_qty_{v}"
        kcal_key = f"meal_kcal_{v}"
        pro_key = f"meal_pro_{v}"
        carbs_key = f"meal_carbs_{v}"
        fat_key = f"meal_fat_{v}"

        # Ingredient edits happen above these widgets. When a recipe is active,
        # refresh the displayed totals from the recalculated per-serving base.
        if st.session_state.get("selected_recipe_ingredients"):
            _qty_for_recipe = float(
                st.session_state.get(qty_key, st.session_state.get("grams_val", 1.0))
            )
            _recipe_form_factor = (
                _qty_for_recipe / 100.0
                if mode == t["per_100g"]
                else _qty_for_recipe
            )
            st.session_state[kcal_key] = int(round(st.session_state["base_cals"] * _recipe_form_factor))
            st.session_state[pro_key] = int(round(st.session_state["base_prot"] * _recipe_form_factor))
            st.session_state[carbs_key] = int(round(st.session_state["base_carbs"] * _recipe_form_factor))
            st.session_state[fat_key] = int(round(st.session_state["base_fat"] * _recipe_form_factor))

        def _current_factor(qty=None):
            if qty is None:
                qty = float(st.session_state.get(qty_key, st.session_state["grams_val"]))
            return qty / 100.0 if mode == t["per_100g"] else qty

        def _sync_final_nutrients_from_base():
            """
            Quando cambiano grammi/porzioni aggiorna SUBITO i quattro widget.
            Impostare soltanto value=... non basta in Streamlit, perché un widget
            con key conserva il proprio valore in session_state.
            """
            qty = float(st.session_state.get(qty_key, st.session_state["grams_val"]))
            st.session_state["grams_val"] = qty
            factor_now = _current_factor(qty)

            st.session_state[kcal_key] = int(round(st.session_state["base_cals"] * factor_now))
            st.session_state[pro_key] = int(round(st.session_state["base_prot"] * factor_now))
            st.session_state[carbs_key] = int(round(st.session_state["base_carbs"] * factor_now))
            st.session_state[fat_key] = int(round(st.session_state["base_fat"] * factor_now))

        def _sync_base_from_manual_nutrient(final_key, base_key):
            """
            Se l'utente corregge manualmente kcal o un macro, aggiorna anche il
            valore base (per 100 g / per porzione). Così il successivo cambio di
            quantità continua a scalare partendo dalla correzione manuale.
            """
            factor_now = _current_factor()
            if factor_now <= 0:
                return
            st.session_state[base_key] = (
                float(st.session_state.get(final_key, 0.0)) / factor_now
            )

        def on_qty_change():
            _sync_final_nutrients_from_base()

        def on_kcal_change():
            _sync_base_from_manual_nutrient(kcal_key, "base_cals")

        def on_pro_change():
            _sync_base_from_manual_nutrient(pro_key, "base_prot")

        def on_carbs_change():
            _sync_base_from_manual_nutrient(carbs_key, "base_carbs")

        def on_fat_change():
            _sync_base_from_manual_nutrient(fat_key, "base_fat")

        # Inizializza i widget nutrienti una sola volta per questa versione del form.
        # Dopo di che saranno i callback a mantenerli sincronizzati.
        initial_factor = _current_factor(float(st.session_state["grams_val"]))
        if kcal_key not in st.session_state:
            st.session_state[kcal_key] = int(round(st.session_state["base_cals"] * initial_factor))
        if pro_key not in st.session_state:
            st.session_state[pro_key] = int(round(st.session_state["base_prot"] * initial_factor))
        if carbs_key not in st.session_state:
            st.session_state[carbs_key] = int(round(st.session_state["base_carbs"] * initial_factor))
        if fat_key not in st.session_state:
            st.session_state[fat_key] = int(round(st.session_state["base_fat"] * initial_factor))

        quantity = st.number_input(
            t["qty_label"] if mode == t["per_100g"] else t["num_portions"],
            value=float(st.session_state["grams_val"]),
            min_value=0.25,
            step=0.25,
            key=qty_key,
            on_change=on_qty_change,
        )

        factor = quantity / 100.0 if mode == t["per_100g"] else quantity
        meal_display_name = f"{name} ({quantity}{'g' if mode == t['per_100g'] else ' porz.'})"

        c1, c2, c3, c4 = st.columns(4)
        cals_in = c1.number_input(
            t["kcal"],
            step=1,
            key=kcal_key,
            on_change=on_kcal_change,
        )
        prot_in = c2.number_input(
            t["pro"],
            step=1,
            key=pro_key,
            on_change=on_pro_change,
        )
        carbs_in = c3.number_input(
            t["carbs"],
            step=1,
            key=carbs_key,
            on_change=on_carbs_change,
        )
        fat_in = c4.number_input(
            t["fat"],
            step=1,
            key=fat_key,
            on_change=on_fat_change,
        )

        if st.button(t["add_meal"], use_container_width=True):
            if not name.strip():
                st.warning("Inserisci un nome per il pasto.")
            else:
                try:
                    # I valori base vengono derivati dai valori finali modificabili,
                    # così eventuali correzioni manuali diventano riutilizzabili.
                    safe_factor = factor if factor > 0 else 1.0
                    insert_meal_with_base_data(
                        log_date=log_date,
                        meal_type=m_type,
                        display_name=meal_display_name,
                        base_name=name.strip(),
                        quantity=quantity,
                        is_per_100g=(mode == t["per_100g"]),
                        calories=cals_in,
                        protein=prot_in,
                        carbs=carbs_in,
                        fat=fat_in,
                        base_calories=float(cals_in) / safe_factor,
                        base_protein=float(prot_in) / safe_factor,
                        base_carbs=float(carbs_in) / safe_factor,
                        base_fat=float(fat_in) / safe_factor,
                        notes=meal_notes,
                        category=meal_category,
                        ingredients_json=st.session_state.get("selected_recipe_ingredients"),
                        recipe_servings=st.session_state.get("selected_recipe_servings"),
                    )
                    refresh_daily_logs(log_date)

                    # Dopo il salvataggio: pulizia completa del form e ritorno
                    # automatico alla prima sorgente di inserimento.
                    clear_meal_entry_after_save()

                    queue_ui_sound("food_saved")
                    st.success(f"{t['inserted']}: {meal_display_name} ({cals_in} kcal)")
                    st.rerun()
                except Exception as e:
                    st.error(t["generic_error"].format(error=e))

# ==============================================================================
# 10. PAGE 2: DAILY OVERVIEW
# ==============================================================================
elif selected_page == t["t2"]:
    render_page_title_card(t["daily_summary"])

    if "last_nav_page" not in st.session_state or st.session_state.last_nav_page != selected_page:
        st.session_state.overview_date = date.today()
        st.session_state.last_nav_page = selected_page

    def update_overview_date():
        st.session_state.overview_date = st.session_state.get("widget_overview_date", date.today())

    summary_date = st.date_input(
        t["summary_date"],
        value=st.session_state.overview_date,
        key="widget_overview_date",
        on_change=update_overview_date,
    )

    daily_log_res = []
    meals_data = []
    raw_activities = []
    all_weight_logs = []

    try:
        daily_log_res = load_daily_log_cached(
            user_id,
            str(summary_date),
            st.session_state.get("auth_access_token"),
        )
    except Exception as e:
        st.error(t["load_data_error"].format(error=e))

    try:
        meals_data = load_daily_meals_cached(
            user_id,
            str(summary_date),
            st.session_state.get("auth_access_token"),
        )
    except Exception as e:
        st.error(t["load_data_error"].format(error=e))

    try:
        raw_activities = load_daily_activities_cached(
            user_id,
            str(summary_date),
            st.session_state.get("auth_access_token"),
        )
    except Exception as e:
        st.error(t["load_data_error"].format(error=e))

    try:
        all_weight_logs = load_weight_history_cached(
            user_id,
            st.session_state.get("auth_access_token"),
        )
    except Exception as e:
        st.error(t["load_data_error"].format(error=e))

    activities_data = [a for a in raw_activities if a.get("activity_name")] if raw_activities else []
    total_cals_in = sum(_safe_float(m.get("calories")) for m in meals_data)

    current_weight = (
        daily_log_res[0].get("weight")
        if daily_log_res and daily_log_res[0].get("weight") is not None
        else (
            float(user_current_weight)
            if user_current_weight is not None
            else None
        )
    )
    initial_weight = all_weight_logs[0]["weight"] if all_weight_logs else 89.0
    target_weight = float(user_target_weight) if user_target_weight else 78.0

    now = datetime.now()
    if summary_date == date.today():
        minutes_passed = max(60, now.hour * 60 + now.minute)
        bmr_so_far = int((float(user_bmr) / (24 * 60)) * minutes_passed)
    else:
        bmr_so_far = int(float(user_bmr))
        minutes_passed = 1440

    extra_burned = sum(_safe_float(a.get("burned_calories")) for a in activities_data)
    total_burned_finora = bmr_so_far + extra_burned
    deficit = total_cals_in - total_burned_finora

    total_estimated_burned = float(user_bmr) + extra_burned
    target_deficit_kcal = int(round(float(user_deficit_target_kcal)))
    ideal_target_cals = max(0, total_estimated_burned - target_deficit_kcal)
    diff_from_ideal = ideal_target_cals - total_cals_in

    coral_light_bg, coral_border = "#FFF5F5", "#FF8B8B"

    # Messaggi cards più immediati.
    if diff_from_ideal > 0:
        in_msg = ux["can_eat_more"].format(
            kcal=f"<b>{int(round(diff_from_ideal))}</b>",
            target=target_deficit_kcal,
        )
    elif diff_from_ideal < 0:
        in_msg = ux["over_target"].format(
            kcal=f"<b>{abs(int(round(diff_from_ideal)))}</b>"
        )
    else:
        in_msg = ux["exact_target"].format(
            target=target_deficit_kcal
        )

    # Proiezione semplice e conservativa:
    # BMR completo della giornata + attività già registrate.
    # Non inventiamo attività future.
    projected_burn_end_day = int(round(float(user_bmr) + extra_burned))

    if summary_date == date.today():
        burn_msg = ux["end_day"].format(
            kcal=f"<b>~{projected_burn_end_day}</b>"
        )
    else:
        burn_msg = ux["day_total"].format(
            kcal=f"<b>{int(round(total_burned_finora))}</b>"
        )

    weight_to_lose = (float(current_weight) if current_weight else float(initial_weight)) - target_weight
    if deficit < 0 and weight_to_lose > 0:
        daily_deficit_abs = abs(deficit)
        total_kcal_needed = weight_to_lose * 7700
        estimated_days = int(total_kcal_needed / daily_deficit_abs) if daily_deficit_abs > 0 else 0
        bilancio_msg = t["balance_days"](estimated_days)
    elif weight_to_lose <= 0:
        bilancio_msg = "🎯 Target di peso raggiunto o superato!"
    else:
        bilancio_msg = t["balance_surplus"]

    weight_msg = t["weight_msg_default"]
    if current_weight:
        diff_ini = float(current_weight) - float(initial_weight)
        diff_tgt = float(current_weight) - target_weight
        weight_msg = t["weight_msg_val"](initial_weight, diff_ini, target_weight, diff_tgt)

    if is_zero_mode():
        st.markdown("""
            <style>
                .custom-card {
                    background:
                        radial-gradient(circle at 96% 4%, rgba(225,6,0,.18), transparent 36%),
                        linear-gradient(145deg,#151515,#090909) !important;
                    border:1.5px solid #C91A16 !important;
                    border-radius:18px;
                    padding:17px;
                    height:100%;
                    box-shadow:0 9px 24px rgba(0,0,0,.30);
                }
                .custom-card-title {font-size:.95rem;font-weight:700;color:#D9D9D9 !important;margin-bottom:5px;}
                .custom-card-value {font-size:1.8rem;font-weight:800;color:#FFFFFF !important;margin-bottom:8px;}
                .custom-card-caption {font-size:.86rem;color:#BDBDBD !important;line-height:1.42;}
                .custom-card * {-webkit-text-fill-color:currentColor !important;}
            </style>
        """, unsafe_allow_html=True)
    else:
        st.markdown(f"""
            <style>
                .custom-card {{
                    background-color:{coral_light_bg};
                    border:1.5px solid {coral_border};
                    border-radius:16px;
                    padding:16px;
                    height:100%;
                    box-shadow:0 2px 6px rgba(255,139,139,.08);
                }}
                .custom-card-title {{font-size:.95rem;font-weight:600;color:#1A2942;margin-bottom:4px;}}
                .custom-card-value {{font-size:1.8rem;font-weight:700;color:#1A2942;margin-bottom:8px;}}
                .custom-card-caption {{font-size:.86rem;color:#4A4A4A;line-height:1.42;}}
            </style>
        """, unsafe_allow_html=True)

    col_c1, col_c2, col_c3, col_c4 = st.columns(4)
    with col_c1:
        st.markdown(f'<div class="custom-card"><div class="custom-card-title">🍽️ {t["card_kcal_in"]}</div><div class="custom-card-value">{int(total_cals_in)} kcal</div><div class="custom-card-caption">{in_msg}</div></div>', unsafe_allow_html=True)
    with col_c2:
        st.markdown(f'<div class="custom-card"><div class="custom-card-title">🔥 {t["card_kcal_burn"]}</div><div class="custom-card-value">{int(total_burned_finora)} kcal</div><div class="custom-card-caption">{burn_msg}</div></div>', unsafe_allow_html=True)
    with col_c3:
        st.markdown(f'<div class="custom-card"><div class="custom-card-title">⚖️ {t["card_balance"]}</div><div class="custom-card-value">{int(deficit):+d} kcal</div><div class="custom-card-caption">{bilancio_msg}</div></div>', unsafe_allow_html=True)
    with col_c4:
        weight_str = f"{float(current_weight):.1f} kg" if current_weight else "N/D"
        st.markdown(f'<div class="custom-card"><div class="custom-card-title">📉 {t["card_weight"]}</div><div class="custom-card-value">{weight_str}</div><div class="custom-card-caption">{weight_msg}</div></div>', unsafe_allow_html=True)

    # ------------------------------------------------------------------
    # PIANIFICAZIONE DELLA GIORNATA E SUGGERIMENTI PASTI
    # ------------------------------------------------------------------
    if summary_date == date.today():
        with st.container(border=True):
            st.markdown(t["day_plan_title"])

            plan_day_label = st.selectbox(t["plan_day"], [t["today"], t["tomorrow"]], index=0, key="overview_plan_day")
            # Non confrontare mai l'etichetta localizzata con "Oggi":
            # in NL/EN/FR il testo cambia. Usiamo la chiave tradotta.
            # Inoltre date + Timedelta restituisce già una data compatibile:
            # chiamare .date() qui può generare AttributeError.
            plan_date = (
                date.today()
                if plan_day_label == t["today"]
                else date.today() + pd.Timedelta(days=1)
            )
            if now.hour < 12:
                st.info(t["morning_plan"])
            else:
                st.caption(t["plan_update_later"])

            saved_day_type = None
            saved_activity = None
            try:
                _plan_row = fetch_daily_log_from_api(
                    user_id,
                    plan_date,
                    st.session_state.get("auth_access_token"),
                )
                plan_log = [_plan_row] if _plan_row else []
                if plan_log:
                    saved_day_type = plan_log[0].get("day_type")
                    saved_activity = plan_log[0].get("activity_plan")
            except Exception:
                plan_log = []

            day_types = (
                ["Lavoro da casa", "Ufficio", "Giornata libera"]
                if user_office_lunch_enabled
                else ["Lavoro da casa", "Giornata libera"]
            )
            activity_types = ["Riposo", "Moderatamente attiva", "Attiva"]

            default_day = saved_day_type or st.session_state.get("day_plan_type", "Lavoro da casa")
            default_activity = saved_activity or st.session_state.get("day_plan_activity", "Riposo")
            if default_day not in day_types: default_day = day_types[0]
            if default_activity not in activity_types: default_activity = activity_types[0]

            pc1, pc2 = st.columns(2)
            with pc1:
                day_type = st.selectbox(t["day_type"], day_types, index=day_types.index(default_day), key=f"overview_day_type_{plan_date}", format_func=tr_day_type)
            with pc2:
                activity_plan = st.selectbox(t["activity_expected"], activity_types, index=activity_types.index(default_activity), key=f"overview_activity_plan_{plan_date}", format_func=tr_activity_plan)

            st.session_state["day_plan_type"] = day_type
            st.session_state["day_plan_activity"] = activity_plan

            if st.button(t["save_day_plan"], key="save_day_plan", use_container_width=True):
                try:
                    payload_plan = {
                        "day_type": day_type,
                        "activity_plan": activity_plan,
                    }
                    update_daily_log_via_api(
                        plan_date,
                        payload_plan,
                        st.session_state.get("auth_access_token"),
                    )
                    refresh_daily_logs(plan_date)
                    play_hidden_local_audio(resolve_ui_sound("day_plan_saved"))
                    st.success(t["plan_saved"].format(date=plan_date.strftime("%d/%m/%Y")))
                except Exception:
                    st.info(t["plan_persistence_note"])

            # Valori rappresentativi per la pianificazione:
            # Riposo 0 kcal extra, Moderatamente attiva 500, Attiva 1000.
            activity_bonus = {"Riposo": 0, "Moderatamente attiva": 500, "Attiva": 1000}[activity_plan]
            daily_budget = float(user_bmr) + activity_bonus

            try:
                plan_meals = load_daily_meals_cached(
                    user_id,
                    str(plan_date),
                    st.session_state.get("auth_access_token"),
                )
            except Exception:
                plan_meals = []

            is_today_plan = plan_date == date.today()
            lunch_logged = any(
                str(m.get("meal_type", "")).casefold() == "pranzo"
                for m in plan_meals
            )
            dinner_logged = any(
                str(m.get("meal_type", "")).casefold() == "cena"
                for m in plan_meals
            )
            calories_already_logged = sum(_safe_float(m.get("calories")) for m in plan_meals)

            # Se oggi la cena è già stata registrata, non suggeriamo un'altra cena.
            if is_today_plan and dinner_logged:
                remaining_budget = max(0.0, daily_budget - calories_already_logged)
                st.markdown(
                    f"**{t['budget_estimated']}:** {daily_budget:.0f} kcal · "
                    f"**{t['already_logged']}:** {calories_already_logged:.0f} kcal · "
                    f"**{t['dinner_available']}:** {remaining_budget:.0f} kcal"
                )
                st.success(t["dinner_already_logged"])

            # Se oggi il pranzo è già loggato, suggeriamo esclusivamente la cena.
            elif is_today_plan and lunch_logged:
                dinner_target = max(0.0, daily_budget - calories_already_logged)
                st.markdown(
                    f"**{t['budget_estimated']}:** {daily_budget:.0f} kcal · "
                    f"**Già registrato oggi:** {calories_already_logged:.0f} kcal · "
                    f"**Cena disponibile:** circa {dinner_target:.0f} kcal"
                )
                dinner = closest_logged_meal(
                    "Cena",
                    dinner_target,
                    allowed_categories={"Casa", "Ristorante"},
                )
                if dinner:
                    st.markdown(
                        f"🍽️ **{t['suggested_dinner']}:** {html.escape(dinner['name'])} — "
                        f"**{dinner['calories']:.0f} kcal** · {dinner['category']} "
                        f"{info_badge(dinner.get('notes'), 'Note cena')}",
                        unsafe_allow_html=True,
                    )
                else:
                    st.caption(t["no_dinner_near"])

            elif user_office_lunch_enabled and day_type == "Ufficio":
                fixed_kcal = 1260.0
                dinner_target = max(0.0, daily_budget - fixed_kcal)
                st.markdown(
                    f"**{t['budget_estimated']}:** {daily_budget:.0f} kcal · "
                    f"**Ufficio già allocato:** 1260 kcal · "
                    f"**Cena:** circa {dinner_target:.0f} kcal"
                )

                # Se serve consultare un pranzo da ufficio, l'unica categoria ammessa è Lavoro.
                office_lunch = closest_logged_meal(
                    "Pranzo",
                    1260.0,
                    allowed_categories={"Lavoro"},
                )
                if office_lunch:
                    st.caption(
                        f"{t['office_lunch_history']}: {office_lunch['name']} "
                        f"({office_lunch['calories']:.0f} kcal)."
                    )

                dinner = closest_logged_meal(
                    "Cena",
                    dinner_target,
                    allowed_categories={"Casa", "Ristorante"},
                )
                if dinner:
                    st.markdown(
                        f"🍽️ **{t['suggested_dinner']}:** {html.escape(dinner['name'])} — "
                        f"circa **{dinner['calories']:.0f} kcal** · {dinner['category']} "
                        f"{info_badge(dinner.get('notes'), 'Note cena')}",
                        unsafe_allow_html=True,
                    )
                else:
                    st.caption(t["no_dinner_history"])

            else:
                if day_type == "Lavoro da casa":
                    already_allocated = 185.0
                    allocated_label = "colazione da casa"
                else:
                    breakfast_logged = sum(
                        _safe_float(m.get("calories"))
                        for m in plan_meals
                        if str(m.get("meal_type", "")).casefold() == "colazione"
                    )
                    already_allocated = breakfast_logged
                    allocated_label = (
                        "colazione già registrata"
                        if breakfast_logged
                        else "nessuna quota fissa"
                    )

                remaining = max(0.0, daily_budget - already_allocated)
                per_meal = remaining / 2.0
                st.markdown(
                    f"**{t['budget_estimated']}:** {daily_budget:.0f} kcal · "
                    f"**{allocated_label}:** {already_allocated:.0f} kcal · "
                    f"**Pranzo:** ~{per_meal:.0f} kcal · **Cena:** ~{per_meal:.0f} kcal"
                )

                # A casa/libero: pranzo solo Casa. Ristorante mai a pranzo.
                lunch = closest_logged_meal(
                    "Pranzo",
                    per_meal,
                    allowed_categories={"Casa"},
                )
                # Cena replicabile: Casa o Ristorante.
                dinner = closest_logged_meal(
                    "Cena",
                    per_meal,
                    allowed_categories={"Casa", "Ristorante"},
                )

                sc1, sc2 = st.columns(2)
                with sc1:
                    if lunch:
                        st.markdown(
                            f"🥗 **{t['suggested_lunch']}**<br>{html.escape(lunch['name'])} · "
                            f"**{lunch['calories']:.0f} kcal** · {lunch['category']} "
                            f"{info_badge(lunch.get('notes'), 'Note pranzo')}",
                            unsafe_allow_html=True,
                        )
                    else:
                        st.caption(t["no_home_lunch"])
                with sc2:
                    if dinner:
                        st.markdown(
                            f"🍽️ **{t['suggested_dinner']}**<br>{html.escape(dinner['name'])} · "
                            f"**{dinner['calories']:.0f} kcal** · {dinner['category']} "
                            f"{info_badge(dinner.get('notes'), 'Note cena')}",
                            unsafe_allow_html=True,
                        )
                    else:
                        st.caption(t["no_dinner"])

            st.caption(t["planning_formula"])

    st.markdown("<br>", unsafe_allow_html=True)

    with st.container(border=True):
        st.markdown(f"### {t['logged_foods']}")
        if meals_data:
            meals_with_id = meals_data
            _meal_rows = []
            for _meal_row in meals_with_id:
                _meal_rows.append({
                    "meal": tr_meal_type(
                        _meal_row.get("meal_type", "")
                    ),
                    "category": tr_category(
                        infer_meal_category(_meal_row)
                    ),
                    "name": _meal_row.get("name", ""),
                    "kcal": int(round(
                        _safe_float(_meal_row.get("calories"))
                    )),
                    "protein": round(
                        _safe_float(_meal_row.get("protein")),
                        1,
                    ),
                    "carbs": round(
                        _safe_float(_meal_row.get("carbs")),
                        1,
                    ),
                    "fat": round(
                        _safe_float(_meal_row.get("fat")),
                        1,
                    ),
                })

            # --------------------------------------------------------------
            # Responsive logged foods
            # Desktop/tablet: keep the compact grid.
            # Mobile: switch to one card per meal so headers and values do not
            # collapse into two unrelated vertical stacks.
            # --------------------------------------------------------------
            st.markdown(
                """
                <style>
                /* Desktop is the default. */
                .st-key-logged_meals_desktop {
                    display:block;
                }
                .st-key-logged_meals_mobile {
                    display:none;
                }

                @media (max-width: 768px) {
                    .st-key-logged_meals_desktop {
                        display:none !important;
                    }
                    .st-key-logged_meals_mobile {
                        display:block !important;
                    }

                    .st-key-logged_meals_mobile
                    [data-testid="stVerticalBlockBorderWrapper"] {
                        border-radius:16px !important;
                    }

                    .st-key-logged_meals_mobile
                    div[data-testid="stButton"] > button {
                        min-height:2.45rem !important;
                    }
                }
                </style>
                """,
                unsafe_allow_html=True,
            )

            # DESKTOP -------------------------------------------------------
            with st.container(key="logged_meals_desktop"):
                _logged_header = st.columns(
                    [0.50, 1.05, 1.05, 2.35, 0.82, 0.90, 1.0, 0.82],
                    gap="small",
                    vertical_alignment="center",
                )
                _logged_labels = [
                    "",
                    t["col_meal"],
                    t["col_category"],
                    t["col_name"],
                    "Kcal",
                    "Pro (g)",
                    "Carbs (g)",
                    "Fat (g)",
                ]
                for _col, _label in zip(
                    _logged_header,
                    _logged_labels,
                ):
                    _col.markdown(
                        "<div style='font-weight:700;color:#7b7e89;"
                        "padding:0.1rem 0 0.45rem 0'>"
                        f"{html.escape(str(_label))}</div>",
                        unsafe_allow_html=True,
                    )

                for _meal_raw, _meal_display in zip(
                    meals_with_id,
                    _meal_rows,
                ):
                    _cols = st.columns(
                        [0.50, 1.05, 1.05, 2.35, 0.82, 0.90, 1.0, 0.82],
                        gap="small",
                        vertical_alignment="center",
                    )

                    if _cols[0].button(
                        "🗑️",
                        key=(
                            "delete_logged_meal_"
                            f"{_meal_raw.get('id')}_{summary_date}"
                        ),
                        help=t["del_meal_btn"],
                        use_container_width=True,
                    ):
                        try:
                            delete_meal_via_api(
                                _meal_raw.get("id"),
                                st.session_state.get("auth_access_token"),
                            )
                            refresh_daily_logs(summary_date)
                            queue_ui_sound("food_deleted")
                            st.rerun()
                        except Exception as exc:
                            st.error(
                                t["delete_meal_error"].format(
                                    error=exc
                                )
                            )

                    _cols[1].write(_meal_display["meal"])
                    _cols[2].write(_meal_display["category"])
                    _cols[3].write(_meal_display["name"])
                    _cols[4].write(_meal_display["kcal"])
                    _cols[5].write(_meal_display["protein"])
                    _cols[6].write(_meal_display["carbs"])
                    _cols[7].write(_meal_display["fat"])

            # MOBILE --------------------------------------------------------
            _mobile_meal_labels = {
                "Italiano": {
                    "protein": "Proteine",
                    "carbs": "Carboidrati",
                    "fat": "Grassi",
                    "delete": "Elimina",
                },
                "English": {
                    "protein": "Protein",
                    "carbs": "Carbs",
                    "fat": "Fat",
                    "delete": "Delete",
                },
                "Nederlands": {
                    "protein": "Eiwit",
                    "carbs": "Koolh.",
                    "fat": "Vet",
                    "delete": "Verwijderen",
                },
                "Français": {
                    "protein": "Protéines",
                    "carbs": "Glucides",
                    "fat": "Lipides",
                    "delete": "Supprimer",
                },
            }.get(
                current_lang,
                {
                    "protein": "Protein",
                    "carbs": "Carbs",
                    "fat": "Fat",
                    "delete": "Delete",
                },
            )

            with st.container(key="logged_meals_mobile"):
                for _mobile_idx, (
                    _meal_raw,
                    _meal_display,
                ) in enumerate(
                    zip(meals_with_id, _meal_rows)
                ):
                    with st.container(border=True):
                        _mobile_name = html.escape(
                            str(_meal_display["name"] or "-")
                        )
                        _mobile_meal = html.escape(
                            str(_meal_display["meal"] or "-")
                        )
                        _mobile_category = html.escape(
                            str(_meal_display["category"] or "-")
                        )

                        st.markdown(
                            f"""
                            <div style="
                                font-size:1.08rem;
                                font-weight:800;
                                line-height:1.22;
                                margin-bottom:0.18rem;
                            ">
                                {_mobile_name}
                            </div>
                            <div style="
                                opacity:.68;
                                font-size:.86rem;
                                margin-bottom:.7rem;
                            ">
                                {_mobile_meal} · {_mobile_category}
                            </div>
                            <div style="
                                font-size:1.38rem;
                                font-weight:850;
                                line-height:1;
                                margin-bottom:.8rem;
                            ">
                                {_meal_display["kcal"]} kcal
                            </div>
                            """,
                            unsafe_allow_html=True,
                        )

                        _m_pro, _m_carbs, _m_fat = st.columns(
                            3,
                            gap="small",
                        )

                        with _m_pro:
                            st.markdown(
                                f"""
                                <div style="
                                    text-align:center;
                                    border:1px solid rgba(127,127,127,.18);
                                    border-radius:10px;
                                    padding:.45rem .2rem;
                                ">
                                    <div style="
                                        font-size:.72rem;
                                        opacity:.68;
                                    ">
                                        {html.escape(_mobile_meal_labels["protein"])}
                                    </div>
                                    <div style="
                                        font-weight:800;
                                        font-size:.95rem;
                                    ">
                                        {_meal_display["protein"]} g
                                    </div>
                                </div>
                                """,
                                unsafe_allow_html=True,
                            )

                        with _m_carbs:
                            st.markdown(
                                f"""
                                <div style="
                                    text-align:center;
                                    border:1px solid rgba(127,127,127,.18);
                                    border-radius:10px;
                                    padding:.45rem .2rem;
                                ">
                                    <div style="
                                        font-size:.72rem;
                                        opacity:.68;
                                    ">
                                        {html.escape(_mobile_meal_labels["carbs"])}
                                    </div>
                                    <div style="
                                        font-weight:800;
                                        font-size:.95rem;
                                    ">
                                        {_meal_display["carbs"]} g
                                    </div>
                                </div>
                                """,
                                unsafe_allow_html=True,
                            )

                        with _m_fat:
                            st.markdown(
                                f"""
                                <div style="
                                    text-align:center;
                                    border:1px solid rgba(127,127,127,.18);
                                    border-radius:10px;
                                    padding:.45rem .2rem;
                                ">
                                    <div style="
                                        font-size:.72rem;
                                        opacity:.68;
                                    ">
                                        {html.escape(_mobile_meal_labels["fat"])}
                                    </div>
                                    <div style="
                                        font-weight:800;
                                        font-size:.95rem;
                                    ">
                                        {_meal_display["fat"]} g
                                    </div>
                                </div>
                                """,
                                unsafe_allow_html=True,
                            )

                        if st.button(
                            "🗑️ " + _mobile_meal_labels["delete"],
                            key=(
                                "mobile_delete_logged_meal_"
                                f"{_meal_raw.get('id')}_"
                                f"{summary_date}_{_mobile_idx}"
                            ),
                            help=t["del_meal_btn"],
                            use_container_width=True,
                        ):
                            try:
                                delete_meal_via_api(
                                    _meal_raw.get("id"),
                                    st.session_state.get("auth_access_token"),
                                )
                                refresh_daily_logs(summary_date)
                                queue_ui_sound("food_deleted")
                                st.rerun()
                            except Exception as exc:
                                st.error(
                                    t["delete_meal_error"].format(
                                        error=exc
                                    )
                                )

            meal_by_id = {m["id"]: m for m in meals_with_id}
            meal_options = {
                m["id"]: f"{tr_meal_type(m.get('meal_type', ''))} - {m.get('name', '')} ({m.get('calories', 0)} kcal)"
                for m in meals_with_id
            }
            selected_meal_id = st.selectbox(
                t["select_meal_edit"],
                options=[""] + list(meal_options),
                format_func=lambda meal_id: t["select_meal_placeholder"] if meal_id == "" else meal_options[meal_id],
                key=f"edit_meal_select_{summary_date}",
            )

            if selected_meal_id:
                selected_meal = meal_by_id[selected_meal_id]
                meal_types = ["Colazione", "Pranzo", "Cena", "Snack"]
                current_type = selected_meal.get("meal_type")
                current_index = meal_types.index(current_type) if current_type in meal_types else 0

                if selected_meal.get("notes"):
                    st.markdown(f"Note {info_badge(selected_meal.get('notes'), 'Note pasto')}", unsafe_allow_html=True)

                current_category = infer_meal_category(selected_meal)

                # Quantità corrente. Le righe nuove hanno quantity/is_per_100g;
                # quelle legacy vengono trattate come una porzione singola.
                current_quantity = _safe_float(selected_meal.get("quantity"))
                if current_quantity <= 0:
                    current_quantity = 1.0

                is_per_100g = bool(selected_meal.get("is_per_100g"))

                # Se il meal è per 100 g, la quantità è espressa in grammi.
                # Se è per porzione, la quantità rappresenta il numero di porzioni.
                if is_per_100g:
                    quantity_label = t["quantity_g"]
                    quantity_step = 1.0
                    quantity_unit = "g"
                else:
                    quantity_label = t["portions"]
                    quantity_step = 0.1
                    quantity_unit = "porz."

                edit_col1, edit_col2, edit_col3 = st.columns([2, 2, 2])
                with edit_col1:
                    new_meal_type = st.selectbox(
                        t["meal_type_label"],
                        meal_types,
                        index=current_index,
                        key=f"edit_meal_type_{selected_meal_id}_{summary_date}",
                        format_func=tr_meal_type,
                    )
                with edit_col2:
                    _edit_categories_available = MEAL_CATEGORIES if user_office_lunch_enabled else [c for c in MEAL_CATEGORIES if c != "Lavoro"]
                    if current_category not in _edit_categories_available:
                        current_category = "Casa"
                    new_meal_category = st.selectbox(
                        t["category_label"],
                        _edit_categories_available,
                        index=_edit_categories_available.index(current_category),
                        key=f"edit_meal_category_{selected_meal_id}_{summary_date}",
                        format_func=tr_category,
                    )
                with edit_col3:
                    new_quantity = st.number_input(
                        quantity_label,
                        min_value=0.1,
                        value=float(current_quantity),
                        step=quantity_step,
                        key=f"edit_meal_quantity_{selected_meal_id}_{summary_date}",
                    )

                st.caption(t["edit_meal_help"])

                if st.button(
                    t["save_changes"],
                    use_container_width=True,
                    key=f"save_meal_edit_{selected_meal_id}_{summary_date}",
                ):
                    try:
                        old_quantity = float(current_quantity)
                        new_quantity = float(new_quantity)

                        base_calories = selected_meal.get("base_calories")
                        base_protein = selected_meal.get("base_protein")
                        base_carbs = selected_meal.get("base_carbs")
                        base_fat = selected_meal.get("base_fat")

                        has_base_values = base_calories is not None

                        if has_base_values:
                            factor = (
                                new_quantity / 100.0
                                if is_per_100g
                                else new_quantity
                            )
                            new_calories = _safe_float(base_calories) * factor
                            new_protein = _safe_float(base_protein) * factor
                            new_carbs = _safe_float(base_carbs) * factor
                            new_fat = _safe_float(base_fat) * factor
                        else:
                            # Legacy: mantiene le proporzioni del record attuale.
                            scale = (
                                new_quantity / old_quantity
                                if old_quantity > 0
                                else 1.0
                            )
                            new_calories = _safe_float(selected_meal.get("calories")) * scale
                            new_protein = _safe_float(selected_meal.get("protein")) * scale
                            new_carbs = _safe_float(selected_meal.get("carbs")) * scale
                            new_fat = _safe_float(selected_meal.get("fat")) * scale

                        base_name = (
                            selected_meal.get("base_name")
                            or _clean_meal_name(selected_meal.get("name"))
                            or "Pasto"
                        )

                        if is_per_100g:
                            new_display_name = f"{base_name} ({new_quantity:g}g)"
                        else:
                            new_display_name = f"{base_name} ({new_quantity:g} porz.)"

                        update_payload = {
                            "meal_type": new_meal_type,
                            "category": new_meal_category,
                            "name": new_display_name,
                            "calories": int(round(new_calories)),
                            "protein": int(round(new_protein)),
                            "carbs": int(round(new_carbs)),
                            "fat": int(round(new_fat)),
                        }

                        # Solo schema esteso.
                        if selected_meal.get("quantity") is not None:
                            update_payload["quantity"] = new_quantity

                        update_meal_via_api(
                            selected_meal_id,
                            update_payload,
                            st.session_state.get("auth_access_token"),
                        )

                        refresh_daily_logs(summary_date)

                        queue_ui_sound("food_updated")
                        st.success(t["meal_updated"].format(meal=tr_meal_type(new_meal_type), category=tr_category(new_meal_category), qty=f"{new_quantity:g}", unit=quantity_unit))
                        st.rerun()

                    except Exception as e:
                        st.error(t["edit_meal_error"].format(error=e))

                st.markdown("---")
                delete_col1, delete_col2 = st.columns([3, 1])
                with delete_col1:
                    st.caption(t["delete_this_meal"].format(name=selected_meal.get("name", t["col_meal"])))
                with delete_col2:
                    if st.button(t["del_meal_btn"], key=f"delete_meal_{selected_meal_id}_{summary_date}", use_container_width=True):
                        try:
                            delete_meal_via_api(
                                selected_meal_id,
                                st.session_state.get("auth_access_token"),
                            )
                            queue_ui_sound("food_deleted")
                            st.success(t["meal_del_success"])
                            st.rerun()
                        except Exception as e:
                            st.error(t["delete_meal_error"].format(error=e))
        else:
            st.info(t["no_meals"])

    # ------------------------------------------------------------------
    # ATTIVITÀ + DISTRIBUZIONE NUTRIZIONALE / KCAL
    # ------------------------------------------------------------------
    _overview_chart_i18n = {
        "Italiano": {
            "title": "🍩 Distribuzione giornaliera",
            "selector": "Visualizza",
            "macros": "Macronutrienti",
            "meals": "Kcal per pasto",
            "protein": "Proteine",
            "carbs": "Carboidrati",
            "fat": "Grassi",
            "no_data": "Nessun dato disponibile per questa data.",
            "macro_unit": "g",
            "kcal_unit": "kcal",
        },
        "English": {
            "title": "🍩 Daily distribution",
            "selector": "View",
            "macros": "Macronutrients",
            "meals": "Kcal by meal",
            "protein": "Protein",
            "carbs": "Carbs",
            "fat": "Fat",
            "no_data": "No data available for this date.",
            "macro_unit": "g",
            "kcal_unit": "kcal",
        },
        "Nederlands": {
            "title": "🍩 Dagelijkse verdeling",
            "selector": "Weergave",
            "macros": "Macronutriënten",
            "meals": "Kcal per maaltijd",
            "protein": "Eiwitten",
            "carbs": "Koolhydraten",
            "fat": "Vetten",
            "no_data": "Geen gegevens beschikbaar voor deze datum.",
            "macro_unit": "g",
            "kcal_unit": "kcal",
        },
        "Français": {
            "title": "🍩 Répartition journalière",
            "selector": "Afficher",
            "macros": "Macronutriments",
            "meals": "Kcal par repas",
            "protein": "Protéines",
            "carbs": "Glucides",
            "fat": "Lipides",
            "no_data": "Aucune donnée disponible pour cette date.",
            "macro_unit": "g",
            "kcal_unit": "kcal",
        },
    }
    _och = _overview_chart_i18n.get(
        current_lang,
        _overview_chart_i18n["Italiano"],
    )

    _activity_col, _chart_col = st.columns(
        2,
        gap="large",
        vertical_alignment="top",
    )

    with _activity_col:
        with st.container(border=True):
            st.markdown(t["burned_acts"])

            rows_acts = [{
                "activity": ux["bmr_base"],
                "burned": int(round(_safe_float(bmr_so_far))),
            }]
            for act in activities_data:
                rows_acts.append({
                    "activity": translate_activity_display(
                        act.get("activity_name"),
                        current_lang,
                    ),
                    "burned": int(round(
                        _safe_float(act.get("burned_calories"))
                    )),
                })

            # ----------------------------------------------------------
            # Responsive activity summary
            # Desktop/tablet keeps the compact grid; mobile uses the same
            # card hierarchy adopted for "Cibi inseriti".
            # ----------------------------------------------------------
            st.markdown(
                """
                <style>
                .st-key-overview_activity_desktop {
                    display:block;
                }
                .st-key-overview_activity_mobile {
                    display:none;
                }

                @media (max-width: 768px) {
                    .st-key-overview_activity_desktop {
                        display:none !important;
                    }
                    .st-key-overview_activity_mobile {
                        display:block !important;
                    }

                    .st-key-overview_activity_mobile
                    [data-testid="stVerticalBlockBorderWrapper"] {
                        border-radius:16px !important;
                    }
                }
                </style>
                """,
                unsafe_allow_html=True,
            )

            # DESKTOP / TABLET --------------------------------------------
            with st.container(key="overview_activity_desktop"):
                render_sanosync_grid_table(
                    rows_acts,
                    [
                        ("activity", t["col_activity"]),
                        ("burned", t["col_burned"]),
                    ],
                    widths=[2.5, 1.0],
                )

            # MOBILE ------------------------------------------------------
            _mobile_activity_i18n = {
                "Italiano": {
                    "kcal": "kcal bruciate",
                    "base": "Metabolismo di base",
                },
                "English": {
                    "kcal": "kcal burned",
                    "base": "Basal metabolism",
                },
                "Nederlands": {
                    "kcal": "kcal verbrand",
                    "base": "Basale stofwisseling",
                },
                "Français": {
                    "kcal": "kcal brûlées",
                    "base": "Métabolisme de base",
                },
            }.get(
                current_lang,
                {
                    "kcal": "kcal burned",
                    "base": "Basal metabolism",
                },
            )

            with st.container(key="overview_activity_mobile"):
                for _act_idx, _act_row in enumerate(rows_acts):
                    _act_name = str(
                        _act_row.get("activity") or "-"
                    )
                    _act_kcal = int(
                        round(
                            _safe_float(
                                _act_row.get("burned")
                            )
                        )
                    )

                    _is_bmr = _act_idx == 0
                    _act_icon = "🔥" if not _is_bmr else "⚙️"
                    _act_meta = (
                        _mobile_activity_i18n["base"]
                        if _is_bmr
                        else _mobile_activity_i18n["kcal"]
                    )

                    with st.container(border=True):
                        # Keep the HTML flush-left. Markdown treats HTML
                        # indented by 4+ spaces as a code block on some mobile
                        # Streamlit/browser combinations.
                        _activity_mobile_html = (
                            '<div style="display:flex;align-items:flex-start;'
                            'justify-content:space-between;gap:.75rem;">'
                            '<div style="min-width:0;">'
                            '<div style="font-size:1.05rem;font-weight:800;'
                            'line-height:1.2;margin-bottom:.22rem;">'
                            f'{_act_icon} {html.escape(_act_name)}'
                            '</div>'
                            '<div style="opacity:.64;font-size:.78rem;">'
                            f'{html.escape(_act_meta)}'
                            '</div>'
                            '</div>'
                            '<div style="flex:0 0 auto;text-align:right;'
                            'font-size:1.25rem;font-weight:850;line-height:1.05;'
                            'white-space:nowrap;">'
                            f'{_act_kcal}'
                            '<span style="display:block;margin-top:.18rem;'
                            'font-size:.68rem;font-weight:600;opacity:.62;">'
                            'kcal'
                            '</span>'
                            '</div>'
                            '</div>'
                        )
                        st.markdown(
                            _activity_mobile_html,
                            unsafe_allow_html=True,
                        )

    with _chart_col:
        with st.container(border=True):
            st.markdown(f"#### {_och['title']}")

            _chart_mode = st.selectbox(
                _och["selector"],
                ["macros", "meals"],
                key=f"overview_distribution_mode_{summary_date}",
                format_func=lambda x: (
                    _och["macros"]
                    if x == "macros"
                    else _och["meals"]
                ),
                label_visibility="collapsed",
            )

            if _chart_mode == "macros":
                _macro_values = {
                    _och["protein"]: sum(
                        _safe_float(m.get("protein"))
                        for m in meals_data
                    ),
                    _och["carbs"]: sum(
                        _safe_float(m.get("carbs"))
                        for m in meals_data
                    ),
                    _och["fat"]: sum(
                        _safe_float(m.get("fat"))
                        for m in meals_data
                    ),
                }
                _macro_values = {
                    k: v
                    for k, v in _macro_values.items()
                    if v > 0
                }

                if _macro_values:
                    _pie = go.Figure(
                        data=[
                            go.Pie(
                                labels=list(_macro_values.keys()),
                                values=list(_macro_values.values()),
                                hole=0.42,
                                marker=dict(colors=(["#E10600","#F2F2F2","#777777"] if is_zero_mode() else None)),
                                textinfo="percent+label",
                                hovertemplate=(
                                    "%{label}: %{value:.1f} "
                                    + _och["macro_unit"]
                                    + "<extra></extra>"
                                ),
                            )
                        ]
                    )
                    _pie.update_layout(
                        height=300,
                        margin=dict(l=8, r=8, t=10, b=8),
                        showlegend=False,
                        paper_bgcolor="rgba(0,0,0,0)",
                        plot_bgcolor="rgba(0,0,0,0)",
                    )
                    st.plotly_chart(
                        _pie,
                        use_container_width=True,
                        config={"displayModeBar": False},
                    )
                else:
                    st.info(_och["no_data"])

            else:
                _meal_kcal = {}
                for _meal in meals_data:
                    _meal_name = tr_meal_type(
                        _meal.get("meal_type", "")
                    )
                    _meal_kcal[_meal_name] = (
                        _meal_kcal.get(_meal_name, 0.0)
                        + _safe_float(_meal.get("calories"))
                    )

                _meal_kcal = {
                    k: v
                    for k, v in _meal_kcal.items()
                    if v > 0
                }

                if _meal_kcal:
                    _pie = go.Figure(
                        data=[
                            go.Pie(
                                labels=list(_meal_kcal.keys()),
                                values=list(_meal_kcal.values()),
                                hole=0.42,
                                marker=dict(colors=(["#E10600","#F2F2F2","#777777","#3A3A3A"] if is_zero_mode() else None)),
                                textinfo="percent+label",
                                hovertemplate=(
                                    "%{label}: %{value:.0f} "
                                    + _och["kcal_unit"]
                                    + "<extra></extra>"
                                ),
                            )
                        ]
                    )
                    _pie.update_layout(
                        height=300,
                        margin=dict(l=8, r=8, t=10, b=8),
                        showlegend=False,
                        paper_bgcolor="rgba(0,0,0,0)",
                        plot_bgcolor="rgba(0,0,0,0)",
                    )
                    st.plotly_chart(
                        _pie,
                        use_container_width=True,
                        config={"displayModeBar": False},
                    )
                else:
                    st.info(_och["no_data"])

# 11. PAGE 3: WEIGHT TRACKING / ANALYTICS
# ==============================================================================
elif selected_page == t["t3"]:
    render_page_title_card(t["weight_tracking"])

    # Se un peso è appena stato salvato, riproduci il relativo feedback sonoro.
    render_pending_weight_sound()

    # ------------------------------------------------------------------
    # GESTIONE PESO — hierarchy:
    # 1. primary action: register today's/new weight
    # 2. secondary action: history/edit/delete, collapsed by default
    # 3. target weight, compact
    # ------------------------------------------------------------------
    logs_all = list(
        reversed(
            fetch_weight_history_from_api(
                user_id,
                st.session_state.get("auth_access_token"),
            )
        )
    )
    edit_options = {
        str(r["id"]): (
            f"{r['date']} · {float(r['weight']):.1f} kg"
        )
        for r in logs_all
    }

    _latest_weight_default = (
        float(logs_all[0]["weight"])
        if logs_all
        and logs_all[0].get("weight") is not None
        else (
            float(user_current_weight)
            if user_current_weight is not None
            else 80.0
        )
    )

    if "new_weight_value" not in st.session_state:
        st.session_state["new_weight_value"] = _latest_weight_default

    _weight_ui = {
        "Italiano": {
            "register_title": "⚖️ Registra peso",
            "register_caption": "Aggiungi una nuova misurazione. Il valore predefinito è l’ultimo peso registrato.",
            "history_title": "🕘 Storico e modifica",
            "history_caption": "Correggi o elimina una misurazione già registrata.",
            "target_title": "🎯 Obiettivo peso",
            "target_caption": "Il target viene usato nelle proiezioni e nel calcolo del mantenimento.",
        },
        "English": {
            "register_title": "⚖️ Log weight",
            "register_caption": "Add a new measurement. The default value is your latest recorded weight.",
            "history_title": "🕘 History & edit",
            "history_caption": "Correct or remove an existing measurement.",
            "target_title": "🎯 Target weight",
            "target_caption": "Your target is used for projections and maintenance calculations.",
        },
        "Nederlands": {
            "register_title": "⚖️ Gewicht registreren",
            "register_caption": "Voeg een nieuwe meting toe. Standaard staat je laatst geregistreerde gewicht ingevuld.",
            "history_title": "🕘 Geschiedenis en bewerken",
            "history_caption": "Corrigeer of verwijder een bestaande meting.",
            "target_title": "🎯 Doelgewicht",
            "target_caption": "Het doel wordt gebruikt voor prognoses en onderhoudsberekeningen.",
        },
        "Français": {
            "register_title": "⚖️ Enregistrer le poids",
            "register_caption": "Ajoutez une nouvelle mesure. La valeur par défaut est votre dernier poids enregistré.",
            "history_title": "🕘 Historique et modification",
            "history_caption": "Corrigez ou supprimez une mesure existante.",
            "target_title": "🎯 Poids cible",
            "target_caption": "La cible est utilisée pour les projections et le calcul du maintien.",
        },
    }.get(current_lang, {})

    # PRIMARY ACTION ---------------------------------------------------------
    with st.container(border=True):
        st.markdown(
            f"### {_weight_ui.get('register_title', '⚖️ Registra peso')}"
        )
        st.caption(
            _weight_ui.get(
                "register_caption",
                "Aggiungi una nuova misurazione.",
            )
        )

        _new_w_col, _new_date_col, _save_col = st.columns(
            [1.0, 1.0, 0.75],
            gap="medium",
            vertical_alignment="bottom",
        )

        with _new_w_col:
            w = st.number_input(
                t["new_weight"],
                min_value=20.0,
                max_value=300.0,
                step=0.1,
                key="new_weight_value",
            )

        with _new_date_col:
            w_date = st.date_input(
                t["weight_date"],
                value=date.today(),
                key="new_weight_date",
            )

        with _save_col:
            if st.button(
                t["save_weight_ui"],
                use_container_width=True,
                type="primary",
                key="save_new_weight_primary",
            ):
                try:
                    previous_rows = []
                    for row in logs_all:
                        try:
                            row_date = pd.to_datetime(
                                row.get("date")
                            ).date()
                            if (
                                row_date < w_date
                                and row.get("weight") is not None
                            ):
                                previous_rows.append(
                                    (
                                        row_date,
                                        float(row["weight"]),
                                    )
                                )
                        except Exception:
                            continue

                    previous_weight = None
                    if previous_rows:
                        previous_rows.sort(
                            key=lambda item: item[0],
                            reverse=True,
                        )
                        previous_weight = previous_rows[0][1]

                    sound_to_play = None
                    if previous_weight is not None:
                        delta_weight = (
                            float(w)
                            - float(previous_weight)
                        )

                        if delta_weight < -0.5:
                            sound_to_play = WEIGHT_SOUND_BIG_LOSS
                        elif delta_weight <= 0:
                            sound_to_play = WEIGHT_SOUND_SMALL_LOSS
                        else:
                            sound_to_play = WEIGHT_SOUND_GAIN

                    create_weight_via_api(
                        w_date,
                        float(w),
                        st.session_state.get("auth_access_token"),
                    )

                    _weight_metadata = dict(
                        getattr(
                            st.session_state.get("user"),
                            "user_metadata",
                            {},
                        )
                        or {}
                    )
                    _weight_metadata[
                        "current_weight"
                    ] = float(w)

                    _target_for_maintenance = _safe_float(
                        _weight_metadata.get(
                            "target_weight"
                        )
                        or user_target_weight
                    )
                    if (
                        _target_for_maintenance > 0
                        and abs(
                            float(w)
                            - _target_for_maintenance
                        )
                        <= 0.05
                    ):
                        _weight_metadata[
                            "deficit_target_kcal"
                        ] = 0
                        _weight_metadata[
                            "deficit_plan"
                        ] = "maintenance"

                    _weight_auth_response = (
                        supabase.auth.update_user(
                            {"data": _weight_metadata}
                        )
                    )
                    if getattr(
                        _weight_auth_response,
                        "user",
                        None,
                    ):
                        st.session_state[
                            "user"
                        ] = _weight_auth_response.user

                    if is_zero_mode():
                        _weight_event = (
                            "weight_big_loss"
                            if (
                                previous_weight is not None
                                and float(w)
                                <= float(previous_weight) - 1.0
                            )
                            else (
                                "weight_small_loss"
                                if (
                                    previous_weight is not None
                                    and float(w)
                                    < float(previous_weight)
                                )
                                else "weight_gain"
                            )
                        )
                        queue_ui_sound(_weight_event)
                    elif sound_to_play is not None:
                        st.session_state[
                            "pending_weight_sound"
                        ] = str(sound_to_play)

                    refresh_daily_logs(w_date)
                    st.success(t["weight_saved"])
                    st.rerun()

                except Exception as e:
                    st.error(
                        f"Errore nel salvataggio del peso: {e}"
                    )

    # SECONDARY ACTION -------------------------------------------------------
    with st.expander(
        _weight_ui.get(
            "history_title",
            "🕘 Storico e modifica",
        ),
        expanded=False,
    ):
        st.caption(
            _weight_ui.get(
                "history_caption",
                "Correggi o elimina una misurazione.",
            )
        )

        if not logs_all:
            st.info(t.get("no_data", "Nessun dato disponibile."))
        else:
            selected_weight_id = st.selectbox(
                t["weight_edit_select"],
                [""] + list(edit_options),
                format_func=lambda x: (
                    t["weight_select_placeholder"]
                    if x == ""
                    else edit_options[x]
                ),
                key="weight_edit_selector",
            )

            if selected_weight_id:
                selected_row = next(
                    r
                    for r in logs_all
                    if str(r["id"]) == selected_weight_id
                )

                _edit_date_col, _edit_weight_col = st.columns(
                    2,
                    gap="medium",
                )
                with _edit_date_col:
                    edited_date = st.date_input(
                        t["date_label"],
                        value=pd.to_datetime(
                            selected_row["date"]
                        ).date(),
                        key=(
                            "edit_weight_date_"
                            f"{selected_weight_id}"
                        ),
                    )
                with _edit_weight_col:
                    edited_weight = st.number_input(
                        t["weight_value"],
                        value=float(
                            selected_row["weight"]
                        ),
                        min_value=20.0,
                        max_value=300.0,
                        step=0.1,
                        key=(
                            "edit_weight_value_"
                            f"{selected_weight_id}"
                        ),
                    )

                _update_col, _delete_col = st.columns(
                    [1, 1],
                    gap="medium",
                )

                with _update_col:
                    if st.button(
                        t["edit_weight"],
                        use_container_width=True,
                        key=(
                            "update_weight_"
                            f"{selected_weight_id}"
                        ),
                    ):
                        try:
                            if (
                                str(edited_date)
                                != str(
                                    selected_row["date"]
                                )
                            ):
                                update_weight_via_api(
                                    selected_row["id"],
                                    log_date=edited_date,
                                    weight=float(edited_weight),
                                    access_token=st.session_state.get("auth_access_token"),
                                )
                            else:
                                update_weight_via_api(
                                    selected_row["id"],
                                    weight=float(edited_weight),
                                    access_token=st.session_state.get("auth_access_token"),
                                )

                            refresh_daily_logs(
                                edited_date
                            )
                            st.success(
                                t["weight_edited"]
                            )
                            st.rerun()
                        except Exception as e:
                            st.error(
                                t[
                                    "weight_edit_error"
                                ].format(error=e)
                            )

                with _delete_col:
                    if st.button(
                        t["delete_weight"],
                        use_container_width=True,
                        key=(
                            "delete_weight_"
                            f"{selected_weight_id}"
                        ),
                    ):
                        try:
                            delete_weight_via_api(
                                selected_row["id"],
                                st.session_state.get("auth_access_token"),
                            )
                            refresh_daily_logs(
                                selected_row["date"]
                            )
                            st.success(
                                t["weight_deleted"]
                            )
                            st.rerun()
                        except Exception as e:
                            st.error(
                                t[
                                    "weight_delete_error"
                                ].format(error=e)
                            )

    # TARGET -----------------------------------------------------------------
    with st.container(border=True):
        _target_title_col, _target_input_col, _target_save_col = st.columns(
            [1.45, 0.9, 0.75],
            gap="medium",
            vertical_alignment="bottom",
        )

        with _target_title_col:
            st.markdown(
                f"### {_weight_ui.get('target_title', '🎯 Obiettivo peso')}"
            )
            st.caption(
                _weight_ui.get(
                    "target_caption",
                    "Target usato per le proiezioni.",
                )
            )

        with _target_input_col:
            new_target = st.number_input(
                t["target_weight_label"],
                value=(
                    float(user_target_weight)
                    if user_target_weight
                    else 75.0
                ),
                min_value=20.0,
                max_value=300.0,
                step=0.5,
                key="weight_target_edit",
            )

        with _target_save_col:
            if st.button(
                t["save_target"],
                use_container_width=True,
                key="save_weight_target_compact",
            ):
                try:
                    res = supabase.auth.update_user(
                        {
                            "data": {
                                "target_weight": float(
                                    new_target
                                )
                            }
                        }
                    )
                    if res.user:
                        st.session_state[
                            "user"
                        ] = res.user

                    st.success(
                        t["target_updated"]
                    )
                    st.rerun()
                except Exception as e:
                    st.error(f"Errore: {e}")

    # ------------------------------------------------------------------
    # KPI ULTIMI 30 GIORNI
    # ------------------------------------------------------------------
    try:
        month_end = pd.Timestamp(date.today())
        month_start = month_end - pd.Timedelta(days=29)

        month_weights_rows = weight_rows_for_range(
            user_id,
            month_start.date(),
            month_end.date(),
            st.session_state.get("auth_access_token"),
        )
        month_meals_rows = fetch_meals_range_from_api(
            month_start.date(),
            month_end.date(),
            st.session_state.get("auth_access_token"),
        )
        month_acts_rows = fetch_activities_range_from_api(
            month_start.date(),
            month_end.date(),
            st.session_state.get("auth_access_token"),
        )

        mw = pd.DataFrame(month_weights_rows)
        mm = pd.DataFrame(month_meals_rows)
        ma = pd.DataFrame(month_acts_rows)

        weight_lost_30 = None
        latest_weight_30 = None
        if not mw.empty and len(mw) >= 2:
            mw["date"] = pd.to_datetime(mw["date"])
            mw["weight"] = pd.to_numeric(mw["weight"], errors="coerce")
            mw = mw.dropna().sort_values("date")
            if len(mw) >= 2:
                first_w = float(mw.iloc[0]["weight"])
                latest_weight_30 = float(mw.iloc[-1]["weight"])
                weight_lost_30 = first_w - latest_weight_30
        elif not mw.empty:
            latest_weight_30 = float(pd.to_numeric(mw.iloc[-1]["weight"], errors="coerce"))

        # Deficit calcolato solo sui giorni in cui esiste almeno un pasto registrato,
        # così un giorno senza logging non viene interpretato come un enorme deficit.
        total_deficit_30 = 0.0
        valid_deficit_days = 0
        avg_daily_deficit_30 = None
        if not mm.empty:
            mm["date"] = pd.to_datetime(mm["date"]).dt.normalize()
            mm["calories"] = pd.to_numeric(mm["calories"], errors="coerce").fillna(0)
            meal_daily = mm.groupby("date")["calories"].sum()

            if not ma.empty:
                ma["date"] = pd.to_datetime(ma["date"]).dt.normalize()
                ma["burned_calories"] = pd.to_numeric(ma["burned_calories"], errors="coerce").fillna(0)
                act_daily = ma.groupby("date")["burned_calories"].sum()
            else:
                act_daily = pd.Series(dtype=float)

            for d, kcal_in in meal_daily.items():
                extra = float(act_daily.get(d, 0.0))
                total_deficit_30 += float(user_bmr) + extra - float(kcal_in)
                valid_deficit_days += 1

            if valid_deficit_days > 0:
                avg_daily_deficit_30 = total_deficit_30 / valid_deficit_days

        ratio_text = "N/D"
        ratio_caption = t["need_two_weights"]
        if weight_lost_30 is not None and weight_lost_30 > 0 and valid_deficit_days > 0:
            kcal_per_kg = total_deficit_30 / weight_lost_30
            ratio_text = f"{kcal_per_kg:,.0f} kcal/kg".replace(",", ".")
            ratio_caption = t["ratio_caption"].format(deficit=f"{total_deficit_30:.0f}", kg=f"{weight_lost_30:.1f}")
        elif weight_lost_30 is not None and weight_lost_30 <= 0:
            ratio_caption = t["no_weight_loss"]

        lost_text = "N/D" if weight_lost_30 is None else f"{-weight_lost_30:+.1f} kg"
        lost_caption = t["first_last_diff"]

        goal_date_text = "N/D"
        goal_caption = t["need_positive_deficit"]
        target_30 = float(user_target_weight) if user_target_weight else None
        current_for_projection = latest_weight_30
        if current_for_projection is None and logs_all:
            try:
                current_for_projection = float(logs_all[0]["weight"])
            except Exception:
                current_for_projection = None

        if target_30 is not None and current_for_projection is not None:
            kg_remaining = current_for_projection - target_30
            if kg_remaining <= 0:
                goal_date_text = t["target_reached"]
                goal_caption = t["target_reached_caption"]
            elif avg_daily_deficit_30 is not None and avg_daily_deficit_30 > 0:
                days_needed = int(__import__("math").ceil((kg_remaining * 7700.0) / avg_daily_deficit_30))
                projected_date = date.today() + pd.Timedelta(days=days_needed)
                goal_date_text = projected_date.strftime("%d/%m/%Y")
                goal_caption = t["estimate_based"].format(deficit=f"{avg_daily_deficit_30:.0f}", days=valid_deficit_days)

        if is_zero_mode():
            st.markdown('''
                <style>
                    .custom-card {
                        background:
                            radial-gradient(circle at 96% 4%, rgba(225,6,0,.18), transparent 36%),
                            linear-gradient(145deg,#151515,#090909);
                        border:1.5px solid #C91A16;
                        border-radius:18px;
                        padding:17px;
                        height:100%;
                        box-shadow:0 9px 24px rgba(0,0,0,.30);
                    }
                    .custom-card-title {font-size:.95rem;font-weight:700;color:#D9D9D9;margin-bottom:5px;}
                    .custom-card-value {font-size:1.8rem;font-weight:800;color:#FFFFFF;margin-bottom:8px;}
                    .custom-card-caption {font-size:.82rem;color:#BDBDBD;line-height:1.38;}
                </style>
            ''', unsafe_allow_html=True)
        else:
            st.markdown('''
                <style>
                    .custom-card {
                        background-color:#FFF5F5;
                        border:1.5px solid #FF8B8B;
                        border-radius:16px;
                        padding:16px;
                        height:100%;
                        box-shadow:0 2px 6px rgba(255,139,139,.08);
                    }
                    .custom-card-title {font-size:.95rem;font-weight:600;color:#1A2942;margin-bottom:4px;}
                    .custom-card-value {font-size:1.8rem;font-weight:700;color:#1A2942;margin-bottom:8px;}
                    .custom-card-caption {font-size:.82rem;color:#555;line-height:1.35;}
                </style>
            ''', unsafe_allow_html=True)

        wk1, wk2, wk3 = st.columns(3)
        with wk1:
            st.markdown(f'<div class="custom-card"><div class="custom-card-title">{t["weight_lost_30"]}</div><div class="custom-card-value">{lost_text}</div><div class="custom-card-caption">{lost_caption}</div></div>', unsafe_allow_html=True)
        with wk2:
            st.markdown(f'<div class="custom-card"><div class="custom-card-title">{t["deficit_per_kg"]}</div><div class="custom-card-value">{ratio_text}</div><div class="custom-card-caption">{ratio_caption}</div></div>', unsafe_allow_html=True)
        with wk3:
            st.markdown(f'<div class="custom-card"><div class="custom-card-title">{t["estimated_target_date"]}</div><div class="custom-card-value">{goal_date_text}</div><div class="custom-card-caption">{goal_caption}</div></div>', unsafe_allow_html=True)
        st.markdown("<br>", unsafe_allow_html=True)
    except Exception as e:
        st.warning(t["monthly_stats_error"].format(error=e))

    with st.container(border=True):
        try:
            ctrl1, ctrl2 = st.columns(2)
            with ctrl1:
                chart_mode = st.selectbox(
                    t["view_label"],
                    ["weight", "kcal", "macros", "meals"],
                    index=0,
                    key="main_analytics_mode",
                    format_func=lambda x: {"weight": t["view_weight"], "kcal": t["view_kcal"], "macros": t["view_macros"], "meals": t["view_meals"]}[x],
                )
            with ctrl2:
                period_options = {f"{d} {t['period_days']}": d for d in (7, 14, 30, 60, 90)}
                selected_period_label = st.selectbox(
                    t["period_label"],
                    list(period_options),
                    index=1,  # default 14 giorni
                    key="weight_chart_period",
                )

            selected_days = period_options[selected_period_label]
            chart_end = pd.Timestamp(date.today())
            chart_start = chart_end - pd.Timedelta(days=selected_days - 1)
            timeline_dates = pd.date_range(chart_start, chart_end, freq="D")

            logs = weight_rows_for_range(
                user_id,
                chart_start.date(),
                chart_end.date(),
                st.session_state.get("auth_access_token"),
            )
            meals_rows = fetch_meals_range_from_api(
                chart_start.date(),
                chart_end.date(),
                st.session_state.get("auth_access_token"),
            )
            acts_rows = fetch_activities_range_from_api(
                chart_start.date(),
                chart_end.date(),
                st.session_state.get("auth_access_token"),
            )

            df_weight = pd.DataFrame(logs)
            meals_df = pd.DataFrame(meals_rows)
            acts_df = pd.DataFrame(acts_rows)

            if not df_weight.empty:
                df_weight["date"] = pd.to_datetime(df_weight["date"]).dt.normalize()
                df_weight["weight"] = pd.to_numeric(df_weight["weight"], errors="coerce")
                df_weight = df_weight.dropna().sort_values("date")
            if not meals_df.empty:
                meals_df["date"] = pd.to_datetime(meals_df["date"]).dt.normalize()
                for col in ["calories", "protein", "carbs", "fat"]:
                    meals_df[col] = pd.to_numeric(meals_df[col], errors="coerce").fillna(0)
            if not acts_df.empty:
                acts_df["date"] = pd.to_datetime(acts_df["date"]).dt.normalize()
                acts_df["burned_calories"] = pd.to_numeric(acts_df["burned_calories"], errors="coerce").fillna(0)

            days_df = pd.DataFrame({"date": timeline_dates})
            if not meals_df.empty:
                meal_totals = meals_df.groupby("date")[["calories", "protein", "carbs", "fat"]].sum().reset_index()
                days_df = days_df.merge(meal_totals, on="date", how="left")
            else:
                for c in ["calories", "protein", "carbs", "fat"]:
                    days_df[c] = 0.0

            for c in ["calories", "protein", "carbs", "fat"]:
                if c not in days_df:
                    days_df[c] = 0.0
            days_df[["calories", "protein", "carbs", "fat"]] = days_df[["calories", "protein", "carbs", "fat"]].fillna(0)

            if not acts_df.empty:
                burn_totals = acts_df.groupby("date")["burned_calories"].sum().reset_index(name="extra")
                days_df = days_df.merge(burn_totals, on="date", how="left")
            else:
                days_df["extra"] = 0.0
            days_df["extra"] = days_df["extra"].fillna(0.0)
            days_df["burned"] = float(user_bmr) + days_df["extra"]

            fig = go.Figure()
            y_title = ""

            if chart_mode == "weight":
                if not df_weight.empty:
                    fig.add_trace(go.Scatter(
                        x=df_weight["date"], y=df_weight["weight"],
                        mode="lines+markers", name=t["view_weight"],
                        line=dict(color="#FF8B8B", width=3),
                        marker=dict(size=8, color="#FF8B8B"),
                        hovertemplate=f"<b>%{{x|%d %b %Y}}</b><br>{t['view_weight']}: <b>%{{y:.1f}} kg</b><extra></extra>",
                    ))

                    target_val = float(user_target_weight) if user_target_weight else 75.0
                    # Trend lineare sui dati disponibili negli ultimi 14 giorni.
                    trend_source = df_weight[df_weight["date"] >= chart_end - pd.Timedelta(days=13)]
                    if len(trend_source) >= 3:
                        x_days = (trend_source["date"] - trend_source["date"].min()).dt.days.astype(float)
                        slope, intercept = pd.Series(trend_source["weight"].values).pipe(
                            lambda y: __import__("numpy").polyfit(x_days, y, 1)
                        )
                        trend_x = pd.date_range(chart_start, chart_end, freq="D")
                        trend_days = (trend_x - trend_source["date"].min()).days.astype(float)
                        trend_y = intercept + slope * trend_days
                        fig.add_trace(go.Scatter(
                            x=trend_x, y=trend_y, mode="lines",
                            name=t["trend"],
                            line=dict(color="#FF8B8B", width=2.5, dash="dash"),
                            hovertemplate=f"<b>{t['trend']}</b><br>%{{x|%d %b}}<br>%{{y:.1f}} kg<extra></extra>",
                        ))

                    fig.add_trace(go.Scatter(
                        x=[chart_start, chart_end], y=[target_val, target_val],
                        mode="lines", name=t["goal"],
                        line=dict(color="#1A2942", width=2.5),
                        hovertemplate=f"{t['goal']}: {target_val:.1f} kg<extra></extra>",
                    ))

                    visible_values = df_weight["weight"].tolist() + [target_val]
                    y_min, y_max = min(visible_values), max(visible_values)
                    spread = max(y_max - y_min, 1.0)
                    pad = max(.5, spread * .18)
                    fig.update_yaxes(range=[y_min - pad, y_max + pad])
                else:
                    st.info(t["no_weight_period"].format(days=selected_days))
                y_title = f"{t['view_weight']} (kg)"

            elif chart_mode == "kcal":
                fig.add_trace(go.Bar(
                    x=days_df["date"], y=days_df["calories"],
                    name=t["ingested_kcal"], marker_color="#FF8B8B",
                    hovertemplate=f"%{{x|%d %b}}<br>{t['ingested_kcal']}: %{{y:.0f}} kcal<extra></extra>",
                ))
                fig.add_trace(go.Bar(
                    x=days_df["date"], y=days_df["burned"],
                    name=t["burned_kcal"], marker_color="#1A2942",
                    hovertemplate=f"%{{x|%d %b}}<br>{t['burned_kcal']}: %{{y:.0f}} kcal<extra></extra>",
                ))
                fig.update_layout(barmode="group")
                y_title = "kcal"

            elif chart_mode == "macros":
                macro_specs = [
                    ("protein", t["protein_full"], "#FF8B8B"),
                    ("carbs", t["carbs_full"], "#1A2942"),
                    ("fat", t["fats_full"], "#FFB4B4"),
                ]
                for col, label, color in macro_specs:
                    fig.add_trace(go.Bar(
                        x=days_df["date"], y=days_df[col], name=label, marker_color=color,
                        hovertemplate=f"%{{x|%d %b}}<br>{label}: %{{y:.1f}} g<extra></extra>",
                    ))
                fig.update_layout(barmode="stack")
                y_title = t["grams"]

            else:  # meals
                meal_order = ["Colazione", "Pranzo", "Snack", "Cena"]
                meal_colors = ["#FF8B8B", "#1A2942", "#FFB4B4", "#667085"]
                for meal_type, color in zip(meal_order, meal_colors):
                    if meals_df.empty:
                        vals = [0.0] * len(days_df)
                    else:
                        series = meals_df[meals_df["meal_type"] == meal_type].groupby("date")["calories"].sum()
                        vals = [float(series.get(d, 0)) for d in days_df["date"]]
                    fig.add_trace(go.Bar(
                        x=days_df["date"], y=vals, name=tr_meal_type(meal_type), marker_color=color,
                        hovertemplate=f"%{{x|%d %b}}<br>{tr_meal_type(meal_type)}: %{{y:.0f}} kcal<extra></extra>",
                    ))
                fig.update_layout(barmode="stack")
                y_title = "kcal"

            fig.update_xaxes(
                range=[chart_start, chart_end + pd.Timedelta(hours=23)],
                tickformat="%d %b",
                showgrid=False,
                fixedrange=False,
            )
            _chart_grid = "#333333" if is_zero_mode() else "#E8ECF2"
            _chart_bg = "#080808" if is_zero_mode() else "#FFFFFF"
            _chart_font = "#F2F2F2" if is_zero_mode() else "#1A2942"
            _legend_bg = "rgba(8,8,8,.88)" if is_zero_mode() else "rgba(255,255,255,.85)"

            fig.update_yaxes(
                title=y_title,
                gridcolor=_chart_grid,
                zeroline=False,
                fixedrange=False,
            )
            fig.update_xaxes(
                color=_chart_font,
            )
            fig.update_yaxes(
                color=_chart_font,
            )
            fig.update_layout(
                height=500,
                plot_bgcolor=_chart_bg,
                paper_bgcolor="rgba(0,0,0,0)",
                hovermode="x unified",
                font=dict(color=_chart_font),
                margin=dict(l=55, r=25, t=45, b=55),
                legend=dict(
                    orientation="h",
                    yanchor="bottom",
                    y=1.02,
                    xanchor="left",
                    x=0,
                    bgcolor=_legend_bg,
                    font=dict(color=_chart_font),
                ),
            )
            st.plotly_chart(fig, use_container_width=True, config={"displayModeBar": False})

            # --------------------------------------------------------------
            # DETTAGLI GIORNALIERI SOTTO IL GRAFICO
            # --------------------------------------------------------------
            detail_cells = []
            for _, row in days_df.iterrows():
                day = row["date"]
                kcal_in = float(row["calories"])
                extra = float(row["extra"])
                if kcal_in <= 0:
                    deficit_icon, deficit_tip = "·", t["no_food_data"]
                else:
                    daily_def = float(user_bmr) + extra - kcal_in
                    if daily_def >= float(user_deficit_target_kcal):
                        deficit_icon = "👍"
                    elif daily_def >= 0:
                        deficit_icon = "😐"
                    else:
                        deficit_icon = "👎"
                    deficit_tip = f"Deficit: {daily_def:.0f} kcal"

                if not acts_df.empty:
                    day_acts = acts_df[acts_df["date"] == day]
                    has_padel = any(str(v).strip().lower() == "padel" for v in day_acts["activity_name"].tolist())
                else:
                    has_padel = False

                if has_padel:
                    activity_icon = "🎾"
                    activity_tip = f"Padel · {extra:.0f} kcal extra"
                elif extra > 300:
                    activity_icon = "🔥"
                    activity_tip = f"{extra:.0f} kcal extra"
                else:
                    activity_icon = "🛏️"
                    activity_tip = f"{extra:.0f} kcal extra"

                detail_cells.append(
                    f'<div style="min-width:48px;text-align:center;padding:5px 3px;">'
                    f'<div style="font-size:11px;color:#667085;">{day.strftime("%d")}<br>{day.strftime("%b")}</div>'
                    f'<div title="{html.escape(deficit_tip, quote=True)}" style="font-size:20px;cursor:help;">{deficit_icon}</div>'
                    f'<div title="{html.escape(activity_tip, quote=True)}" style="font-size:18px;cursor:help;">{activity_icon}</div>'
                    f'</div>'
                )

            timeline_html = (
                '<div style="border:1px solid #E8ECF2;border-radius:12px;padding:8px 10px;overflow-x:auto;">'
                '<div style="font-size:12px;color:#667085;margin-bottom:4px;">'
                f'Dettagli: 👍 deficit ≥{int(round(float(user_deficit_target_kcal)))} · '
                f'😐 deficit 0–{max(0, int(round(float(user_deficit_target_kcal))) - 1)} · '
                '👎 surplus &nbsp;|&nbsp; 🎾 Padel · 🔥 extra >300 · 🛏️ extra ≤300'
                '</div>'
                f'<div style="display:flex;gap:2px;min-width:{max(100, len(detail_cells)*50)}px;">'
                + "".join(detail_cells) +
                '</div></div>'
            )
            st.markdown(timeline_html, unsafe_allow_html=True)

        except Exception as e:
            st.error(t["chart_error"].format(error=e))
            print(traceback.format_exc())

# 12. PAGE 4: RICETTE / RECIPES
# ==============================================================================
elif selected_page == t["t4"]:
    render_page_title_card(t["recipes_title"])
    st.caption(t["recipes_caption"])

    if "recipe_form_version" not in st.session_state:
        st.session_state["recipe_form_version"] = 0
    v = st.session_state["recipe_form_version"]

    _recipe_compact_i18n = {
        "Italiano": {
            "my": "👤 Le mie ricette",
            "shared": "🌍 Ricette condivise",
            "generator": "✨ Generatore Ricetta AI",
            "builder": "➕ Crea un pasto da ingredienti",
            "generator_caption": (
                "Imposta i tuoi obiettivi. Se inserisci ingredienti disponibili, "
                "SanoSync li userà come base e aggiungerà solo ciò che serve per creare una ricetta sensata."
            ),
            "available": "Ingredienti che vuoi usare (opzionale)",
            "available_help": (
                "Se li inserisci, il generatore si comporta automaticamente come uno Svuotafrigo. "
                "Indica anche le quantità quando le conosci."
            ),
            "ingredient_ai_label": "✨ **SanoSync AI · Calcola da ingredienti**",
            "ingredient_ai_placeholder": "Es. 250g di pollo, 120g di riso, 200g di zucchine, 10g di olio",
            "ingredient_ai_help": (
                "Scrivi liberamente gli ingredienti e le quantità. SanoSync AI riconosce gli alimenti "
                "e stima automaticamente kcal e macronutrienti, compilando la tabella."
            ),
            "ingredient_ai_button": "✨ Analizza con SanoSync AI",
            "ingredient_ai_spinner": "Sto analizzando gli ingredienti…",
            "ingredient_ai_done": "✅ Ingredienti compilati automaticamente.",
            "ingredient_ai_empty": "Inserisci almeno un ingrediente.",
            "ingredient_ai_error": "Errore durante l'analisi degli ingredienti: {error}",
            "ingredient_voice_error": "Impossibile trascrivere l’audio: {error}","creation_mode":"Come vuoi creare la ricetta?","mode_known":"🍳 So già cosa cucinare","mode_ai":"✨ Voglio un aiuto dall’AI","ingredient_entry_mode":"Come vuoi inserire gli ingredienti?","ingredient_entry_manual":"✍️ Manualmente","ingredient_entry_ai":"✨ Con SanoSync AI","manual_add":"➕ Aggiungi ingrediente","manual_name":"Ingrediente","manual_qty":"Quantità (g)","manual_kcal":"Kcal","manual_pro":"Pro","manual_carbs":"Carbs","manual_fat":"Fat","mode_known_help":"Scrivi gli ingredienti che hai deciso di usare: SanoSync calcolerà automaticamente kcal e macro.","mode_ai_help":"Descrivi i tuoi obiettivi e lascia che SanoSync proponga una ricetta completa.","ai_starting_ingredients":"✨ Ingredienti di partenza per l’AI (opzionale)","ai_starting_help":"Se li inserisci, l’AI li userà come base (modalità svuotafrigo) e aggiungerà solo ciò che serve.","ai_generated_loaded":"✅ Ricetta AI caricata in modifica. Controlla ingredienti e valori prima di salvarla.",
        },
        "English": {
            "my": "👤 My recipes",
            "shared": "🌍 Shared recipes",
            "generator": "✨ AI Recipe Generator",
            "builder": "➕ Create a meal from ingredients",
            "generator_caption": (
                "Set your targets. If you enter available ingredients, SanoSync will use them as the base "
                "and add only what is needed to make a coherent recipe."
            ),
            "available": "Ingredients you want to use (optional)",
            "available_help": (
                "If you enter ingredients, the generator automatically works as a fridge clear-out. "
                "Add quantities when you know them."
            ),
            "ingredient_ai_label": "✨ **SanoSync AI · Calculate from ingredients**",
            "ingredient_ai_placeholder": "E.g. 250g chicken, 120g rice, 200g courgette, 10g oil",
            "ingredient_ai_help": (
                "Enter ingredients and quantities freely. SanoSync AI recognizes the foods "
                "and estimates calories and macros, then fills the table automatically."
            ),
            "ingredient_ai_button": "✨ Analyze with SanoSync AI",
            "ingredient_ai_spinner": "Analyzing ingredients…",
            "ingredient_ai_done": "✅ Ingredients filled automatically.",
            "ingredient_ai_empty": "Enter at least one ingredient.",
            "ingredient_ai_error": "Ingredient analysis error: {error}",
            "ingredient_voice_error": "Could not transcribe the audio: {error}","creation_mode":"How do you want to create the recipe?","mode_known":"🍳 I already know what to cook","mode_ai":"✨ I want AI help","ingredient_entry_mode":"How do you want to enter ingredients?","ingredient_entry_manual":"✍️ Manually","ingredient_entry_ai":"✨ With SanoSync AI","manual_add":"➕ Add ingredient","manual_name":"Ingredient","manual_qty":"Quantity (g)","manual_kcal":"Kcal","manual_pro":"Protein","manual_carbs":"Carbs","manual_fat":"Fat","mode_known_help":"Enter the ingredients you have chosen: SanoSync will calculate calories and macros automatically.","mode_ai_help":"Set your targets and let SanoSync propose a complete recipe.","ai_starting_ingredients":"✨ Starting ingredients for AI (optional)","ai_starting_help":"If provided, AI will use them as the base (fridge-clear-out mode) and add only what is needed.","ai_generated_loaded":"✅ AI recipe loaded for editing. Review ingredients and values before saving.",
        },
        "Nederlands": {
            "my": "👤 Mijn recepten",
            "shared": "🌍 Gedeelde recepten",
            "generator": "✨ AI-receptgenerator",
            "builder": "➕ Maak een maaltijd van ingrediënten",
            "generator_caption": (
                "Stel je doelen in. Als je beschikbare ingrediënten invoert, gebruikt SanoSync die als basis "
                "en voegt alleen toe wat nodig is voor een logisch recept."
            ),
            "available": "Ingrediënten die je wilt gebruiken (optioneel)",
            "available_help": (
                "Als je ingrediënten invoert, werkt de generator automatisch als koelkast-opmaker. "
                "Voeg hoeveelheden toe als je die weet."
            ),
            "ingredient_ai_label": "✨ **SanoSync AI · Bereken uit ingrediënten**",
            "ingredient_ai_placeholder": "Bijv. 250g kip, 120g rijst, 200g courgette, 10g olie",
            "ingredient_ai_help": (
                "Voer ingrediënten en hoeveelheden vrij in. SanoSync AI herkent de voedingsmiddelen "
                "en schat calorieën en macro's, waarna de tabel automatisch wordt ingevuld."
            ),
            "ingredient_ai_button": "✨ Analyseer met SanoSync AI",
            "ingredient_ai_spinner": "Ingrediënten analyseren…",
            "ingredient_ai_done": "✅ Ingrediënten automatisch ingevuld.",
            "ingredient_ai_empty": "Voer minstens één ingrediënt in.",
            "ingredient_ai_error": "Fout bij ingrediëntanalyse: {error}",
            "ingredient_voice_error": "Kon de audio niet transcriberen: {error}","creation_mode":"Hoe wil je het recept maken?","mode_known":"🍳 Ik weet al wat ik wil koken","mode_ai":"✨ Ik wil hulp van AI","ingredient_entry_mode":"Hoe wil je ingrediënten invoeren?","ingredient_entry_manual":"✍️ Handmatig","ingredient_entry_ai":"✨ Met SanoSync AI","manual_add":"➕ Ingrediënt toevoegen","manual_name":"Ingrediënt","manual_qty":"Hoeveelheid (g)","manual_kcal":"Kcal","manual_pro":"Eiwit","manual_carbs":"Koolh.","manual_fat":"Vet","mode_known_help":"Voer de gekozen ingrediënten in: SanoSync berekent automatisch calorieën en macro’s.","mode_ai_help":"Stel je doelen in en laat SanoSync een compleet recept voorstellen.","ai_starting_ingredients":"✨ Startingrediënten voor AI (optioneel)","ai_starting_help":"Als je ze invoert, gebruikt AI ze als basis (koelkast-opmaakmodus) en voegt alleen toe wat nodig is.","ai_generated_loaded":"✅ AI-recept geladen om te bewerken. Controleer ingrediënten en waarden voor je opslaat.",
        },
        "Français": {
            "my": "👤 Mes recettes",
            "shared": "🌍 Recettes partagées",
            "generator": "✨ Générateur de recette IA",
            "builder": "➕ Créer un repas à partir d'ingrédients",
            "generator_caption": (
                "Définissez vos objectifs. Si vous indiquez des ingrédients disponibles, SanoSync les utilisera "
                "comme base et n'ajoutera que ce qui est nécessaire pour obtenir une recette cohérente."
            ),
            "available": "Ingrédients que vous souhaitez utiliser (optionnel)",
            "available_help": (
                "Si vous renseignez des ingrédients, le générateur fonctionne automatiquement en mode vide-frigo. "
                "Ajoutez les quantités lorsque vous les connaissez."
            ),
            "ingredient_ai_label": "✨ **SanoSync AI · Calculer à partir des ingrédients**",
            "ingredient_ai_placeholder": "Ex. 250g de poulet, 120g de riz, 200g de courgettes, 10g d'huile",
            "ingredient_ai_help": (
                "Saisissez librement les ingrédients et les quantités. SanoSync AI reconnaît les aliments "
                "et estime calories et macros, puis remplit automatiquement le tableau."
            ),
            "ingredient_ai_button": "✨ Analyser avec SanoSync AI",
            "ingredient_ai_spinner": "Analyse des ingrédients…",
            "ingredient_ai_done": "✅ Ingrédients remplis automatiquement.",
            "ingredient_ai_empty": "Saisissez au moins un ingrédient.",
            "ingredient_ai_error": "Erreur d'analyse des ingrédients : {error}",
            "ingredient_voice_error": "Impossible de transcrire l’audio : {error}","creation_mode":"Comment souhaitez-vous créer la recette ?","mode_known":"🍳 Je sais déjà quoi cuisiner","mode_ai":"✨ Je veux l’aide de l’IA","ingredient_entry_mode":"Comment souhaitez-vous saisir les ingrédients ?","ingredient_entry_manual":"✍️ Manuellement","ingredient_entry_ai":"✨ Avec SanoSync AI","manual_add":"➕ Ajouter un ingrédient","manual_name":"Ingrédient","manual_qty":"Quantité (g)","manual_kcal":"Kcal","manual_pro":"Prot.","manual_carbs":"Gluc.","manual_fat":"Lip.","mode_known_help":"Saisissez les ingrédients choisis : SanoSync calculera automatiquement calories et macros.","mode_ai_help":"Définissez vos objectifs et laissez SanoSync proposer une recette complète.","ai_starting_ingredients":"✨ Ingrédients de départ pour l’IA (optionnel)","ai_starting_help":"Si vous les indiquez, l’IA les utilisera comme base (mode vide-frigo) et n’ajoutera que le nécessaire.","ai_generated_loaded":"✅ Recette IA chargée en modification. Vérifiez les ingrédients et valeurs avant l’enregistrement.",
        },
    }
    _rcu = _recipe_compact_i18n.get(
        current_lang,
        _recipe_compact_i18n["Italiano"],
    )

    # ------------------------------------------------------------------
    # ✨ GENERATORE RICETTA AI
    # ------------------------------------------------------------------
    _ai_recipe_i18n = {
        "Italiano": {
            "title": "✨ Generatore Ricetta AI",
            "caption": "Genera una ricetta rispettando i tuoi obiettivi.",
            "mode": "Modalità",
            "mode_generate": "Genera ricetta",
            "mode_fridge": "Svuotafrigo",
            "meal_type": "Tipo di pasto",
            "style": "Tipo di ricetta",
            "style_options": ["Carne", "Pesce", "Vegetariana", "Vegana"],
            "restrictions": "Restrizioni",
            "restriction_options": ["Gluten free", "Lactose free"],
            "servings": "Porzioni",
            "kcal": "Kcal desiderate per porzione",
            "protein": "Proteine minime per porzione (g, opzionale)",
            "macro": "Focus nutrizionale",
            "macro_options": ["Nessuno", "Alte proteine", "Low carb", "Low fat"],
            "total_time": "Tempo totale massimo",
            "active_time": "Tempo attivo massimo",
            "equipment": "Attrezzatura disponibile",
            "equipment_options": ["Forno", "Air fryer", "Microonde", "Padella", "Pentola", "Blender"],
            "available": "Ingredienti disponibili",
            "available_help": "Inserisci anche le quantità quando le conosci, ad es. pollo 250 g, zucchine 300 g.",
            "avoid": "Ingredienti da evitare",
            "today": "🎯 Usa i miei target di oggi",
            "today_done": "Target di oggi caricati.",
            "generate": "✨ Genera ricetta",
            "generating": "Sto creando la ricetta…",
            "regenerate": "🔄 Genera un'altra",
            "edit": "✏️ Modifica",
            "save": "💾 Salva nelle mie ricette",
            "insert": "🍽️ Inserisci oggi",
            "saved": "✅ Ricetta salvata nelle tue ricette.",
            "inserted": "✅ Ricetta inserita nel diario di oggi.",
            "editable": "La ricetta è stata caricata nel form manuale qui sotto: puoi modificarla.",
            "ai_note": "✨ Kcal e macronutrienti sono stime AI e possono essere modificati prima del salvataggio.",
            "ingredients": "Ingredienti",
            "instructions": "Preparazione",
            "time": "Tempo",
            "active": "attivi",
            "per_serving": "per porzione",
            "warning_target": "Con gli ingredienti disponibili la ricetta è sotto il target richiesto.",
            "error": "Errore nella generazione della ricetta: {error}",
            "fridge_required": "Per Svuotafrigo inserisci almeno un ingrediente disponibile.",
        },
        "English": {
            "title": "✨ AI Recipe Generator",
            "caption": "Generate a recipe that matches your targets.",
            "mode": "Mode",
            "mode_generate": "Generate recipe",
            "mode_fridge": "Fridge clear-out",
            "meal_type": "Meal type",
            "style": "Recipe type",
            "style_options": ["Meat", "Fish", "Vegetarian", "Vegan"],
            "restrictions": "Restrictions",
            "restriction_options": ["Gluten free", "Lactose free"],
            "servings": "Servings",
            "kcal": "Target kcal per serving",
            "protein": "Minimum protein per serving (g, optional)",
            "macro": "Nutrition focus",
            "macro_options": ["None", "High protein", "Low carb", "Low fat"],
            "total_time": "Maximum total time",
            "active_time": "Maximum active time",
            "equipment": "Available equipment",
            "equipment_options": ["Oven", "Air fryer", "Microwave", "Pan", "Pot", "Blender"],
            "available": "Available ingredients",
            "available_help": "Add quantities when known, e.g. chicken 250 g, courgette 300 g.",
            "avoid": "Ingredients to avoid",
            "today": "🎯 Use today's targets",
            "today_done": "Today's targets loaded.",
            "generate": "✨ Generate recipe",
            "generating": "Creating your recipe…",
            "regenerate": "🔄 Generate another",
            "edit": "✏️ Edit",
            "save": "💾 Save to my recipes",
            "insert": "🍽️ Log today",
            "saved": "✅ Recipe saved to your recipes.",
            "inserted": "✅ Recipe added to today's log.",
            "editable": "The recipe has been loaded into the manual form below so you can edit it.",
            "ai_note": "✨ Calories and macros are AI estimates and can be edited before saving.",
            "ingredients": "Ingredients",
            "instructions": "Instructions",
            "time": "Time",
            "active": "active",
            "per_serving": "per serving",
            "warning_target": "With the available ingredients the recipe is below the requested target.",
            "error": "Recipe generation error: {error}",
            "fridge_required": "Add at least one available ingredient for Fridge clear-out mode.",
        },
        "Nederlands": {
            "title": "✨ AI-receptgenerator",
            "caption": "Genereer een recept dat bij je doelen past.",
            "mode": "Modus",
            "mode_generate": "Recept genereren",
            "mode_fridge": "Koelkast leegmaken",
            "meal_type": "Maaltijdtype",
            "style": "Type recept",
            "style_options": ["Vlees", "Vis", "Vegetarisch", "Vegan"],
            "restrictions": "Beperkingen",
            "restriction_options": ["Glutenvrij", "Lactosevrij"],
            "servings": "Porties",
            "kcal": "Gewenste kcal per portie",
            "protein": "Minimale eiwitten per portie (g, optioneel)",
            "macro": "Voedingsfocus",
            "macro_options": ["Geen", "Eiwitrijk", "Low carb", "Low fat"],
            "total_time": "Maximale totale tijd",
            "active_time": "Maximale actieve tijd",
            "equipment": "Beschikbare apparatuur",
            "equipment_options": ["Oven", "Air fryer", "Magnetron", "Koekenpan", "Pan", "Blender"],
            "available": "Beschikbare ingrediënten",
            "available_help": "Voeg hoeveelheden toe indien bekend, bv. kip 250 g, courgette 300 g.",
            "avoid": "Te vermijden ingrediënten",
            "today": "🎯 Gebruik mijn doelen van vandaag",
            "today_done": "Doelen van vandaag geladen.",
            "generate": "✨ Recept genereren",
            "generating": "Recept wordt gemaakt…",
            "regenerate": "🔄 Genereer een andere",
            "edit": "✏️ Bewerken",
            "save": "💾 Opslaan bij mijn recepten",
            "insert": "🍽️ Vandaag registreren",
            "saved": "✅ Recept opgeslagen bij je recepten.",
            "inserted": "✅ Recept toegevoegd aan vandaag.",
            "editable": "Het recept is in het handmatige formulier hieronder geladen en kan worden aangepast.",
            "ai_note": "✨ Calorieën en macro's zijn AI-schattingen en kunnen voor het opslaan worden aangepast.",
            "ingredients": "Ingrediënten",
            "instructions": "Bereiding",
            "time": "Tijd",
            "active": "actief",
            "per_serving": "per portie",
            "warning_target": "Met de beschikbare ingrediënten ligt het recept onder het gevraagde doel.",
            "error": "Fout bij het genereren van het recept: {error}",
            "fridge_required": "Voeg minstens één beschikbaar ingrediënt toe voor Koelkast leegmaken.",
        },
        "Français": {
            "title": "✨ Générateur de recette IA",
            "caption": "Générez une recette adaptée à vos objectifs.",
            "mode": "Mode",
            "mode_generate": "Générer une recette",
            "mode_fridge": "Vide-frigo",
            "meal_type": "Type de repas",
            "style": "Type de recette",
            "style_options": ["Viande", "Poisson", "Végétarienne", "Végane"],
            "restrictions": "Restrictions",
            "restriction_options": ["Sans gluten", "Sans lactose"],
            "servings": "Portions",
            "kcal": "Kcal souhaitées par portion",
            "protein": "Protéines minimales par portion (g, optionnel)",
            "macro": "Priorité nutritionnelle",
            "macro_options": ["Aucune", "Riche en protéines", "Low carb", "Low fat"],
            "total_time": "Temps total maximum",
            "active_time": "Temps actif maximum",
            "equipment": "Équipement disponible",
            "equipment_options": ["Four", "Air fryer", "Micro-ondes", "Poêle", "Casserole", "Blender"],
            "available": "Ingrédients disponibles",
            "available_help": "Ajoutez les quantités si vous les connaissez, ex. poulet 250 g, courgettes 300 g.",
            "avoid": "Ingrédients à éviter",
            "today": "🎯 Utiliser mes objectifs du jour",
            "today_done": "Objectifs du jour chargés.",
            "generate": "✨ Générer la recette",
            "generating": "Création de la recette…",
            "regenerate": "🔄 Générer une autre",
            "edit": "✏️ Modifier",
            "save": "💾 Enregistrer dans mes recettes",
            "insert": "🍽️ Enregistrer aujourd'hui",
            "saved": "✅ Recette enregistrée dans vos recettes.",
            "inserted": "✅ Recette ajoutée au journal d'aujourd'hui.",
            "editable": "La recette a été chargée dans le formulaire manuel ci-dessous pour être modifiée.",
            "ai_note": "✨ Les calories et macros sont des estimations IA et peuvent être modifiées avant l'enregistrement.",
            "ingredients": "Ingrédients",
            "instructions": "Préparation",
            "time": "Temps",
            "active": "actif",
            "per_serving": "par portion",
            "warning_target": "Avec les ingrédients disponibles, la recette est sous l'objectif demandé.",
            "error": "Erreur lors de la génération : {error}",
            "fridge_required": "Ajoutez au moins un ingrédient disponible pour le mode Vide-frigo.",
        },
    }

    _air = _ai_recipe_i18n.get(current_lang, _ai_recipe_i18n["Italiano"])


    # ------------------------------------------------------------------
    # ➕ CREAZIONE RICETTA UNIFICATA
    # ------------------------------------------------------------------

    # Apply an AI-generated recipe BEFORE any builder widget is instantiated.
    _pending_recipe = st.session_state.pop("_pending_ai_recipe_for_builder", None)
    if _pending_recipe:
        # This block runs before the recipe_creation_mode radio is instantiated,
        # so setting the widget key here is safe.
        st.session_state["recipe_creation_mode"] = "known"
        st.session_state["recipe_builder_ingredients"] = list(
            _pending_recipe.get("ingredients") or []
        )
        st.session_state[f"recipe_builder_name_{v}"] = str(
            _pending_recipe.get("name") or ""
        )
        st.session_state[f"recipe_builder_notes_{v}"] = _ai_recipe_notes(
            _pending_recipe
        )
        st.session_state[f"recipe_servings_{v}"] = float(
            _pending_recipe.get("servings") or 1.0
        )

        _pending_meal_type = _pending_recipe.get("meal_type") or "Cena"
        if _pending_meal_type not in ["Colazione", "Pranzo", "Cena", "Snack"]:
            _pending_meal_type = "Cena"
        st.session_state[f"recipe_meal_type_{v}"] = _pending_meal_type
        st.session_state[f"recipe_category_{v}"] = "Casa"
        st.session_state[f"recipe_ai_ingredient_text_{v}"] = ", ".join(
            f"{_safe_float(i.get('quantity_g')):g}g {i.get('name', '')}"
            for i in (_pending_recipe.get("ingredients") or [])
        )
        st.session_state["_show_ai_recipe_loaded_message"] = True

    # Apply pending mode changes BEFORE the radio widget is instantiated.
    _pending_creation_mode = st.session_state.pop(
        "_pending_recipe_creation_mode",
        None,
    )
    if _pending_creation_mode in ("known", "ai"):
        st.session_state["recipe_creation_mode"] = _pending_creation_mode

    with st.expander(_rcu["builder"], expanded=True):
        _creation_mode = st.radio(
            _rcu["creation_mode"],
            ["known", "ai"],
            horizontal=True,
            key="recipe_creation_mode",
            format_func=lambda x: (
                _rcu["mode_known"] if x == "known" else _rcu["mode_ai"]
            ),
        )

        if _creation_mode == "ai":
            st.caption(_rcu["mode_ai_help"])

            _ai1, _ai2 = st.columns(2)
            with _ai1:
                if "unified_ai_recipe_meal_type" not in st.session_state:
                    st.session_state["unified_ai_recipe_meal_type"] = (
                        suggest_next_meal_type(date.today())
                    )
                _ai_meal_type = st.selectbox(
                    _air["meal_type"],
                    ["Colazione", "Pranzo", "Cena", "Snack"],
                    key="unified_ai_recipe_meal_type",
                    format_func=tr_meal_type,
                )
            with _ai2:
                _ai_servings = st.number_input(
                    _air["servings"],
                    min_value=1.0,
                    max_value=20.0,
                    value=2.0,
                    step=1.0,
                    key="unified_ai_recipe_servings",
                )

            _ai_restrictions = st.multiselect(
                _air["restrictions"],
                _air["restriction_options"],
                key="unified_ai_recipe_restrictions",
            )

            if "unified_ai_recipe_target_kcal" not in st.session_state:
                st.session_state["unified_ai_recipe_target_kcal"] = 600.0
            if "unified_ai_recipe_target_protein" not in st.session_state:
                st.session_state["unified_ai_recipe_target_protein"] = 0.0

            if st.button(
                _air["today"],
                key="unified_ai_recipe_use_today",
                use_container_width=True,
            ):
                try:
                    _today_str_ai = str(date.today())
                    _today_ai_totals = get_daily_totals(_today_str_ai)
                    _meals_ai = _today_ai_totals["meals"]
                    _acts_ai = _today_ai_totals["activities"]
                    _eaten_ai = _today_ai_totals["calories"]
                    _protein_ai = _today_ai_totals["protein"]
                    _activity_ai = _today_ai_totals["activity"]

                    _maintenance_ai = max(
                        0.0,
                        _safe_float(user_bmr) + _activity_ai,
                    )
                    _target_intake_ai = max(
                        0.0,
                        _maintenance_ai
                        - _safe_float(user_deficit_target_kcal),
                    )
                    _remaining_ai = max(
                        100.0,
                        _target_intake_ai - _eaten_ai,
                    )

                    st.session_state["unified_ai_recipe_target_kcal"] = float(
                        round(_remaining_ai)
                    )
                    if (
                        user_protein_goal_enabled
                        and user_protein_goal_g > 0
                    ):
                        st.session_state[
                            "unified_ai_recipe_target_protein"
                        ] = float(
                            max(
                                0.0,
                                round(user_protein_goal_g - _protein_ai),
                            )
                        )
                    st.success(_air["today_done"])
                    st.rerun()
                except Exception as exc:
                    print(f"AI recipe target lookup error: {exc}")

            _b1, _b2, _b3 = st.columns(3)
            with _b1:
                _ai_target_kcal = st.number_input(
                    _air["kcal"],
                    min_value=100.0,
                    max_value=3000.0,
                    step=25.0,
                    key="unified_ai_recipe_target_kcal",
                )
            with _b2:
                _ai_target_protein = st.number_input(
                    _air["protein"],
                    min_value=0.0,
                    max_value=250.0,
                    step=5.0,
                    key="unified_ai_recipe_target_protein",
                    help="0 = optional",
                )
            with _b3:
                _ai_macro_focus = st.selectbox(
                    _air["macro"],
                    _air["macro_options"],
                    key="unified_ai_recipe_macro_focus",
                )

            _time_options = [10, 20, 30, 45, 60]
            _c1, _c2 = st.columns(2)
            with _c1:
                _ai_total_minutes = st.selectbox(
                    _air["total_time"],
                    _time_options,
                    index=2,
                    key="unified_ai_recipe_total_time",
                    format_func=lambda x: f"{x} min",
                )
            with _c2:
                _ai_active_minutes = st.selectbox(
                    _air["active_time"],
                    [10, 15, 20, 30, 45],
                    index=1,
                    key="unified_ai_recipe_active_time",
                    format_func=lambda x: f"{x} min",
                )

            _ai_equipment = st.multiselect(
                _air["equipment"],
                _air["equipment_options"],
                default=_air["equipment_options"],
                key="unified_ai_recipe_equipment",
            )

            _ai_available = st.text_area(
                _rcu["ai_starting_ingredients"],
                key="unified_ai_recipe_available",
                help=_rcu["ai_starting_help"],
                placeholder="pollo 250 g, zucchine 300 g, yogurt 150 g",
                height=90,
            )
            _ai_avoid = st.text_input(
                _air["avoid"],
                key="unified_ai_recipe_avoid",
                placeholder="cipolla, funghi...",
            )

            if st.button(
                _air["generate"],
                type="primary",
                use_container_width=True,
                key="unified_ai_recipe_generate",
            ):
                try:
                    if float(_ai_target_kcal) < 200:
                        st.info(
                            "Target calorico molto basso: SanoSync AI proverà a creare comunque "
                            "una ricetta completa e, se necessario, proporrà il minimo realistico."
                        )
                    with st.spinner(_air["generating"]):
                        _effective_ai_mode = (
                            "fridge"
                            if _ai_available.strip()
                            else "generate"
                        )
                        _generated = generate_ai_recipe_with_groq(
                            language=current_lang,
                            mode=_effective_ai_mode,
                            meal_type=_ai_meal_type,
                            restrictions=_ai_restrictions,
                            servings=_ai_servings,
                            target_kcal=_ai_target_kcal,
                            protein_target=_ai_target_protein,
                            macro_focus=_ai_macro_focus,
                            total_minutes=_ai_total_minutes,
                            active_minutes=min(
                                int(_ai_active_minutes),
                                int(_ai_total_minutes),
                            ),
                            equipment=_ai_equipment,
                            available_ingredients=_ai_available,
                            avoid_ingredients=_ai_avoid,
                        )

                    if not (_generated.get("ingredients") or []):
                        _generated = regenerate_ai_recipe_if_empty(
                            language=current_lang,
                            mode=_effective_ai_mode,
                            meal_type=_ai_meal_type,
                            restrictions=_ai_restrictions,
                            servings=_ai_servings,
                            target_kcal=_ai_target_kcal,
                            protein_target=_ai_target_protein,
                            macro_focus=_ai_macro_focus,
                            total_minutes=_ai_total_minutes,
                            active_minutes=min(
                                int(_ai_active_minutes),
                                int(_ai_total_minutes),
                            ),
                            equipment=_ai_equipment,
                            available_ingredients=_ai_available,
                            avoid_ingredients=_ai_avoid,
                        )

                    if not (_generated.get("ingredients") or []):
                        raise RuntimeError(
                            "L'AI non è riuscita a costruire una ricetta coerente con questi vincoli. "
                            "Prova ad aumentare leggermente le kcal oppure ridurre i vincoli."
                        )

                    st.session_state[
                        "unified_ai_recipe_result"
                    ] = _generated
                    st.session_state[
                        "_pending_recipe_creation_mode"
                    ] = "ai"
                    queue_ui_sound("ai_recipe_generated")
                    st.rerun()

                except Exception as exc:
                    st.error(_air["error"].format(error=exc))
                    print(traceback.format_exc())

            _ai_generated_result = st.session_state.get(
                "unified_ai_recipe_result"
            )

            if _ai_generated_result:
                _ai_nutr = _ai_generated_result.get(
                    "nutrition_per_serving",
                    {},
                )

                st.divider()
                st.markdown(
                    f"### 🍽️ {html.escape(str(_ai_generated_result.get('name') or 'Ricetta AI'))}"
                )

                st.caption(
                    f"⏱️ {_ai_generated_result.get('total_minutes', 0)} min · "
                    f"{_ai_generated_result.get('active_minutes', 0)} min {_air['active']} · "
                    f"🍽️ {_safe_float(_ai_generated_result.get('servings') or 1):g}"
                )

                _m1, _m2, _m3, _m4 = st.columns(4)
                _m1.metric(
                    "Kcal",
                    int(round(_safe_float(_ai_nutr.get("calories")))),
                )
                _m2.metric(
                    "Pro",
                    f"{_safe_float(_ai_nutr.get('protein')):.1f} g",
                )
                _m3.metric(
                    "Carbs",
                    f"{_safe_float(_ai_nutr.get('carbs')):.1f} g",
                )
                _m4.metric(
                    "Fat",
                    f"{_safe_float(_ai_nutr.get('fat')):.1f} g",
                )

                if _ai_generated_result.get("warning"):
                    st.warning(
                        str(_ai_generated_result.get("warning"))
                    )

                _ai_description = str(
                    _ai_generated_result.get("description") or ""
                ).strip()
                if _ai_description:
                    st.markdown(_ai_description)

                with st.expander(
                    f"🥕 {_air['ingredients']}",
                    expanded=False,
                ):
                    _ingredient_lines = [
                        (
                            f"{str(_ing.get('name') or '').strip()} — "
                            f"{_safe_float(_ing.get('quantity_g')):g} g"
                        )
                        for _ing in (
                            _ai_generated_result.get("ingredients") or []
                        )
                        if str(_ing.get("name") or "").strip()
                    ]
                    render_compact_ai_list(
                        _ingredient_lines,
                        numbered=False,
                    )

                with st.expander(
                    f"👩‍🍳 {_air['instructions']}",
                    expanded=False,
                ):
                    render_compact_ai_list(
                        _ai_generated_result.get("instructions") or [],
                        numbered=True,
                    )

                _r1, _r2 = st.columns(2)
                with _r1:
                    if st.button(
                        _air["regenerate"],
                        use_container_width=True,
                        key="unified_ai_recipe_regenerate",
                    ):
                        st.session_state.pop(
                            "unified_ai_recipe_result",
                            None,
                        )
                        st.rerun()

                with _r2:
                    if st.button(
                        _air["edit"],
                        use_container_width=True,
                        key="unified_ai_recipe_use_edit",
                    ):
                        st.session_state[
                            "_pending_ai_recipe_for_builder"
                        ] = _ai_generated_result
                        st.session_state.pop(
                            "unified_ai_recipe_result",
                            None,
                        )
                        st.rerun()

        else:
            st.caption(_rcu["mode_known_help"])

            if st.session_state.pop(
                "_show_ai_recipe_loaded_message",
                False,
            ):
                st.success(_rcu["ai_generated_loaded"])

            rc1, rc2 = st.columns(2)
            with rc1:
                _recipe_meal_key = f"recipe_meal_type_{v}"
                if _recipe_meal_key not in st.session_state:
                    st.session_state[_recipe_meal_key] = (
                        suggest_next_meal_type(date.today())
                    )
                recipe_meal_type = st.selectbox(
                    t["meal_type_label"],
                    ["Colazione", "Pranzo", "Cena", "Snack"],
                    key=_recipe_meal_key,
                    format_func=tr_meal_type,
                )
            with rc2:
                _recipe_categories_available = (
                    MEAL_CATEGORIES
                    if user_office_lunch_enabled
                    else [
                        c
                        for c in MEAL_CATEGORIES
                        if c != "Lavoro"
                    ]
                )
                recipe_category = st.selectbox(
                    t["category_label"],
                    _recipe_categories_available,
                    index=0,
                    key=f"recipe_category_{v}",
                    help=t["recipe_category_help"],
                    format_func=tr_category,
                )

            _recipe_name_col, _recipe_serv_col = st.columns(
                [3.2, 1.0],
                gap="medium",
                vertical_alignment="bottom",
            )
            with _recipe_name_col:
                r_name = st.text_input(
                    t["col_name"],
                    placeholder=t["recipe_name_placeholder"],
                    key=f"recipe_builder_name_{v}",
                )
            with _recipe_serv_col:
                recipe_servings = st.number_input(
                    t["recipe_servings"],
                    min_value=1.0,
                    max_value=100.0,
                    value=4.0,
                    step=1.0,
                    key=f"recipe_servings_{v}",
                    help=t["recipe_servings_help"],
                )

            _optional_details_labels = {
                "Italiano": "▸ Dettagli opzionali · note e foto",
                "English": "▸ Optional details · notes and photo",
                "Nederlands": "▸ Optionele details · notities en foto",
                "Français": "▸ Détails optionnels · notes et photo",
            }
            with st.expander(
                _optional_details_labels.get(
                    current_lang,
                    _optional_details_labels["Italiano"],
                ),
                expanded=False,
            ):
                r_notes = st.text_area(
                    t["notes_optional"],
                    placeholder=t["notes_placeholder"],
                    key=f"recipe_builder_notes_{v}",
                    height=80,
                )

                recipe_photo = st.file_uploader(
                    t["recipe_photo"],
                    type=["jpg", "jpeg", "png", "webp"],
                    key=f"recipe_photo_{v}",
                    help=t["recipe_photo_help"],
                )
                if recipe_photo is not None:
                    st.image(
                        recipe_photo,
                        caption=r_name.strip() or None,
                        width=260,
                    )

            _ingredient_entry_mode = st.radio(
                _rcu["ingredient_entry_mode"],
                ["manual", "ai"],
                horizontal=True,
                key=f"recipe_ingredient_entry_mode_{v}",
                format_func=lambda x: (
                    _rcu["ingredient_entry_manual"]
                    if x == "manual"
                    else _rcu["ingredient_entry_ai"]
                ),
            )

            if _ingredient_entry_mode == "ai":
                _recipe_ai_text_key = f"recipe_ai_ingredient_text_{v}"

                render_ai_spotlight_css()

                with st.container(key=f"ai_spotlight_recipe_{v}"):
                    render_ai_ingredient_header(
                        title=_rcu["ingredient_ai_label"].replace("**", ""),
                        help_text=_rcu["ingredient_ai_help"],
                        widget_key=f"sanosync_voice_recipe_{v}",
                        target_key=_recipe_ai_text_key,
                        language=current_lang,
                        error_label=_rcu["ingredient_voice_error"],
                    )

                    _ingredient_free_text = st.text_area(
                        "SanoSync AI",
                        key=_recipe_ai_text_key,
                        placeholder=_rcu["ingredient_ai_placeholder"],
                        height=100,
                        label_visibility="collapsed",
                        help=_rcu["ingredient_ai_help"],
                    )

                if st.button(
                    _rcu["ingredient_ai_button"],
                    use_container_width=True,
                    key=f"recipe_ai_parse_ingredients_{v}",
                ):
                    if not str(_ingredient_free_text or "").strip():
                        st.warning(_rcu["ingredient_ai_empty"])
                    else:
                        try:
                            with st.spinner(_rcu["ingredient_ai_spinner"]):
                                _parsed_ingredients = (
                                    parse_recipe_ingredients_with_ai(
                                        _ingredient_free_text,
                                        current_lang,
                                    )
                                )

                            if not _parsed_ingredients:
                                st.warning(_rcu["ingredient_ai_empty"])
                            else:
                                st.session_state[
                                    "recipe_builder_ingredients"
                                ] = _parsed_ingredients
                                queue_ui_sound("ai_ingredients_analyzed")
                                st.success(_rcu["ingredient_ai_done"])
                                st.rerun()

                        except Exception as exc:
                            st.error(
                                _rcu["ingredient_ai_error"].format(
                                    error=exc
                                )
                            )
                            print(traceback.format_exc())

            else:
                # Manual ingredient entry. Nutrient values refer to the
                # entered quantity; internally they are converted to /100 g
                # so existing recipe calculations remain unchanged.
                _manual_cols_1 = st.columns([2.2, 1.1, 1.0], gap="small")
                with _manual_cols_1[0]:
                    _manual_name = st.text_input(
                        _rcu["manual_name"],
                        key=f"manual_recipe_ing_name_{v}",
                    )
                with _manual_cols_1[1]:
                    _manual_qty = st.number_input(
                        _rcu["manual_qty"],
                        min_value=0.0,
                        value=100.0,
                        step=1.0,
                        key=f"manual_recipe_ing_qty_{v}",
                    )
                with _manual_cols_1[2]:
                    _manual_kcal = st.number_input(
                        _rcu["manual_kcal"],
                        min_value=0.0,
                        value=0.0,
                        step=1.0,
                        key=f"manual_recipe_ing_kcal_{v}",
                    )

                _manual_cols_2 = st.columns(3, gap="small")
                with _manual_cols_2[0]:
                    _manual_pro = st.number_input(
                        _rcu["manual_pro"],
                        min_value=0.0,
                        value=0.0,
                        step=0.1,
                        key=f"manual_recipe_ing_pro_{v}",
                    )
                with _manual_cols_2[1]:
                    _manual_carbs = st.number_input(
                        _rcu["manual_carbs"],
                        min_value=0.0,
                        value=0.0,
                        step=0.1,
                        key=f"manual_recipe_ing_carbs_{v}",
                    )
                with _manual_cols_2[2]:
                    _manual_fat = st.number_input(
                        _rcu["manual_fat"],
                        min_value=0.0,
                        value=0.0,
                        step=0.1,
                        key=f"manual_recipe_ing_fat_{v}",
                    )

                if st.button(
                    _rcu["manual_add"],
                    use_container_width=True,
                    key=f"manual_recipe_ing_add_{v}",
                ):
                    if str(_manual_name or "").strip() and _manual_qty > 0:
                        _factor_100 = 100.0 / float(_manual_qty)
                        _manual_item = {
                            "name": str(_manual_name).strip(),
                            "quantity_g": float(_manual_qty),
                            "calories_per_100g": float(_manual_kcal) * _factor_100,
                            "protein_per_100g": float(_manual_pro) * _factor_100,
                            "carbs_per_100g": float(_manual_carbs) * _factor_100,
                            "fat_per_100g": float(_manual_fat) * _factor_100,
                            "source": "manual",
                        }
                        _existing_manual = list(
                            st.session_state.get(
                                "recipe_builder_ingredients",
                                [],
                            )
                        )
                        _existing_manual.append(_manual_item)
                        st.session_state[
                            "recipe_builder_ingredients"
                        ] = _existing_manual

                        # Clear only the manual-add widgets on the next run.
                        for _manual_key in (
                            f"manual_recipe_ing_name_{v}",
                            f"manual_recipe_ing_kcal_{v}",
                            f"manual_recipe_ing_pro_{v}",
                            f"manual_recipe_ing_carbs_{v}",
                            f"manual_recipe_ing_fat_{v}",
                        ):
                            st.session_state.pop(_manual_key, None)
                        st.rerun()

            ingredients = st.session_state.get(
                "recipe_builder_ingredients",
                [],
            )

            if ingredients:
                st.markdown(t["ingredients_title"])

                _edit_help = {
                    "Italiano": "I valori stimati da SanoSync AI sono modificabili prima del salvataggio.",
                    "English": "Values estimated by SanoSync AI can be edited before saving.",
                    "Nederlands": "De door SanoSync AI geschatte waarden kunnen vóór het opslaan worden aangepast.",
                    "Français": "Les valeurs estimées par SanoSync AI peuvent être modifiées avant l’enregistrement.",
                }.get(
                    current_lang,
                    "I valori stimati da SanoSync AI sono modificabili prima del salvataggio.",
                )
                st.caption(_edit_help)

                # Interactive and editable ingredient table.
                # Kcal/macros shown here are totals for the selected quantity.
                # When edited, we convert them back to per-100g values so all
                # existing recipe calculations continue to work unchanged.
                _hdr = st.columns(
                    [0.55, 2.15, 1.25, 1.0, 1.0, 1.0, 1.0],
                    gap="small",
                )
                _headers = [
                    "",
                    t["ingredient_col"],
                    "Quantità (g)" if current_lang == "Italiano" else (
                        "Quantity (g)" if current_lang == "English" else (
                            "Hoeveelheid (g)" if current_lang == "Nederlands"
                            else "Quantité (g)"
                        )
                    ),
                    "Kcal",
                    "Pro",
                    "Carbs",
                    "Fat",
                ]
                for _col, _label in zip(_hdr, _headers):
                    _col.markdown(
                        f"<div style='font-weight:600;color:#7b7e89;"
                        f"padding:0.15rem 0 0.45rem 0'>{_label}</div>",
                        unsafe_allow_html=True,
                    )

                _edited_ingredients = []

                for _idx, _ing in enumerate(ingredients):
                    _qty = max(
                        float(_ing.get("quantity_g", 0) or 0),
                        0.0,
                    )
                    _factor = _qty / 100.0

                    _current_kcal = (
                        float(_ing.get("calories_per_100g", 0) or 0)
                        * _factor
                    )
                    _current_pro = (
                        float(_ing.get("protein_per_100g", 0) or 0)
                        * _factor
                    )
                    _current_carbs = (
                        float(_ing.get("carbs_per_100g", 0) or 0)
                        * _factor
                    )
                    _current_fat = (
                        float(_ing.get("fat_per_100g", 0) or 0)
                        * _factor
                    )

                    _cols = st.columns(
                        [0.55, 2.15, 1.25, 1.0, 1.0, 1.0, 1.0],
                        gap="small",
                        vertical_alignment="center",
                    )

                    _delete = _cols[0].button(
                        "🗑️",
                        key=f"delete_recipe_ingredient_{v}_{_idx}",
                        help=t["remove_ingredient"],
                        use_container_width=True,
                    )

                    _cols[1].write(str(_ing.get("name", "")))

                    _new_qty = _cols[2].number_input(
                        _headers[2],
                        min_value=0.0,
                        value=float(_qty),
                        step=1.0,
                        key=f"edit_recipe_qty_{v}_{_idx}",
                        label_visibility="collapsed",
                    )
                    _new_kcal = _cols[3].number_input(
                        "Kcal",
                        min_value=0.0,
                        value=float(round(_current_kcal, 1)),
                        step=1.0,
                        key=f"edit_recipe_kcal_{v}_{_idx}",
                        label_visibility="collapsed",
                    )
                    _new_pro = _cols[4].number_input(
                        "Pro",
                        min_value=0.0,
                        value=float(round(_current_pro, 1)),
                        step=0.1,
                        key=f"edit_recipe_pro_{v}_{_idx}",
                        label_visibility="collapsed",
                    )
                    _new_carbs = _cols[5].number_input(
                        "Carbs",
                        min_value=0.0,
                        value=float(round(_current_carbs, 1)),
                        step=0.1,
                        key=f"edit_recipe_carbs_{v}_{_idx}",
                        label_visibility="collapsed",
                    )
                    _new_fat = _cols[6].number_input(
                        "Fat",
                        min_value=0.0,
                        value=float(round(_current_fat, 1)),
                        step=0.1,
                        key=f"edit_recipe_fat_{v}_{_idx}",
                        label_visibility="collapsed",
                    )

                    if _delete:
                        continue

                    _new_ing = dict(_ing)
                    _new_ing["quantity_g"] = float(_new_qty)

                    if float(_new_qty) > 0:
                        _to_100g = 100.0 / float(_new_qty)
                        _new_ing["calories_per_100g"] = (
                            float(_new_kcal) * _to_100g
                        )
                        _new_ing["protein_per_100g"] = (
                            float(_new_pro) * _to_100g
                        )
                        _new_ing["carbs_per_100g"] = (
                            float(_new_carbs) * _to_100g
                        )
                        _new_ing["fat_per_100g"] = (
                            float(_new_fat) * _to_100g
                        )
                    else:
                        _new_ing["calories_per_100g"] = 0.0
                        _new_ing["protein_per_100g"] = 0.0
                        _new_ing["carbs_per_100g"] = 0.0
                        _new_ing["fat_per_100g"] = 0.0

                    _edited_ingredients.append(_new_ing)

                # Keep the edited values as the authoritative recipe data.
                st.session_state[
                    "recipe_builder_ingredients"
                ] = _edited_ingredients
                ingredients = _edited_ingredients

                total_weight, totals, per100 = (
                    calculate_recipe_totals(ingredients)
                )

                _servings_safe = max(
                    float(recipe_servings),
                    1.0,
                )
                _per_serving = {
                    key: float(value) / _servings_safe
                    for key, value in totals.items()
                }
                _serving_weight = (
                    float(total_weight) / _servings_safe
                )

                st.markdown(
                    f"**{t['total_recipe']}:** "
                    f"{total_weight:.0f} g · "
                    f"**{totals['calories']:.0f} kcal** · "
                    f"Pro {totals['protein']:.1f} g · "
                    f"Carbs {totals['carbs']:.1f} g · "
                    f"Fat {totals['fat']:.1f} g"
                )
                st.markdown(
                    f"**{t['per_serving']}:** "
                    f"**{_per_serving['calories']:.0f} kcal** · "
                    f"Pro {_per_serving['protein']:.1f} g · "
                    f"Carbs {_per_serving['carbs']:.1f} g · "
                    f"Fat {_per_serving['fat']:.1f} g"
                )
                st.caption(
                    t["serving_weight"].format(
                        grams=f"{_serving_weight:.0f}"
                    )
                    + " · "
                    + f"{t['per_100g_label']}: "
                    f"{per100['calories']:.0f} kcal · "
                    f"Pro {per100['protein']:.1f} g · "
                    f"Carbs {per100['carbs']:.1f} g · "
                    f"Fat {per100['fat']:.1f} g"
                )

                recipe_is_shared = st.checkbox(
                    t["share_recipe"],
                    value=False,
                    key=f"recipe_share_{v}",
                    help=t["share_help"],
                )

                if st.button(
                    t["save_as_meal"],
                    use_container_width=True,
                    key=f"save_recipe_builder_{v}",
                ):
                    if not r_name.strip():
                        st.warning(t["enter_name"])
                    else:
                        try:
                            recipe_image_url = None
                            if recipe_photo is not None:
                                try:
                                    recipe_image_url = (
                                        upload_recipe_image(
                                            recipe_photo
                                        )
                                    )
                                except Exception as upload_exc:
                                    st.error(
                                        t[
                                            "recipe_photo_error"
                                        ].format(
                                            error=upload_exc
                                        )
                                    )
                                    st.stop()

                            insert_recipe_library(
                                name=r_name.strip(),
                                meal_type=recipe_meal_type,
                                category=recipe_category,
                                recipe_servings=recipe_servings,
                                calories=totals["calories"],
                                protein=totals["protein"],
                                carbs=totals["carbs"],
                                fat=totals["fat"],
                                notes=r_notes,
                                ingredients_json=ingredients,
                                is_shared=recipe_is_shared,
                                image_url=recipe_image_url,
                            )
                            st.session_state[
                                "recipe_builder_ingredients"
                            ] = []
                            st.session_state[
                                "recipe_form_version"
                            ] += 1
                            queue_ui_sound("recipe_saved")
                            st.success(t["composed_saved"])
                            st.rerun()
                        except Exception as e:
                            st.error(
                                "Impossibile salvare la ricetta "
                                "nel catalogo. Verifica che la "
                                "tabella recipe_library sia stata "
                                "creata. Errore: " + str(e)
                            )
            else:
                st.info(t["add_one_ingredient"])


    # ------------------------------------------------------------------
    # 👤 LE MIE RICETTE
    # ------------------------------------------------------------------
    with st.expander(_rcu["my"], expanded=False):

        try:
            my_recipe_rows = fetch_personal_recipes_from_api(
                st.session_state.get("auth_access_token")
            )
        except Exception as exc:
            my_recipe_rows = []
            print(f"Errore caricamento ricette personali: {exc}")

        # Mostriamo una sola versione per nome, prendendo la più recente.
        my_recipes = []
        _seen_my = set()
        for r in my_recipe_rows:
            label = str(r.get("name") or "Ricetta").strip()
            key = label.casefold()
            if key in _seen_my:
                continue
            _seen_my.add(key)
            r["_recipe_label"] = label
            my_recipes.append(r)

        if my_recipes:
            for _idx in range(0, len(my_recipes), 2):
                _card_cols = st.columns(2)
                for _offset, _col in enumerate(_card_cols):
                    _recipe_idx = _idx + _offset
                    if _recipe_idx >= len(my_recipes):
                        continue

                    r = my_recipes[_recipe_idx]
                    with _col:
                        with st.container(border=True):
                            _recipe_image = recipe_image_url(r)
                            render_recipe_card_image(
                                _recipe_image,
                                r.get("_recipe_label") or r.get("name") or "Recipe",
                            )

                            _photo_label = (
                                t["recipe_replace_photo"]
                                if r.get("image_url")
                                else t["recipe_add_photo"]
                            )

                            _photo_toggle_key = f"show_recipe_photo_upload_{r.get('id')}"

                            if st.button(
                                _photo_label,
                                key=f"toggle_recipe_photo_{r.get('id')}",
                                use_container_width=True,
                            ):
                                st.session_state[_photo_toggle_key] = not st.session_state.get(
                                    _photo_toggle_key,
                                    False,
                                )

                            if st.session_state.get(_photo_toggle_key, False):
                                with st.container(border=True):
                                    _new_recipe_photo = st.file_uploader(
                                        _photo_label,
                                        type=["jpg", "jpeg", "png", "webp"],
                                        key=f"existing_recipe_photo_{r.get('id')}",
                                        label_visibility="collapsed",
                                    )

                                    if _new_recipe_photo is not None:
                                        st.image(
                                            _new_recipe_photo,
                                            width=260,
                                        )

                                        if st.button(
                                            t["recipe_photo_save"],
                                            key=f"save_existing_recipe_photo_{r.get('id')}",
                                            use_container_width=True,
                                        ):
                                            try:
                                                _new_url = upload_recipe_image(
                                                    _new_recipe_photo
                                                )
                                                update_recipe_via_api(
                                                    r["id"],
                                                    {"image_url": _new_url},
                                                    st.session_state.get("auth_access_token"),
                                                )
                                                st.session_state[_photo_toggle_key] = False
                                                queue_ui_sound("recipe_photo_saved")
                                                st.success(t["recipe_photo_saved"])
                                                st.rerun()
                                            except Exception as exc:
                                                st.error(
                                                    t["recipe_photo_error"].format(
                                                        error=exc
                                                    )
                                                )

                            st.markdown(f"### {html.escape(str(r['_recipe_label']))}")

                            _share_label = (
                                f"🌍 {t['recipe_shared_badge']}"
                                if r.get("is_shared")
                                else f"🔒 {t['recipe_private']}"
                            )
                            st.caption(
                                f"{tr_meal_type(r.get('meal_type'))} · "
                                f"{tr_category(infer_meal_category(r))} · "
                                f"{_share_label}"
                            )

                            _recipe_servings = float(
                                r.get("recipe_servings") or 1.0
                            )
                            _recipe_servings = max(_recipe_servings, 1.0)
                            _per_kcal = float(r.get("calories") or 0) / _recipe_servings
                            _per_pro = float(r.get("protein") or 0) / _recipe_servings
                            _per_carbs = float(r.get("carbs") or 0) / _recipe_servings
                            _per_fat = float(r.get("fat") or 0) / _recipe_servings

                            st.caption(
                                f"🍽️ {_recipe_servings:g} {t['num_portions'].lower()}"
                            )

                            _m1, _m2 = st.columns(2)
                            _m1.metric(
                                f"{t['per_serving']} · Kcal",
                                int(round(_per_kcal)),
                            )
                            _m2.metric(
                                f"{t['per_serving']} · Protein",
                                f"{_per_pro:.1f} g",
                            )

                            st.caption(
                                f"{t['per_serving']}: "
                                f"Carbs {_per_carbs:.1f} g · Fat {_per_fat:.1f} g"
                            )
                            st.caption(
                                f"{t['total_recipe']}: "
                                f"{int(r.get('calories') or 0)} kcal"
                            )

                            if r.get("notes"):
                                st.caption(str(r.get("notes")))

                            render_recipe_ingredients_dropdown(
                                r,
                                f"my_recipe_{r.get('id')}",
                            )

                            # ------------------------------------------
                            # Colazione standard personale.
                            # Only personal breakfast recipes can be
                            # assigned. Work is hidden when Office mode
                            # is disabled.
                            # ------------------------------------------
                            if str(r.get("meal_type")) == "Colazione":
                                _default_breakfast_ids = (
                                    get_default_breakfast_recipe_ids()
                                )
                                _recipe_id_str = str(r.get("id"))

                                _default_i18n = {
                                    "Italiano": {
                                        "home_set": "🏠 Usa come Colazione Casa standard",
                                        "home_active": "✅ Colazione Casa standard",
                                        "work_set": "💼 Usa come Colazione Lavoro standard",
                                        "work_active": "✅ Colazione Lavoro standard",
                                        "remove": "Rimuovi standard",
                                        "saved": "Colazione standard aggiornata.",
                                    },
                                    "English": {
                                        "home_set": "🏠 Set as default Home breakfast",
                                        "home_active": "✅ Default Home breakfast",
                                        "work_set": "💼 Set as default Work breakfast",
                                        "work_active": "✅ Default Work breakfast",
                                        "remove": "Remove default",
                                        "saved": "Default breakfast updated.",
                                    },
                                    "Nederlands": {
                                        "home_set": "🏠 Instellen als standaardontbijt thuis",
                                        "home_active": "✅ Standaardontbijt thuis",
                                        "work_set": "💼 Instellen als standaardontbijt werk",
                                        "work_active": "✅ Standaardontbijt werk",
                                        "remove": "Standaard verwijderen",
                                        "saved": "Standaardontbijt bijgewerkt.",
                                    },
                                    "Français": {
                                        "home_set": "🏠 Définir comme petit-déjeuner maison",
                                        "home_active": "✅ Petit-déjeuner maison par défaut",
                                        "work_set": "💼 Définir comme petit-déjeuner travail",
                                        "work_active": "✅ Petit-déjeuner travail par défaut",
                                        "remove": "Retirer le défaut",
                                        "saved": "Petit-déjeuner par défaut mis à jour.",
                                    },
                                }.get(current_lang, {})

                                _eligible_default_categories = ["Casa"]
                                if user_office_lunch_enabled:
                                    _eligible_default_categories.append(
                                        "Lavoro"
                                    )

                                for _default_category in (
                                    _eligible_default_categories
                                ):
                                    _is_default = (
                                        _default_breakfast_ids.get(
                                            _default_category
                                        )
                                        == _recipe_id_str
                                    )

                                    if _default_category == "Casa":
                                        _set_label = _default_i18n.get(
                                            "home_active"
                                            if _is_default
                                            else "home_set",
                                            "🏠 Colazione Casa",
                                        )
                                    else:
                                        _set_label = _default_i18n.get(
                                            "work_active"
                                            if _is_default
                                            else "work_set",
                                            "💼 Colazione Lavoro",
                                        )

                                    _action_label = (
                                        f"{_set_label} · "
                                        f"{_default_i18n.get('remove', 'Rimuovi')}"
                                        if _is_default
                                        else _set_label
                                    )

                                    if st.button(
                                        _action_label,
                                        key=(
                                            "default_breakfast_recipe_"
                                            f"{r.get('id')}_"
                                            f"{_default_category}"
                                        ),
                                        use_container_width=True,
                                    ):
                                        set_default_breakfast_recipe(
                                            _default_category,
                                            None
                                            if _is_default
                                            else r.get("id"),
                                        )
                                        st.success(
                                            _default_i18n.get(
                                                "saved",
                                                "Colazione standard aggiornata.",
                                            )
                                        )
                                        st.rerun()

            # Gestione condivisione delle ricette già esistenti.
            st.markdown(t["sharing_manage"])
            recipe_options = {
                r["_recipe_label"]: r for r in my_recipes
            }
            selected_recipe_label = st.selectbox(
                t["sharing_select"],
                list(recipe_options.keys()),
                key="recipe_share_manage_select",
            )
            selected_recipe_row = recipe_options[selected_recipe_label]

            new_share_state = st.checkbox(
                t["share_recipe"],
                value=bool(selected_recipe_row.get("is_shared")),
                key=f"recipe_share_manage_{selected_recipe_row['id']}",
                help=t["share_help"],
            )

            if st.button(
                t["sharing_save"],
                key="recipe_share_manage_save",
                use_container_width=True,
            ):
                try:
                    set_recipe_sharing_via_api(
                        selected_recipe_row["id"],
                        bool(new_share_state),
                        st.session_state.get("auth_access_token"),
                    )
                    queue_ui_sound(
                        "recipe_shared"
                        if bool(new_share_state)
                        else "recipe_unshared"
                    )
                    st.success(t["sharing_updated"])
                    st.rerun()
                except Exception as exc:
                    st.error(str(exc))
        else:
            st.info(t["no_my_recipes"])

    # ------------------------------------------------------------------
    # 🌍 RICETTE CONDIVISE / PUBBLICHE
    # ------------------------------------------------------------------
    with st.expander(_rcu["shared"], expanded=False):

        try:
            shared_recipe_rows = fetch_shared_recipes_from_api(
                st.session_state.get("auth_access_token")
            )
        except Exception as exc:
            shared_recipe_rows = []
            print(f"Errore caricamento ricette condivise: {exc}")

        shared_recipes = []
        _seen_shared = set()
        for r in shared_recipe_rows:
            label = str(r.get("name") or "Ricetta").strip()

            # user_id + nome evita che ricette omonime di due persone
            # vengano fuse tra loro.
            key = (str(r.get("user_id")), label.casefold())
            if key in _seen_shared:
                continue

            _seen_shared.add(key)
            r["_recipe_label"] = label
            shared_recipes.append(r)

        if shared_recipes:
            for _idx in range(0, len(shared_recipes), 2):
                _card_cols = st.columns(2)
                for _offset, _col in enumerate(_card_cols):
                    _recipe_idx = _idx + _offset
                    if _recipe_idx >= len(shared_recipes):
                        continue

                    r = shared_recipes[_recipe_idx]
                    with _col:
                        with st.container(border=True):
                            _recipe_image = recipe_image_url(r)
                            render_recipe_card_image(
                                _recipe_image,
                                r.get("_recipe_label") or r.get("name") or "Recipe",
                            )

                            st.markdown(f"### {html.escape(str(r['_recipe_label']))}")
                            st.caption(
                                f"{tr_meal_type(r.get('meal_type'))} · "
                                f"{tr_category(infer_meal_category(r))} · "
                                f"🌍 {t['recipe_shared_badge']}"
                            )

                            _recipe_servings = float(
                                r.get("recipe_servings") or 1.0
                            )
                            _recipe_servings = max(_recipe_servings, 1.0)
                            _per_kcal = float(r.get("calories") or 0) / _recipe_servings
                            _per_pro = float(r.get("protein") or 0) / _recipe_servings
                            _per_carbs = float(r.get("carbs") or 0) / _recipe_servings
                            _per_fat = float(r.get("fat") or 0) / _recipe_servings

                            st.caption(
                                f"🍽️ {_recipe_servings:g} {t['num_portions'].lower()}"
                            )

                            _m1, _m2 = st.columns(2)
                            _m1.metric(
                                f"{t['per_serving']} · Kcal",
                                int(round(_per_kcal)),
                            )
                            _m2.metric(
                                f"{t['per_serving']} · Protein",
                                f"{_per_pro:.1f} g",
                            )

                            st.caption(
                                f"{t['per_serving']}: "
                                f"Carbs {_per_carbs:.1f} g · Fat {_per_fat:.1f} g"
                            )
                            st.caption(
                                f"{t['total_recipe']}: "
                                f"{int(r.get('calories') or 0)} kcal"
                            )

                            if r.get("notes"):
                                st.caption(str(r.get("notes")))

                            render_recipe_ingredients_dropdown(
                                r,
                                f"shared_recipe_{r.get('id')}",
                            )
        else:
            st.info(t["no_shared_recipes"])

# ==============================================================================
# 13. PAGE 5: ACTIVITY & STEPS LOGGING
# ==============================================================================
elif selected_page == t["t5"]:
    render_page_title_card(t["register_activity"])
    act_date = st.date_input(t["act_date"], value=date.today())
    
    try:
        existing_log = load_daily_log_cached(
            user_id,
            str(act_date),
            st.session_state.get("auth_access_token"),
        )
        day_steps = (
            existing_log[0].get("steps", 0)
            if existing_log and existing_log[0].get("steps")
            else 0
        )
        day_activities = load_daily_activities_cached(
            user_id,
            str(act_date),
            st.session_state.get("auth_access_token"),
        )
    except Exception:
        day_steps = 0
        day_activities = []

    # Riepilogo calorie attività per la giornata selezionata
    def _activity_kcal(name):
        return sum(
            int(a.get("burned_calories") or 0)
            for a in day_activities
            if str(a.get("activity_name") or "").strip().casefold() == name.casefold()
        )

    steps_kcal = _activity_kcal("Passi (Stima)")
    padel_kcal = _activity_kcal("Padel")
    bike_kcal = sum(
        int(a.get("burned_calories") or 0)
        for a in day_activities
        if str(a.get("activity_name") or "").strip().casefold() in {"bici", "bici elettrica"}
    )
    total_extra_kcal = sum(int(a.get("burned_calories") or 0) for a in day_activities)

    # Verifichiamo se ci sono attività strutturate oltre ai passi
    has_structured_activity = any(a.get("activity_name") not in ["Passi (Stima)"] for a in day_activities)

    # Status Movimento intelligente: se c'è un'attività strutturata, lo status riflette l'allenamento!
    move_bg, move_border = "#FFFFFF", "#FF8B8B"
    if has_structured_activity:
        move_msg = ux["activity_logged_note"]
        status_display_text = ux["activity_logged"]
    elif day_steps >= 10000:
        move_msg = t["status_very_active"]
        status_display_text = f"{day_steps} {ux['step_word']}"
    elif day_steps >= 5000:
        move_msg = t["status_good"]
        status_display_text = f"{day_steps} {ux['step_word']}"
    else:
        move_msg = t["status_lazy"]
        status_display_text = f"{day_steps} {ux['step_word']}"

    # Tile con lo stesso design della Panoramica
    if is_zero_mode():
        st.markdown("""
            <style>
                .custom-card {
                    background:
                        radial-gradient(circle at 96% 4%, rgba(225,6,0,.18), transparent 36%),
                        linear-gradient(145deg,#151515,#090909);
                    border:1.5px solid #C91A16;
                    border-radius:18px;
                    padding:17px;
                    height:100%;
                    box-shadow:0 9px 24px rgba(0,0,0,.30);
                }
                .custom-card-title {font-size:.95rem;font-weight:700;color:#D9D9D9;margin-bottom:5px;}
                .custom-card-value {font-size:1.8rem;font-weight:800;color:#FFFFFF;margin-bottom:8px;}
                .custom-card-caption {font-size:.82rem;color:#BDBDBD;line-height:1.38;}
            </style>
        """, unsafe_allow_html=True)
    else:
        st.markdown("""
            <style>
                .custom-card {
                    background-color:#FFF5F5;
                    border:1.5px solid #FF8B8B;
                    border-radius:16px;
                    padding:16px;
                    height:100%;
                    box-shadow:0 2px 6px rgba(255,139,139,.08);
                }
                .custom-card-title {font-size:.95rem;font-weight:600;color:#1A2942;margin-bottom:4px;}
                .custom-card-value {font-size:1.8rem;font-weight:700;color:#1A2942;margin-bottom:8px;}
                .custom-card-caption {font-size:.82rem;color:#555;line-height:1.35;}
            </style>
        """, unsafe_allow_html=True)

    ac1, ac2 = st.columns(2)
    with ac1:
        st.markdown(
            f'<div class="custom-card"><div class="custom-card-title">{t["status_move_title"]}</div>'
            f'<div class="custom-card-value">{status_display_text}</div>'
            f'<div class="custom-card-caption">{move_msg}</div></div>',
            unsafe_allow_html=True,
        )
    with ac2:
        extra_caption = (
            ux["extra_burned_note"]
            if total_extra_kcal > 0 else ux["no_extra"]
        )
        st.markdown(
            f'<div class="custom-card"><div class="custom-card-title">{ux["extra_burned"]}</div>'
            f'<div class="custom-card-value">{total_extra_kcal} kcal</div>'
            f'<div class="custom-card-caption">{extra_caption}</div></div>',
            unsafe_allow_html=True,
        )

    st.markdown("<br>", unsafe_allow_html=True)
    other_kcal = max(0, total_extra_kcal - steps_kcal - padel_kcal - bike_kcal)
    kc1, kc2, kc3 = st.columns(3)
    with kc1:
        st.markdown(f'<div class="custom-card"><div class="custom-card-title">{ux["steps"]}</div><div class="custom-card-value">{steps_kcal} kcal</div><div class="custom-card-caption">{ux["steps_note"]}</div></div>', unsafe_allow_html=True)
    with kc2:
        st.markdown(f'<div class="custom-card"><div class="custom-card-title">🎾 Padel</div><div class="custom-card-value">{padel_kcal} kcal</div><div class="custom-card-caption">{ux["padel_note"]}</div></div>', unsafe_allow_html=True)
    with kc3:
        bike_caption = f"{ux['bike_note']} {ux['other_activities']}: {other_kcal} kcal." if other_kcal > 0 else ux["bike_note"]
        st.markdown(f'<div class="custom-card"><div class="custom-card-title">🚲 {ux["bike"]}</div><div class="custom-card-value">{bike_kcal} kcal</div><div class="custom-card-caption">{bike_caption}</div></div>', unsafe_allow_html=True)

    st.markdown("<br>", unsafe_allow_html=True)

    # 3 Colonne: Passi, Bici (Normale ed Elettrica), Altro
    col_a1, col_a2, col_a3 = st.columns(3)
    
    with col_a1:
        with st.container(border=True):
            st.markdown(f"### {t['steps_title']}")
            new_steps = st.number_input(ux["total_steps"], value=int(day_steps), min_value=0, step=500)
            if st.button(t["update_steps"], use_container_width=True):
                try:
                    update_daily_log_via_api(
                        act_date,
                        {"steps": int(new_steps)},
                        st.session_state.get("auth_access_token"),
                    )
                    
                    # Sottraiamo dai passi totali quelli già attribuiti
                    # ad attività strutturate (per esempio una corsa GPX).
                    step_info = recalculate_step_calories_for_day(
                        user_id,
                        act_date,
                        total_steps=int(new_steps),
                    )
                    estim_cals = step_info["estimated_kcal"]

                    refresh_daily_logs(act_date)
                    
                    queue_ui_sound("steps_saved")
                    st.toast(ux["steps_updated_toast"].format(kcal=estim_cals), icon="👣")
                    if step_info["activity_steps"] > 0:
                        st.success(
                            f"✅ {t['steps_updated']} "
                            f"({step_info['eligible_steps']} passi calorici su "
                            f"{step_info['total_steps']}; "
                            f"{step_info['activity_steps']} già inclusi nelle attività; "
                            f"{estim_cals} kcal stimate)"
                        )
                    else:
                        st.success(
                            f"✅ {t['steps_updated']} ({estim_cals} kcal stimate)"
                        )
                    st.rerun()
                except Exception as e:
                    err_text = str(e)
                    if "daily_logs_date_key" in err_text or "23505" in err_text:
                        st.error(
                            "Il database ha ancora un vincolo UNIQUE sulla sola data. "
                            "Per usare più utenti devi eseguire la migrazione SQL "
                            "daily_logs_user_date_fix.sql che trovi insieme al codice."
                        )
                    else:
                        st.error(f"Errore nel salvataggio dei passi: {e}")

    with col_a2:
        with st.container(border=True):
            st.markdown(f"### {ux['bike_and_ebike']}")
            bike_type = st.radio(t["bike_type"], [t["normal_bike"], t["ebike"]], horizontal=True, key=f"bike_type_{act_date}")
            bike_min = st.number_input(ux["bike_minutes"], value=0, min_value=0, step=5, key=f"bike_min_{act_date}")
            
            if st.button(ux["add_bike"], use_container_width=True):
                if bike_min > 0:
                    if bike_type == t["ebike"]:
                        estim_cals = int(bike_min * 4)  # Stima E-bike: ~4 kcal/min
                        act_label = "Bici Elettrica"
                    else:
                        estim_cals = int(bike_min * 8)  # Stima Bici normale: ~8 kcal/min
                        act_label = "Bici"
                        
                    create_activity_via_api(
                        {
                            "date": str(act_date),
                            "activity_name": act_label,
                            "burned_calories": estim_cals,
                        },
                        st.session_state.get("auth_access_token"),
                    )
                    
                    # Bici/E-Bike è compatibile con i passi:
                    # NON azzeriamo le kcal attribuite ai passi.

                    refresh_daily_logs(act_date)
                    
                    queue_ui_sound("activity_saved")
                    st.toast(ux["bike_added"].format(minutes=bike_min, activity=translate_activity_display(act_label, current_lang), kcal=estim_cals), icon="🚲")
                    st.success(ux["bike_added"].format(minutes=bike_min, activity=translate_activity_display(act_label, current_lang), kcal=estim_cals))
                    st.rerun()
                else:
                    st.warning(ux["enter_one_minute"])

    with col_a3:
        with st.container(border=True):
            st.markdown(f"### {t['other_act']}")
            with st.form("activity_form", clear_on_submit=True):
                extra_act = st.selectbox(
                    t["activity_label"],
                    ["Padel", "Palestra", "Nuoto", "Altro"],
                    format_func=lambda x: {
                        "Padel": "Padel",
                        "Palestra": ux["activity_gym"],
                        "Nuoto": ux["activity_swim"],
                        "Altro": ux["activity_other"],
                    }.get(x, x),
                )
                extra_cals = st.number_input(ux["burned_kcal_field"], value=0, min_value=0, step=50)
                
                submitted_act = st.form_submit_button(
                    t["add_act_btn"],
                    use_container_width=True,
                    key="activity_add_submit",
                )
                if submitted_act:
                    # Inseriamo l'attività
                    create_activity_via_api(
                        {
                            "date": str(act_date),
                            "activity_name": extra_act,
                            "burned_calories": int(extra_cals),
                        },
                        st.session_state.get("auth_access_token"),
                    )
                    
                    # Per attività manuali senza un numero preciso di passi
                    # manteniamo il comportamento conservativo anti-doppio conteggio.
                    if _is_step_conflicting_activity(extra_act):
                        recalculate_step_calories_for_day(
                            user_id,
                            act_date,
                            total_steps=int(day_steps),
                        )

                    refresh_daily_logs(act_date)
                    
                    # Usiamo st.success e st.toast per garantire il feedback visivo immediato
                    queue_ui_sound("activity_saved")
                    st.toast(ux["activity_saved"].format(activity={"Palestra":ux["activity_gym"],"Nuoto":ux["activity_swim"],"Altro":ux["activity_other"]}.get(extra_act, extra_act), kcal=extra_cals), icon="🎯")
                    st.success(ux["activity_saved"].format(activity={"Palestra":ux["activity_gym"],"Nuoto":ux["activity_swim"],"Altro":ux["activity_other"]}.get(extra_act, extra_act), kcal=extra_cals))
                    st.rerun()


    st.markdown("<br>", unsafe_allow_html=True)
    with st.container(border=True):
        st.markdown("### 🗺️ Importa attività GPX")
        st.caption(
            "Carica una traccia .gpx da Zepp/Amazfit, Garmin o altre app. "
            "Il file viene analizzato localmente da SanoSync."
        )

        gpx_flash_message = st.session_state.pop(
            "gpx_last_action_message",
            None,
        )
        if gpx_flash_message:
            st.success(gpx_flash_message)

        gpx_upload_generation = int(
            st.session_state.get("gpx_upload_generation", 0)
        )
        gpx_file = st.file_uploader(
            "File GPX",
            type=["gpx"],
            key=f"gpx_uploader_{act_date}_{gpx_upload_generation}",
        )

        if gpx_file is not None:
            try:
                gpx_data = parse_gpx_activity(
                    gpx_file.getvalue(),
                    filename=gpx_file.name,
                )
                gpx_date = gpx_data.get("date") or act_date

                if gpx_date != act_date:
                    st.info(
                        f"Il GPX risulta del {gpx_date}. "
                        "Verrà salvato in quella data."
                    )

                gm1, gm2, gm3, gm4 = st.columns(4)
                gm1.metric("Distanza", f"{gpx_data['distance_km']:.2f} km")
                gm2.metric(
                    "Durata",
                    _format_duration(gpx_data["duration_seconds"]),
                )
                gm3.metric(
                    "Passi attività",
                    f"{gpx_data['estimated_steps']:,}".replace(",", "."),
                )
                gm4.metric(
                    "FC media",
                    (
                        f"{gpx_data['avg_hr']:.0f} bpm"
                        if gpx_data["avg_hr"] is not None else "—"
                    ),
                )

                if gpx_data.get("avg_step_cadence") is not None:
                    cadence_text = (
                        f"Cadenza media: "
                        f"{gpx_data['avg_step_cadence']:.0f} passi/min."
                    )
                    if gpx_data.get("cadence_factor") == 2.0:
                        cadence_text += (
                            " Zepp/Amazfit sembra esportarla per singolo lato; "
                            "SanoSync l'ha convertita in passi/min."
                        )
                    st.caption(cadence_text)

                c1, c2 = st.columns(2)
                with c1:
                    gpx_activity_type = st.selectbox(
                        "Tipo attività",
                        ["Corsa", "Camminata", "Trekking", "Bici", "Altro"],
                        key=f"gpx_type_{gpx_data['source_ref'][:12]}",
                    )

                nearest_weight, nearest_weight_date = nearest_weight_for_date(
                    user_id, gpx_date
                )
                with c2:
                    gpx_weight = st.number_input(
                        "Peso per la stima kcal (kg)",
                        min_value=30.0,
                        max_value=250.0,
                        value=round(float(nearest_weight or 70.0), 1),
                        step=0.1,
                        key=f"gpx_weight_{gpx_data['source_ref'][:12]}",
                    )

                if nearest_weight is not None:
                    st.caption(
                        f"Peso dal log più vicino: {nearest_weight:.1f} kg "
                        f"({nearest_weight_date})."
                    )

                gpx_kcal = estimate_gpx_kcal(
                    gpx_activity_type,
                    gpx_data["distance_km"],
                    gpx_weight,
                )

                st.markdown(
                    f"**Anteprima:** {gpx_activity_type} · "
                    f"{gpx_data['distance_km']:.2f} km · "
                    f"{_format_duration(gpx_data['duration_seconds'])} · "
                    f"**{gpx_kcal} kcal**"
                )

                with st.expander("🗺️ Anteprima percorso", expanded=False):
                    render_gpx_route_map(gpx_data["route_points"], height=360)

                step_based = gpx_activity_type in {
                    "Corsa", "Camminata", "Trekking"
                }
                if step_based and gpx_data["estimated_steps"] > 0:
                    preview_activities = list(day_activities) + [{
                        "activity_name": gpx_activity_type,
                        "activity_steps": gpx_data["estimated_steps"],
                    }]
                    preview_offset = calculate_step_calorie_offset(
                        day_steps, preview_activities
                    )
                    st.info(
                        f"Offset passi: {day_steps} totali − "
                        f"{preview_offset['activity_steps']} già nelle attività "
                        f"= {preview_offset['eligible_steps']} passi calorici "
                        f"({preview_offset['estimated_kcal']} kcal)."
                    )
                elif step_based:
                    st.warning(
                        "Questo GPX non contiene una cadenza utilizzabile: "
                        "posso importare kcal/distanza, ma non l'offset passi."
                    )

                gpx_day_activities = (
                    day_activities
                    if gpx_date == act_date
                    else fetch_daily_activities_from_api(
                        user_id,
                        str(gpx_date),
                        st.session_state.get("auth_access_token"),
                    )
                )
                existing_activity = next(
                    (
                        a for a in gpx_day_activities
                        if str(a.get("source_ref") or "")
                        == gpx_data["source_ref"]
                    ),
                    None,
                )

                existing_has_map = bool(
                    existing_activity
                    and existing_activity.get("route_points")
                )
                existing_has_charts = bool(
                    existing_activity
                    and existing_activity.get("sensor_series")
                )

                if (
                    existing_activity
                    and existing_has_map
                    and existing_has_charts
                ):
                    st.warning("Questo GPX risulta già importato.")
                elif existing_activity and st.button(
                    "📈 Aggiorna mappa e grafici del GPX già importato",
                    key=f"backfill_gpx_details_{gpx_data['source_ref'][:16]}",
                    use_container_width=True,
                ):
                    update_activity_via_api(
                        existing_activity["id"],
                        {
                            "route_points": gpx_data["route_points"],
                            "sensor_series": gpx_data["sensor_series"],
                            "distance_km": float(gpx_data["distance_km"]),
                            "duration_seconds": int(gpx_data["duration_seconds"]),
                            "avg_hr": (
                                float(gpx_data["avg_hr"])
                                if gpx_data["avg_hr"] is not None else None
                            ),
                            "avg_cadence": (
                                float(gpx_data["avg_step_cadence"])
                                if gpx_data["avg_step_cadence"] is not None
                                else None
                            ),
                        },
                        st.session_state.get("auth_access_token"),
                    )
                    st.session_state["gpx_upload_generation"] = (
                        gpx_upload_generation + 1
                    )
                    st.session_state["gpx_last_action_message"] = (
                        "✅ Mappa e grafici aggiunti all'attività GPX."
                    )
                    st.rerun()
                elif st.button(
                    "📥 Importa GPX in Attività",
                    key=f"import_gpx_{gpx_data['source_ref'][:16]}",
                    type="primary",
                    use_container_width=True,
                ):
                    activity_steps = (
                        gpx_data["estimated_steps"] if step_based else 0
                    )
                    create_activity_via_api(
                        {
                            "date": str(gpx_date),
                            "activity_name": (
                                f"{gpx_activity_type} GPX · "
                                f"{gpx_data['distance_km']:.2f} km"
                            ),
                            "burned_calories": int(gpx_kcal),
                            "activity_steps": int(activity_steps),
                            "distance_km": float(gpx_data["distance_km"]),
                            "duration_seconds": int(
                                gpx_data["duration_seconds"]
                            ),
                            "source": "gpx",
                            "source_file_name": gpx_data["filename"],
                            "source_ref": gpx_data["source_ref"],
                            "avg_hr": (
                                float(gpx_data["avg_hr"])
                                if gpx_data["avg_hr"] is not None else None
                            ),
                            "avg_cadence": (
                                float(gpx_data["avg_step_cadence"])
                                if gpx_data["avg_step_cadence"] is not None
                                else None
                            ),
                            "route_points": gpx_data["route_points"],
                        },
                        st.session_state.get("auth_access_token"),
                    )

                    daily_log = fetch_daily_log_from_api(
                        user_id,
                        str(gpx_date),
                        st.session_state.get("auth_access_token"),
                    )
                    offset = recalculate_step_calories_for_day(
                        user_id,
                        gpx_date,
                        total_steps=int((daily_log or {}).get("steps") or 0),
                    )

                    refresh_daily_logs(gpx_date)
                    queue_ui_sound("activity_saved")
                    st.session_state["gpx_upload_generation"] = (
                        gpx_upload_generation + 1
                    )
                    st.session_state["gpx_last_action_message"] = (
                        f"✅ GPX importato: {gpx_kcal} kcal · "
                        f"{activity_steps} passi attività · "
                        f"{offset['eligible_steps']} passi calorici residui."
                    )
                    st.rerun()

            except Exception as exc:
                st.error(f"Impossibile leggere/importare il GPX: {exc}")



    st.markdown("<br>", unsafe_allow_html=True)
    with st.container(border=True):
        st.markdown("### 📚 Registro attività GPX")
        st.caption(
            "Le ultime attività importate da file GPX. "
            "Selezionane una per vedere dettagli e percorso."
        )

        try:
            gpx_log_rows = fetch_gpx_activity_log(user_id, limit=50)
        except Exception as exc:
            gpx_log_rows = []
            st.error(f"Impossibile caricare il registro GPX: {exc}")

        if not gpx_log_rows:
            st.info("Non ci sono ancora attività GPX nel registro.")
        else:
            log_table_rows = []
            for row in gpx_log_rows:
                log_table_rows.append(
                    {
                        "Data": row.get("date"),
                        "Attività": row.get("activity_name") or "GPX",
                        "Distanza km": row.get("distance_km"),
                        "Durata": _format_duration(
                            row.get("duration_seconds") or 0
                        ),
                        "Passi attività": row.get("activity_steps") or 0,
                        "Kcal": row.get("burned_calories") or 0,
                        "FC media": row.get("avg_hr"),
                    }
                )

            st.dataframe(
                pd.DataFrame(log_table_rows),
                use_container_width=True,
                hide_index=True,
            )

            def _gpx_log_label(row):
                date_label = str(row.get("date") or "—")
                activity_label = str(row.get("activity_name") or "Attività GPX")
                kcal_label = int(row.get("burned_calories") or 0)
                return f"{date_label} · {activity_label} · {kcal_label} kcal"

            selected_index = st.selectbox(
                "Apri attività",
                options=list(range(len(gpx_log_rows))),
                format_func=lambda idx: _gpx_log_label(gpx_log_rows[idx]),
                key="gpx_activity_log_selected",
            )
            selected_activity = gpx_log_rows[selected_index]

            selected_activity_id = selected_activity.get("id")
            selected_activity_date = selected_activity.get("date")

            with st.expander("📊 Informazioni attività", expanded=False):
                lm1, lm2, lm3, lm4 = st.columns(4)
                distance_value = selected_activity.get("distance_km")
                lm1.metric(
                    "Distanza",
                    (
                        f"{float(distance_value):.2f} km"
                        if distance_value is not None else "—"
                    ),
                )
                lm2.metric(
                    "Durata",
                    _format_duration(
                        selected_activity.get("duration_seconds") or 0
                    ),
                )
                lm3.metric(
                    "Passi attività",
                    f"{int(selected_activity.get('activity_steps') or 0):,}".replace(
                        ",", "."
                    ),
                )
                lm4.metric(
                    "Kcal",
                    int(selected_activity.get("burned_calories") or 0),
                )

                detail_bits = []
                if selected_activity.get("avg_hr") is not None:
                    detail_bits.append(
                        f"FC media "
                        f"{float(selected_activity['avg_hr']):.0f} bpm"
                    )
                if selected_activity.get("avg_cadence") is not None:
                    detail_bits.append(
                        f"Cadenza "
                        f"{float(selected_activity['avg_cadence']):.0f} "
                        f"passi/min"
                    )
                if selected_activity.get("source_file_name"):
                    detail_bits.append(
                        f"File: {selected_activity['source_file_name']}"
                    )
                if detail_bits:
                    st.caption(" · ".join(detail_bits))

                sensor_series = selected_activity.get("sensor_series") or []
                sensor_rows = []
                for sample in sensor_series:
                    if not isinstance(sample, dict):
                        continue
                    try:
                        minute_value = float(sample.get("minute"))
                    except Exception:
                        continue
                    sensor_rows.append(
                        {
                            "Minuti": minute_value,
                            "Frequenza cardiaca": sample.get("hr"),
                            "Cadenza": sample.get("cadence"),
                        }
                    )

                if sensor_rows:
                    sensor_df = (
                        pd.DataFrame(sensor_rows)
                        .sort_values("Minuti")
                    )
                    hr_df = sensor_df.dropna(
                        subset=["Frequenza cardiaca"]
                    )
                    cadence_df = sensor_df.dropna(
                        subset=["Cadenza"]
                    )

                    if not hr_df.empty or not cadence_df.empty:
                        st.markdown("#### Andamento durante l'attività")
                        chart_tabs = st.tabs(
                            [
                                "❤️ Frequenza cardiaca",
                                "👟 Cadenza passi",
                            ]
                        )

                        with chart_tabs[0]:
                            if not hr_df.empty:
                                st.line_chart(
                                    hr_df[
                                        ["Minuti", "Frequenza cardiaca"]
                                    ].set_index("Minuti"),
                                    use_container_width=True,
                                    height=280,
                                    x_label="Minuti",
                                    y_label="bpm",
                                )
                            else:
                                st.info(
                                    "Il GPX non contiene dati di frequenza "
                                    "cardiaca utilizzabili."
                                )

                        with chart_tabs[1]:
                            if not cadence_df.empty:
                                st.line_chart(
                                    cadence_df[
                                        ["Minuti", "Cadenza"]
                                    ].set_index("Minuti"),
                                    use_container_width=True,
                                    height=280,
                                    x_label="Minuti",
                                    y_label="passi/min",
                                )
                            else:
                                st.info(
                                    "Il GPX non contiene dati di cadenza "
                                    "utilizzabili."
                                )
                else:
                    st.info(
                        "Grafici non ancora disponibili per questa attività. "
                        "Ricarica lo stesso GPX nell'importatore e usa "
                        "“Aggiorna mappa e grafici del GPX già importato”."
                    )

            route = _route_points_from_activity(selected_activity)
            with st.expander("🗺️ Mappa percorso", expanded=False):
                if route:
                    render_gpx_route_map(route, height=460)
                else:
                    st.info(
                        "Questa attività è stata importata prima del supporto "
                        "mappe. Ricarica lo stesso GPX nell'importatore qui "
                        "sopra e usa “Aggiorna mappa e grafici del GPX già importato”."
                    )

            with st.expander("🗑️ Elimina attività", expanded=False):
                st.warning(
                    "L'eliminazione rimuove questa attività dal registro e "
                    "ricalcola automaticamente le kcal dei passi del giorno."
                )
                confirm_delete = st.checkbox(
                    "Confermo di voler eliminare questa attività",
                    key=f"confirm_delete_gpx_{selected_activity_id}",
                )
                if st.button(
                    "Elimina definitivamente",
                    key=f"delete_gpx_{selected_activity_id}",
                    type="primary",
                    disabled=not confirm_delete,
                    use_container_width=True,
                ):
                    delete_activity_via_api(
                        selected_activity_id,
                        st.session_state.get("auth_access_token"),
                    )

                    # Recalculate the step-calorie offset because removing a
                    # GPX activity frees its activity_steps again.
                    if selected_activity_date:
                        deleted_day_log = fetch_daily_log_from_api(
                            user_id,
                            str(selected_activity_date),
                            st.session_state.get("auth_access_token"),
                        )
                        recalculate_step_calories_for_day(
                            user_id,
                            selected_activity_date,
                            total_steps=int(
                                (deleted_day_log or {}).get("steps") or 0
                            ),
                        )
                        try:
                            deleted_date_obj = date.fromisoformat(
                                str(selected_activity_date)
                            )
                            refresh_daily_logs(deleted_date_obj)
                        except Exception:
                            pass

                    st.session_state.pop(
                        f"confirm_delete_gpx_{selected_activity_id}",
                        None,
                    )
                    st.session_state["gpx_last_action_message"] = (
                        "🗑️ Attività GPX eliminata."
                    )
                    st.rerun()



# ============================================================
# ZERO MODE — final component-level visual fixes
# ============================================================
def _zero_mode_component_visual_fixes():
    # Use the same source of truth as the rest of the app.
    if not is_zero_mode():
        return

    st.markdown(
        """
        <style>
        /* =========================================================
           ZERO — DATE FIELD
           ========================================================= */
        [data-testid="stDateInput"] input,
        [data-testid="stDateInput"] [data-baseweb="input"] input,
        [data-testid="stDateInput"] [data-baseweb="input"],
        [data-testid="stDateInput"] [data-baseweb="base-input"] {
            background:#151515 !important;
            background-color:#151515 !important;
            color:#FFFFFF !important;
            -webkit-text-fill-color:#FFFFFF !important;
            border-color:#6E6E6E !important;
            caret-color:#FFFFFF !important;
        }

        [data-testid="stDateInput"] input::selection {
            background:#E32020 !important;
            color:#FFFFFF !important;
        }

        /* =========================================================
           ZERO — CALENDAR POPOVER
           Streamlit's date picker is a BaseWeb calendar rendered in
           a portal outside the main app container. Keep it light,
           but force readable dark text explicitly.
           ========================================================= */
        div[data-baseweb="popover"] div[data-baseweb="calendar"],
        div[data-baseweb="calendar"],
        div[data-baseweb="calendar"] > div {
            background:#F7F7F8 !important;
            background-color:#F7F7F8 !important;
        }

        div[data-baseweb="calendar"],
        div[data-baseweb="calendar"] div,
        div[data-baseweb="calendar"] span,
        div[data-baseweb="calendar"] button,
        div[data-baseweb="calendar"] select,
        div[data-baseweb="calendar"] option {
            color:#252832 !important;
            -webkit-text-fill-color:#252832 !important;
        }

        div[data-baseweb="calendar"] button:disabled,
        div[data-baseweb="calendar"] [aria-disabled="true"],
        div[data-baseweb="calendar"] [aria-disabled="true"] * {
            color:#A7A9AF !important;
            -webkit-text-fill-color:#A7A9AF !important;
            opacity:1 !important;
        }

        div[data-baseweb="calendar"] [aria-selected="true"],
        div[data-baseweb="calendar"] [aria-selected="true"] *,
        div[data-baseweb="calendar"] button[aria-selected="true"] {
            background:#FF4B55 !important;
            background-color:#FF4B55 !important;
            color:#FFFFFF !important;
            -webkit-text-fill-color:#FFFFFF !important;
            border-radius:10px !important;
        }

        div[data-baseweb="calendar"] svg,
        div[data-baseweb="calendar"] path {
            color:#252832 !important;
            fill:#252832 !important;
        }

        /* =========================================================
           ZERO — PROFILE / LANGUAGE POPOVER
           Streamlit popovers can be rendered either with stPopover
           wrappers or a BaseWeb popover portal, so target both.
           ========================================================= */

        /* Outer panel */
        div[data-testid="stPopoverBody"],
        div[data-testid="stPopoverBody"] > div,
        div[data-baseweb="popover"]:has([data-testid="stSelectbox"]) > div {
            background:
                radial-gradient(circle at 100% 0%, rgba(150,12,12,.24), transparent 40%),
                linear-gradient(145deg,#111111,#070707) !important;
            background-color:#0B0B0B !important;
            border:1px solid #B91C1C !important;
            border-radius:20px !important;
            box-shadow:0 18px 42px rgba(0,0,0,.55) !important;
        }

        /* Typography inside panel */
        div[data-testid="stPopoverBody"] *,
        div[data-baseweb="popover"]:has([data-testid="stSelectbox"]) * {
            color:#F5F5F5 !important;
            -webkit-text-fill-color:#F5F5F5 !important;
        }

        /* Language select shell */
        div[data-testid="stPopoverBody"] [data-testid="stSelectbox"] [data-baseweb="select"] > div,
        div[data-baseweb="popover"] [data-testid="stSelectbox"] [data-baseweb="select"] > div {
            background:#171717 !important;
            background-color:#171717 !important;
            border:1px solid #6E6E6E !important;
            color:#F5F5F5 !important;
        }

        /* Select arrow segment */
        div[data-testid="stPopoverBody"] [data-testid="stSelectbox"] [data-baseweb="select"] > div > div:last-child,
        div[data-baseweb="popover"] [data-testid="stSelectbox"] [data-baseweb="select"] > div > div:last-child {
            background:#171717 !important;
            border-left:1px solid #3C3C3C !important;
        }

        div[data-testid="stPopoverBody"] [data-testid="stSelectbox"] svg,
        div[data-baseweb="popover"] [data-testid="stSelectbox"] svg {
            fill:#F5F5F5 !important;
            color:#F5F5F5 !important;
        }

        /* Profile primary action */
        div[data-testid="stPopoverBody"] [data-testid="stBaseButton-primary"],
        div[data-testid="stPopoverBody"] button[kind="primary"],
        div[data-baseweb="popover"] [data-testid="stBaseButton-primary"] {
            background:linear-gradient(90deg,#E10600,#A80000) !important;
            border:1.5px solid #FF2A20 !important;
            color:#FFFFFF !important;
            font-weight:800 !important;
            box-shadow:none !important;
        }

        /* Logout / secondary action */
        div[data-testid="stPopoverBody"] [data-testid="stBaseButton-secondary"],
        div[data-testid="stPopoverBody"] button[kind="secondary"],
        div[data-baseweb="popover"] [data-testid="stBaseButton-secondary"] {
            background:#111111 !important;
            border:1px solid #777777 !important;
            color:#FFFFFF !important;
            font-weight:700 !important;
        }

        div[data-testid="stPopoverBody"] hr,
        div[data-baseweb="popover"] hr {
            border-color:#555555 !important;
        }

        /* Popover arrow */
        div[data-baseweb="popover"] [data-baseweb="popover"] {
            background:#0B0B0B !important;
        }
        </style>
        """,
        unsafe_allow_html=True,
    )
