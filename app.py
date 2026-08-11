import streamlit as st
import pandas as pd
from datetime import date, timedelta
from supabase import create_client, Client

# --- CSS MODERNO ---
st.markdown("""
    <style>
    /* Arrotonda i contenitori e i bottoni */
    .stButton>button {
        border-radius: 20px;
        background-color: #007BFF;
        color: white;
        width: 100%;
    }
    .stTextInput>div>div>input, .stSelectbox>div>div>select, .stNumberInput>div>div>input {
        border-radius: 15px;
    }
    /* Stile per le card */
    div[data-testid="stMetricValue"] {
        font-size: 24px;
        color: #007BFF;
    }
    </style>
    """, unsafe_allow_html=True)

st.set_page_config(page_title="Tracker Pro", layout="wide")

# Credenziali Supabase
SUPABASE_URL = "https://inhmvbdujpxrqrlcgmqw.supabase.co"
SUPABASE_KEY = "sb_publishable_1fQpT5dZqjre5D7MXm1aMg_ZQVRMjJq"

@st.cache_resource
def init_supabase() -> Client:
    return create_client(SUPABASE_URL, SUPABASE_KEY)

supabase = init_supabase()

st.title("⚖️ Tracker Pro")

# --- NAVIGAZIONE A TAB (Miglioramento #4) ---
tab1, tab2, tab3, tab4 = st.tabs(["🚀 Inserimento", "📊 Overview", "📈 Peso", "🍳 Ricette"])

# --- TAB 1: INSERIMENTO ---
with tab1:
    st.header("Registra la giornata")
    log_date = st.date_input("Data", value=date.today())
    
    # Base Calorie
    with st.form("day_type_form"):
        day_type = st.selectbox("Tipo di Giornata (Base)", ["Casa (1900 kcal)", "Ufficio (2200 kcal)"])
        extra_act = st.selectbox("Attività Extra", ["Nessuna", "Padel", "Bici", "Camminata"])
        extra_cals = st.number_input("Kcal Extra", value=0, step=50)
        if st.form_submit_button("Salva Configurazione Giornata"):
            base_cals = 2200 if "Ufficio" in day_type else 1900
            base_name = "Ufficio" if "Ufficio" in day_type else "Casa"
            # Pulizia e inserimento... (logica precedente)
            supabase.table("activities").delete().eq("date", str(log_date)).execute()
            supabase.table("activities").insert([
                {"date": str(log_date), "activity_name": base_name, "burned_calories": base_cals},
                {"date": str(log_date), "activity_name": extra_act, "burned_calories": extra_cals}
            ]).execute()
            st.success("Configurazione salvata!")

    # Pasti
    with st.form("meal_form"):
        meal_type = st.selectbox("Pasto", ["Colazione", "Pranzo", "Cena", "Snack"])
        name = st.text_input("Nome Pasto")
        c1, c2, c3, c4 = st.columns(4)
        cals = c1.number_input("Kcal", value=0)
        prot = c2.number_input("Pro", value=0)
        carbs = c3.number_input("Carbs", value=0)
        fat = c4.number_input("Fat", value=0)
        if st.form_submit_button("Aggiungi Pasto"):
            supabase.table("meals").insert({"date": str(log_date), "meal_type": meal_type, "name": name, "calories": cals, "protein": prot, "carbs": carbs, "fat": fat}).execute()
            st.success("Pasto aggiunto!")

    if st.button("🔄 Aggiorna Totali"):
        # Logica ricalcolo...
        st.rerun()

# --- TAB 2: OVERVIEW ---
with tab2:
    st.header("🎯 Overview Giornaliera")
    # Qui inserisci le metriche con lo stile arrotondato creato nel CSS
    # ... (Codice Overview precedente)

# --- TAB 3: PESO ---
with tab3:
    st.header("Grafico Peso")
    # ... (Codice grafico)

# --- TAB 4: RICETTE ---
with tab4:
    st.header("Gestione Ricette")
    # ... (Codice ricette)
