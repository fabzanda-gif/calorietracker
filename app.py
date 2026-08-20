import streamlit as st
import streamlit.components.v1 as components
import pandas as pd
from datetime import date, datetime
import requests
import traceback
import re
import json
import html
from html import escape
import uuid
import base64
import hashlib
import io
from pathlib import Path
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
APP_LOGO_FILE = ASSET_DIR / "Gemini_Generated_Image_oxrwohoxrwohoxrw.jpeg"

WEIGHT_SOUND_BIG_LOSS = ASSET_DIR / "assets/sounds/bmw-check-oshibka.mp3"
WEIGHT_SOUND_SMALL_LOSS = ASSET_DIR / "assets/sounds/26f8b9_sonic_ring_sound_effect.mp3"
WEIGHT_SOUND_GAIN = ASSET_DIR / "assets/sounds/sonicded.mp3"


def play_hidden_local_audio(audio_path):
    """Riproduce un MP3 locale senza mostrare un player nella UI."""
    try:
        audio_path = Path(audio_path)
        if not audio_path.exists():
            st.warning(f"File audio non trovato: {audio_path.name}")
            return

        audio_b64 = base64.b64encode(audio_path.read_bytes()).decode("ascii")
        components.html(
            f"""
            <audio autoplay>
                <source src="data:audio/mpeg;base64,{audio_b64}" type="audio/mpeg">
            </audio>
            """,
            height=0,
            width=0,
        )
    except Exception as e:
        print(f"Weight sound error: {e}")


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
        .sano-budget-value span { color:#FF9A9A !important; }
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
            background:linear-gradient(90deg,#FF8B8B,#FFB0B0);
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
    "custom": 0,
    "slow": 250,
    "medium": 500,
    "fast": 750,
}

DEFICIT_PRESET_LABELS = {
    "Italiano": {
        "custom": "Custom",
        "slow": "Lento · 250 kcal",
        "medium": "Medio · 500 kcal",
        "fast": "Veloce · 750 kcal",
        "title": "🎯 Obiettivo calorico",
        "speed": "Velocità di dimagrimento",
        "field": "Deficit kcal di base",
        "help": (
            "Il preset imposta automaticamente il deficit. "
            "Il valore sotto resta sempre modificabile manualmente."
        ),
    },
    "English": {
        "custom": "Custom",
        "slow": "Slow · 250 kcal",
        "medium": "Medium · 500 kcal",
        "fast": "Fast · 750 kcal",
        "title": "🎯 Calorie target",
        "speed": "Weight-loss speed",
        "field": "Base calorie deficit",
        "help": (
            "The preset automatically sets the deficit. "
            "You can always edit the value below manually."
        ),
    },
    "Nederlands": {
        "custom": "Aangepast",
        "slow": "Langzaam · 250 kcal",
        "medium": "Gemiddeld · 500 kcal",
        "fast": "Snel · 750 kcal",
        "title": "🎯 Caloriedoel",
        "speed": "Snelheid van gewichtsverlies",
        "field": "Basis calorietekort",
        "help": (
            "De voorinstelling vult het tekort automatisch in. "
            "Je kunt de waarde hieronder altijd handmatig wijzigen."
        ),
    },
    "Français": {
        "custom": "Personnalisé",
        "slow": "Lent · 250 kcal",
        "medium": "Moyen · 500 kcal",
        "fast": "Rapide · 750 kcal",
        "title": "🎯 Objectif calorique",
        "speed": "Vitesse de perte de poids",
        "field": "Déficit calorique de base",
        "help": (
            "Le préréglage renseigne automatiquement le déficit. "
            "Vous pouvez toujours modifier la valeur ci-dessous."
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

    for key, kcal in DEFICIT_PRESETS.items():
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

def refresh_daily_logs(log_date):
    pass

def _safe_float(value):
    try:
        if value in (None, ""):
            return 0.0
        return float(value)
    except (TypeError, ValueError):
        return 0.0




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

    addon = protein_addons.get(language, protein_addons["Italiano"]).get(
        protein_status,
        "",
    )
    return (base + addon).strip()


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
            model="qwen/qwen3.6-27b",
            messages=[
                {
                    "role": "system",
                    "content": SANOSYNC_COACH_SYSTEM_PROMPT,
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

        message = str(
            response.choices[0].message.content or ""
        ).strip()

        # Prevent unexpectedly long UI output even if the provider ignores limits.
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


def translate_activity_display(value, lang):
    maps = {
        "Italiano": {"Bici": "Bici", "Bici Elettrica": "Bici Elettrica", "Passi (Stima)": "Passi (Stima)", "BMR (Base)": "BMR (Base)"},
        "English": {"Bici": "Bike", "Bici Elettrica": "Electric Bike", "Passi (Stima)": "Steps (Estimate)", "BMR (Base)": "BMR (Base)"},
        "Nederlands": {"Bici": "Fiets", "Bici Elettrica": "Elektrische fiets", "Passi (Stima)": "Stappen (Schatting)", "BMR (Base)": "BMR (Basis)"},
        "Français": {"Bici": "Vélo", "Bici Elettrica": "Vélo électrique", "Passi (Stima)": "Pas (Estimation)", "BMR (Base)": "BMR (Base)"},
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


def closest_logged_meal(meal_type, target_calories, allowed_categories=None):
    """Trova il meal replicabile più vicino al target rispettando contesto e categoria."""
    try:
        rows = (
            supabase.table("meals")
            .select("id,date,meal_type,name,base_name,calories,notes,category")
            .eq("user_id", user_id)
            .eq("meal_type", meal_type)
            .execute().data
            or []
        )
    except Exception:
        rows = (
            supabase.table("meals")
            .select("id,date,meal_type,name,base_name,calories,notes")
            .eq("user_id", user_id)
            .eq("meal_type", meal_type)
            .execute().data
            or []
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
    try:
        rows = (
            supabase.table("meals")
            .select(
                "id,date,name,base_name,quantity,is_per_100g,"
                "base_calories,base_protein,base_carbs,base_fat,"
                "calories,protein,carbs,fat,notes,category,ingredients_json,recipe_servings,is_shared,image_url"
            )
            .eq("user_id", user_id)
            .order("date", desc=True)
            .execute().data
            or []
        )
        enhanced_schema = True
    except Exception:
        # Compatibilità temporanea prima della migrazione SQL.
        rows = (
            supabase.table("meals")
            .select("id,date,name,calories,protein,carbs,fat")
            .eq("user_id", user_id)
            .order("date", desc=True)
            .execute().data
            or []
        )
        enhanced_schema = False

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
    try:
        return supabase.table("meals").insert(payload).execute()
    except Exception as e:
        # Fallback per consentire all'app di continuare a funzionare prima
        # che venga applicata la migrazione dei campi base_*.
        print(f"Inserimento meals con schema esteso fallito, fallback legacy: {e}")
        legacy_payload = {
            k: payload[k]
            for k in ("user_id", "date", "meal_type", "name", "calories", "protein", "carbs", "fat")
        }
        return supabase.table("meals").insert(legacy_payload).execute()


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
    return supabase.table(RECIPE_LIBRARY_TABLE).insert(payload).execute()


def load_available_recipes():
    """
    Ricette disponibili nel logging:
    - tutte le proprie
    - quelle condivise dagli altri utenti
    Le proprie hanno precedenza in caso di stesso nome.
    """
    rows = (
        supabase.table(RECIPE_LIBRARY_TABLE)
        .select(
            "id,user_id,name,meal_type,category,recipe_servings,"
            "calories,protein,carbs,fat,notes,ingredients_json,"
            "is_shared,image_url,created_at"
        )
        .or_(f"user_id.eq.{user_id},is_shared.eq.true")
        .order("created_at", desc=True)
        .execute().data
        or []
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
    Importante: viene creato NORMALMENTE, senza ClientOptions/storage custom.
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
    Genera URL OAuth separato per provider.
    Ogni tentativo usa un proprio client/verifier PKCE.
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
    Scambia il code PKCE e trasferisce esplicitamente la sessione
    al client Supabase principale, come nell'app di riferimento.
    """
    code_param = st.query_params.get("code")
    flow_id = st.query_params.get("auth_flow")

    if not code_param or not flow_id:
        return False

    try:
        # Fondamentale: recuperiamo lo STESSO client usato per iniziare
        # questo specifico flusso OAuth/PKCE.
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

        # Passaggio esplicito dei token al client principale.
        # È il punto importante della versione che funziona bene anche
        # quando Streamlit ricrea la pagina dopo il redirect OAuth.
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

    current_login_lang = st.selectbox(
        LOGIN_I18N[st.session_state["login_lang_selector"]]["language"],
        ["Italiano", "English", "Nederlands", "Français"],
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
            st.session_state["signup_deficit_plan"] = "custom"
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
# 5. RESTORE SESSION / GOOGLE CALLBACK
# ==============================================================================
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
    latest_weight_data = (
        supabase.table("daily_logs")
        .select("weight,date")
        .eq("user_id", user_id)
        .not_.is_("weight", "null")
        .order("date", desc=True)
        .limit(1)
        .execute()
        .data
        or []
    )
    if latest_weight_data:
        latest_weight_row = latest_weight_data[0]
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
                supabase.table("daily_logs").upsert(
                    {
                        "user_id": user_id,
                        "date": str(date.today()),
                        "weight": float(w_val),
                    },
                    on_conflict="user_id,date",
                ).execute()

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
            "menu": "⚙️",
            "settings": "⚙️ Impostazioni",
            "language": "🌐 Lingua",
            "logout": "🚪 Esci",
        },
        "English": {
            "menu": "⚙️",
            "settings": "⚙️ Settings",
            "language": "🌐 Language",
            "logout": "🚪 Log out",
        },
        "Nederlands": {
            "menu": "⚙️",
            "settings": "⚙️ Instellingen",
            "language": "🌐 Taal",
            "logout": "🚪 Uitloggen",
        },
        "Français": {
            "menu": "⚙️",
            "settings": "⚙️ Paramètres",
            "language": "🌐 Langue",
            "logout": "🚪 Se déconnecter",
        },
    }

    _menu_lang = st.session_state.get("lang_selector", "Italiano")
    _pm = _profile_menu_i18n.get(
        _menu_lang,
        _profile_menu_i18n["Italiano"],
    )

    # --------------------------------------------------------------
    # MENU PROFILO — in alto a sinistra, separato da foto e saluto.
    # --------------------------------------------------------------
    st.markdown(
        """
        <style>
        /* Trigger del menu */
        .st-key-profile_menu_popover {
            width:42px !important;
            margin:0 0 .75rem 0 !important;
        }

        .st-key-profile_menu_popover button {
            width:42px !important;
            min-width:42px !important;
            height:42px !important;
            min-height:42px !important;
            padding:0 !important;
            border-radius:12px !important;
            border:1.5px solid rgba(255,139,139,.72) !important;
            background:linear-gradient(145deg,#FFFFFF,#FFF4F4) !important;
            color:#192E49 !important;
            box-shadow:0 5px 14px rgba(0,0,0,.10) !important;
            font-size:1.05rem !important;
            font-weight:900 !important;
        }

        .st-key-profile_menu_popover button *,
        .st-key-profile_menu_popover button span,
        .st-key-profile_menu_popover button p {
            color:#192E49 !important;
            opacity:1 !important;
        }

        .st-key-profile_menu_popover button:hover {
            background:#FFEDED !important;
            border-color:#FF6F6F !important;
            transform:translateY(-1px);
        }

        /* Pannello del popover coerente con SanoSync */
        div[data-testid="stPopoverBody"] {
            border:1px solid #FFD0D0 !important;
            border-radius:18px !important;
            background:
                radial-gradient(circle at 100% 0%, rgba(255,139,139,.16), transparent 35%),
                linear-gradient(145deg,#FFFFFF,#FFF7F7) !important;
            box-shadow:0 16px 38px rgba(23,42,70,.16) !important;
            padding:1rem !important;
        }

        /* Pulsante Impostazioni */
        .st-key-profile_menu_settings button {
            background:linear-gradient(135deg,#FF8B8B,#FF7474) !important;
            color:#FFFFFF !important;
            border:1px solid #FF7474 !important;
            border-radius:11px !important;
            min-height:44px !important;
            font-weight:850 !important;
            box-shadow:0 6px 16px rgba(255,139,139,.22) !important;
        }

        .st-key-profile_menu_settings button *,
        .st-key-profile_menu_settings button p,
        .st-key-profile_menu_settings button span {
            color:#FFFFFF !important;
        }

        /* Logout secondario ma coerente */
        .st-key-profile_menu_logout button {
            background:#FFFFFF !important;
            color:#192E49 !important;
            border:1.5px solid #FF8B8B !important;
            border-radius:11px !important;
            min-height:44px !important;
            font-weight:850 !important;
        }

        .st-key-profile_menu_logout button *,
        .st-key-profile_menu_logout button p,
        .st-key-profile_menu_logout button span {
            color:#192E49 !important;
        }

        .st-key-profile_menu_logout button:hover {
            background:#FFF1F1 !important;
        }

        /* Select lingua */
        .st-key-profile_menu_language div[data-baseweb="select"] > div {
            border-radius:11px !important;
            border-color:#FFD0D0 !important;
            background:#FFFFFF !important;
        }

        /* Foto profilo più pulita e coerente */
        [data-testid="stSidebar"] [data-testid="stImage"] img {
            border-radius:14px !important;
        }

        .sanosync-account-row {
            margin-top:.10rem;
        }
        </style>
        """,
        unsafe_allow_html=True,
    )

    with st.popover(
        _pm["menu"],
        key="profile_menu_popover",
        help=_pm["settings"],
    ):
        if st.button(
            _pm["settings"],
            key="profile_menu_settings",
            use_container_width=True,
        ):
            # Sincronizza sempre la lingua della pagina Impostazioni
            # con la lingua attualmente attiva nell'app.
            # La pagina Impostazioni parte sempre dalla lingua corrente.
            st.session_state.pop("settings_language_live", None)
            st.session_state["settings_language_live"] = (
                st.session_state.get("lang_selector", "Italiano")
            )
            st.session_state["show_personal_settings"] = True
            st.rerun()

        _language_options = [
            "Italiano",
            "English",
            "Nederlands",
            "Français",
        ]
        _current_menu_lang = st.session_state.get(
            "lang_selector",
            "Italiano",
        )
        if _current_menu_lang not in _language_options:
            _current_menu_lang = "Italiano"

        # Quando siamo nella pagina Impostazioni, la lingua viene gestita
        # esclusivamente dal selettore in cima a quella pagina. Evitiamo di
        # renderizzare anche questo widget perché una sua key "vecchia"
        # poteva riportare silenziosamente l'app all'italiano.
        if not st.session_state.get("show_personal_settings", False):
            _new_menu_lang = st.selectbox(
                _pm["language"],
                _language_options,
                index=_language_options.index(_current_menu_lang),
                key="profile_menu_language",
                format_func=format_language_option,
            )

            if _new_menu_lang != st.session_state.get("lang_selector"):
                st.session_state["lang_selector"] = _new_menu_lang
                st.session_state["login_lang_selector"] = _new_menu_lang
                st.rerun()

        st.divider()

        if st.button(
            _pm.get("logout", "🚪 Logout"),
            key="profile_menu_logout",
            use_container_width=True,
        ):
            try:
                supabase.auth.sign_out()
            except Exception:
                pass

            for _auth_key in (
                "user",
                "auth_access_token",
                "auth_refresh_token",
                "show_personal_settings",
                AUTH_FLOW_STATE_KEY,
            ):
                st.session_state.pop(_auth_key, None)

            _cookie_delete(SESSION_COOKIE)
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
        "opt_off": "🔍 Cerca online (Open Food Facts)",
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
        "opt_off": "🔍 Search online (Open Food Facts)",
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
        "opt_off": "🔍 Online zoeken (Open Food Facts)",
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
    "opt_off": "🔍 Rechercher en ligne (Open Food Facts)",
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
    # --- INSERIMENTO LOGO ---
    st.sidebar.image("logo2.png", use_container_width=True)

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
    ux = _ui_extra.get(current_lang, _ui_extra["Italiano"])

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
        _today_meals = (
            supabase.table("meals")
            .select("calories,protein")
            .eq("user_id", user_id)
            .eq("date", _today_str)
            .execute().data
            or []
        )
        _today_acts = (
            supabase.table("activities")
            .select("burned_calories")
            .eq("user_id", user_id)
            .eq("date", _today_str)
            .execute().data
            or []
        )

        _today_eaten = sum(
            _safe_float(row.get("calories"))
            for row in _today_meals
        )
        _today_activity = sum(
            _safe_float(row.get("burned_calories"))
            for row in _today_acts
        )

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
        "title": "⚙️ Impostazioni personali",
        "subtitle": "Gestisci i dati del tuo profilo SanoSync.",
        "back": "← Torna all'app",
        "account": "👤 Account e dati personali",
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
    },
    "English": {
        "title": "⚙️ Personal settings",
        "subtitle": "Manage your SanoSync profile information.",
        "back": "← Back to the app",
        "account": "👤 Account and personal details",
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
    },
    "Nederlands": {
        "title": "⚙️ Persoonlijke instellingen",
        "subtitle": "Beheer je SanoSync-profielgegevens.",
        "back": "← Terug naar de app",
        "account": "👤 Account en persoonlijke gegevens",
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
    },
    "Français": {
        "title": "⚙️ Paramètres personnels",
        "subtitle": "Gérez les informations de votre profil SanoSync.",
        "back": "← Retour à l'application",
        "account": "👤 Compte et informations personnelles",
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
    },
}



def render_personal_settings_page():
    # ------------------------------------------------------------------
    # LINGUA SEMPRE IN ALTO
    # La select aggiorna subito l'interfaccia, senza aspettare "Salva".
    # ------------------------------------------------------------------
    _settings_languages = ["Italiano", "English", "Nederlands", "Français"]

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

            supabase.table("daily_logs").upsert(
                {
                    "user_id": user_id,
                    "date": str(date.today()),
                    "weight": float(new_current_weight),
                },
                on_conflict="user_id,date",
            ).execute()

            if getattr(response, "user", None):
                st.session_state["user"] = response.user

            st.session_state["lang_selector"] = new_language
            st.session_state["login_lang_selector"] = new_language

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


# 9. PAGE 1: MEAL LOGGING
# ==============================================================================
if selected_page == t["t1"]:
    log_date = st.date_input("📅 Data", value=date.today())
    render_page_title_card(t["tab1_title"])

    recipe_source_label = {
        "Italiano": "🍲 Ricette",
        "English": "🍲 Recipes",
        "Nederlands": "🍲 Recepten",
    }.get(current_lang, "🍲 Ricette")

    _input_source_options = [
        t["opt_quick"],
        t["opt_off"],
        t["opt_scan"],
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

    input_source = st.radio(
        t["input_source_lbl"],
        _input_source_options,
        horizontal=True,
        key="meal_input_source",
    )

    is_online = input_source == t["opt_off"]
    is_quick = input_source == t["opt_quick"]
    is_recipe = False  # Ricette integrate in Immissione Rapida
    is_scan = input_source == t["opt_scan"]
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
                        is_100g=True, note="", category="Casa"):
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
    # Card comune per Quick Entry / Open Food Facts / Ricette / Foto AI
    # --------------------------------------------------------------
    with st.container(border=True):
        st.markdown(f"### {input_source}")
        # ------------------------------------------------------------------
        # A. Open Food Facts
        # ------------------------------------------------------------------
        if is_online:
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
                recipe_rows = (
                    supabase.table("meals")
                    .select(
                        "id,date,name,base_name,quantity,is_per_100g,"
                        "base_calories,base_protein,base_carbs,base_fat,"
                        "calories,protein,carbs,fat,notes,category,ingredients_json"
                    )
                    .eq("user_id", user_id)
                    .order("date", desc=True)
                    .execute().data
                    or []
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

        # --------------------------------------------------------------
        # Tipo di pasto suggerito automaticamente.
        # - nessun pasto principale registrato -> Colazione
        # - Colazione presente -> Pranzo
        # - Pranzo presente -> Cena
        # - Snack non viene mai selezionato automaticamente
        #
        # Il calcolo viene rifatto a ogni nuova versione del form, quindi dopo
        # aver salvato un pasto il successivo propone automaticamente il passo
        # logico seguente.
        # --------------------------------------------------------------
        try:
            _logged_meal_types_today = (
                supabase.table("meals")
                .select("meal_type")
                .eq("user_id", user_id)
                .eq("date", str(log_date))
                .execute().data
                or []
            )
            _logged_main_types = {
                str(row.get("meal_type") or "").strip().casefold()
                for row in _logged_meal_types_today
            }
        except Exception as _meal_type_exc:
            print(f"Meal type default error: {_meal_type_exc}")
            _logged_main_types = set()

        if "pranzo" in _logged_main_types:
            _suggested_meal_type = "Cena"
        elif "colazione" in _logged_main_types:
            _suggested_meal_type = "Pranzo"
        else:
            _suggested_meal_type = "Colazione"

        _meal_type_key = f"meal_type_input_{v}"
        if _meal_type_key not in st.session_state:
            st.session_state[_meal_type_key] = _suggested_meal_type

        m_type = st.selectbox(
            t["meal"],
            meal_options,
            key=_meal_type_key,
            format_func=tr_meal_type,
        )

        name = st.text_input(
            t["meal_name"],
            value=st.session_state["m_name"],
            key=f"input_meal_name_{v}",
        )

        _meal_categories_available = MEAL_CATEGORIES if user_office_lunch_enabled else [c for c in MEAL_CATEGORIES if c != "Lavoro"]
        default_category = st.session_state.get("selected_source_category", "Casa")
        if default_category not in _meal_categories_available:
            default_category = "Casa"
        meal_category = st.selectbox(
            t["category_label"],
            _meal_categories_available,
            index=_meal_categories_available.index(default_category),
            key=f"meal_category_{v}",
            help=t["category_help"],
            format_func=tr_category,
        )

        meal_notes = st.text_area(
            t["notes_optional"],
            value=st.session_state.get("selected_source_note", ""),
            placeholder=ux["notes_ph"],
            key=f"meal_notes_{v}",
            height=80,
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
                        ingredients_json=None,
                    )
                    refresh_daily_logs(log_date)

                    # Dopo il salvataggio: pulizia completa del form e ritorno
                    # automatico alla prima sorgente di inserimento.
                    clear_meal_entry_after_save()

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

    try:
        daily_log_res = supabase.table("daily_logs").select("*").eq("date", str(summary_date)).eq("user_id", user_id).execute().data or []
        meals_data = supabase.table("meals").select("*").eq("date", str(summary_date)).eq("user_id", user_id).execute().data or []
        raw_activities = supabase.table("activities").select("activity_name, burned_calories").eq("date", str(summary_date)).eq("user_id", user_id).execute().data or []
        all_weight_logs = supabase.table("daily_logs").select("weight, date").eq("user_id", user_id).not_.is_("weight", "null").order("date", desc=False).execute().data or []
    except Exception as e:
        st.error(t["load_data_error"].format(error=e))
        daily_log_res, meals_data, raw_activities, all_weight_logs = [], [], [], []

    activities_data = [a for a in raw_activities if a.get("activity_name")] if raw_activities else []
    total_cals_in = sum(_safe_float(m.get("calories")) for m in meals_data)

    current_weight = daily_log_res[0].get("weight") if daily_log_res else None
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

    st.markdown(f"""
        <style>
            .custom-card {{
                background-color: {coral_light_bg};
                border: 1.5px solid {coral_border};
                border-radius: 16px;
                padding: 16px;
                height: 100%;
                box-shadow: 0 2px 6px rgba(255, 139, 139, 0.08);
            }}
            .custom-card-title {{ font-size: .95rem; font-weight: 600; color: #1A2942; margin-bottom: 4px; }}
            .custom-card-value {{ font-size: 1.8rem; font-weight: 700; color: #1A2942; margin-bottom: 8px; }}
            .custom-card-caption {{ font-size: .86rem; color: #4A4A4A; line-height: 1.42; }}
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
                plan_log = (
                    supabase.table("daily_logs").select("id,day_type,activity_plan")
                    .eq("user_id", user_id).eq("date", str(plan_date)).execute().data or []
                )
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
                    existing = supabase.table("daily_logs").select("id").eq("user_id", user_id).eq("date", str(plan_date)).execute().data or []
                    payload_plan = {"day_type": day_type, "activity_plan": activity_plan}
                    if existing:
                        supabase.table("daily_logs").update(payload_plan).eq("id", existing[0]["id"]).execute()
                    else:
                        supabase.table("daily_logs").insert({"user_id": user_id, "date": str(plan_date), **payload_plan}).execute()
                    st.success(t["plan_saved"].format(date=plan_date.strftime("%d/%m/%Y")))
                except Exception:
                    st.info(t["plan_persistence_note"])

            # Valori rappresentativi per la pianificazione:
            # Riposo 0 kcal extra, Moderatamente attiva 500, Attiva 1000.
            activity_bonus = {"Riposo": 0, "Moderatamente attiva": 500, "Attiva": 1000}[activity_plan]
            daily_budget = float(user_bmr) + activity_bonus

            try:
                plan_meals = (
                    supabase.table("meals")
                    .select("meal_type,calories,category,name,base_name")
                    .eq("user_id", user_id).eq("date", str(plan_date)).execute().data or []
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
            try:
                meals_with_id = (
                    supabase.table("meals")
                    .select(
                        "id,meal_type,name,base_name,quantity,is_per_100g,"
                        "base_calories,base_protein,base_carbs,base_fat,"
                        "calories,protein,carbs,fat,notes,category"
                    )
                    .eq("date", str(summary_date))
                    .eq("user_id", user_id)
                    .execute()
                    .data
                    or []
                )
            except Exception:
                # Compatibilità con eventuali righe/schema legacy.
                meals_with_id = (
                    supabase.table("meals")
                    .select("id,meal_type,name,calories,protein,carbs,fat")
                    .eq("date", str(summary_date))
                    .eq("user_id", user_id)
                    .execute()
                    .data
                    or []
                )

            df_meals = pd.DataFrame(meals_with_id)
            df_display = df_meals.rename(columns={
                "meal_type": t["col_meal"], "name": t["col_name"], "calories": "Kcal",
                "protein": "Pro (g)", "carbs": "Carbs (g)", "fat": "Fat (g)", "category": t["col_category"],
            })
            df_display[t["col_meal"]] = df_display[t["col_meal"]].map(tr_meal_type)
            df_display[t["col_category"]] = [tr_category(infer_meal_category(m)) for m in meals_with_id]
            st.dataframe(
                df_display[[t["col_meal"], t["col_category"], t["col_name"], "Kcal", "Pro (g)", "Carbs (g)", "Fat (g)"]],
                use_container_width=True,
                hide_index=True,
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

                        supabase.table("meals").update(
                            update_payload
                        ).eq("id", selected_meal_id).eq(
                            "user_id", user_id
                        ).execute()

                        refresh_daily_logs(summary_date)

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
                            supabase.table("meals").delete().eq("id", selected_meal_id).eq("user_id", user_id).execute()
                            st.success(t["meal_del_success"])
                            st.rerun()
                        except Exception as e:
                            st.error(t["delete_meal_error"].format(error=e))
        else:
            st.info(t["no_meals"])

    with st.container(border=True):
        st.markdown(t["burned_acts"])
        rows_acts = [{t["col_activity"]: ux["bmr_base"], t["col_burned"]: bmr_so_far}]
        for act in activities_data:
            rows_acts.append({t["col_activity"]: translate_activity_display(act.get("activity_name"), current_lang), t["col_burned"]: act.get("burned_calories")})
        st.dataframe(pd.DataFrame(rows_acts), use_container_width=True, hide_index=True)

# 11. PAGE 3: WEIGHT TRACKING / ANALYTICS
# ==============================================================================
elif selected_page == t["t3"]:
    render_page_title_card(t["weight_tracking"])

    # Se un peso è appena stato salvato, riproduci il relativo feedback sonoro.
    render_pending_weight_sound()

    with st.container(border=True):
        st.markdown(t["weight_manage"])
        logs_all = (
            supabase.table("daily_logs").select("id, date, weight").eq("user_id", user_id)
            .not_.is_("weight", "null").order("date", desc=True).execute().data or []
        )
        edit_options = {str(r["id"]): f"{r['date']} · {float(r['weight']):.1f} kg" for r in logs_all}

        c1, c2 = st.columns(2)
        with c1:
            w = st.number_input(t["new_weight"], value=80.0, min_value=20.0, max_value=300.0, step=0.1, key="new_weight_value")
            w_date = st.date_input(t["weight_date"], value=date.today(), key="new_weight_date")
            if st.button(t["save_weight_ui"], use_container_width=True):
                try:
                    # Cerchiamo il peso cronologicamente precedente alla data
                    # che stiamo registrando. Un eventuale peso già presente
                    # nello stesso giorno non viene usato come confronto.
                    previous_rows = []
                    for row in logs_all:
                        try:
                            row_date = pd.to_datetime(row.get("date")).date()
                            if row_date < w_date and row.get("weight") is not None:
                                previous_rows.append((row_date, float(row["weight"])))
                        except Exception:
                            continue

                    previous_weight = None
                    if previous_rows:
                        previous_rows.sort(key=lambda item: item[0], reverse=True)
                        previous_weight = previous_rows[0][1]

                    # Decidiamo il suono PRIMA del salvataggio, ma lo accodiamo
                    # solo dopo che Supabase conferma il successo.
                    sound_to_play = None
                    if previous_weight is not None:
                        delta_weight = float(w) - float(previous_weight)

                        # Perdita > 0.5 kg
                        if delta_weight < -0.5:
                            sound_to_play = WEIGHT_SOUND_BIG_LOSS

                        # Perdita da 0.5 kg fino a peso invariato incluso
                        elif delta_weight <= 0:
                            sound_to_play = WEIGHT_SOUND_SMALL_LOSS

                        # Aumento di peso
                        else:
                            sound_to_play = WEIGHT_SOUND_GAIN

                    supabase.table("daily_logs").upsert(
                        {
                            "user_id": user_id,
                            "date": str(w_date),
                            "weight": float(w),
                        },
                        on_conflict="user_id,date",
                    ).execute()

                    if sound_to_play is not None:
                        st.session_state["pending_weight_sound"] = str(sound_to_play)

                    st.success(t["weight_saved"])
                    st.rerun()

                except Exception as e:
                    st.error(f"Errore nel salvataggio del peso: {e}")

        with c2:
            selected_weight_id = st.selectbox(
                t["weight_edit_select"],
                [""] + list(edit_options),
                format_func=lambda x: t["weight_select_placeholder"] if x == "" else edit_options[x],
                key="weight_edit_selector",
            )
            if selected_weight_id:
                selected_row = next(r for r in logs_all if str(r["id"]) == selected_weight_id)
                ew1, ew2 = st.columns(2)
                with ew1:
                    edited_date = st.date_input(t["date_label"], value=pd.to_datetime(selected_row["date"]).date(), key=f"edit_weight_date_{selected_weight_id}")
                with ew2:
                    edited_weight = st.number_input(t["weight_value"], value=float(selected_row["weight"]), min_value=20.0, max_value=300.0, step=0.1, key=f"edit_weight_value_{selected_weight_id}")
                b1, b2 = st.columns(2)
                with b1:
                    if st.button(t["edit_weight"], use_container_width=True, key=f"update_weight_{selected_weight_id}"):
                        try:
                            if str(edited_date) != str(selected_row["date"]):
                                supabase.table("daily_logs").delete().eq("id", selected_row["id"]).eq("user_id", user_id).execute()
                                supabase.table("daily_logs").upsert(
                                    {"user_id": user_id, "date": str(edited_date), "weight": float(edited_weight)},
                                    on_conflict="user_id,date",
                                ).execute()
                            else:
                                supabase.table("daily_logs").update({"weight": float(edited_weight)}).eq("id", selected_row["id"]).eq("user_id", user_id).execute()
                            st.success(t["weight_edited"])
                            st.rerun()
                        except Exception as e:
                            st.error(t["weight_edit_error"].format(error=e))
                with b2:
                    if st.button(t["delete_weight"], use_container_width=True, key=f"delete_weight_{selected_weight_id}"):
                        try:
                            # Non cancelliamo l'intera riga se contiene passi o piano giornata:
                            # azzeriamo solo weight. Se la riga ha solo il peso, Supabase
                            # conserverà una riga innocua con weight NULL.
                            supabase.table("daily_logs").update({"weight": None}).eq("id", selected_row["id"]).eq("user_id", user_id).execute()
                            st.success(t["weight_deleted"])
                            st.rerun()
                        except Exception as e:
                            st.error(t["weight_delete_error"].format(error=e))

    with st.container(border=True):
        st.markdown(f"#### {t['update_target']}")
        new_target = st.number_input(
            t["target_weight_label"],
            value=float(user_target_weight) if user_target_weight else 75.0,
            min_value=20.0, max_value=300.0, step=0.5,
            key="weight_target_edit",
        )
        if st.button(t["save_target"], use_container_width=True):
            try:
                res = supabase.auth.update_user({"data": {"target_weight": float(new_target)}})
                if res.user:
                    st.session_state["user"] = res.user
                st.success(t["target_updated"])
                st.rerun()
            except Exception as e:
                st.error(f"Errore: {e}")

    # ------------------------------------------------------------------
    # KPI ULTIMI 30 GIORNI
    # ------------------------------------------------------------------
    try:
        month_end = pd.Timestamp(date.today())
        month_start = month_end - pd.Timedelta(days=29)

        month_weights_rows = (
            supabase.table("daily_logs").select("date, weight").eq("user_id", user_id)
            .gte("date", str(month_start.date())).lte("date", str(month_end.date()))
            .not_.is_("weight", "null").order("date", desc=False).execute().data or []
        )
        month_meals_rows = (
            supabase.table("meals").select("date, calories").eq("user_id", user_id)
            .gte("date", str(month_start.date())).lte("date", str(month_end.date()))
            .execute().data or []
        )
        month_acts_rows = (
            supabase.table("activities").select("date, burned_calories").eq("user_id", user_id)
            .gte("date", str(month_start.date())).lte("date", str(month_end.date()))
            .execute().data or []
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

        st.markdown('''
            <style>
                .custom-card {
                    background-color: #FFF5F5;
                    border: 1.5px solid #FF8B8B;
                    border-radius: 16px;
                    padding: 16px;
                    height: 100%;
                    box-shadow: 0 2px 6px rgba(255,139,139,.08);
                }
                .custom-card-title { font-size:.95rem;font-weight:600;color:#1A2942;margin-bottom:4px; }
                .custom-card-value { font-size:1.8rem;font-weight:700;color:#1A2942;margin-bottom:8px; }
                .custom-card-caption { font-size:.82rem;color:#555;line-height:1.35; }
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

            logs = (
                supabase.table("daily_logs").select("date, weight").eq("user_id", user_id)
                .gte("date", str(chart_start.date())).lte("date", str(chart_end.date()))
                .not_.is_("weight", "null").order("date", desc=False).execute().data or []
            )
            meals_rows = (
                supabase.table("meals").select("date, meal_type, name, calories, protein, carbs, fat")
                .eq("user_id", user_id).gte("date", str(chart_start.date())).lte("date", str(chart_end.date()))
                .execute().data or []
            )
            acts_rows = (
                supabase.table("activities").select("date, activity_name, burned_calories")
                .eq("user_id", user_id).gte("date", str(chart_start.date())).lte("date", str(chart_end.date()))
                .execute().data or []
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
            fig.update_yaxes(title=y_title, gridcolor="#E8ECF2", zeroline=False, fixedrange=False)
            fig.update_layout(
                height=500,
                plot_bgcolor="#FFFFFF",
                paper_bgcolor="rgba(0,0,0,0)",
                hovermode="x unified",
                font=dict(color="#1A2942"),
                margin=dict(l=55, r=25, t=45, b=55),
                legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="left", x=0, bgcolor="rgba(255,255,255,.85)"),
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

    # ------------------------------------------------------------------
    # 👤 LE MIE RICETTE
    # ------------------------------------------------------------------
    with st.container(border=True):
        st.markdown(t["my_recipes"])

        try:
            my_recipe_rows = (
                supabase.table(RECIPE_LIBRARY_TABLE)
                .select(
                    "id,user_id,name,meal_type,category,recipe_servings,""calories,protein,carbs,fat,notes,ingredients_json,""is_shared,image_url,created_at"
                )
                .eq("user_id", user_id)
                .order("created_at", desc=True)
                .execute().data
                or []
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
                                                (
                                                    supabase.table(RECIPE_LIBRARY_TABLE)
                                                    .update({"image_url": _new_url})
                                                    .eq("id", r["id"])
                                                    .eq("user_id", user_id)
                                                    .execute()
                                                )
                                                st.session_state[_photo_toggle_key] = False
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
                    (
                        supabase.table(RECIPE_LIBRARY_TABLE)
                        .update({"is_shared": bool(new_share_state)})
                        .eq("id", selected_recipe_row["id"])
                        .eq("user_id", user_id)
                        .execute()
                    )
                    st.success(t["sharing_updated"])
                    st.rerun()
                except Exception as exc:
                    st.error(str(exc))
        else:
            st.info(t["no_my_recipes"])

    # ------------------------------------------------------------------
    # 🌍 RICETTE CONDIVISE DAGLI ALTRI UTENTI
    # ------------------------------------------------------------------
    with st.container(border=True):
        st.markdown(t["shared_recipes"])

        try:
            shared_recipe_rows = (
                supabase.table(RECIPE_LIBRARY_TABLE)
                .select(
                    "id,user_id,name,meal_type,category,recipe_servings,""calories,protein,carbs,fat,notes,ingredients_json,""is_shared,image_url,created_at"
                )
                .eq("is_shared", True)
                .order("created_at", desc=True)
                .execute().data
                or []
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

    with st.container(border=True):
        st.markdown(t["create_meal_ingredients"])

        rc1, rc2 = st.columns(2)
        with rc1:
            recipe_meal_type = st.selectbox(
                t["meal_type_label"],
                ["Colazione", "Pranzo", "Cena", "Snack"],
                key=f"recipe_meal_type_{v}",
                format_func=tr_meal_type,
            )
        with rc2:
            _recipe_categories_available = MEAL_CATEGORIES if user_office_lunch_enabled else [c for c in MEAL_CATEGORIES if c != "Lavoro"]
            recipe_category = st.selectbox(
                t["category_label"],
                _recipe_categories_available,
                index=0,
                key=f"recipe_category_{v}",
                help=t["recipe_category_help"],
                format_func=tr_category,
            )

        r_name = st.text_input(
            t["col_name"],
            placeholder=t["recipe_name_placeholder"],
            key=f"recipe_builder_name_{v}",
        )
        r_notes = st.text_area(
            t["notes_optional"],
            placeholder=t["notes_placeholder"],
            key=f"recipe_builder_notes_{v}",
            height=90,
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

        recipe_servings = st.number_input(
            t["recipe_servings"],
            min_value=1.0,
            max_value=100.0,
            value=4.0,
            step=1.0,
            key=f"recipe_servings_{v}",
            help=t["recipe_servings_help"],
        )

        st.markdown(t["add_ingredient_title"])
        source = st.radio(
            t["ingredient_source"],
            ["database", "manual"],
            horizontal=True,
            key=f"ingredient_source_{v}",
            format_func=lambda x: t["db_off"] if x == "database" else t["manual_entry"],
        )

        ingredient_name = ""
        base = {"calories": 0.0, "protein": 0.0, "carbs": 0.0, "fat": 0.0}

        if source == "database":
            iq = st.text_input(t["ingredient_search"], key=f"ingredient_search_{v}")
            if st.button(t["search_ingredient"], key=f"ingredient_search_btn_{v}"):
                if len(iq.strip()) >= 2 or iq.strip().isdigit():
                    with st.spinner(t["searching_ingredient"]):
                        st.session_state[f"ingredient_results_{v}"] = search_open_food_facts(iq)
                    st.rerun()
                else:
                    st.warning(t["min_2_chars"])

            results = st.session_state.get(f"ingredient_results_{v}", {})
            if results:
                sel = st.selectbox(
                    t["results"],
                    [""] + list(results),
                    key=f"ingredient_result_select_{v}",
                )
                if sel:
                    p_data = results[sel]
                    ingredient_name = p_data.get("name", sel)
                    base = {k: float(p_data.get(k, 0) or 0) for k in base}
                    st.caption(
                        f"{t['per_100g_label']}: {base['calories']:.0f} kcal · "
                        f"Pro {base['protein']:.1f} g · Carbs {base['carbs']:.1f} g · Fat {base['fat']:.1f} g"
                    )
        else:
            ingredient_name = st.text_input(
                t["ingredient_name"],
                key=f"manual_ingredient_name_{v}",
            )
            mc1, mc2, mc3, mc4 = st.columns(4)
            base["calories"] = mc1.number_input(
                "Kcal / 100g", min_value=0.0, step=1.0, key=f"manual_kcal_{v}"
            )
            base["protein"] = mc2.number_input(
                "Pro / 100g", min_value=0.0, step=0.1, key=f"manual_pro_{v}"
            )
            base["carbs"] = mc3.number_input(
                "Carbs / 100g", min_value=0.0, step=0.1, key=f"manual_carbs_{v}"
            )
            base["fat"] = mc4.number_input(
                "Fat / 100g", min_value=0.0, step=0.1, key=f"manual_fat_{v}"
            )

        quantity = st.number_input(
            t["ingredient_qty"],
            min_value=0.1,
            value=100.0,
            step=1.0,
            key=f"ingredient_qty_{v}",
        )

        if st.button(
            t["add_ingredient"],
            use_container_width=True,
            key=f"add_ingredient_{v}",
        ):
            if not ingredient_name.strip():
                st.warning(t["select_or_enter_ingredient"])
            else:
                st.session_state["recipe_builder_ingredients"].append({
                    "name": ingredient_name.strip(),
                    "quantity_g": float(quantity),
                    "calories_per_100g": float(base["calories"]),
                    "protein_per_100g": float(base["protein"]),
                    "carbs_per_100g": float(base["carbs"]),
                    "fat_per_100g": float(base["fat"]),
                    "source": source,
                })
                st.success(t["ingredient_added"].format(name=ingredient_name))
                st.rerun()

        ingredients = st.session_state.get("recipe_builder_ingredients", [])

        if ingredients:
            st.markdown(t["ingredients_title"])
            rows = []
            for idx, ing in enumerate(ingredients):
                ing_factor = float(ing["quantity_g"]) / 100.0
                rows.append({
                    "#": idx + 1,
                    t["ingredient_col"]: ing["name"],
                    t["quantity_g"]: ing["quantity_g"],
                    "Kcal": round(ing["calories_per_100g"] * ing_factor),
                    "Pro": round(ing["protein_per_100g"] * ing_factor, 1),
                    "Carbs": round(ing["carbs_per_100g"] * ing_factor, 1),
                    "Fat": round(ing["fat_per_100g"] * ing_factor, 1),
                })
            st.dataframe(pd.DataFrame(rows), use_container_width=True, hide_index=True)

            remove_idx = st.selectbox(
                t["remove_ingredient"],
                [""] + [str(i + 1) for i in range(len(ingredients))],
                key=f"remove_ingredient_{v}",
            )
            if remove_idx and st.button(
                t["remove_ingredient_btn"],
                key=f"remove_ingredient_btn_{v}",
            ):
                del st.session_state["recipe_builder_ingredients"][int(remove_idx) - 1]
                st.rerun()

            total_weight, totals, per100 = calculate_recipe_totals(ingredients)

            _servings_safe = max(float(recipe_servings), 1.0)
            _per_serving = {
                key: float(value) / _servings_safe
                for key, value in totals.items()
            }
            _serving_weight = float(total_weight) / _servings_safe

            st.markdown(
                f"**{t['total_recipe']}:** {total_weight:.0f} g · "
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
                + f"{t['per_100g_label']}: {per100['calories']:.0f} kcal · "
                + f"Pro {per100['protein']:.1f} g · "
                + f"Carbs {per100['carbs']:.1f} g · "
                + f"Fat {per100['fat']:.1f} g"
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
                                recipe_image_url = upload_recipe_image(recipe_photo)
                            except Exception as upload_exc:
                                st.error(
                                    t["recipe_photo_error"].format(
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
                        st.session_state["recipe_builder_ingredients"] = []
                        st.session_state["recipe_form_version"] += 1
                        st.success(t["composed_saved"])
                        st.rerun()
                    except Exception as e:
                        st.error(
                            "Impossibile salvare la ricetta nel catalogo. "
                            "Verifica che la tabella recipe_library sia stata creata. Errore: " + str(e)
                        )
        else:
            st.info(t["add_one_ingredient"])

# ==============================================================================
# 13. PAGE 5: ACTIVITY & STEPS LOGGING
# ==============================================================================
elif selected_page == t["t5"]:
    render_page_title_card(t["register_activity"])
    act_date = st.date_input(t["act_date"], value=date.today())
    
    try:
        existing_log = supabase.table("daily_logs").select("steps").eq("date", str(act_date)).eq("user_id", user_id).execute().data
        day_steps = existing_log[0].get("steps", 0) if existing_log and existing_log[0].get("steps") else 0
        
        # Recuperiamo anche le attività registrate per questa data per la logica intelligente
        day_activities = supabase.table("activities").select("activity_name, burned_calories").eq("date", str(act_date)).eq("user_id", user_id).execute().data or []
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
    st.markdown("""
        <style>
            .custom-card {
                background-color: #FFF5F5;
                border: 1.5px solid #FF8B8B;
                border-radius: 16px;
                padding: 16px;
                height: 100%;
                box-shadow: 0 2px 6px rgba(255,139,139,.08);
            }
            .custom-card-title { font-size:.95rem;font-weight:600;color:#1A2942;margin-bottom:4px; }
            .custom-card-value { font-size:1.8rem;font-weight:700;color:#1A2942;margin-bottom:8px; }
            .custom-card-caption { font-size:.82rem;color:#555;line-height:1.35; }
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
                    existing = supabase.table("daily_logs").select("id").eq("user_id", user_id).eq("date", str(act_date)).execute().data
                    
                    if existing:
                        supabase.table("daily_logs").update({"steps": int(new_steps)}).eq("user_id", user_id).eq("date", str(act_date)).execute()
                    else:
                        supabase.table("daily_logs").insert({"user_id": user_id, "date": str(act_date), "steps": int(new_steps)}).execute()
                    
                    # I passi sono incompatibili SOLO con attività che già
                    # incorporano gli stessi passi/spostamenti: Padel e Corsa.
                    # Bici/E-Bike e le altre attività possono invece sommarsi.
                    step_conflicting_activities = {"padel", "corsa", "running"}
                    has_step_conflict = any(
                        str(a.get("activity_name") or "").strip().casefold()
                        in step_conflicting_activities
                        for a in day_activities
                    )
                    estim_cals = 0 if has_step_conflict else int(new_steps * 0.04)
                    
                    existing_act = supabase.table("activities").select("id").eq("user_id", user_id).eq("date", str(act_date)).eq("activity_name", "Passi (Stima)").execute().data
                    
                    if existing_act:
                        supabase.table("activities").update({"burned_calories": estim_cals}).eq("id", existing_act[0]["id"]).execute()
                    else:
                        supabase.table("activities").insert({"user_id": user_id, "date": str(act_date), "activity_name": "Passi (Stima)", "burned_calories": estim_cals}).execute()
                    
                    refresh_daily_logs(act_date)
                    
                    st.toast(ux["steps_updated_toast"].format(kcal=estim_cals), icon="👣")
                    st.success(f"✅ {t['steps_updated']} ({estim_cals} kcal stimate)")
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
                        
                    supabase.table("activities").insert({"user_id": user_id, "date": str(act_date), "activity_name": act_label, "burned_calories": estim_cals}).execute()
                    
                    # Bici/E-Bike è compatibile con i passi:
                    # NON azzeriamo le kcal attribuite ai passi.

                    refresh_daily_logs(act_date)
                    
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
                    supabase.table("activities").insert({"user_id": user_id, "date": str(act_date), "activity_name": extra_act, "burned_calories": int(extra_cals)}).execute()
                    
                    # Padel e Corsa sono incompatibili con le kcal dei passi,
                    # perché i passi di quelle attività sarebbero già compresi.
                    # Palestra/Nuoto/Altro restano invece cumulabili con i passi.
                    if str(extra_act).strip().casefold() in {"padel", "corsa", "running"}:
                        passi_act = (
                            supabase.table("activities")
                            .select("id")
                            .eq("user_id", user_id)
                            .eq("date", str(act_date))
                            .eq("activity_name", "Passi (Stima)")
                            .execute()
                            .data
                        )
                        if passi_act:
                            supabase.table("activities").update(
                                {"burned_calories": 0}
                            ).eq("id", passi_act[0]["id"]).execute()

                    refresh_daily_logs(act_date)
                    
                    # Usiamo st.success e st.toast per garantire il feedback visivo immediato
                    st.toast(ux["activity_saved"].format(activity={"Palestra":ux["activity_gym"],"Nuoto":ux["activity_swim"],"Altro":ux["activity_other"]}.get(extra_act, extra_act), kcal=extra_cals), icon="🎯")
                    st.success(ux["activity_saved"].format(activity={"Palestra":ux["activity_gym"],"Nuoto":ux["activity_swim"],"Altro":ux["activity_other"]}.get(extra_act, extra_act), kcal=extra_cals))
                    st.rerun()
