import streamlit as st
import pandas as pd
from datetime import date, datetime
import requests
import base64
import secrets
import hashlib
import traceback
from supabase import create_client
from streamlit_cookies_controller import CookieController
import plotly.express as px

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
SUPABASE_URL = st.secrets["SUPABASE_URL"]
SUPABASE_KEY = st.secrets["SUPABASE_KEY"]

if "supabase" not in st.session_state:
    st.session_state["supabase"] = create_client(SUPABASE_URL, SUPABASE_KEY)

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
    "prod_select": ""
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
            url = f"https://world.openfoodfacts.org/api/v2/product/{query}.json"
            response = requests.get(url, timeout=10)
            payload = response.json()
            if payload.get("status") != 1:
                return {}
            products = [payload.get("product", {})]
        else:
            url = "https://world.openfoodfacts.org/cgi/search.pl"
            response = requests.get(
                url, 
                params={
                    "search_terms": query, 
                    "search_simple": 1, 
                    "action": "process", 
                    "json": 1, 
                    "page_size": 20
                }, 
                timeout=10
            )
            products = response.json().get("products", [])

        results = {}
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

# ==============================================================================
# 4. AUTHENTICATION & SESSION MANAGEMENT (PERSISTENTE CON COOKIE PKCE)
# ==============================================================================
def generate_pkce_pair():
    code_verifier = base64.urlsafe_b64encode(secrets.token_bytes(32)).decode('utf-8').rstrip('=')
    code_challenge = base64.urlsafe_b64encode(
        hashlib.sha256(code_verifier.encode('utf-8')).digest()
    ).decode('utf-8').rstrip('=')
    
    controller.set("pkce_verifier_cookie", code_verifier, max_age=300)
    return code_verifier, code_challenge

def save_authenticated_session(response):
    try:
        user = response.user if hasattr(response, 'user') and response.user else response.session.user
        st.session_state["user"] = user
        
        if response.session:
            controller.set(
                "supabase_session", 
                {
                    "access_token": response.session.access_token, 
                    "refresh_token": response.session.refresh_token
                }, 
                max_age=30*24*60*60
            )
    except Exception as e:
        st.error(f"Errore nel salvataggio della sessione: {e}")
        print(traceback.format_exc())

def show_login_page():
    st.title("SanoSync")
    
    verifier, challenge = generate_pkce_pair()
    st.session_state.pkce_verifier = verifier
    
    try:
        login_url = supabase.auth.sign_in_with_oauth({
            "provider": "google",
            "options": {
                "redirect_to": "https://diario-alimentare.streamlit.app",
                "code_challenge": challenge,
                "code_challenge_method": "s256"
            }
        }).url
    except Exception as e:
        st.error(f"Errore nell'inizializzazione Google login: {e}")
        login_url = "#"
    
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

# --- ESECUZIONE DEL CONTROLLO SESSIONE ALL'AVVIO ---
if "user" not in st.session_state or st.session_state["user"] is None:
    query_code = st.query_params.get("code")
    if query_code:
        verifier = st.session_state.get("pkce_verifier")
        if not verifier:
            verifier = controller.get("pkce_verifier_cookie")
            
        if verifier:
            try:
                response = supabase.auth.exchange_code_for_session({
                    "auth_code": query_code,
                    "code_verifier": verifier
                })
                save_authenticated_session(response)
                st.query_params.clear()
                st.session_state.pkce_verifier = None
                controller.set("pkce_verifier_cookie", None, max_age=0)
                st.rerun()
            except Exception as e:
                st.error(f"Login OAuth fallito: {str(e)}")
        else:
            st.query_params.clear()

    if "user" not in st.session_state or st.session_state["user"] is None:
        try:
            saved_cookie = controller.get("supabase_session")
            if isinstance(saved_cookie, dict) and saved_cookie.get("access_token"):
                response = supabase.auth.set_session(
                    saved_cookie["access_token"], 
                    saved_cookie["refresh_token"]
                )
                if response and response.session:
                    save_authenticated_session(response)
                    st.rerun()
        except Exception as e:
            print(f"Cookie restore error: {e}")

