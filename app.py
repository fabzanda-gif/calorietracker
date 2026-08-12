import streamlit as st
import pandas as pd
from datetime import date, datetime, timedelta
import requests
from supabase import create_client
from streamlit_cookies_controller import CookieController
import plotly.express as px
import hashlib
import base64
import secrets
import traceback

## ==============================================================================
## 1. SETUP & CONFIGURATION
## ==============================================================================
st.set_page_config(page_title="Tracker Pro", layout="wide")

SUPABASE_URL = st.secrets["SUPABASE_URL"]
SUPABASE_KEY = st.secrets["SUPABASE_KEY"]

if "supabase" not in st.session_state:
    st.session_state["supabase"] = create_client(SUPABASE_URL, SUPABASE_KEY)

supabase = st.session_state["supabase"]
controller = CookieController()

## ==============================================================================
## 2. INITIALIZE SESSION STATE
## ==============================================================================
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

## ==============================================================================
## 3. UTILITY FUNCTIONS
## ==============================================================================
def calculate_bmr(weight, height, gender):
    """Calculate Basal Metabolic Rate using Mifflin-St Jeor equation"""
    if gender == "Uomo":
        return int((10 * weight) + (6.25 * height) - (5 * 30) + 5)
    else:
        return int((10 * weight) + (6.25 * height) - (5 * 30) - 161)

def refresh_daily_logs(log_date):
    """Placeholder for daily log refresh logic"""
    pass

def search_open_food_facts(query):
    """Search Open Food Facts database"""
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

## ==============================================================================
## 4. AUTHENTICATION FUNCTIONS
## ==============================================================================
def generate_pkce_pair():
    """Generate PKCE code_verifier and code_challenge for OAuth security"""
    code_verifier = base64.urlsafe_b64encode(secrets.token_bytes(32)).decode('utf-8').rstrip('=')
    code_challenge = base64.urlsafe_b64encode(
        hashlib.sha256(code_verifier.encode('utf-8')).digest()
    ).decode('utf-8').rstrip('=')
    return code_verifier, code_challenge

def save_authenticated_session(response):
    """Save authenticated user session to state and cookies"""
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

def restore_session_from_cookie():
    """Restore user session from stored cookies"""
    try:
        saved = controller.get("supabase_session")
        if not isinstance(saved, dict) or not saved.get("access_token"):
            return False
        
        response = supabase.auth.set_session(saved["access_token"], saved["refresh_token"])
        if response and response.session:
            save_authenticated_session(response)
            return True
        return False
    except Exception as e:
        print(f"Cookie restore error: {e}")
        return False

def handle_oauth_callback():
    """Handle OAuth callback from Google redirect"""
    code = st.query_params.get("code")
    if not code:
        return False
    
    verifier = st.session_state.get("pkce_verifier")
    if not verifier:
        st.error("❌ Sessione scaduta. Per favore accedi di nuovo.")
        return False
    
    try:
        response = supabase.auth.exchange_code_for_session({
            "auth_code": code,
            "code_verifier": verifier
        })
        save_authenticated_session(response)
        st.query_params.clear()
        st.session_state.pkce_verifier = None
        return True
    except Exception as e:
        st.error(f"Login fallito: {str(e)}")
        print(f"OAuth error: {traceback.format_exc()}")
        return False

def show_login_page():
    """Display login/registration page"""
    st.title("🔐 Accesso Tracker Pro")
    
    ## Google OAuth Login
    st.subheader("Accedi con Google")
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
        st.link_button("🔓 Accedi con Google", login_url, use_container_width=True)
    except Exception as e:
        st.error(f"Errore nell'inizializzazione Google login: {e}")
    
    st.markdown("---")
    
    ## Email Authentication
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
            gender = st.selectbox(
                "Genere", 
                ["Uomo", "Donna"], 
                index=None, 
                placeholder="Seleziona genere..."
            )
            height = st.number_input(
                "Altezza (cm)", 
                value=175.0, 
                min_value=100.0, 
                max_value=250.0, 
                step=1.0
            )
            current_weight = st.number_input(
                "Peso Attuale (kg)", 
                value=80.0, 
                min_value=20.0, 
                max_value=300.0, 
                step=0.5
            )
            target_weight = st.number_input(
                "Peso Obiettivo (kg)", 
                value=75.0, 
                min_value=20.0, 
                max_value=300.0, 
                step=0.5
            )
        
        submit_label = "Accedi" if auth_mode == "Login" else "Registrati"
        if st.form_submit_button(submit_label):
            try:
                if auth_mode == "Login":
                    response = supabase.auth.sign_in_with_password({
                        "email": email, 
                        "password": password
                    })
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

## ==============================================================================
## 5. AUTHENTICATION FLOW
## ==============================================================================
if "user" not in st.session_state or st.session_state["user"] is None:
    if handle_oauth_callback():
        st.rerun()

if "user" not in st.session_state or st.session_state["user"] is None:
    if restore_session_from_cookie():
        st.rerun()

if "user" not in st.session_state or st.session_state["user"] is None:
    show_login_page()
    st.stop()

## ==============================================================================
## 6. USER DATA RETRIEVAL
## ==============================================================================
user
