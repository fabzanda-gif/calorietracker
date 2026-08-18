import streamlit as st
import streamlit.components.v1 as components
import pandas as pd
from datetime import date, datetime
import requests
import traceback
import re
import json
import html
import base64
import secrets
import hashlib
from urllib.parse import urlencode
from supabase import create_client
from supabase.client import ClientOptions
from streamlit_cookies_controller import CookieController
import plotly.express as px
import plotly.graph_objects as go

# ==============================================================================
# 1. SETUP INIZIALE E CONFIGURAZIONE PAGINA
# ==============================================================================
st.set_page_config(
    page_title="SanoSync",
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
def calculate_bmr(weight, height, gender):
    if gender in ["Uomo", "Male", "Man"]:
        return int((10 * weight) + (6.25 * height) - (5 * 30) + 5)
    else:
        return int((10 * weight) + (6.25 * height) - (5 * 30) - 161)

def refresh_daily_logs(log_date):
    pass

def _safe_float(value):
    try:
        if value in (None, ""):
            return 0.0
        return float(value)
    except (TypeError, ValueError):
        return 0.0



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
                "calories,protein,carbs,fat,notes,category,ingredients_json"
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
                               notes="", category="Casa", ingredients_json=None):
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
# Autenticazione email/password + Google OAuth con sessione persistente.
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

# PKCE temporaneo per il login Google.
GOOGLE_PKCE_COOKIE = "sanosync_google_pkce"
GOOGLE_PKCE_MAX_AGE = 10 * 60


def _read_cookie(name):
    """Legge un cookie sia dopo un vero refresh sia durante un normale rerun."""
    try:
        value = st.context.cookies.get(name)
        if value:
            return str(value).strip().strip('"')
    except Exception:
        pass

    try:
        value = controller.get(name)
        if value:
            return str(value).strip().strip('"')
    except Exception:
        pass

    return None


def _pkce_challenge(verifier):
    return base64.urlsafe_b64encode(
        hashlib.sha256(verifier.encode("utf-8")).digest()
    ).decode("utf-8").rstrip("=")


def _new_google_pkce_pair():
    """
    Genera una nuova coppia PKCE.

    Il verifier NON viene scritto qui con CookieController perché quel write è
    asincrono rispetto alla navigazione OAuth. Verrà scritto dal browser in modo
    sincrono nell'onclick del pulsante Google.
    """
    verifier = base64.urlsafe_b64encode(
        secrets.token_bytes(48)
    ).decode("utf-8").rstrip("=")

    challenge = _pkce_challenge(verifier)
    return verifier, challenge


def _clear_google_pkce():
    st.session_state.pop("google_pkce_verifier", None)
    _cookie_delete(GOOGLE_PKCE_COOKIE)


def get_google_oauth_url(challenge):
    params = {
        "provider": "google",
        "redirect_to": APP_URL,
        "code_challenge": challenge,
        "code_challenge_method": "s256",
    }
    return f"{SUPABASE_URL}/auth/v1/authorize?{urlencode(params)}"


def google_login_button():
    """
    Genera il pulsante di login Google con PKCE.

    Il verifier viene scritto nel cookie al click e il link usa target="_top"
    così la navigazione OAuth esce dall'iframe Streamlit.
    """
    verifier, challenge = _new_google_pkce_pair()
    oauth_url = get_google_oauth_url(challenge)

    # Escaping per JavaScript e per l'attributo href
    safe_verifier = verifier.replace("\\", "\\\\").replace("'", "\\'")
    safe_url = oauth_url.replace("\\", "\\\\").replace("'", "\\'")

    button_html = f"""
    <div style="width:100%;">
      <a
        href="{safe_url}"
        target="_top"
        onclick="
          try {{
            document.cookie = '{GOOGLE_PKCE_COOKIE}={safe_verifier}; Path=/; Max-Age={GOOGLE_PKCE_MAX_AGE}; SameSite=Lax; Secure';
            console.log('PKCE verifier salvato nel cookie via link click');
            // Lasciamo che il browser segua l'anchor; non forziamo window.top dalla sandbox.
          }} catch(e) {{
            console.error('Errore Google login:', e);
            alert('Errore nella configurazione di Google Login');
            return false;
          }}
        "
        style="display:block;text-decoration:none;"
      >
        <button
          id="google-login-btn"
          style="
            width:100%;
            padding:0.72rem 1rem;
            border-radius:10px;
            border:2px solid #FF8B8B;
            background:#FF8B8B;
            color:white;
            font-weight:800;
            cursor:pointer;
            font-size:1rem;
          "
          type="button"
        >
          Continua con Google
        </button>
      </a>
    </div>
    """
    components.html(button_html, height=72)



def handle_google_oauth_callback():
    """Scambia il code PKCE restituito da Supabase per una sessione."""
    auth_code = st.query_params.get("code")
    oauth_error = st.query_params.get("error")
    oauth_error_description = st.query_params.get("error_description")

    if oauth_error:
        _clear_google_pkce()
        st.query_params.clear()
        st.error(
            f"Google/Supabase ha annullato il login: "
            f"{oauth_error_description or oauth_error}"
        )
        return False

    if not auth_code:
        return False

    verifier = _read_cookie(GOOGLE_PKCE_COOKIE)

    if not verifier:
        st.query_params.clear()
        st.error(
            "Il callback Google è arrivato, ma il verifier PKCE non è più "
            "disponibile. Riprova il login."
        )
        return False

    try:
        response = requests.post(
            f"{SUPABASE_URL}/auth/v1/token?grant_type=pkce",
            headers={
                "apikey": SUPABASE_KEY,
                "Content-Type": "application/json",
            },
            json={
                "auth_code": str(auth_code),
                "code_verifier": verifier,
            },
            timeout=20,
        )

        if not response.ok:
            try:
                detail = response.json()
            except Exception:
                detail = response.text[:500]

            raise RuntimeError(
                f"Token exchange HTTP {response.status_code}: {detail}"
            )

        payload = response.json()
        access_token = payload.get("access_token")
        refresh_token = payload.get("refresh_token")

        if not access_token or not refresh_token:
            raise RuntimeError(
                "Supabase non ha restituito access_token e refresh_token."
            )

        auth_response = supabase.auth.set_session(
            access_token,
            refresh_token,
        )

        save_authenticated_session(auth_response)
        _clear_google_pkce()
        st.query_params.clear()
        st.rerun()
        return True

    except Exception as e:
        _clear_google_pkce()
        st.query_params.clear()
        st.error(f"Login Google fallito: {e}")
        return False


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

def save_authenticated_session(response):
    session = getattr(response, "session", None)
    user_obj = getattr(response, "user", None)

    if session is None:
        raise RuntimeError("Supabase non ha restituito una sessione valida.")
    if user_obj is None:
        user_obj = getattr(session, "user", None)
    if user_obj is None:
        raise RuntimeError("Supabase non ha restituito l'utente autenticato.")
    if not getattr(session, "refresh_token", None):
        raise RuntimeError("Supabase non ha restituito il refresh token.")

    st.session_state["user"] = user_obj
    _cookie_set(SESSION_COOKIE, session.refresh_token, SESSION_COOKIE_MAX_AGE)
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

