import streamlit as st
import pandas as pd
from datetime import date, datetime
import requests
from supabase import create_client, Client
from streamlit_cookies_controller import CookieController
import plotly.express as px

# ==============================================================================
# 1. SETUP INIZIALE E CONNESSIONE SUPABASE (Tramite Streamlit Secrets)
# ==============================================================================
SUPABASE_URL = st.secrets["SUPABASE_URL"]
SUPABASE_KEY = st.secrets["SUPABASE_KEY"]

@st.cache_resource
def init_supabase() -> Client:
    return create_client(SUPABASE_URL, SUPABASE_KEY)

supabase = init_supabase()
controller = CookieController()

# --- Rilevamento automatico dell'URL corrente (Locale vs Cloud) ---
# Questo evita problemi di redirect mismatch tra localhost e Streamlit Cloud
try:
    host_url = st.context.headers.get("Host", "localhost:8501")
    if "localhost" in host_url or "127.0.0.1" in host_url:
        REDIRECT_URL = "http://localhost:8501"
    else:
        REDIRECT_URL = "https://diario-alimentare.streamlit.app"
except Exception:
    REDIRECT_URL = "https://diario-alimentare.streamlit.app"

# --- FUNZIONE CALCOLO BMR (Formula Mifflin-St Jeor) ---
def calculate_bmr(weight, height, gender):
    if gender == "Uomo":
        return int((10 * weight) + (6.25 * height) - (5 * 30) + 5)
    else:
        return int((10 * weight) + (6.25 * height) - (5 * 30) - 161)

# ==============================================================================
# 2. GESTIONE AUTENTICAZIONE (LOGIN, SIGNUP, GOOGLE OAUTH)
# ==============================================================================
if "user" not in st.session_state:
    saved_session = controller.get("supabase_session")
    if saved_session:
        st.session_state["user"] = saved_session
        st.rerun()
    else:
        st.set_page_config(page_title="Accesso - Tracker Pro")
        st.title("🔐 Accesso Tracker Pro")
        
        # --- BLOCCO LOGIN GOOGLE ---
        if st.button("🌐 Accedi / Registrati con Google"):
            try:
                res = supabase.auth.sign_in_with_oauth({
                    "provider": "google",
                    "options": {
                        "redirect_to": REDIRECT_URL
                    }
                })
                if res.url:
                    st.markdown(f'<meta http-equiv="refresh" content="0;url={res.url}">', unsafe_allow_html=True)
            except Exception as e:
                st.error(f"Errore con Google Auth: {e}")

        st.markdown("---")
        auth_mode = st.radio("Oppure via Email", ["Login", "Registrazione"], horizontal=True)
        
        # --- FORM EMAIL ---
        with st.form("auth_form"):
            email = st.text_input("Email")
            password = st.text_input("Password (min. 6 caratteri)", type="password")
            
            target_weight = 78.0
            height = 175.0
            current_weight = 81.0
            gender = "Uomo"
            
            if auth_mode == "Registrazione":
                st.markdown("### 📋 Parametri Fisici Iniziali")
                gender = st.selectbox("Genere", ["Uomo", "Donna"])
                height = st.number_input("Altezza (cm)", value=175.0, step=1.0)
                current_weight = st.number_input("Peso Attuale (kg)", value=81.0, step=0.5)
                target_weight = st.number_input("Peso Obiettivo (kg)", value=78.0, step=0.5)
            
            submit_label = "Accedi" if auth_mode == "Login" else "Registrati"
            if st.form_submit_button(submit_label):
                try:
                    if auth_mode == "Login":
                        user = supabase.auth.sign_in_with_password({"email": email, "password": password})
                        st.session_state["user"] = user
                        controller.set("supabase_session", user, max_age=30*24*60*60)
                        st.rerun()
                    else:
                        calculated_bmr = calculate_bmr(current_weight, height, gender)
                        user = supabase.auth.sign_up({
                            "email": email, 
                            "password": password,
                            "options": {
                                "data": {
                                    "target_weight": float(target_weight),
                                    "bmr": calculated_bmr,
                                    "height": float(height),
                                    "gender": gender
                                }
                            }
                        })
                        st.success("Account creato con successo! Effettua il login.")
                except Exception as e:
                    st.error(f"Errore durante l'autenticazione: {e}")
        st.stop()

# ==============================================================================
# 3. CONFIGURAZIONE UTENTE E DATI MANCANTI (POST-LOGIN)
# ==============================================================================
st.set_page_config(page_title="Tracker Pro", layout="wide")
user_data = st.session_state["user"]
user_id = user_data.user.id
user_metadata = getattr(user_data.user, 'user_metadata', {})

display_name = user_metadata.get('display_name', user_data.user.email.split('@')[0])
user_target_weight = user_metadata.get('target_weight')
user_bmr = user_metadata.get('bmr')

# --- CONFIGURAZIONE PROFILO (Obbligatoria per Google Auth) ---
if not user_target_weight or not user_bmr:
    st.warning("⚠️ Per iniziare, configura i tuoi dati.")
    with st.form("missing_data_form"):
        st.subheader("📋 Configurazione Profilo")
        gen = st.selectbox("Genere", ["Uomo", "Donna"])
        h_val = st.number_input("Altezza (cm)", value=175.0, step=1.0)
        w_val = st.number_input("Peso Attuale (kg)", value=81.0, step=0.5)
        t_val = st.number_input("Peso Obiettivo (kg)", value=78.0, step=0.5)
        
        if st.form_submit_button("Salva e Inizia"):
            calculated_bmr = calculate_bmr(w_val, h_val, gen)
            try:
                res = supabase.auth.update_user({"data": {
                    "target_weight": float(t_val),
                    "bmr": calculated_bmr,
                    "height": float(h_val),
                    "gender": gen
                }})
                st.session_state["user"] = res
                st.rerun()
            except Exception as e:
                st.error(f"Errore: {e}")
    st.stop()

user_target_weight = float(user_target_weight)
user_bmr = int(user_bmr)

# ==============================================================================
# 4. INTERFACCIA E LOGICA APPLICATIVA (Tab 1 - Tab 4)
# ==============================================================================
# Inserisci qui il resto del codice delle tue tab (Tab 1, Tab 2, Tab 3, Tab 4)