if "user" not in st.session_state or st.session_state["user"] is None:
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
    
    # 1. Radio button con callback per gestire il cambio valore istantaneo
    def on_mode_change():
        new_mode = st.session_state[f"mode_radio_{v}"]
        if new_mode == t["per_100g"]:
            st.session_state["grams_val"] = 100.0
            st.session_state["is_per_100g_val"] = True
        else:
            st.session_state["grams_val"] = 1.0
            st.session_state["is_per_100g_val"] = False
        st.session_state[f"dyn_qty_{v}"] = st.session_state["grams_val"]

    mode = st.radio(
        t["calc_mode"], 
        [t["per_100g"], t["per_portion"]], 
        index=0 if st.session_state["is_per_100g_val"] else 1, 
        horizontal=True,
        key=f"mode_radio_{v}",
        on_change=on_mode_change
    )
    
    # 2. Number input che usa il valore di sessione aggiornato dalla callback
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
            
            meal_options_del = {f"{m['meal_type']} - {m['name']} ({m['calories']} kcal)": m['id'] for m in meals_with_id}
            selected_meal_to_del = st.selectbox(t["del_meal"], [""] + list(meal_options_del.keys()))
            
            if selected_meal_to_del:
                if st.button(t["del_meal_btn"]):
                    meal_id_to_delete = meal_options_del[selected_meal_to_del]
                    supabase.table("meals").delete().eq("id", meal_id_to_delete).execute()
                    st.success(t["meal_del_success"])
                    st.rerun()
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
    
    with st.container(border=True):
        col_w1, col_w2 = st.columns(2)
        
        with col_w1:
            st.markdown(f"#### {t['log_today_weight']}")
            w = st.number_input(
                t["insert_weight"], 
                value=80.0, 
                min_value=20.0, 
                max_value=300.0,
                step=0.1
            )
            if st.button(t["save_weight"], use_container_width=True):
                try:
                    supabase.table("daily_logs").upsert({
                        "user_id": user_id,
                        "date": str(date.today()),
                        "weight": w
                    }, on_conflict="user_id,date").execute()
                    st.success("✅ Peso salvato!")
                    st.rerun()
                except Exception as e:
                    st.error(f"Errore: {e}")
        
        with col_w2:
            st.markdown(f"#### {t['update_target']}")
            new_target = st.number_input(
                "Peso Obiettivo (kg)", 
                value=float(user_target_weight) if user_target_weight else 75.0,
                min_value=20.0,
                max_value=300.0,
                step=0.5
            )
            if st.button(t["save_target"], use_container_width=True):
                try:
                    res = supabase.auth.update_user({
                        "data": {"target_weight": float(new_target)}
                    })
                    if res.user:
                        st.session_state["user"] = res.user
                    st.success(t["target_updated"])
                    st.rerun()
                except Exception as e:
                    st.error(f"Errore: {e}")
                    print(traceback.format_exc())
    
    with st.container(border=True):
        try:
            logs = supabase.table("daily_logs").select("date, weight").eq("user_id", user_id).not_.is_("weight", "null").order("date", desc=False).execute().data
            
            if logs:
                df = pd.DataFrame(logs)
                df['date'] = pd.to_datetime(df['date'])
                
                df_full = df.set_index('date').reindex(pd.date_range(df['date'].min(), df['date'].max())).interpolate().reset_index().rename(columns={'index': 'date'})
                
                real_dates = set(df['date'])
                df_full['is_real'] = df_full['date'].isin(real_dates)
                
                target_val = float(user_target_weight) if user_target_weight else 75.0
                latest_weight = df['weight'].iloc[-1]
                
                forecast_markdown = ""
                days_to_goal = 0
                estimated_date = None
                
                if len(df) >= 3 and latest_weight > target_val:
                    recent_df = df.tail(min(len(df), 14))
                    days_diff = (recent_df['date'].max() - recent_df['date'].min()).days
                    weight_diff = recent_df['weight'].iloc[-1] - recent_df['weight'].iloc[0]
                    
                    if days_diff > 0 and weight_diff < 0:
                        kg_per_day = abs(weight_diff / days_diff)
                        kg_to_lose = latest_weight - target_val
                        days_to_goal = int(kg_to_lose / kg_per_day)
                        
                        estimated_date = datetime.now() + pd.Timedelta(days=days_to_goal)
                        est_date_str = estimated_date.strftime('%d %B %Y')
                        
                        forecast_markdown = f"""
                        <div style="background-color: #FFFFFF; border: 1px solid #FF8B8B; padding: 12px 16px; border-radius: 10px; margin-top: 15px; color: #1A2942; font-weight: 500;">
                            {t['weight_forecast_title']}<br>
                            <span style="font-size: 14px; font-weight: 400;">{t['forecast_days'](days_to_goal, est_date_str)}</span>
                        </div>
                        """
                    else:
                        forecast_markdown = f"""
                        <div style="background-color: #FFFFFF; border: 1px solid #FF8B8B; padding: 12px 16px; border-radius: 10px; margin-top: 15px; color: #1A2942; font-weight: 500;">
                            {t['weight_forecast_title']}<br>
                            <span style="font-size: 14px; font-weight: 400;">{t['forecast_flat_up']}</span>
                        </div>
                        """

                df_full['date_str'] = df_full['date'].dt.strftime('%d %b %Y')
                df_full['weight_str'] = df_full['weight'].round(1).astype(str) + " kg"
                
                df_real = df_full[df_full['is_real']]
                df_interp = df_full[~df_full['is_real']]
                
                fig = px.bar()
                
                fig.add_bar(
                    x=df_real['date'], y=df_real['weight'],
                    marker_color='#FF8B8B',
                    customdata=df_real[['date_str', 'weight_str']],
                    hovertemplate="<b>⚖️ %{customdata[0]}</b><br><b>%{customdata[1]}</b><extra></extra>",
                    name="Reale"
                )
                
                fig.add_bar(
                    x=df_interp['date'], y=df_interp['weight'],
                    marker_color='rgba(26, 41, 66, 0.2)',
                    customdata=df_interp[['date_str', 'weight_str']],
                    hovertemplate="<b>⚖️ %{customdata[0]}</b><br><b>%{customdata[1]} (Proiezione)</b><extra></extra>",
                    name="Proiezione"
                )

                if len(df) >= 3 and latest_weight > target_val and estimated_date and days_to_goal > 0:
                    first_real_date = df_real['date'].iloc[0]
                    first_real_weight = df_real['weight'].iloc[0]
                    
                    fig.add_scatter(
                        x=[first_real_date, estimated_date],
                        y=[first_real_weight, target_val],
                        mode='lines+markers',
                        line=dict(color='#FF8B8B', width=3, dash='dash'),
                        marker=dict(size=6, color='#FF8B8B'),
                        name="Trend Globale"
                    )
                
                min_weight = min(75, float(user_target_weight) - 3) if user_target_weight else 75
                max_weight = max(90, float(user_target_weight) + 10) if user_target_weight else 90
                fig.update_yaxes(range=[min_weight, max_weight])
                
                fig.add_hline(
                    y=target_val, 
                    line_dash="solid", 
                    line_color='#1A2942', 
                    line_width=2.5
                )
                
                fig.add_annotation(
                    xref="paper", yref="y", x=0.98, y=target_val + 2.0,
                    text=f"<b>🎯 GOAL: {target_val} kg</b>",
                    showarrow=False,
                    font=dict(color="#1A2942", size=14, family="sans-serif"),
                    align="right",
                    bgcolor="rgba(255, 255, 255, 0.9)",
                    bordercolor="#FF8B8B",
                    borderwidth=1,
                    borderpad=4
                )
                
                fig.update_layout(
                    showlegend=False,
                    plot_bgcolor="#FFFFFF", 
                    paper_bgcolor="rgba(0,0,0,0)",
                    barmode='overlay',
                    hovermode='x unified',
                    font=dict(color="#1A2942")
                )
                st.plotly_chart(fig, use_container_width=True)
                
                if forecast_markdown:
                    st.markdown(forecast_markdown, unsafe_allow_html=True)
            else:
                st.info("📊 Nessun dato di peso registrato ancora. Inizia registrando il tuo peso!")
        except Exception as e:
            st.error(f"Errore nel caricamento grafico: {e}")
            print(traceback.format_exc())