def show_login_page():
    st.title("SanoSync")
    st.caption("Accedi con Google oppure usa email e password.")

    try:
        google_login_button()
        st.caption(
            "Il login Google viene aperto nella stessa scheda; il verifier PKCE "
            "viene salvato nel browser prima del redirect."
        )
    except Exception as e:
        st.error(f"Impossibile inizializzare Google Login: {e}")

    st.markdown("---")

    auth_mode = st.radio(
        "Account",
        ["Login", "Registrazione"],
        horizontal=True,
    )

    with st.form("auth_form"):
        email = st.text_input("Email")
        password = st.text_input(
            "Password (min. 6 caratteri)",
            type="password",
        )

        display_name_input = ""
        target_weight = None
        height = None
        current_weight = None
        gender = None

        if auth_mode == "Registrazione":
            st.markdown("#### 📋 Parametri Fisici Iniziali")
            display_name_input = st.text_input("Display Name", value="")
            gender = st.selectbox(
                "Genere",
                ["Uomo", "Donna"],
                index=None,
                placeholder="Seleziona genere...",
            )
            height = st.number_input(
                "Altezza (cm)",
                value=175.0,
                min_value=100.0,
                max_value=250.0,
                step=1.0,
            )
            current_weight = st.number_input(
                "Peso Attuale (kg)",
                value=80.0,
                min_value=20.0,
                max_value=300.0,
                step=0.5,
            )
            target_weight = st.number_input(
                "Peso Obiettivo (kg)",
                value=75.0,
                min_value=20.0,
                max_value=300.0,
                step=0.5,
            )

        submit_label = "Accedi" if auth_mode == "Login" else "Registrati"
        submitted = st.form_submit_button(
            submit_label,
            use_container_width=True,
        )

        if submitted:
            try:
                if auth_mode == "Login":
                    if not email.strip() or not password:
                        st.warning("Inserisci email e password.")
                    else:
                        response = supabase.auth.sign_in_with_password({
                            "email": email.strip(),
                            "password": password,
                        })

                        if response and response.session:
                            save_authenticated_session(response)
                            _clear_google_pkce()
                            st.success("✅ Login effettuato.")
                            st.rerun()
                        else:
                            st.error("Credenziali non valide.")

                else:
                    if not email.strip() or len(password) < 6:
                        st.warning(
                            "Inserisci una email valida e una password "
                            "di almeno 6 caratteri."
                        )
                    elif not height or not current_weight or not target_weight or not gender:
                        st.warning("Compila tutti i parametri fisici.")
                    else:
                        calculated_bmr = calculate_bmr(
                            current_weight,
                            height,
                            gender,
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
                                    "bmr": calculated_bmr,
                                    "height": float(height),
                                    "gender": gender,
                                }
                            },
                        })

                        # Se la conferma email è disabilitata, Supabase può già
                        # restituire una sessione.
                        if response and getattr(response, "session", None):
                            save_authenticated_session(response)
                            st.success(
                                "✅ Account creato e accesso effettuato."
                            )
                            st.rerun()
                        else:
                            st.success(
                                "✅ Account creato. Controlla l'email se è "
                                "richiesta la conferma, poi effettua il login."
                            )

            except Exception as e:
                st.error(
                    f"Errore durante l'autenticazione: {str(e)}"
                )
                print(traceback.format_exc())


# ==============================================================================
# 5. RESTORE SESSION / GOOGLE CALLBACK
# ==============================================================================
# Il callback OAuth viene gestito prima del restore normale della sessione.
if st.session_state.get("user") is None and (
    st.query_params.get("code") or st.query_params.get("error")
):
    handle_google_oauth_callback()

# A ogni refresh del browser Streamlit ricrea session_state. Prima di mostrare
# il login proviamo quindi a ricostruire la sessione dal refresh token salvato
# nel cookie persistente.
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

display_name = u_meta.get("display_name") or user.email.split("@")[0] or "User"
user_target_weight = u_meta.get("target_weight")
user_bmr = u_meta.get("bmr")
user_height = u_meta.get("height")
user_gender = u_meta.get("gender")

# ==============================================================================
# 7. PROFILE COMPLETION CHECK
# ==============================================================================
profile_incomplete = (
    user_target_weight is None or 
    user_bmr is None or 
    user_height is None or 
    user_gender is None
)

if profile_incomplete:
    st.warning("⚠️ Per iniziare, configura i tuoi dati.")
    with st.form("missing_data_form"):
        st.subheader("📋 Configurazione Profilo")
        gen = st.selectbox("Genere", ["Uomo", "Donna"], index=0 if user_gender is None else (0 if user_gender == "Uomo" else 1))
        h_val = st.number_input("Altezza (cm)", value=float(user_height) if user_height else 175.0, min_value=100.0, max_value=250.0, step=1.0)
        w_val = st.number_input("Peso Attuale (kg)", value=float(user_target_weight) if user_target_weight else 80.0, min_value=20.0, max_value=300.0, step=0.5)
        t_val = st.number_input("Peso Obiettivo (kg)", value=float(user_target_weight) if user_target_weight else 75.0, min_value=20.0, max_value=300.0, step=0.5)
        
        if st.form_submit_button("Salva e Inizia"):
            calculated_bmr = calculate_bmr(w_val, h_val, gen)
            try:
                res = supabase.auth.update_user({"data": {
                    "target_weight": float(t_val),
                    "bmr": calculated_bmr,
                    "height": float(h_val),
                    "gender": gen
                }})
                if hasattr(res, 'user') and res.user:
                    st.session_state["user"] = res.user
                st.success("✅ Profilo aggiornato!")
                st.rerun()
            except Exception as e:
                st.error(f"Errore: {e}")
                print(traceback.format_exc())
    st.stop()

