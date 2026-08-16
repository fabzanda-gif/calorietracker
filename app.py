import streamlit as st
import pandas as pd
from datetime import date, datetime
import requests
import base64
import secrets
import hashlib
import traceback
import re
import json
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

        /* Pulsanti corpo centrale */
        .main .stButton>button {
            border-radius: 10px;
            background-color: #FFFFFF;
            color: #1A2942;
            border: 1px solid #FF8B8B;
        }
        .main .stButton>button:hover { background-color: #FFF5F5; border-color: #1A2942; }

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
APP_URL = st.secrets.get("APP_URL", "https://diario-alimentare.streamlit.app").rstrip("/")

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
controller = CookieController()

# ==============================================================================
# 2. INITIALIZE SESSION STATE
# ==============================================================================
state_defaults = {
    "user": None,
    "pkce_verifier": None,
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

def search_open_food_facts(query):
    query = query.strip()
    if not query:
        return {}

    try:
        if query.isdigit():
            # Tentativo sul database olandese per codice a barre
            url = f"https://nl.openfoodfacts.org/api/v2/product/{query}.json"
            response = requests.get(url, timeout=10)
            payload = response.json()
            if payload.get("status") != 1:
                # Fallback sul database mondiale
                url_world = f"https://world.openfoodfacts.org/api/v2/product/{query}.json"
                response = requests.get(url_world, timeout=10)
                payload = response.json()
                if payload.get("status") != 1:
                    return {}
            products = [payload.get("product", {})]
        else:
            # Ricerca testuale focalizzata sul mercato olandese (cc=nl)
            url = "https://nl.openfoodfacts.org/cgi/search.pl"
            response = requests.get(
                url, 
                params={
                    "search_terms": query, 
                    "search_simple": 1, 
                    "action": "process", 
                    "json": 1, 
                    "page_size": 20,
                    "cc": "nl"
                }, 
                timeout=10
            )
            products = response.json().get("products", [])

        results = {}
        for p in products:
            name = p.get("product_name", "Prodotto sconosciuto")
            brands = p.get("brands", "")
            full_name = f"{brands} - {name}" if brands else name
            
            nutriscore = p.get("nutriments", {})
            # Estrazione sicura dei macronutrienti per 100g
            cals = nutriscore.get("energy-kcal_100g", nutriscore.get("energy-kcal", 0)) or 0
            prot = nutriscore.get("proteins_100g", 0) or 0
            carbs = nutriscore.get("carbohydrates_100g", 0) or 0
            fat = nutriscore.get("fat_100g", 0) or 0
            
            results[full_name] = {
                "name": full_name,
                "calories": float(cals),
                "protein": float(prot),
                "carbs": float(carbs),
                "fat": float(fat)
            }
        return results

    except Exception as e:
        print(f"Errore nella ricerca Open Food Facts: {e}")
        return {}
        for i, p in enumerate(products):
            name = p.get("product_name") or "Prodotto senza nome"
            nutriments = p.get("nutriments") or {}
            label = f"{name} - {p.get('brands', '')}".strip(" -")
            results[label] = {
                "name": name,
                "calories": nutriments.get("energy-kcal_100g", 0) or 0,
                "protein": nutriments.get("proteins_100g", 0) or 0,
                "carbs": nutriments.get("carbohydrates_100g", 0) or 0,
                "fat": nutriments.get("fat_100g", 0) or 0,
            }
        return results
    except Exception as e:
        st.error(f"Errore nella ricerca: {e}")
        return {}

def save_meal_as_quick_entry(meal_name, calories, protein, carbs, fat):
    """Salva/aggiorna automaticamente un cibo registrato come immissione rapida."""
    try:
        clean_name = re.sub(r"\s*\((?:[0-9]+(?:\.[0-9]+)?)\s*(?:g|porz\.)\)\s*$", "", str(meal_name)).strip()
        if not clean_name:
            clean_name = str(meal_name).strip()
        existing = (
            supabase.table("recipes").select("id").eq("user_id", user_id).eq("name", clean_name)
            .limit(1).execute().data or []
        )
        payload = {
            "name": clean_name,
            "calories": int(round(float(calories))),
            "protein": int(round(float(protein))),
            "carbs": int(round(float(carbs))),
            "fat": int(round(float(fat))),
            "is_per_100g": 0,
            "user_id": user_id,
        }
        if existing:
            supabase.table("recipes").update(payload).eq("id", existing[0]["id"]).eq("user_id", user_id).execute()
        else:
            supabase.table("recipes").insert(payload).execute()
        return True
    except Exception as e:
        print(f"Auto-salvataggio quick entry fallito: {e}")
        return False

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
# Il cookie viene usato come "remember me". Il refresh token di Supabase è
# normalmente di lunga durata; il cookie dura 10 anni, ma può comunque essere
# cancellato dal browser, dal logout o se Supabase invalida il refresh token.
SESSION_COOKIE = "supabase_session"
PKCE_COOKIE = "pkce_verifier_cookie"
SESSION_COOKIE_MAX_AGE = 10 * 365 * 24 * 60 * 60
PKCE_COOKIE_MAX_AGE = 10 * 60

def _cookie_set(name, value, max_age):
    """Scrive un cookie senza far fallire l'app se il componente non è pronto."""
    controller.set(name, value, max_age=max_age)

def _cookie_delete(name):
    try:
        controller.set(name, None, max_age=0)
    except Exception:
        pass

def generate_pkce_pair():
    """Genera una coppia PKCE e salva il verifier nel browser."""
    verifier = base64.urlsafe_b64encode(secrets.token_bytes(32)).decode("utf-8").rstrip("=")
    challenge = base64.urlsafe_b64encode(
        hashlib.sha256(verifier.encode("utf-8")).digest()
    ).decode("utf-8").rstrip("=")

    _cookie_set(PKCE_COOKIE, verifier, PKCE_COOKIE_MAX_AGE)
    st.session_state["pkce_verifier"] = verifier
    return verifier, challenge

def save_authenticated_session(response):
    """Salva user + token correnti e aggiorna SEMPRE il cookie con il refresh token nuovo."""
    session = getattr(response, "session", None)
    user = getattr(response, "user", None)

    if session is None:
        raise RuntimeError("Supabase non ha restituito una sessione valida.")

    if user is None:
        user = getattr(session, "user", None)

    if user is None:
        raise RuntimeError("Supabase non ha restituito l'utente autenticato.")

    st.session_state["user"] = user

    # IMPORTANTE: il refresh token può ruotare. Non conserviamo mai quello vecchio.
    _cookie_set(
        SESSION_COOKIE,
        {
            "access_token": session.access_token,
            "refresh_token": session.refresh_token,
        },
        SESSION_COOKIE_MAX_AGE,
    )

    return user

def exchange_pkce_code(auth_code, code_verifier):
    """Scambia manualmente il code PKCE.

    Lo facciamo via endpoint Auth perché il verifier è conservato nel nostro cookie
    e non nello storage interno del client Python. Questo evita che un nuovo run
    Streamlit perda il verifier necessario al callback.
    """
    token_url = f"{SUPABASE_URL}/auth/v1/token?grant_type=pkce"
    response = requests.post(
        token_url,
        headers={
            "apikey": SUPABASE_KEY,
            "Authorization": f"Bearer {SUPABASE_KEY}",
            "Content-Type": "application/json",
        },
        json={
            "auth_code": auth_code,
            "code_verifier": code_verifier,
        },
        timeout=20,
    )

    if not response.ok:
        try:
            detail = response.json()
        except Exception:
            detail = response.text
        raise RuntimeError(f"PKCE exchange HTTP {response.status_code}: {detail}")

    payload = response.json()
    access_token = payload.get("access_token")
    refresh_token = payload.get("refresh_token")

    if not access_token or not refresh_token:
        raise RuntimeError("Il callback OAuth non ha restituito access_token/refresh_token.")

    # Stabilisce la sessione nel client Supabase usato da questa run.
    response_obj = supabase.auth.set_session(access_token, refresh_token)
    return response_obj

def restore_session_from_cookie():
    """Ripristina la sessione al refresh e rinnova i token se necessario."""
    saved = controller.get(SESSION_COOKIE)

    if not isinstance(saved, dict):
        return False

    access_token = saved.get("access_token")
    refresh_token = saved.get("refresh_token")
    if not access_token or not refresh_token:
        return False

    try:
        # set_session() aggiorna automaticamente la sessione se l'access token
        # è scaduto, usando il refresh token.
        response = supabase.auth.set_session(access_token, refresh_token)
        if response and getattr(response, "session", None):
            save_authenticated_session(response)
            return True
    except Exception as e:
        print(f"Cookie restore error: {e}")

    # Token non più valido: eliminiamo il cookie locale e chiediamo un nuovo login.
    _cookie_delete(SESSION_COOKIE)
    return False

def build_google_login_url():
    """Costruisce l'URL OAuth Google con PKCE e redirect esplicito."""
    from urllib.parse import urlencode

    verifier, challenge = generate_pkce_pair()

    params = {
        "provider": "google",
        "redirect_to": APP_URL,
        "code_challenge": challenge,
        "code_challenge_method": "s256",
    }

    return f"{SUPABASE_URL}/auth/v1/authorize?{urlencode(params)}"

def show_login_page():
    st.title("SanoSync")

    # NON generiamo un nuovo verifier a ogni rerun.
    # Il link viene creato una sola volta finché non parte un nuovo tentativo.
    if not st.session_state.get("google_login_url"):
        try:
            st.session_state["google_login_url"] = build_google_login_url()
        except Exception as e:
            st.error(f"Errore nell'inizializzazione Google login: {e}")
            st.session_state["google_login_url"] = "#"

    login_url = st.session_state["google_login_url"]

    google_button_html = f"""
    <div style="display: flex; justify-content: center; margin: 10px 0 20px 0;">
        <a href="{login_url}" target="_self" style="
            display: flex;
            align-items: center;
            justify-content: center;
            background-color: #FFFFFF;
            color: #1A2942;
            border: 1px solid #FF8B8B;
            border-radius: 8px;
            padding: 12px 24px;
            font-family: 'Hanken Grotesk', Roboto, Arial, sans-serif;
            font-size: 16px;
            font-weight: 500;
            text-decoration: none;
            box-shadow: 0 1px 3px rgba(26,41,66,0.08);
            transition: background-color 0.2s, box-shadow 0.2s;
            width: 100%;
        ">
            <svg style="width: 20px; height: 20px; margin-right: 12px;" viewBox="0 0 24 24">
                <path fill="#4285F4" d="M23.745 12.27c0-.7-.06-1.4-.19-2.07H12v4.51h6.6c-.29 1.52-1.14 2.82-2.4 3.68v3.05h3.88c2.27-2.09 3.665-5.17 3.665-9.17z"/>
                <path fill="#34A853" d="M12 24c3.24 0 5.95-1.08 7.93-2.91l-3.88-3.05c-1.08.72-2.45 1.16-4.05 1.16-3.13 0-5.78-2.11-6.73-4.96H1.18v3.15C3.15 21.3 7.22 24 12 24z"/>
                <path fill="#FBBC05" d="M5.27 14.24c-.25-.72-.38-1.49-.38-2.24s.13-1.52.38-2.24V6.61H1.18C.43 8.13 0 9.87 0 12s.43 3.87 1.18 5.39l4.09-3.15z"/>
                <path fill="#EA4335" d="M12 4.75c1.77 0 3.35.61 4.6 1.8l3.42-3.42C17.95 1.19 15.24 0 12 0 7.22 0 3.15 2.7 1.18 6.61l4.09 3.15c.95-2.85 3.6-4.96 6.73-4.96z"/>
            </svg>
            Accedi con Google
        </a>
    </div>
    """
    st.markdown(google_button_html, unsafe_allow_html=True)
    st.markdown("---")

    auth_mode = st.radio("Oppure via Email", ["Login", "Registrazione"], horizontal=True)

    with st.form("auth_form"):
        email = st.text_input("Email")
        password = st.text_input("Password (min. 6 caratteri)", type="password")

        display_name_input = ""
        target_weight = None
        height = None
        current_weight = None
        gender = None

        if auth_mode == "Registrazione":
            st.markdown("#### 📋 Parametri Fisici Iniziali")
            display_name_input = st.text_input("Display Name", value="")
            gender = st.selectbox("Genere", ["Uomo", "Donna"], index=None, placeholder="Seleziona genere...")
            height = st.number_input("Altezza (cm)", value=175.0, min_value=100.0, max_value=250.0, step=1.0)
            current_weight = st.number_input("Peso Attuale (kg)", value=80.0, min_value=20.0, max_value=300.0, step=0.5)
            target_weight = st.number_input("Peso Obiettivo (kg)", value=75.0, min_value=20.0, max_value=300.0, step=0.5)

        submit_label = "Accedi" if auth_mode == "Login" else "Registrati"
        if st.form_submit_button(submit_label):
            try:
                if auth_mode == "Login":
                    response = supabase.auth.sign_in_with_password({"email": email, "password": password})
                    if response and response.session:
                        save_authenticated_session(response)
                        st.session_state["google_login_url"] = None
                        st.success("Login effettuato!")
                        st.rerun()
                    else:
                        st.error("Credenziali non valide")
                else:
                    if not height or not current_weight or not target_weight or not gender:
                        st.warning("Per favore compila tutti i campi fisici per la registrazione.")
                    else:
                        calculated_bmr = calculate_bmr(current_weight, height, gender)
                        supabase.auth.sign_up({
                            "email": email,
                            "password": password,
                            "options": {
                                "data": {
                                    "display_name": display_name_input or email.split("@")[0],
                                    "target_weight": float(target_weight),
                                    "bmr": calculated_bmr,
                                    "height": float(height),
                                    "gender": gender
                                }
                            }
                        })
                        st.success("✅ Account creato con successo! Effettua il login.")
                        st.rerun()
            except Exception as e:
                st.error(f"Errore durante l'autenticazione: {str(e)}")
                print(traceback.format_exc())

# ==============================================================================
# 5. RESTORE SESSION / OAUTH CALLBACK
# ==============================================================================
# 1) Se Google ci ha riportato con ?code=..., completiamo il PKCE.
# 2) Altrimenti proviamo il cookie persistente.
# 3) Solo se entrambi falliscono mostriamo la login page.

if st.session_state.get("user") is None:
    query_code = st.query_params.get("code")

    if query_code:
        verifier = st.session_state.get("pkce_verifier") or controller.get(PKCE_COOKIE)

        if verifier:
            try:
                response = exchange_pkce_code(query_code, verifier)
                save_authenticated_session(response)

                # Il code OAuth è monouso: rimuoviamolo immediatamente dall'URL.
                st.query_params.clear()
                st.session_state["pkce_verifier"] = None
                st.session_state["google_login_url"] = None
                _cookie_delete(PKCE_COOKIE)

                # NON facciamo st.rerun() qui: continuiamo questa stessa run
                # con la sessione appena autenticata.
            except Exception as e:
                print(traceback.format_exc())
                st.error(f"Login Google fallito: {e}")
                st.query_params.clear()
                st.session_state["pkce_verifier"] = None
                st.session_state["google_login_url"] = None
                _cookie_delete(PKCE_COOKIE)
        else:
            st.error("Il callback Google è arrivato senza il PKCE verifier. Riprova il login.")
            st.query_params.clear()
            st.session_state["google_login_url"] = None

if st.session_state.get("user") is None:
    restore_session_from_cookie()

if st.session_state.get("user") is None:
    show_login_page()
    st.stop()

# ==============================================================================
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
        controller.set("supabase_session", None, max_age=0)
        st.session_state.clear()
        st.rerun()

# Script JavaScript per chiudere automaticamente la sidebar su mobile dopo un click
st.markdown("""
    <script>
        function isMobile() {
            return window.innerWidth <= 768;
        }

        document.addEventListener('click', function(event) {
            const sidebar = document.querySelector('[data-testid="stSidebar"]');
            if (sidebar && sidebar.contains(event.target) && isMobile()) {
                const closeBtn = document.querySelector('[data-testid="stSidebarNav"] button, [data-testid="stSidebar"] button');
                if (closeBtn) {
                    setTimeout(() => {
                        const toggleTrigger = document.querySelector('[data-testid="collapsedControl"]');
                        if (toggleTrigger) {
                            const expanded = sidebar.getAttribute("aria-expanded");
                            if (expanded === "true" || !expanded) {
                                toggleTrigger.click();
                            }
                        }
                    }, 150);
                }
            }
        });
    </script>
""", unsafe_allow_html=True)

# ==============================================================================
# 9. PAGE 1: MEAL LOGGING
# ==============================================================================
if selected_page == t["t1"]:
    log_date = st.date_input("📅 Data", value=date.today())
    
    st.subheader(t["tab1_title"])
    
    input_source = st.radio(
        t["input_source_lbl"], 
        [t["opt_off"], t["opt_quick"]], 
        horizontal=True
    )
    
    is_recipe = (input_source == t["opt_quick"])
    v = st.session_state["form_version"]
    
    if "base_cals" not in st.session_state:
        st.session_state["base_cals"] = 0.0
        st.session_state["base_prot"] = 0.0
        st.session_state["base_carbs"] = 0.0
        st.session_state["base_fat"] = 0.0
        st.session_state["m_name"] = ""
        st.session_state["grams_val"] = 100.0
        st.session_state["is_per_100g_val"] = True
    
    def reset_or_update(name="", cals=0, prot=0, carbs=0, fat=0, selected="", grams=100.0, is_100g=True):
        st.session_state["m_name"] = name
        st.session_state["base_cals"] = float(cals)
        st.session_state["base_prot"] = float(prot)
        st.session_state["base_carbs"] = float(carbs)
        st.session_state["base_fat"] = float(fat)
        st.session_state["grams_val"] = float(grams)
        st.session_state["is_per_100g_val"] = is_100g
        st.session_state["last_selected"] = selected
        st.session_state["form_version"] += 1
    
    if st.session_state.get("last_source") != input_source:
        st.session_state["last_source"] = input_source
        reset_or_update()
        st.rerun()
    
    if not is_recipe:
        search_q = st.text_input(t["search_food"])
        if st.button(t["search_btn"]):
            if len(search_q) >= 2:
                with st.spinner('Ricerca in corso...'):
                    st.session_state["api_res"] = search_open_food_facts(search_q)
                st.session_state["prod_select"] = ""
                st.session_state["last_selected"] = ""
                st.rerun()
            else:
                st.warning("Inserisci almeno 2 caratteri o un codice a barre valido.")
        
        api_res = st.session_state.get("api_res", {})
        if api_res:
            sel_prod = st.selectbox(t["select_db"], [""] + list(api_res.keys()), key=f"prod_select_{v}")
            if sel_prod and sel_prod != st.session_state.get("last_selected"):
                p_data = api_res[sel_prod]
                reset_or_update(p_data.get('name',''), p_data.get('calories',0), p_data.get('protein',0), p_data.get('carbs',0), p_data.get('fat',0), sel_prod, 100.0, True)
                st.rerun()
    else:
        try:
            recipes_data = supabase.table("recipes").select("*").eq("user_id", user_id).execute().data
            recipes_dict = {r["name"]: r for r in recipes_data} if recipes_data else {}
            if recipes_dict:
                sel_recipe = st.selectbox(t["select_recipe"], [""] + list(recipes_dict.keys()), key=f"recipe_select_{v}")
                if sel_recipe and sel_recipe != st.session_state.get("last_selected"):
                    r = recipes_dict[sel_recipe]
                    is_100g = bool(r.get('is_per_100g', 1))
                    reset_or_update(r.get('name',''), r.get('calories',0), r.get('protein',0), r.get('carbs',0), r.get('fat',0), sel_recipe, 100.0 if is_100g else 1.0, is_100g)
                    st.rerun()
            else:
                st.info(t["no_recipes"])
        except Exception as e:
            st.error(f"Errore: {e}")
    
    st.markdown("---")
    meal_options = ["Colazione", "Pranzo", "Cena", "Snack"]
    m_type = st.selectbox(t["meal"], meal_options, key=f"meal_type_input_{v}")
    name = st.text_input(t["meal_name"], value=st.session_state["m_name"], key=f"input_meal_name_{v}")
    
    # Gestione della modalità (Per 100g / Per Porzione)
    mode_options = [t["per_100g"], t["per_portion"]]
    default_index = 0 if st.session_state["is_per_100g_val"] else 1
    
    mode = st.radio(
        t["calc_mode"], 
        mode_options, 
        index=default_index, 
        horizontal=True,
        key=f"mode_radio_{v}"
    )
    
    # Aggiorniamo i valori di sessione se la modalità è cambiata
    is_now_100g = (mode == t["per_100g"])
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
        on_change=on_qty_change
    )
    
    factor = (quantity / 100.0) if mode == t["per_100g"] else quantity
    meal_display_name = f"{name} ({quantity}{'g' if mode == t['per_100g'] else ' porz.'})"
    
    final_cals = int(st.session_state["base_cals"] * factor)
    final_prot = int(st.session_state["base_prot"] * factor)
    final_carbs = int(st.session_state["base_carbs"] * factor)
    final_fat = int(st.session_state["base_fat"] * factor)
    
    c1, c2, c3, c4 = st.columns(4)
    cals_in = c1.number_input(t["kcal"], value=final_cals, step=1)
    prot_in = c2.number_input(t["pro"], value=final_prot, step=1)
    carbs_in = c3.number_input(t["carbs"], value=final_carbs, step=1)
    fat_in = c4.number_input(t["fat"], value=final_fat, step=1)
    
    if st.button(t["add_meal"], use_container_width=True):
        try:
            supabase.table("meals").insert({
                "user_id": user_id, "date": str(log_date), "meal_type": m_type,
                "name": meal_display_name, "calories": cals_in, "protein": prot_in, 
                "carbs": carbs_in, "fat": fat_in
            }).execute()
            save_meal_as_quick_entry(meal_display_name, cals_in, prot_in, carbs_in, fat_in)
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
        on_change=update_overview_date
    )
    
    try:
        daily_log_res = supabase.table("daily_logs").select("*").eq("date", str(summary_date)).eq("user_id", user_id).execute().data or []
        meals_data = supabase.table("meals").select("*").eq("date", str(summary_date)).eq("user_id", user_id).execute().data or []
        raw_activities = supabase.table("activities").select("activity_name, burned_calories").eq("date", str(summary_date)).eq("user_id", user_id).execute().data or []
        
        all_weight_logs = supabase.table("daily_logs").select("weight, date").eq("user_id", user_id).not_.is_("weight", "null").order("date", desc=False).execute().data or []
    except Exception as e:
        st.error(f"Errore nel caricamento dati: {e}")
        daily_log_res = []
        meals_data = []
        raw_activities = []
        all_weight_logs = []
    
    activities_data = [a for a in raw_activities if a.get("activity_name")] if raw_activities else []
    total_cals_in = sum(m.get('calories', 0) for m in meals_data) if meals_data else 0
    
    current_weight = None
    if daily_log_res and len(daily_log_res) > 0:
        row = daily_log_res[0]
        current_weight = row.get('weight')
    
    initial_weight = 89.0 
    if all_weight_logs:
        initial_weight = all_weight_logs[0]['weight']
    target_weight = float(user_target_weight) if user_target_weight else 78.0
    
    now = datetime.now()
    if summary_date == date.today():
        minutes_passed = max(60, now.hour * 60 + now.minute)
        bmr_so_far = int((user_bmr / (24 * 60)) * minutes_passed)
    else:
        bmr_so_far = user_bmr
        minutes_passed = 1440
    
    extra_burned = sum(a.get('burned_calories', 0) for a in activities_data) if activities_data else 0
    total_burned_finora = bmr_so_far + extra_burned
    deficit = total_cals_in - total_burned_finora
    
    # --- CALCOLO TARGET E DEFICIT (BMR + EXTRA - 500) ---
    total_estimated_burned = user_bmr + extra_burned
    ideal_target_cals = max(0, total_estimated_burned - 500)
    diff_from_ideal = ideal_target_cals - total_cals_in

    # Sfondo corallo leggerissimo (#FFF5F5) con bordo corallo (#FF8B8B)
    coral_light_bg, coral_border = "#FFF5F5", "#FF8B8B"
    in_msg = t["in_msg_deficit"](ideal_target_cals, diff_from_ideal)

    if extra_burned > 0:
        burn_msg = t["burn_msg_yes"](extra_burned)
    else:
        burn_msg = t["burn_msg_no"]

    weight_to_lose = (current_weight if current_weight else initial_weight) - target_weight
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
        diff_ini = current_weight - initial_weight
        diff_tgt = current_weight - target_weight
        weight_msg = t["weight_msg_val"](initial_weight, diff_ini, target_weight, diff_tgt)

    # CSS per i widget con sfondo corallo soft ed eliminazione bordi doppi
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
            .custom-card-title {{
                font-size: 0.95rem;
                font-weight: 600;
                color: #1A2942;
                margin-bottom: 4px;
            }}
            .custom-card-value {{
                font-size: 1.8rem;
                font-weight: 700;
                color: #1A2942;
                margin-bottom: 8px;
            }}
            .custom-card-caption {{
                font-size: 0.82rem;
                color: #555555;
                line-height: 1.35;
            }}
        </style>
    """, unsafe_allow_html=True)

    col_c1, col_c2, col_c3, col_c4 = st.columns(4)
    
    with col_c1:
        st.markdown(f"""
            <div class="custom-card">
                <div class="custom-card-title">🍽️ {t['card_kcal_in']}</div>
                <div class="custom-card-value">{total_cals_in} kcal</div>
                <div class="custom-card-caption">{in_msg}</div>
            </div>
        """, unsafe_allow_html=True)
            
    with col_c2:
        st.markdown(f"""
            <div class="custom-card">
                <div class="custom-card-title">🔥 {t['card_kcal_burn']}</div>
                <div class="custom-card-value">{total_burned_finora} kcal</div>
                <div class="custom-card-caption">{burn_msg}</div>
            </div>
        """, unsafe_allow_html=True)
            
    with col_c3:
        st.markdown(f"""
            <div class="custom-card">
                <div class="custom-card-title">⚖️ {t['card_balance']}</div>
                <div class="custom-card-value">{deficit:+d} kcal</div>
                <div class="custom-card-caption">{bilancio_msg}</div>
            </div>
        """, unsafe_allow_html=True)
            
    with col_c4:
        weight_str = f"{current_weight} kg" if current_weight else "N/D"
        st.markdown(f"""
            <div class="custom-card">
                <div class="custom-card-title">📉 {t['card_weight']}</div>
                <div class="custom-card-value">{weight_str}</div>
                <div class="custom-card-caption">{weight_msg}</div>
            </div>
        """, unsafe_allow_html=True)
    
    st.markdown("<br>", unsafe_allow_html=True)

    with st.container(border=True):
        st.markdown(f"### {t['logged_foods']}")
        if meals_data:
            meals_with_id = supabase.table("meals").select("id, meal_type, name, calories, protein, carbs, fat").eq("date", str(summary_date)).eq("user_id", user_id).execute().data
            
            df_meals = pd.DataFrame(meals_with_id)
            df_display = df_meals.rename(columns={
                "meal_type": "Pasto", "name": "Nome", "calories": "Kcal", 
                "protein": "Pro (g)", "carbs": "Carbs (g)", "fat": "Fat (g)"
            })
            st.dataframe(df_display[["Pasto", "Nome", "Kcal", "Pro (g)", "Carbs (g)", "Fat (g)"]], use_container_width=True, hide_index=True)
            
            # ------------------------------------------------------------------
            # MODIFICA / ELIMINAZIONE PASTI
            # ------------------------------------------------------------------
            # Il valore della selectbox è l'ID del record, così anche due pasti
            # con lo stesso nome possono essere modificati separatamente.
            meal_by_id = {m["id"]: m for m in meals_with_id}
            meal_options = {
                m["id"]: f"{m.get('meal_type', '')} - {m.get('name', '')} ({m.get('calories', 0)} kcal)"
                for m in meals_with_id
            }

            selected_meal_id = st.selectbox(
                "🍽️ Seleziona il pasto da modificare",
                options=[""] + list(meal_options.keys()),
                format_func=lambda meal_id: (
                    "Seleziona un pasto..."
                    if meal_id == ""
                    else meal_options[meal_id]
                ),
                key=f"edit_meal_select_{summary_date}"
            )

            if selected_meal_id:
                selected_meal = meal_by_id[selected_meal_id]
                meal_types = ["Colazione", "Pranzo", "Cena", "Snack"]

                current_type = selected_meal.get("meal_type")
                current_index = meal_types.index(current_type) if current_type in meal_types else 0

                edit_col1, edit_col2 = st.columns([2, 1])

                with edit_col1:
                    new_meal_type = st.selectbox(
                        "Tipo di pasto",
                        meal_types,
                        index=current_index,
                        key=f"edit_meal_type_{selected_meal_id}_{summary_date}"
                    )

                with edit_col2:
                    st.markdown("<br>", unsafe_allow_html=True)
                    save_meal_type = st.button(
                        "💾 Salva modifica",
                        use_container_width=True,
                        key=f"save_meal_type_{selected_meal_id}_{summary_date}"
                    )

                if save_meal_type:
                    try:
                        supabase.table("meals").update(
                            {"meal_type": new_meal_type}
                        ).eq("id", selected_meal_id).eq(
                            "user_id", user_id
                        ).execute()

                        st.success(
                            f"✅ Tipo di pasto modificato in **{new_meal_type}**."
                        )
                        st.rerun()
                    except Exception as e:
                        st.error(f"Errore nella modifica del pasto: {e}")

                st.markdown("---")

                delete_col1, delete_col2 = st.columns([3, 1])
                with delete_col1:
                    st.caption(
                        f"Elimina definitivamente **{selected_meal.get('name', 'questo pasto')}** "
                        "se non vuoi più conservarlo."
                    )
                with delete_col2:
                    if st.button(
                        t["del_meal_btn"],
                        key=f"delete_meal_{selected_meal_id}_{summary_date}",
                        use_container_width=True
                    ):
                        try:
                            supabase.table("meals").delete().eq(
                                "id", selected_meal_id
                            ).eq("user_id", user_id).execute()
                            st.success(t["meal_del_success"])
                            st.rerun()
                        except Exception as e:
                            st.error(f"Errore nell'eliminazione del pasto: {e}")

        else:
            st.info(t["no_meals"])
    
    with st.container(border=True):
        st.markdown(t["burned_acts"])
        rows_acts = [{"Attività": "BMR (Base)", "Kcal Bruciate": bmr_so_far}]
        if activities_data:
            for act in activities_data:
                rows_acts.append({
                    "Attività": act.get("activity_name"),
                    "Kcal Bruciate": act.get("burned_calories")
                })
        
        df_acts = pd.DataFrame(rows_acts)
        st.dataframe(df_acts, use_container_width=True, hide_index=True)

# ==============================================================================
# 11. PAGE 3: WEIGHT TRACKING
# ==============================================================================
elif selected_page == t["t3"]:
    st.subheader(t["weight_tracking"])

    # ------------------------------------------------------------------
    # INSERIMENTO / MODIFICA / CANCELLAZIONE PESO
    # ------------------------------------------------------------------
    with st.container(border=True):
        st.markdown("#### ⚖️ Gestione pesi")
        logs_all = (
            supabase.table("daily_logs").select("id, date, weight").eq("user_id", user_id)
            .not_.is_("weight", "null").order("date", desc=True).execute().data or []
        )
        edit_options = {
            str(r["id"]): f"{r['date']} · {float(r['weight']):.1f} kg" for r in logs_all
        }
        c1, c2 = st.columns(2)
        with c1:
            w = st.number_input("Nuovo peso (kg)", value=80.0, min_value=20.0, max_value=300.0, step=0.1, key="new_weight_value")
            w_date = st.date_input("Data del peso", value=date.today(), key="new_weight_date")
            if st.button("💾 Salva peso", use_container_width=True):
                try:
                    supabase.table("daily_logs").upsert({
                        "user_id": user_id, "date": str(w_date), "weight": float(w)
                    }, on_conflict="user_id,date").execute()
                    st.success("✅ Peso salvato!")
                    st.rerun()
                except Exception as e:
                    st.error(f"Errore nel salvataggio del peso: {e}")
        with c2:
            selected_weight_id = st.selectbox("Peso da modificare o eliminare", [""] + list(edit_options.keys()),
                                              format_func=lambda x: "Seleziona un peso..." if x == "" else edit_options[x],
                                              key="weight_edit_selector")
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
                            # Se cambia data, eliminiamo il vecchio record e lo riscriviamo sulla nuova data.
                            if str(edited_date) != str(selected_row["date"]):
                                supabase.table("daily_logs").delete().eq("id", selected_row["id"]).eq("user_id", user_id).execute()
                                supabase.table("daily_logs").upsert({"user_id": user_id, "date": str(edited_date), "weight": float(edited_weight)}, on_conflict="user_id,date").execute()
                            else:
                                supabase.table("daily_logs").update({"weight": float(edited_weight)}).eq("id", selected_row["id"]).eq("user_id", user_id).execute()
                            st.success("✅ Peso modificato!")
                            st.rerun()
                        except Exception as e:
                            st.error(f"Errore nella modifica: {e}")
                with b2:
                    if st.button("🗑️ Cancella peso", use_container_width=True, key=f"delete_weight_{selected_weight_id}"):
                        try:
                            supabase.table("daily_logs").delete().eq("id", selected_row["id"]).eq("user_id", user_id).execute()
                            st.success("✅ Peso cancellato.")
                            st.rerun()
                        except Exception as e:
                            st.error(f"Errore nella cancellazione: {e}")

    with st.container(border=True):
        st.markdown(f"#### {t['update_target']}")
        new_target = st.number_input("Peso Obiettivo (kg)", value=float(user_target_weight) if user_target_weight else 75.0, min_value=20.0, max_value=300.0, step=0.5, key="weight_target_edit")
        if st.button(t["save_target"], use_container_width=True):
            try:
                res = supabase.auth.update_user({"data": {"target_weight": float(new_target)}})
                if res.user:
                    st.session_state["user"] = res.user
                st.success(t["target_updated"])
                st.rerun()
            except Exception as e:
                st.error(f"Errore: {e}")

    with st.container(border=True):
        try:
            logs = (supabase.table("daily_logs").select("date, weight").eq("user_id", user_id)
                    .not_.is_("weight", "null").order("date", desc=False).execute().data or [])
            if not logs:
                st.info("📊 Nessun dato di peso registrato ancora.")
            else:
                df_weight = pd.DataFrame(logs)
                df_weight["date"] = pd.to_datetime(df_weight["date"]).dt.normalize()
                df_weight["weight"] = pd.to_numeric(df_weight["weight"], errors="coerce")
                df_weight = df_weight.dropna().sort_values("date")

                period_options = {"5 giorni": 5, "15 giorni": 15, "30 giorni": 30, "60 giorni": 60, "90 giorni": 90, "120 giorni": 120, "180 giorni": 180}
                selected_period_label = st.selectbox("Periodo del grafico", list(period_options), index=2, key="weight_chart_period")
                selected_days = period_options[selected_period_label]
                chart_end = df_weight["date"].max()
                chart_start = chart_end - pd.Timedelta(days=selected_days - 1)
                timeline_dates = pd.date_range(chart_start, chart_end, freq="D")
                df_visible = df_weight[(df_weight["date"] >= chart_start) & (df_weight["date"] <= chart_end)].copy()

                # Dati pasti e attività della stessa finestra.
                meals_rows = (supabase.table("meals").select("date, meal_type, name, calories, protein, carbs, fat")
                              .eq("user_id", user_id).gte("date", str(chart_start.date())).lte("date", str(chart_end.date())).execute().data or [])
                acts_rows = (supabase.table("activities").select("date, activity_name, burned_calories")
                             .eq("user_id", user_id).gte("date", str(chart_start.date())).lte("date", str(chart_end.date())).execute().data or [])
                meals_df = pd.DataFrame(meals_rows)
                acts_df = pd.DataFrame(acts_rows)
                if not meals_df.empty:
                    meals_df["date"] = pd.to_datetime(meals_df["date"]).dt.normalize()
                    for col in ["calories", "protein", "carbs", "fat"]:
                        meals_df[col] = pd.to_numeric(meals_df[col], errors="coerce").fillna(0)
                if not acts_df.empty:
                    acts_df["date"] = pd.to_datetime(acts_df["date"]).dt.normalize()
                    acts_df["burned_calories"] = pd.to_numeric(acts_df["burned_calories"], errors="coerce").fillna(0)

                target_val = float(user_target_weight) if user_target_weight else 75.0
                latest_weight = float(df_weight["weight"].iloc[-1])
                # Proiezione: trend degli ultimi 14 giorni.
                estimated_date = None
                days_to_goal = 0
                recent_df = df_weight.tail(min(len(df_weight), 14))
                if len(recent_df) >= 3 and latest_weight > target_val:
                    days_diff = (recent_df["date"].max() - recent_df["date"].min()).days
                    weight_diff = float(recent_df["weight"].iloc[-1] - recent_df["weight"].iloc[0])
                    if days_diff > 0 and weight_diff < 0:
                        kg_per_day = abs(weight_diff / days_diff)
                        days_to_goal = max(1, int((latest_weight - target_val) / kg_per_day))
                        estimated_date = df_weight["date"].max() + pd.Timedelta(days=days_to_goal)

                fig = go.Figure()
                fig.add_trace(go.Scatter(
                    x=df_visible["date"], y=df_visible["weight"], mode="lines+markers", name="Peso reale",
                    line=dict(color="#FF8B8B", width=3), marker=dict(size=8, color="#FF8B8B"),
                    hovertemplate="<b>%{x|%d %b %Y}</b><br>Peso: <b>%{y:.1f} kg</b><extra></extra>"
                ))
                if estimated_date is not None:
                    first = df_weight.iloc[0]
                    fig.add_trace(go.Scatter(
                        x=[first["date"], estimated_date], y=[float(first["weight"]), target_val],
                        mode="lines+markers", name="Proiezione",
                        line=dict(color="#FF8B8B", width=2.5, dash="dash"), marker=dict(size=6, color="#FF8B8B"),
                        hovertemplate="<b>Proiezione</b><br>%{x|%d %b %Y}<br>%{y:.1f} kg<extra></extra>"
                    ))
                fig.add_trace(go.Scatter(
                    x=[chart_start, chart_end], y=[target_val, target_val], mode="lines", name="Obiettivo",
                    line=dict(color="#1A2942", width=2.5), hovertemplate=f"Obiettivo: {target_val:.1f} kg<extra></extra>"
                ))

                # Zoom orizzontale + autoscaling verticale.
                vals = df_visible["weight"].tolist() + [target_val]
                if estimated_date is not None and chart_start <= estimated_date <= chart_end:
                    vals.append(target_val)
                y_min, y_max = min(vals), max(vals)
                spread = max(y_max - y_min, 1.0)
                padding = max(0.6, spread * 0.18)
                fig.update_xaxes(range=[chart_start, chart_end + pd.Timedelta(hours=23)], showgrid=False, fixedrange=False)
                fig.update_yaxes(range=[y_min - padding, y_max + padding], title="Peso (kg)", gridcolor="#E8ECF2", zeroline=False, fixedrange=False)
                fig.update_layout(height=470, plot_bgcolor="#FFFFFF", paper_bgcolor="rgba(0,0,0,0)", hovermode="x unified",
                                  font=dict(color="#1A2942"), margin=dict(l=55, r=25, t=45, b=55),
                                  legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="left", x=0, bgcolor="rgba(255,255,255,0.85)"))
                st.plotly_chart(fig, use_container_width=True, config={"displayModeBar": False})

                # --------------------------------------------------------------
                # SECONDO GRAFICO: DEFICIT / MACROS / PASTI
                # --------------------------------------------------------------
                chart_mode = st.selectbox("Analisi giornaliera", ["Deficit", "Macros", "Pasti"], index=0, key="daily_analysis_mode")
                days_df = pd.DataFrame({"date": timeline_dates})
                if not meals_df.empty:
                    daily_meals = meals_df.groupby("date")[["calories", "protein", "carbs", "fat"]].sum().reset_index()
                    days_df = days_df.merge(daily_meals, on="date", how="left")
                else:
                    days_df[["calories", "protein", "carbs", "fat"]] = 0
                days_df[["calories", "protein", "carbs", "fat"]] = days_df[["calories", "protein", "carbs", "fat"]].fillna(0)
                if not acts_df.empty:
                    daily_burn = acts_df.groupby("date")["burned_calories"].sum().reset_index(name="extra")
                    days_df = days_df.merge(daily_burn, on="date", how="left")
                else:
                    days_df["extra"] = 0
                days_df["extra"] = days_df["extra"].fillna(0)
                days_df["burned"] = float(user_bmr) + days_df["extra"]

                # Icone per ogni giorno.
                deficit_icons, activity_icons, deficit_titles, activity_titles = [], [], [], []
                for _, r in days_df.iterrows():
                    kcal_in = float(r["calories"])
                    extra = float(r["extra"])
                    if kcal_in <= 0:
                        deficit_icons.append("·"); deficit_titles.append("Nessun dato alimentare")
                    else:
                        d = float(user_bmr) + extra - kcal_in
                        if d >= 500: deficit_icons.append("👍")
                        elif d >= 0: deficit_icons.append("😐")
                        else: deficit_icons.append("👎")
                        deficit_titles.append(f"Deficit: {d:.0f} kcal")
                    if not acts_df.empty:
                        day_rows = acts_df[acts_df["date"] == r["date"]]
                        padel = any(str(n).strip().lower() == "padel" for n in day_rows["activity_name"].tolist())
                    else: padel = False
                    if padel: activity_icons.append("🎾")
                    elif extra > 300: activity_icons.append("🔥")
                    else: activity_icons.append("🛏️")
                    activity_titles.append(f"Extra: {extra:.0f} kcal")

                daily_fig = go.Figure()
                if chart_mode == "Deficit":
                    daily_fig.add_trace(go.Bar(x=days_df["date"], y=days_df["calories"], name="Kcal ingerite", marker_color="#FF8B8B", hovertemplate="%{x|%d %b}<br>Ingerite: %{y:.0f} kcal<extra></extra>"))
                    daily_fig.add_trace(go.Bar(x=days_df["date"], y=days_df["burned"], name="Kcal bruciate", marker_color="#1A2942", hovertemplate="%{x|%d %b}<br>Bruciate: %{y:.0f} kcal<extra></extra>"))
                    daily_fig.update_layout(barmode="group", yaxis_title="kcal")
                elif chart_mode == "Macros":
                    daily_fig.add_trace(go.Bar(x=days_df["date"], y=days_df["protein"], name="Proteine", marker_color="#FF8B8B", hovertemplate="%{x|%d %b}<br>Proteine: %{y:.0f} g<extra></extra>"))
                    daily_fig.add_trace(go.Bar(x=days_df["date"], y=days_df["carbs"], name="Carboidrati", marker_color="#1A2942", hovertemplate="%{x|%d %b}<br>Carboidrati: %{y:.0f} g<extra></extra>"))
                    daily_fig.add_trace(go.Bar(x=days_df["date"], y=days_df["fat"], name="Grassi", marker_color="#FFB4B4", hovertemplate="%{x|%d %b}<br>Grassi: %{y:.0f} g<extra></extra>"))
                    daily_fig.update_layout(barmode="stack", yaxis_title="grammi")
                else:
                    meal_order = ["Colazione", "Pranzo", "Snack", "Cena"]
                    meal_colors = ["#FF8B8B", "#1A2942", "#FFB4B4", "#667085"]
                    if meals_df.empty:
                        for meal_type, color in zip(meal_order, meal_colors):
                            daily_fig.add_trace(go.Bar(x=days_df["date"], y=[0]*len(days_df), name=meal_type, marker_color=color))
                    else:
                        for meal_type, color in zip(meal_order, meal_colors):
                            md = meals_df[meals_df["meal_type"] == meal_type].groupby("date")["calories"].sum()
                            vals = [float(md.get(d, 0)) for d in days_df["date"]]
                            daily_fig.add_trace(go.Bar(x=days_df["date"], y=vals, name=meal_type, marker_color=color))
                    daily_fig.update_layout(barmode="stack", yaxis_title="kcal")

                # Le icone sono parte del secondo grafico ma fuori dall'area delle colonne.
                if len(days_df) <= 45:
                    for idx, r in days_df.iterrows():
                        daily_fig.add_annotation(x=r["date"], y=1.02, yref="paper", text=deficit_icons[idx], showarrow=False, font=dict(size=18), hovertext=deficit_titles[idx])
                        daily_fig.add_annotation(x=r["date"], y=0.94, yref="paper", text=activity_icons[idx], showarrow=False, font=dict(size=17), hovertext=activity_titles[idx])
                daily_fig.update_xaxes(range=[chart_start, chart_end + pd.Timedelta(hours=23)], tickformat="%d %b", fixedrange=False)
                daily_fig.update_layout(height=410, plot_bgcolor="#FFFFFF", paper_bgcolor="rgba(0,0,0,0)", hovermode="x unified",
                                       font=dict(color="#1A2942"), margin=dict(l=55, r=25, t=55, b=55),
                                       legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="left", x=0, bgcolor="rgba(255,255,255,0.85)"))
                st.plotly_chart(daily_fig, use_container_width=True, config={"displayModeBar": False})

                if len(days_df) > 45:
                    st.caption("💡 Per periodi lunghi le icone restano disponibili nei tooltip per mantenere il grafico leggibile.")

                # --------------------------------------------------------------
                # PROIEZIONE TESTUALE
                # --------------------------------------------------------------
                if estimated_date is not None:
                    st.markdown(f"<div style='background:#FFFFFF;border:1px solid #FF8B8B;padding:12px 16px;border-radius:10px;color:#1A2942;'>🔮 <b>Proiezione:</b> al ritmo attuale potresti raggiungere {target_val:.1f} kg intorno al <b>{estimated_date.strftime('%d %b %Y')}</b>.</div>", unsafe_allow_html=True)
        except Exception as e:
            st.error(f"Errore nel caricamento grafici: {e}")
            print(traceback.format_exc())

# ==============================================================================
# 12. PAGE 4: QUICK ENTRIES / RICETTE
# ==============================================================================
elif selected_page == t["t4"]:
    st.subheader(t["quick_entries"])
    if "recipe_form_version" not in st.session_state:
        st.session_state["recipe_form_version"] = 0
    v = st.session_state["recipe_form_version"]

    # Importazione di tutti i cibi già registrati come immissioni rapide.
    with st.container(border=True):
        st.markdown("### 📥 Importa cibi da meals")
        st.caption("Ogni cibo registrato nella tabella meals può diventare un'immissione rapida riutilizzabile.")
        if st.button("🔄 Importa tutti i cibi già registrati", use_container_width=True):
            try:
                all_meals = supabase.table("meals").select("name, calories, protein, carbs, fat").eq("user_id", user_id).execute().data or []
                count = 0
                for m in all_meals:
                    if save_meal_as_quick_entry(m.get("name", ""), m.get("calories", 0), m.get("protein", 0), m.get("carbs", 0), m.get("fat", 0)):
                        count += 1
                st.success(f"✅ Importati/aggiornati {count} cibi nelle immissioni rapide.")
                st.rerun()
            except Exception as e:
                st.error(f"Errore durante l'importazione: {e}")

    with st.container(border=True):
        st.markdown(f"### {t['saved_entries']}")
        entries = supabase.table("recipes").select("*").eq("user_id", user_id).order("name").execute().data or []
        if entries:
            df_entries = pd.DataFrame(entries)
            df_display = df_entries.rename(columns={"name":"Nome", "calories":"Kcal", "protein":"Pro", "carbs":"Carbs", "fat":"Fat"})
            st.dataframe(df_display[["Nome", "Kcal", "Pro", "Carbs", "Fat"]], use_container_width=True, hide_index=True)
            entry_by_id = {str(e.get("id")): e for e in entries}
            selected_entry_id = st.selectbox("Seleziona ricetta da eliminare", [""] + list(entry_by_id), format_func=lambda x: "Seleziona..." if not x else entry_by_id[x].get("name", ""), key=f"del_recipe_sel_{v}")
            if selected_entry_id and st.button("🗑️ Elimina ricetta", key=f"del_recipe_btn_{v}"):
                try:
                    supabase.table("recipes").delete().eq("id", selected_entry_id).eq("user_id", user_id).execute()
                    st.success("Ricetta eliminata.")
                    st.rerun()
                except Exception as e:
                    st.error(f"Errore durante l'eliminazione: {e}")
        else:
            st.info("Nessuna immissione rapida presente.")

    with st.container(border=True):
        st.markdown("### ➕ Aggiungi nuova Ricetta")
        r_name = st.text_input("Nome ricetta", placeholder="Es. Pasta al pomodoro", key=f"recipe_builder_name_{v}")

        st.markdown("#### 🥕 Aggiungi ingrediente")
        source = st.radio("Fonte ingrediente", ["Database / Open Food Facts", "Inserimento manuale"], horizontal=True, key=f"ingredient_source_{v}")
        ingredient_name = ""
        base = {"calories":0.0,"protein":0.0,"carbs":0.0,"fat":0.0}
        if source.startswith("Database"):
            iq = st.text_input("Cerca ingrediente", key=f"ingredient_search_{v}")
            if st.button("🔍 Cerca ingrediente", key=f"ingredient_search_btn_{v}"):
                if len(iq.strip()) >= 2:
                    st.session_state[f"ingredient_results_{v}"] = search_open_food_facts(iq)
                    st.rerun()
            results = st.session_state.get(f"ingredient_results_{v}", {})
            if results:
                sel = st.selectbox("Risultati", [""] + list(results), key=f"ingredient_result_select_{v}")
                if sel:
                    p = results[sel]
                    ingredient_name = p.get("name", sel)
                    base = {k: float(p.get(k,0) or 0) for k in base}
        else:
            ingredient_name = st.text_input("Nome ingrediente", key=f"manual_ingredient_name_{v}")
            mc1, mc2, mc3, mc4 = st.columns(4)
            base["calories"] = mc1.number_input("Kcal / 100g", min_value=0.0, step=1.0, key=f"manual_kcal_{v}")
            base["protein"] = mc2.number_input("Pro / 100g", min_value=0.0, step=0.1, key=f"manual_pro_{v}")
            base["carbs"] = mc3.number_input("Carbs / 100g", min_value=0.0, step=0.1, key=f"manual_carbs_{v}")
            base["fat"] = mc4.number_input("Fat / 100g", min_value=0.0, step=0.1, key=f"manual_fat_{v}")
        quantity = st.number_input("Quantità (g)", min_value=0.1, value=100.0, step=1.0, key=f"ingredient_qty_{v}")
        if st.button("➕ Aggiungi ingrediente alla ricetta", use_container_width=True, key=f"add_ingredient_{v}"):
            if not ingredient_name.strip():
                st.warning("Inserisci o seleziona un ingrediente.")
            else:
                st.session_state["recipe_builder_ingredients"].append({
                    "name": ingredient_name.strip(), "quantity_g": float(quantity),
                    "calories_per_100g": float(base["calories"]), "protein_per_100g": float(base["protein"]),
                    "carbs_per_100g": float(base["carbs"]), "fat_per_100g": float(base["fat"]),
                    "source": "database" if source.startswith("Database") else "manual"
                })
                st.success(f"✅ {ingredient_name} aggiunto.")
                st.rerun()

        ingredients = st.session_state.get("recipe_builder_ingredients", [])
        if ingredients:
            st.markdown("#### 📋 Ingredienti della ricetta")
            rows = []
            for idx, ing in enumerate(ingredients):
                factor = float(ing["quantity_g"]) / 100
                rows.append({"#": idx+1, "Ingrediente": ing["name"], "Quantità (g)": ing["quantity_g"], "Kcal": round(ing["calories_per_100g"]*factor), "Pro": round(ing["protein_per_100g"]*factor,1), "Carbs": round(ing["carbs_per_100g"]*factor,1), "Fat": round(ing["fat_per_100g"]*factor,1)})
            st.dataframe(pd.DataFrame(rows), use_container_width=True, hide_index=True)
            remove_idx = st.selectbox("Rimuovi ingrediente", [""] + [str(i+1) for i in range(len(ingredients))], key=f"remove_ingredient_{v}")
            if remove_idx and st.button("🗑️ Rimuovi ingrediente", key=f"remove_ingredient_btn_{v}"):
                del st.session_state["recipe_builder_ingredients"][int(remove_idx)-1]
                st.rerun()

            total_weight, totals, per100 = calculate_recipe_totals(ingredients)
            st.markdown(f"**Totale ricetta:** {total_weight:.0f} g · **{totals['calories']:.0f} kcal** · Pro {totals['protein']:.1f} g · Carbs {totals['carbs']:.1f} g · Fat {totals['fat']:.1f} g")
            if st.button("💾 Salva nuova Ricetta", use_container_width=True, key=f"save_recipe_builder_{v}"):
                if not r_name.strip():
                    st.warning("Inserisci un nome per la ricetta.")
                else:
                    try:
                        ingredient_json = json.dumps(ingredients, ensure_ascii=False)
                        existing = supabase.table("recipes").select("id").eq("user_id", user_id).eq("name", r_name.strip()).limit(1).execute().data or []
                        payload = {
                            "name": r_name.strip(), "calories": int(round(per100["calories"])),
                            "protein": int(round(per100["protein"])), "carbs": int(round(per100["carbs"])),
                            "fat": int(round(per100["fat"])), "is_per_100g": 1, "user_id": user_id,
                            "ingredients_json": ingredient_json
                        }
                        if existing:
                            supabase.table("recipes").update(payload).eq("id", existing[0]["id"]).eq("user_id", user_id).execute()
                        else:
                            supabase.table("recipes").insert(payload).execute()
                        st.session_state["recipe_builder_ingredients"] = []
                        st.session_state["recipe_form_version"] += 1
                        st.success("✅ Ricetta salvata nelle immissioni rapide!")
                        st.rerun()
                    except Exception as e:
                        st.error("Impossibile salvare la ricetta. Assicurati di aver aggiunto la colonna ingredients_json alla tabella recipes. Errore: " + str(e))
        else:
            st.info("Aggiungi almeno un ingrediente per costruire la ricetta.")

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

    st.markdown(f"""<style>div[data-testid="stMetric"]:has(div:contains("Status")) {{ background-color: {move_bg} ; border: 1px solid {move_border} ; padding: 15px; border-radius: 10px; }}</style>""", unsafe_allow_html=True)
    
    with st.container(border=True):
        st.metric(t["status_move_title"], status_display_text)
        st.caption(move_msg)

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