# ==============================================================================
# 12. PAGE 4: QUICK ENTRIES (IMMISSIONI RAPIDE)
# ==============================================================================
elif selected_page == t["t4"]:
    st.subheader(t["quick_entries"])

    if "recipe_form_version" not in st.session_state:
        st.session_state["recipe_form_version"] = 0
    
    v = st.session_state["recipe_form_version"]

    with st.container(border=True):
        st.markdown(f"### {t['saved_entries']}")
        entries = supabase.table("recipes").select("*").eq("user_id", user_id).execute().data
        if entries:
            df_entries = pd.DataFrame(entries)
            df_display = df_entries.rename(columns={
                "name": "Nome", "calories": "Kcal", 
                "protein": "Pro", "carbs": "Carbs", "fat": "Fat"
            })
            st.dataframe(df_display[["Nome", "Kcal", "Pro", "Carbs", "Fat"]], use_container_width=True, hide_index=True)
            
            st.markdown(f"### {t['del_quick']}")
            entry_options_del = {e['name']: e['name'] for e in entries}
            sel_entry_del = st.selectbox(t["select_quick_del"], [""] + list(entry_options_del.keys()), key=f"del_recipe_sel_{v}")
            if sel_entry_del:
                if st.button(t["del_quick_btn"], key=f"del_recipe_btn_{v}"):
                    try:
                        supabase.table("recipes").delete().eq("user_id", user_id).eq("name", sel_entry_del).execute()
                        st.success(f"Immissione Rapida '{sel_entry_del}' eliminata!")
                        st.rerun()
                    except Exception as e:
                        st.error(f"Errore durante l'eliminazione: {e}")
        else:
            st.info("Nessuna immissione rapida presente.")

    with st.container(border=True):
        with st.form(f"quick_entry_add_{v}"):
            st.markdown(f"### {t['quick_add_title']}")
            r_name = st.text_input(t["recipe_name"], placeholder="Es. Pasta al pomodoro o Snack", key=f"r_name_{v}")
            
            calc_type = st.radio(
                t["calc_mode_radio"],
                ["Per 100g (valori scalabili)", "Per porzione fissa (valori assoluti)"],
                horizontal=True,
                key=f"r_calc_type_{v}"
            )
            
            st.caption(t["caption_calc"])
            
            c1, c2, c3, c4 = st.columns(4)
            cals = c1.number_input("Kcal", value=0.0, min_value=0.0, step=1.0, key=f"r_cal_{v}")
            prot = c2.number_input("Pro (g)", value=0.0, min_value=0.0, step=0.5, key=f"r_prot_{v}")
            carbs = c3.number_input("Carbs (g)", value=0.0, min_value=0.0, step=0.5, key=f"r_carbs_{v}")
            fat = c4.number_input("Fat (g)", value=0.0, min_value=0.0, step=0.5, key=f"r_fat_{v}")
            
            is_per_100g = 1 if "100g" in calc_type else 0
            
            if st.form_submit_button(t["save_recipe"], use_container_width=True):
                if not r_name.strip():
                    st.warning("Inserisci un nome valido.")
                else:
                    try:
                        supabase.table("recipes").insert({
                            "name": r_name.strip(), 
                            "calories": int(cals), 
                            "protein": int(prot), 
                            "carbs": int(carbs), 
                            "fat": int(fat),
                            "is_per_100g": is_per_100g,
                            "user_id": user_id
                        }).execute()
                        
                        st.session_state["recipe_form_version"] += 1
                        st.success(t["recipe_saved"])
                        st.rerun()
                    except Exception as e:
                        try:
                            supabase.table("recipes").insert({
                                "name": r_name.strip(), 
                                "calories": int(cals), 
                                "protein": int(prot), 
                                "carbs": int(carbs), 
                                "fat": int(fat),
                                "user_id": user_id
                            }).execute()
                            
                            st.session_state["recipe_form_version"] += 1
                            st.success(t["recipe_saved"])
                            st.rerun()
                        except Exception as inner_e:
                            st.error(f"Errore durante il salvataggio: {inner_e}")
                            print(traceback.format_exc())