# ==============================================================================
# 8. NAVIGATION & LANGUAGE
# ==============================================================================
translations = {
    "Italiano": {
        "t1": "🚀 Inserimento", 
        "t2": "📊 Panoramica", 
        "t3": "📈 Peso", 
        "t4": "⚡ Immissione Rapida", 
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
        "opt_quick": "🍳 Immissione Rapida",
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
        "t4": "⚡ Quick Entries", 
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
        "opt_quick": "🍳 Quick Entry",
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
        "t4": "⚡ Snelle Invoer", 
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
        "opt_quick": "🍳 Snelle Invoer",
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

with st.sidebar:
    # --- INSERIMENTO LOGO ---
    st.sidebar.image("https://inhmvbdujpxrqrlcgmqw.supabase.co/storage/v1/object/sign/public-assets/logo2.png?token=eyJraWQiOiJzdG9yYWdlLXVybC1zaWduaW5nLWtleV9jZTZjYWVhZi00MTYxLTQyYzctODliZS05ODY1ZGZiMzFlN2EiLCJhbGciOiJIUzI1NiJ9.eyJ1cmwiOiJwdWJsaWMtYXNzZXRzL2xvZ28yLnBuZyIsInNjb3BlIjoiZG93bmxvYWQiLCJpYXQiOjE3ODY1NjA3MjAsImV4cCI6MTgxODA5NjcyMH0.jrnw8BnoiAmsuywkaLe5Uk1ruiHpEjF4nxNnrJyF3s4", use_container_width=True)
    st.markdown("---") # Linea di separazione dopo il logo
    current_lang = st.selectbox("🌐 Lingua", ["Italiano", "English", "Nederlands"], key="lang_selector")
    t = translations[current_lang]
    
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
        if st.button(page_name, key=f"nav_{page_id}", use_container_width=True, type="primary" if is_active else "secondary"):
            st.session_state.current_page_id = page_id
            st.rerun()

    selected_page_id = st.session_state.current_page_id
    selected_page = t[selected_page_id]

    st.markdown("---")
    if st.button(t["logout"], use_container_width=True):
        supabase.auth.sign_out()
        _cookie_delete(SESSION_COOKIE)
        st.session_state.clear()
        st.rerun()

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

# 9. PAGE 1: MEAL LOGGING
# ==============================================================================
if selected_page == t["t1"]:
    log_date = st.date_input("📅 Data", value=date.today())
    st.subheader(t["tab1_title"])

    recipe_source_label = {
        "Italiano": "🍲 Ricette",
        "English": "🍲 Recipes",
        "Nederlands": "🍲 Recepten",
    }.get(current_lang, "🍲 Ricette")

    input_source = st.radio(
        t["input_source_lbl"],
        [t["opt_off"], t["opt_quick"], recipe_source_label],
        horizontal=True,
    )

    is_online = input_source == t["opt_off"]
    is_quick = input_source == t["opt_quick"]
    is_recipe = input_source == recipe_source_label
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

    if st.session_state.get("last_source") != input_source:
        st.session_state["last_source"] = input_source
        reset_or_update()
        st.rerun()

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
                    st.info("Nessun prodotto trovato. Prova marca + nome oppure un codice a barre.")
                st.rerun()
            else:
                st.warning("Inserisci almeno 2 caratteri o un codice a barre valido.")

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
            if quick_entries:
                quick_by_label = {q["label"]: q for q in quick_entries}
                sel_quick = st.selectbox(
                    "Seleziona un alimento già utilizzato",
                    [""] + list(quick_by_label.keys()),
                    key=f"quick_meal_select_{v}",
                )
                if sel_quick and sel_quick != st.session_state.get("last_selected"):
                    q = quick_by_label[sel_quick]
                    reset_or_update(
                        q["name"], q["calories"], q["protein"], q["carbs"], q["fat"],
                        sel_quick, q["default_quantity"], q["is_per_100g"], q.get("notes", ""), q.get("category", "Casa"),
                    )
                    st.rerun()
            else:
                st.info("Nessun alimento ancora disponibile. Registra prima un pasto nella Tab 1.")
        except Exception as e:
            st.error(f"Errore nel caricamento delle immissioni rapide: {e}")

    # ------------------------------------------------------------------
    # C. Ricette = meals composti da ingredienti (un solo database)
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
                    is_100g = bool(r.get("is_per_100g", True))
                    reset_or_update(
                        sel_recipe,
                        _safe_float(r.get("base_calories") if r.get("base_calories") is not None else r.get("calories")),
                        _safe_float(r.get("base_protein") if r.get("base_protein") is not None else r.get("protein")),
                        _safe_float(r.get("base_carbs") if r.get("base_carbs") is not None else r.get("carbs")),
                        _safe_float(r.get("base_fat") if r.get("base_fat") is not None else r.get("fat")),
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

    st.markdown("---")
    meal_options = ["Colazione", "Pranzo", "Cena", "Snack"]
    m_type = st.selectbox(t["meal"], meal_options, key=f"meal_type_input_{v}")
    name = st.text_input(t["meal_name"], value=st.session_state["m_name"], key=f"input_meal_name_{v}")

    default_category = st.session_state.get("selected_source_category", "Casa")
    if default_category not in MEAL_CATEGORIES:
        default_category = "Casa"
    meal_category = st.selectbox(
        "Categoria",
        MEAL_CATEGORIES,
        index=MEAL_CATEGORIES.index(default_category),
        key=f"meal_category_{v}",
        help="Casa = replicabile a casa · Lavoro = pasto aziendale · Ristorante = fuori casa · Una-tantum = evento/non replicabile",
    )

    meal_notes = st.text_area(
        "Note (opzionali)",
        value=st.session_state.get("selected_source_note", ""),
        placeholder="Es. senza lattosio, marca preferita, preparazione, condimenti...",
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

    def on_qty_change():
        st.session_state["grams_val"] = st.session_state.get(f"dyn_qty_{v}", 100.0)

    quantity = st.number_input(
        t["qty_label"] if mode == t["per_100g"] else t["num_portions"],
        value=float(st.session_state["grams_val"]),
        min_value=0.25,
        step=0.25,
        key=f"dyn_qty_{v}",
        on_change=on_qty_change,
    )

    factor = quantity / 100.0 if mode == t["per_100g"] else quantity
    meal_display_name = f"{name} ({quantity}{'g' if mode == t['per_100g'] else ' porz.'})"

    final_cals = int(st.session_state["base_cals"] * factor)
    final_prot = int(st.session_state["base_prot"] * factor)
    final_carbs = int(st.session_state["base_carbs"] * factor)
    final_fat = int(st.session_state["base_fat"] * factor)

    c1, c2, c3, c4 = st.columns(4)
    cals_in = c1.number_input(t["kcal"], value=final_cals, step=1, key=f"meal_kcal_{v}")
    prot_in = c2.number_input(t["pro"], value=final_prot, step=1, key=f"meal_pro_{v}")
    carbs_in = c3.number_input(t["carbs"], value=final_carbs, step=1, key=f"meal_carbs_{v}")
    fat_in = c4.number_input(t["fat"], value=final_fat, step=1, key=f"meal_fat_{v}")

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
                reset_or_update()
                st.success(f"{t['inserted']}: {meal_display_name} ({cals_in} kcal)")
                st.rerun()
            except Exception as e:
                st.error(f"Errore: {e}")

# ==============================================================================
# 10. PAGE 2: DAILY OVERVIEW
# ==============================================================================
elif selected_page == t["t2"]:
    st.subheader(t["daily_summary"])

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
        st.error(f"Errore nel caricamento dati: {e}")
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
    ideal_target_cals = max(0, total_estimated_burned - 500)
    diff_from_ideal = ideal_target_cals - total_cals_in

    coral_light_bg, coral_border = "#FFF5F5", "#FF8B8B"
    in_msg = t["in_msg_deficit"](int(ideal_target_cals), int(diff_from_ideal))
    burn_msg = t["burn_msg_yes"](int(extra_burned)) if extra_burned > 0 else t["burn_msg_no"]

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
            .custom-card-caption {{ font-size: .82rem; color: #555; line-height: 1.35; }}
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
            st.markdown("### 🧭 Piano della giornata")

            plan_day_label = st.selectbox("Giorno da pianificare", ["Oggi", "Domani"], index=0, key="overview_plan_day")
            plan_date = date.today() if plan_day_label == "Oggi" else (date.today() + pd.Timedelta(days=1)).date()
            if now.hour < 12:
                st.info("Buongiorno! Imposta il tipo di giornata e il livello di attività previsto per pianificare i pasti.")
            else:
                st.caption("Puoi aggiornare il piano della giornata anche dopo la mattina.")

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

            day_types = ["Lavoro da casa", "Ufficio", "Giornata libera"]
            activity_types = ["Riposo", "Moderatamente attiva", "Attiva"]

            default_day = saved_day_type or st.session_state.get("day_plan_type", "Lavoro da casa")
            default_activity = saved_activity or st.session_state.get("day_plan_activity", "Riposo")
            if default_day not in day_types: default_day = day_types[0]
            if default_activity not in activity_types: default_activity = activity_types[0]

            pc1, pc2 = st.columns(2)
            with pc1:
                day_type = st.selectbox("Tipo di giornata", day_types, index=day_types.index(default_day), key=f"overview_day_type_{plan_date}")
            with pc2:
                activity_plan = st.selectbox("Attività prevista", activity_types, index=activity_types.index(default_activity), key=f"overview_activity_plan_{plan_date}")

            st.session_state["day_plan_type"] = day_type
            st.session_state["day_plan_activity"] = activity_plan

            if st.button("💾 Salva piano della giornata", key="save_day_plan", use_container_width=True):
                try:
                    existing = supabase.table("daily_logs").select("id").eq("user_id", user_id).eq("date", str(plan_date)).execute().data or []
                    payload_plan = {"day_type": day_type, "activity_plan": activity_plan}
                    if existing:
                        supabase.table("daily_logs").update(payload_plan).eq("id", existing[0]["id"]).execute()
                    else:
                        supabase.table("daily_logs").insert({"user_id": user_id, "date": str(plan_date), **payload_plan}).execute()
                    st.success(f"✅ Piano salvato per {plan_date.strftime('%d/%m/%Y')}.")
                except Exception:
                    st.info("Il piano resta attivo in questa sessione. Esegui la migrazione SQL aggiornata per renderlo persistente.")

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
            calories_already_logged = sum(_safe_float(m.get("calories")) for m in plan_meals)

            # Se oggi il pranzo è già loggato, suggeriamo esclusivamente la cena.
            if is_today_plan and lunch_logged:
                dinner_target = max(0.0, daily_budget - calories_already_logged)
                st.markdown(
                    f"**Budget stimato:** {daily_budget:.0f} kcal · "
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
                        f"🍽️ **Cena suggerita:** {html.escape(dinner['name'])} — "
                        f"**{dinner['calories']:.0f} kcal** · {dinner['category']} "
                        f"{info_badge(dinner.get('notes'), 'Note cena')}",
                        unsafe_allow_html=True,
                    )
                else:
                    st.caption("Nessuna cena replicabile nello storico abbastanza vicina al target.")

            elif day_type == "Ufficio":
                fixed_kcal = 1260.0
                dinner_target = max(0.0, daily_budget - fixed_kcal)
                st.markdown(
                    f"**Budget stimato:** {daily_budget:.0f} kcal · "
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
                        f"Pranzo ufficio nello storico: {office_lunch['name']} "
                        f"({office_lunch['calories']:.0f} kcal)."
                    )

                dinner = closest_logged_meal(
                    "Cena",
                    dinner_target,
                    allowed_categories={"Casa", "Ristorante"},
                )
                if dinner:
                    st.markdown(
                        f"🍽️ **Cena suggerita:** {html.escape(dinner['name'])} — "
                        f"circa **{dinner['calories']:.0f} kcal** · {dinner['category']} "
                        f"{info_badge(dinner.get('notes'), 'Note cena')}",
                        unsafe_allow_html=True,
                    )
                else:
                    st.caption("Non ho ancora abbastanza cene replicabili nello storico.")

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
                    f"**Budget stimato:** {daily_budget:.0f} kcal · "
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
                            f"🥗 **Pranzo suggerito**<br>{html.escape(lunch['name'])} · "
                            f"**{lunch['calories']:.0f} kcal** · {lunch['category']} "
                            f"{info_badge(lunch.get('notes'), 'Note pranzo')}",
                            unsafe_allow_html=True,
                        )
                    else:
                        st.caption("Nessun pranzo Casa replicabile disponibile nello storico.")
                with sc2:
                    if dinner:
                        st.markdown(
                            f"🍽️ **Cena suggerita**<br>{html.escape(dinner['name'])} · "
                            f"**{dinner['calories']:.0f} kcal** · {dinner['category']} "
                            f"{info_badge(dinner.get('notes'), 'Note cena')}",
                            unsafe_allow_html=True,
                        )
                    else:
                        st.caption("Nessuna cena replicabile disponibile nello storico.")

            st.caption("Per la pianificazione uso +0 kcal (riposo), +500 kcal (moderatamente attiva), +1000 kcal (attiva). La soglia osservata nel grafico resta: riposo <300 kcal extra, attività intensa ≥800 kcal.")

    st.markdown("<br>", unsafe_allow_html=True)

    with st.container(border=True):
        st.markdown(f"### {t['logged_foods']}")
        if meals_data:
            try:
                meals_with_id = supabase.table("meals").select("id, meal_type, name, calories, protein, carbs, fat, notes, category").eq("date", str(summary_date)).eq("user_id", user_id).execute().data or []
            except Exception:
                meals_with_id = supabase.table("meals").select("id, meal_type, name, calories, protein, carbs, fat").eq("date", str(summary_date)).eq("user_id", user_id).execute().data or []

            df_meals = pd.DataFrame(meals_with_id)
            df_display = df_meals.rename(columns={
                "meal_type": "Pasto", "name": "Nome", "calories": "Kcal",
                "protein": "Pro (g)", "carbs": "Carbs (g)", "fat": "Fat (g)", "category": "Categoria",
            })
            df_display["Categoria"] = [infer_meal_category(m) for m in meals_with_id]
            st.dataframe(
                df_display[["Pasto", "Categoria", "Nome", "Kcal", "Pro (g)", "Carbs (g)", "Fat (g)"]],
                use_container_width=True,
                hide_index=True,
            )

            meal_by_id = {m["id"]: m for m in meals_with_id}
            meal_options = {
                m["id"]: f"{m.get('meal_type', '')} - {m.get('name', '')} ({m.get('calories', 0)} kcal)"
                for m in meals_with_id
            }
            selected_meal_id = st.selectbox(
                "🍽️ Seleziona il pasto da modificare",
                options=[""] + list(meal_options),
                format_func=lambda meal_id: "Seleziona un pasto..." if meal_id == "" else meal_options[meal_id],
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

                edit_col1, edit_col2, edit_col3 = st.columns([2, 2, 1])
                with edit_col1:
                    new_meal_type = st.selectbox(
                        "Tipo di pasto",
                        meal_types,
                        index=current_index,
                        key=f"edit_meal_type_{selected_meal_id}_{summary_date}",
                    )
                with edit_col2:
                    new_meal_category = st.selectbox(
                        "Categoria",
                        MEAL_CATEGORIES,
                        index=MEAL_CATEGORIES.index(current_category),
                        key=f"edit_meal_category_{selected_meal_id}_{summary_date}",
                    )
                with edit_col3:
                    st.markdown("<br>", unsafe_allow_html=True)
                    save_meal_type = st.button(
                        "💾 Salva",
                        use_container_width=True,
                        key=f"save_meal_type_{selected_meal_id}_{summary_date}",
                    )

                if save_meal_type:
                    try:
                        supabase.table("meals").update({
                            "meal_type": new_meal_type,
                            "category": new_meal_category,
                        }).eq("id", selected_meal_id).eq("user_id", user_id).execute()
                        st.success(
                            f"✅ Pasto aggiornato: **{new_meal_type} · {new_meal_category}**."
                        )
                        st.rerun()
                    except Exception as e:
                        st.error(f"Errore nella modifica del pasto: {e}")

                st.markdown("---")
                delete_col1, delete_col2 = st.columns([3, 1])
                with delete_col1:
                    st.caption(f"Elimina definitivamente **{selected_meal.get('name', 'questo pasto')}** se non vuoi più conservarlo.")
                with delete_col2:
                    if st.button(t["del_meal_btn"], key=f"delete_meal_{selected_meal_id}_{summary_date}", use_container_width=True):
                        try:
                            supabase.table("meals").delete().eq("id", selected_meal_id).eq("user_id", user_id).execute()
                            st.success(t["meal_del_success"])
                            st.rerun()
                        except Exception as e:
                            st.error(f"Errore nell'eliminazione del pasto: {e}")
        else:
            st.info(t["no_meals"])

    with st.container(border=True):
        st.markdown(t["burned_acts"])
        rows_acts = [{"Attività": "BMR (Base)", "Kcal Bruciate": bmr_so_far}]
        for act in activities_data:
            rows_acts.append({"Attività": act.get("activity_name"), "Kcal Bruciate": act.get("burned_calories")})
        st.dataframe(pd.DataFrame(rows_acts), use_container_width=True, hide_index=True)

# 11. PAGE 3: WEIGHT TRACKING / ANALYTICS
# ==============================================================================
elif selected_page == t["t3"]:
    st.subheader(t["weight_tracking"])

    with st.container(border=True):
        st.markdown("#### ⚖️ Gestione pesi")
        logs_all = (
            supabase.table("daily_logs").select("id, date, weight").eq("user_id", user_id)
            .not_.is_("weight", "null").order("date", desc=True).execute().data or []
        )
        edit_options = {str(r["id"]): f"{r['date']} · {float(r['weight']):.1f} kg" for r in logs_all}

        c1, c2 = st.columns(2)
        with c1:
            w = st.number_input("Nuovo peso (kg)", value=80.0, min_value=20.0, max_value=300.0, step=0.1, key="new_weight_value")
            w_date = st.date_input("Data del peso", value=date.today(), key="new_weight_date")
            if st.button("💾 Salva peso", use_container_width=True):
                try:
                    supabase.table("daily_logs").upsert(
                        {"user_id": user_id, "date": str(w_date), "weight": float(w)},
                        on_conflict="user_id,date",
                    ).execute()
                    st.success("✅ Peso salvato!")
                    st.rerun()
                except Exception as e:
                    st.error(f"Errore nel salvataggio del peso: {e}")

        with c2:
            selected_weight_id = st.selectbox(
                "Peso da modificare o eliminare",
                [""] + list(edit_options),
                format_func=lambda x: "Seleziona un peso..." if x == "" else edit_options[x],
                key="weight_edit_selector",
            )
            if selected_weight_id:
                selected_row = next(r for r in logs_all if str(r["id"]) == selected_weight_id)
                ew1, ew2 = st.columns(2)
                with ew1:
                    edited_date = st.date_input("Data", value=pd.to_datetime(selected_row["date"]).date(), key=f"edit_weight_date_{selected_weight_id}")
                with ew2:
                    edited_weight = st.number_input("Peso (kg)", value=float(selected_row["weight"]), min_value=20.0, max_value=300.0, step=0.1, key=f"edit_weight_value_{selected_weight_id}")
                b1, b2 = st.columns(2)
                with b1:
                    if st.button("✏️ Modifica peso", use_container_width=True, key=f"update_weight_{selected_weight_id}"):
                        try:
                            if str(edited_date) != str(selected_row["date"]):
                                supabase.table("daily_logs").delete().eq("id", selected_row["id"]).eq("user_id", user_id).execute()
                                supabase.table("daily_logs").upsert(
                                    {"user_id": user_id, "date": str(edited_date), "weight": float(edited_weight)},
                                    on_conflict="user_id,date",
                                ).execute()
                            else:
                                supabase.table("daily_logs").update({"weight": float(edited_weight)}).eq("id", selected_row["id"]).eq("user_id", user_id).execute()
                            st.success("✅ Peso modificato!")
                            st.rerun()
                        except Exception as e:
                            st.error(f"Errore nella modifica: {e}")
                with b2:
                    if st.button("🗑️ Cancella peso", use_container_width=True, key=f"delete_weight_{selected_weight_id}"):
                        try:
                            # Non cancelliamo l'intera riga se contiene passi o piano giornata:
                            # azzeriamo solo weight. Se la riga ha solo il peso, Supabase
                            # conserverà una riga innocua con weight NULL.
                            supabase.table("daily_logs").update({"weight": None}).eq("id", selected_row["id"]).eq("user_id", user_id).execute()
                            st.success("✅ Peso cancellato.")
                            st.rerun()
                        except Exception as e:
                            st.error(f"Errore nella cancellazione: {e}")

    with st.container(border=True):
        st.markdown(f"#### {t['update_target']}")
        new_target = st.number_input(
            "Peso Obiettivo (kg)",
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
        ratio_caption = "Servono almeno due pesi e dati alimentari nell'ultimo mese."
        if weight_lost_30 is not None and weight_lost_30 > 0 and valid_deficit_days > 0:
            kcal_per_kg = total_deficit_30 / weight_lost_30
            ratio_text = f"{kcal_per_kg:,.0f} kcal/kg".replace(",", ".")
            ratio_caption = f"{total_deficit_30:.0f} kcal di deficit / {weight_lost_30:.1f} kg persi."
        elif weight_lost_30 is not None and weight_lost_30 <= 0:
            ratio_caption = "Nessuna perdita di peso misurata negli ultimi 30 giorni."

        lost_text = "N/D" if weight_lost_30 is None else f"{weight_lost_30:+.1f} kg"
        lost_caption = "Differenza tra la prima e l'ultima misurazione degli ultimi 30 giorni."

        goal_date_text = "N/D"
        goal_caption = "Serve un deficit medio positivo per stimare la data obiettivo."
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
                goal_date_text = "Raggiunto 🎯"
                goal_caption = "Il peso più recente è già pari o inferiore all'obiettivo."
            elif avg_daily_deficit_30 is not None and avg_daily_deficit_30 > 0:
                days_needed = int(__import__("math").ceil((kg_remaining * 7700.0) / avg_daily_deficit_30))
                projected_date = date.today() + pd.Timedelta(days=days_needed)
                goal_date_text = projected_date.strftime("%d/%m/%Y")
                goal_caption = f"Stima basata su {avg_daily_deficit_30:.0f} kcal/giorno di deficit medio ({valid_deficit_days} giorni loggati)."

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
            st.markdown(f'<div class="custom-card"><div class="custom-card-title">📉 Peso perso · 30 giorni</div><div class="custom-card-value">{lost_text}</div><div class="custom-card-caption">{lost_caption}</div></div>', unsafe_allow_html=True)
        with wk2:
            st.markdown(f'<div class="custom-card"><div class="custom-card-title">⚡ Deficit / kg perso</div><div class="custom-card-value">{ratio_text}</div><div class="custom-card-caption">{ratio_caption}</div></div>', unsafe_allow_html=True)
        with wk3:
            st.markdown(f'<div class="custom-card"><div class="custom-card-title">🎯 Data obiettivo stimata</div><div class="custom-card-value">{goal_date_text}</div><div class="custom-card-caption">{goal_caption}</div></div>', unsafe_allow_html=True)
        st.markdown("<br>", unsafe_allow_html=True)
    except Exception as e:
        st.warning(f"Impossibile calcolare le statistiche mensili: {e}")

    with st.container(border=True):
        try:
            ctrl1, ctrl2 = st.columns(2)
            with ctrl1:
                chart_mode = st.selectbox(
                    "Visualizzazione",
                    ["Peso", "Kcal", "Macros", "Pasti"],
                    index=0,
                    key="main_analytics_mode",
                )
            with ctrl2:
                period_options = {"7 giorni": 7, "14 giorni": 14, "30 giorni": 30, "60 giorni": 60, "90 giorni": 90}
                selected_period_label = st.selectbox(
                    "Periodo",
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

            if chart_mode == "Peso":
                if not df_weight.empty:
                    fig.add_trace(go.Scatter(
                        x=df_weight["date"], y=df_weight["weight"],
                        mode="lines+markers", name="Peso reale",
                        line=dict(color="#FF8B8B", width=3),
                        marker=dict(size=8, color="#FF8B8B"),
                        hovertemplate="<b>%{x|%d %b %Y}</b><br>Peso: <b>%{y:.1f} kg</b><extra></extra>",
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
                            name="Proiezione",
                            line=dict(color="#FF8B8B", width=2.5, dash="dash"),
                            hovertemplate="<b>Trend</b><br>%{x|%d %b}<br>%{y:.1f} kg<extra></extra>",
                        ))

                    fig.add_trace(go.Scatter(
                        x=[chart_start, chart_end], y=[target_val, target_val],
                        mode="lines", name="Obiettivo",
                        line=dict(color="#1A2942", width=2.5),
                        hovertemplate=f"Obiettivo: {target_val:.1f} kg<extra></extra>",
                    ))

                    visible_values = df_weight["weight"].tolist() + [target_val]
                    y_min, y_max = min(visible_values), max(visible_values)
                    spread = max(y_max - y_min, 1.0)
                    pad = max(.5, spread * .18)
                    fig.update_yaxes(range=[y_min - pad, y_max + pad])
                else:
                    st.info(f"Nessun peso registrato negli ultimi {selected_days} giorni.")
                y_title = "Peso (kg)"

            elif chart_mode == "Kcal":
                fig.add_trace(go.Bar(
                    x=days_df["date"], y=days_df["calories"],
                    name="Kcal ingerite", marker_color="#FF8B8B",
                    hovertemplate="%{x|%d %b}<br>Ingerite: %{y:.0f} kcal<extra></extra>",
                ))
                fig.add_trace(go.Bar(
                    x=days_df["date"], y=days_df["burned"],
                    name="Kcal bruciate", marker_color="#1A2942",
                    hovertemplate="%{x|%d %b}<br>Bruciate: %{y:.0f} kcal<extra></extra>",
                ))
                fig.update_layout(barmode="group")
                y_title = "kcal"

            elif chart_mode == "Macros":
                macro_specs = [
                    ("protein", "Proteine", "#FF8B8B"),
                    ("carbs", "Carboidrati", "#1A2942"),
                    ("fat", "Grassi", "#FFB4B4"),
                ]
                for col, label, color in macro_specs:
                    fig.add_trace(go.Bar(
                        x=days_df["date"], y=days_df[col], name=label, marker_color=color,
                        hovertemplate=f"%{{x|%d %b}}<br>{label}: %{{y:.1f}} g<extra></extra>",
                    ))
                fig.update_layout(barmode="stack")
                y_title = "grammi"

            else:  # Pasti
                meal_order = ["Colazione", "Pranzo", "Snack", "Cena"]
                meal_colors = ["#FF8B8B", "#1A2942", "#FFB4B4", "#667085"]
                for meal_type, color in zip(meal_order, meal_colors):
                    if meals_df.empty:
                        vals = [0.0] * len(days_df)
                    else:
                        series = meals_df[meals_df["meal_type"] == meal_type].groupby("date")["calories"].sum()
                        vals = [float(series.get(d, 0)) for d in days_df["date"]]
                    fig.add_trace(go.Bar(
                        x=days_df["date"], y=vals, name=meal_type, marker_color=color,
                        hovertemplate=f"%{{x|%d %b}}<br>{meal_type}: %{{y:.0f}} kcal<extra></extra>",
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
                    deficit_icon, deficit_tip = "·", "Nessun dato alimentare"
                else:
                    daily_def = float(user_bmr) + extra - kcal_in
                    if daily_def >= 500:
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
                'Dettagli: 👍 deficit ≥500 · 😐 deficit 0–499 · 👎 surplus &nbsp;|&nbsp; 🎾 Padel · 🔥 extra >300 · 🛏️ extra ≤300'
                '</div>'
                f'<div style="display:flex;gap:2px;min-width:{max(100, len(detail_cells)*50)}px;">'
                + "".join(detail_cells) +
                '</div></div>'
            )
            st.markdown(timeline_html, unsafe_allow_html=True)

        except Exception as e:
            st.error(f"Errore nel caricamento del grafico: {e}")
            print(traceback.format_exc())

# 12. PAGE 4: RICETTE / MEAL COMPOSTI
# ==============================================================================
elif selected_page == t["t4"]:
    st.subheader("🍲 Ricette")
    st.caption(
        "Le ricette non usano più una tabella separata: sono normali record di `meals` "
        "con gli ingredienti salvati in `ingredients_json`. Quick Entry, Ricette e suggerimenti "
        "usano quindi lo stesso database."
    )

    if "recipe_form_version" not in st.session_state:
        st.session_state["recipe_form_version"] = 0
    v = st.session_state["recipe_form_version"]

    with st.container(border=True):
        st.markdown("### 📋 Ricette disponibili")
        try:
            recipe_meals = (
                supabase.table("meals")
                .select(
                    "id,date,meal_type,category,name,base_name,calories,protein,carbs,fat,"
                    "base_calories,base_protein,base_carbs,base_fat,notes,ingredients_json"
                )
                .eq("user_id", user_id)
                .order("date", desc=True)
                .execute().data
                or []
            )
        except Exception:
            recipe_meals = []

        recipe_meals = [r for r in recipe_meals if r.get("ingredients_json")]

        if recipe_meals:
            display_rows = []
            seen_names = set()
            for r in recipe_meals:
                label = (r.get("base_name") or _clean_meal_name(r.get("name")) or "Ricetta").strip()
                key = label.casefold()
                if key in seen_names:
                    continue
                seen_names.add(key)
                display_rows.append({
                    "Nome": label,
                    "Pasto": r.get("meal_type"),
                    "Categoria": infer_meal_category(r),
                    "Kcal": r.get("calories"),
                    "Pro (g)": r.get("protein"),
                    "Carbs (g)": r.get("carbs"),
                    "Fat (g)": r.get("fat"),
                    "Data": r.get("date"),
                })
            st.dataframe(pd.DataFrame(display_rows), use_container_width=True, hide_index=True)

            for r in recipe_meals:
                if r.get("notes"):
                    label = r.get("base_name") or _clean_meal_name(r.get("name"))
                    st.markdown(
                        f"**{html.escape(str(label or 'Ricetta'))}** "
                        f"{info_badge(r.get('notes'), 'Note ricetta')}",
                        unsafe_allow_html=True,
                    )
        else:
            st.info("Nessuna ricetta composta presente in meals.")

    with st.container(border=True):
        st.markdown("### ➕ Crea un meal da ingredienti")

        rc1, rc2, rc3 = st.columns(3)
        with rc1:
            recipe_log_date = st.date_input(
                "Data",
                value=date.today(),
                key=f"recipe_meal_date_{v}",
            )
        with rc2:
            recipe_meal_type = st.selectbox(
                "Tipo di pasto",
                ["Colazione", "Pranzo", "Cena", "Snack"],
                key=f"recipe_meal_type_{v}",
            )
        with rc3:
            recipe_category = st.selectbox(
                "Categoria",
                MEAL_CATEGORIES,
                index=0,
                key=f"recipe_category_{v}",
                help="Una-tantum non entra nei suggerimenti. Ristorante non viene mai suggerito a pranzo.",
            )

        r_name = st.text_input(
            "Nome",
            placeholder="Es. Pasta al pomodoro",
            key=f"recipe_builder_name_{v}",
        )
        r_notes = st.text_area(
            "Note (opzionali)",
            placeholder="Es. preparazione, sostituzioni, condimenti...",
            key=f"recipe_builder_notes_{v}",
            height=90,
        )

        st.markdown("#### 🥕 Aggiungi ingrediente")
        source = st.radio(
            "Fonte ingrediente",
            ["Database / Open Food Facts", "Inserimento manuale"],
            horizontal=True,
            key=f"ingredient_source_{v}",
        )

        ingredient_name = ""
        base = {"calories": 0.0, "protein": 0.0, "carbs": 0.0, "fat": 0.0}

        if source.startswith("Database"):
            iq = st.text_input("Cerca ingrediente", key=f"ingredient_search_{v}")
            if st.button("🔍 Cerca ingrediente", key=f"ingredient_search_btn_{v}"):
                if len(iq.strip()) >= 2 or iq.strip().isdigit():
                    with st.spinner("Ricerca ingrediente..."):
                        st.session_state[f"ingredient_results_{v}"] = search_open_food_facts(iq)
                    st.rerun()
                else:
                    st.warning("Inserisci almeno 2 caratteri.")

            results = st.session_state.get(f"ingredient_results_{v}", {})
            if results:
                sel = st.selectbox(
                    "Risultati",
                    [""] + list(results),
                    key=f"ingredient_result_select_{v}",
                )
                if sel:
                    p_data = results[sel]
                    ingredient_name = p_data.get("name", sel)
                    base = {k: float(p_data.get(k, 0) or 0) for k in base}
                    st.caption(
                        f"Per 100g: {base['calories']:.0f} kcal · "
                        f"Pro {base['protein']:.1f} g · Carbs {base['carbs']:.1f} g · Fat {base['fat']:.1f} g"
                    )
        else:
            ingredient_name = st.text_input(
                "Nome ingrediente",
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
            "Quantità ingrediente (g)",
            min_value=0.1,
            value=100.0,
            step=1.0,
            key=f"ingredient_qty_{v}",
        )

        if st.button(
            "➕ Aggiungi ingrediente",
            use_container_width=True,
            key=f"add_ingredient_{v}",
        ):
            if not ingredient_name.strip():
                st.warning("Inserisci o seleziona un ingrediente.")
            else:
                st.session_state["recipe_builder_ingredients"].append({
                    "name": ingredient_name.strip(),
                    "quantity_g": float(quantity),
                    "calories_per_100g": float(base["calories"]),
                    "protein_per_100g": float(base["protein"]),
                    "carbs_per_100g": float(base["carbs"]),
                    "fat_per_100g": float(base["fat"]),
                    "source": "database" if source.startswith("Database") else "manual",
                })
                st.success(f"✅ {ingredient_name} aggiunto.")
                st.rerun()

        ingredients = st.session_state.get("recipe_builder_ingredients", [])

        if ingredients:
            st.markdown("#### 📋 Ingredienti")
            rows = []
            for idx, ing in enumerate(ingredients):
                ing_factor = float(ing["quantity_g"]) / 100.0
                rows.append({
                    "#": idx + 1,
                    "Ingrediente": ing["name"],
                    "Quantità (g)": ing["quantity_g"],
                    "Kcal": round(ing["calories_per_100g"] * ing_factor),
                    "Pro": round(ing["protein_per_100g"] * ing_factor, 1),
                    "Carbs": round(ing["carbs_per_100g"] * ing_factor, 1),
                    "Fat": round(ing["fat_per_100g"] * ing_factor, 1),
                })
            st.dataframe(pd.DataFrame(rows), use_container_width=True, hide_index=True)

            remove_idx = st.selectbox(
                "Rimuovi ingrediente",
                [""] + [str(i + 1) for i in range(len(ingredients))],
                key=f"remove_ingredient_{v}",
            )
            if remove_idx and st.button(
                "🗑️ Rimuovi ingrediente",
                key=f"remove_ingredient_btn_{v}",
            ):
                del st.session_state["recipe_builder_ingredients"][int(remove_idx) - 1]
                st.rerun()

            total_weight, totals, per100 = calculate_recipe_totals(ingredients)

            st.markdown(
                f"**Totale meal:** {total_weight:.0f} g · **{totals['calories']:.0f} kcal** · "
                f"Pro {totals['protein']:.1f} g · Carbs {totals['carbs']:.1f} g · Fat {totals['fat']:.1f} g"
            )
            st.caption(
                f"Per 100 g: {per100['calories']:.0f} kcal · "
                f"Pro {per100['protein']:.1f} g · Carbs {per100['carbs']:.1f} g · Fat {per100['fat']:.1f} g"
            )

            if st.button(
                "💾 Salva come meal",
                use_container_width=True,
                key=f"save_recipe_builder_{v}",
            ):
                if not r_name.strip():
                    st.warning("Inserisci un nome.")
                else:
                    try:
                        display_name = f"{r_name.strip()} ({total_weight:.0f}g)"
                        insert_meal_with_base_data(
                            log_date=recipe_log_date,
                            meal_type=recipe_meal_type,
                            display_name=display_name,
                            base_name=r_name.strip(),
                            quantity=total_weight,
                            is_per_100g=True,
                            calories=totals["calories"],
                            protein=totals["protein"],
                            carbs=totals["carbs"],
                            fat=totals["fat"],
                            base_calories=per100["calories"],
                            base_protein=per100["protein"],
                            base_carbs=per100["carbs"],
                            base_fat=per100["fat"],
                            notes=r_notes,
                            category=recipe_category,
                            ingredients_json=ingredients,
                        )
                        refresh_daily_logs(recipe_log_date)
                        st.session_state["recipe_builder_ingredients"] = []
                        st.session_state["recipe_form_version"] += 1
                        st.success("✅ Meal composto salvato in meals!")
                        st.rerun()
                    except Exception as e:
                        st.error(
                            "Impossibile salvare il meal composto. Applica la nuova migrazione SQL "
                            "per aggiungere category e ingredients_json a meals. Errore: " + str(e)
                        )
        else:
            st.info("Aggiungi almeno un ingrediente per costruire il meal.")

# ==============================================================================
# 13. PAGE 5: ACTIVITY & STEPS LOGGING
# ==============================================================================
elif selected_page == t["t5"]:
    st.subheader(t["register_activity"])
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
        move_msg = "🌟 Ottimo! Hai completato un'attività fisica strutturata oggi."
        status_display_text = "🏋️ Attività registrata"
    elif day_steps >= 10000:
        move_msg = t["status_very_active"]
        status_display_text = f"{day_steps} passi"
    elif day_steps >= 5000:
        move_msg = t["status_good"]
        status_display_text = f"{day_steps} passi"
    else:
        move_msg = t["status_lazy"]
        status_display_text = f"{day_steps} passi"

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
            "Somma delle calorie registrate nelle attività della giornata selezionata."
            if total_extra_kcal > 0 else "Nessuna caloria extra registrata per questa giornata."
        )
        st.markdown(
            f'<div class="custom-card"><div class="custom-card-title">🔥 Kcal bruciate extra</div>'
            f'<div class="custom-card-value">{total_extra_kcal} kcal</div>'
            f'<div class="custom-card-caption">{extra_caption}</div></div>',
            unsafe_allow_html=True,
        )

    st.markdown("<br>", unsafe_allow_html=True)
    other_kcal = max(0, total_extra_kcal - steps_kcal - padel_kcal - bike_kcal)
    kc1, kc2, kc3 = st.columns(3)
    with kc1:
        st.markdown(f'<div class="custom-card"><div class="custom-card-title">👣 Passi</div><div class="custom-card-value">{steps_kcal} kcal</div><div class="custom-card-caption">Calorie attribuite ai passi.</div></div>', unsafe_allow_html=True)
    with kc2:
        st.markdown(f'<div class="custom-card"><div class="custom-card-title">🎾 Padel</div><div class="custom-card-value">{padel_kcal} kcal</div><div class="custom-card-caption">Calorie registrate come Padel.</div></div>', unsafe_allow_html=True)
    with kc3:
        bike_caption = f"Bici + E-Bike. Altre attività: {other_kcal} kcal." if other_kcal > 0 else "Somma di Bici ed E-Bike."
        st.markdown(f'<div class="custom-card"><div class="custom-card-title">🚲 Bici</div><div class="custom-card-value">{bike_kcal} kcal</div><div class="custom-card-caption">{bike_caption}</div></div>', unsafe_allow_html=True)

    st.markdown("<br>", unsafe_allow_html=True)

    # 3 Colonne: Passi, Bici (Normale ed Elettrica), Altro
    col_a1, col_a2, col_a3 = st.columns(3)
    
    with col_a1:
        with st.container(border=True):
            st.markdown(f"### {t['steps_title']}")
            new_steps = st.number_input("Totale passi", value=int(day_steps), min_value=0, step=500)
            if st.button(t["update_steps"], use_container_width=True):
                try:
                    existing = supabase.table("daily_logs").select("id").eq("user_id", user_id).eq("date", str(act_date)).execute().data
                    
                    if existing:
                        supabase.table("daily_logs").update({"steps": int(new_steps)}).eq("user_id", user_id).eq("date", str(act_date)).execute()
                    else:
                        supabase.table("daily_logs").insert({"user_id": user_id, "date": str(act_date), "steps": int(new_steps)}).execute()
                    
                    # Se ci sono già altre attività strutturate, i passi non devono generare kcal duplicate (0 kcal dai passi)
                    # Altrimenti stimiamo le kcal dai passi come prima (0.04 kcal per passo)
                    has_other_acts = any(a.get("activity_name") not in ["Passi (Stima)"] for a in day_activities)
                    estim_cals = 0 if has_other_acts else int(new_steps * 0.04)
                    
                    existing_act = supabase.table("activities").select("id").eq("user_id", user_id).eq("date", str(act_date)).eq("activity_name", "Passi (Stima)").execute().data
                    
                    if existing_act:
                        supabase.table("activities").update({"burned_calories": estim_cals}).eq("id", existing_act[0]["id"]).execute()
                    else:
                        supabase.table("activities").insert({"user_id": user_id, "date": str(act_date), "activity_name": "Passi (Stima)", "burned_calories": estim_cals}).execute()
                    
                    refresh_daily_logs(act_date)
                    
                    st.toast(f"✅ Passi aggiornati! ({estim_cals} kcal)", icon="👣")
                    st.success(f"✅ {t['steps_updated']} ({estim_cals} kcal stimate)")
                    st.rerun()
                except Exception as e:
                    st.error(f"Errore nel salvataggio dei passi: {e}")

    with col_a2:
        with st.container(border=True):
            st.markdown("### 🚲 Bici & E-Bike")
            bike_type = st.radio("Tipo Bici", ["Bici Normale", "E-Bike (Elettrica)"], horizontal=True, key=f"bike_type_{act_date}")
            bike_min = st.number_input("Minuti Bici", value=0, min_value=0, step=5, key=f"bike_min_{act_date}")
            
            if st.button("💾 Aggiungi Bici", use_container_width=True):
                if bike_min > 0:
                    if "Elettrica" in bike_type:
                        estim_cals = int(bike_min * 4)  # Stima E-bike: ~4 kcal/min
                        act_label = "Bici Elettrica"
                    else:
                        estim_cals = int(bike_min * 8)  # Stima Bici normale: ~8 kcal/min
                        act_label = "Bici"
                        
                    supabase.table("activities").insert({"user_id": user_id, "date": str(act_date), "activity_name": act_label, "burned_calories": estim_cals}).execute()
                    
                    # Se inseriamo una bici, rimuoviamo o azzeriamo l'impatto dei passi per evitare sovrastima
                    passi_act = supabase.table("activities").select("id").eq("user_id", user_id).eq("date", str(act_date)).eq("activity_name", "Passi (Stima)").execute().data
                    if passi_act:
                        supabase.table("activities").update({"burned_calories": 0}).eq("id", passi_act[0]["id"]).execute()

                    refresh_daily_logs(act_date)
                    
                    st.toast(f"✅ Aggiunti {bike_min} min di {act_label}! ({estim_cals} kcal)", icon="🚲")
                    st.success(f"✅ Aggiunti {bike_min} min di {act_label} ({estim_cals} kcal)!")
                    st.rerun()
                else:
                    st.warning("Inserisci almeno 1 minuto.")

    with col_a3:
        with st.container(border=True):
            st.markdown(f"### {t['other_act']}")
            with st.form("activity_form", clear_on_submit=True):
                extra_act = st.selectbox(t["activity_label"], ["Padel", "Palestra", "Nuoto", "Altro"])
                extra_cals = st.number_input("Kcal bruciate", value=0, min_value=0, step=50)
                
                submitted_act = st.form_submit_button(t["add_act_btn"], use_container_width=True)
                if submitted_act:
                    # Inseriamo l'attività
                    supabase.table("activities").insert({"user_id": user_id, "date": str(act_date), "activity_name": extra_act, "burned_calories": int(extra_cals)}).execute()
                    
                    # Azzeriamo l'impatto dei passi per evitare la sovrastima delle calorie
                    passi_act = supabase.table("activities").select("id").eq("user_id", user_id).eq("date", str(act_date)).eq("activity_name", "Passi (Stima)").execute().data
                    if passi_act:
                        supabase.table("activities").update({"burned_calories": 0}).eq("id", passi_act[0]["id"]).execute()

                    refresh_daily_logs(act_date)
                    
                    # Usiamo st.success e st.toast per garantire il feedback visivo immediato
                    st.toast(f"✅ {extra_act} registrato con successo! ({extra_cals} kcal)", icon="🎯")
                    st.success(f"✅ {extra_act} registrato con successo! ({extra_cals} kcal)")
                    st.rerun()