# ==============================================================================
# 13. PAGE 5: ACTIVITY & STEPS LOGGING
# ==============================================================================
elif selected_page == t["t5"]:
    st.subheader(t["register_activity"])
    act_date = st.date_input(t["act_date"], value=date.today())
    
    try:
        existing_log = supabase.table("daily_logs").select("steps").eq("date", str(act_date)).eq("user_id", user_id).execute().data
        day_steps = existing_log[0].get("steps", 0) if existing_log and existing_log[0].get("steps") else 0
    except Exception:
        day_steps = 0

    move_bg, move_border = "#FFFFFF", "#FF8B8B"
    if day_steps >= 10000:
        move_msg = t["status_very_active"]
    elif day_steps >= 5000:
        move_msg = t["status_good"]
    else:
        move_msg = t["status_lazy"]

    st.markdown(f"""<style>div[data-testid="stMetric"]:has(div:contains("Status")) {{ background-color: {move_bg} ; border: 1px solid {move_border} ; padding: 15px; border-radius: 10px; }}</style>""", unsafe_allow_html=True)
    
    with st.container(border=True):
        st.metric(t["status_move_title"], f"{day_steps} passi")
        st.caption(move_msg)

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
                    
                    estim_cals = int(new_steps * 0.04)
                    existing_act = supabase.table("activities").select("id").eq("user_id", user_id).eq("date", str(act_date)).eq("activity_name", "Passi (Stima)").execute().data
                    
                    if existing_act:
                        supabase.table("activities").update({"burned_calories": estim_cals}).eq("id", existing_act[0]["id"]).execute()
                    else:
                        supabase.table("activities").insert({"user_id": user_id, "date": str(act_date), "activity_name": "Passi (Stima)", "burned_calories": estim_cals}).execute()
                    
                    refresh_daily_logs(act_date)
                    
                    st.toast(f"✅ Passi aggiornati con successo! ({estim_cals} kcal stimate)", icon="👣")
                    st.success(f"✅ {t['steps_updated']} ({estim_cals} kcal totali stimate)")
                    st.rerun()
                except Exception as e:
                    st.error(f"Errore nel salvataggio dei passi: {e}")

    with col_a2:
        with st.container(border=True):
            st.markdown(f"### {t['bike_title']}")
            bike_min = st.number_input(t["bike_min"], value=0, min_value=0, step=5)
            if st.button(t["add_bike"], use_container_width=True):
                if bike_min > 0:
                    estim_cals = int(bike_min * 8)
                    supabase.table("activities").insert({"user_id": user_id, "date": str(act_date), "activity_name": "Bici", "burned_calories": estim_cals}).execute()
                    refresh_daily_logs(act_date)
                    
                    st.toast(f"✅ Aggiunti {bike_min} min di bici! ({estim_cals} kcal)", icon="🚲")
                    st.success(f"✅ Aggiunte {bike_min} min di bici ({estim_cals} kcal)!")
                    st.rerun()
                else:
                    st.warning("Inserisci almeno 1 minuto di bici.")

    with col_a3:
        with st.container(border=True):
            st.markdown(f"### {t['other_act']}")
            with st.form("activity_form", clear_on_submit=True):
                extra_act = st.selectbox(t["activity_label"], ["Padel", "Palestra", "Nuoto", "Altro"])
                extra_cals = st.number_input("Kcal bruciate", value=0, min_value=0, step=50)
                if st.form_submit_button(t["add_act_btn"], use_container_width=True):
                    supabase.table("activities").insert({"user_id": user_id, "date": str(act_date), "activity_name": extra_act, "burned_calories": int(extra_cals)}).execute()
                    refresh_daily_logs(act_date)
                    
                    st.toast(f"✅ {extra_act} registrato con successo! ({extra_cals} kcal)", icon="🎯")
                    st.success(f"✅ {extra_act} registrato con successo! ({extra_cals} kcal)")
                    st.rerun()
