import streamlit as st
import pandas as pd
from datetime import date, timedelta
from supabase import create_client, Client

# --- CSS MODERNO ---
st.markdown("""
    <style>
    .stButton>button { border-radius: 20px; background-color: #007BFF; color: white; width: 100%; }
    .stTextInput>div>div>input, .stSelectbox>div>div>select, .stNumberInput>div>div>input { border-radius: 15px; }
    div[data-testid="stMetricValue"] { font-size: 24px; color: #007BFF; }
    </style>
    """, unsafe_allow_html=True)

st.set_page_config(page_title="Tracker Pro", layout="wide")

SUPABASE_URL = "https://inhmvbdujpxrqrlcgmqw.supabase.co"
SUPABASE_KEY = "sb_publishable_1fQpT5dZqjre5D7MXm1aMg_ZQVRMjJq"

@st.cache_resource
def init_supabase() -> Client:
    return create_client(SUPABASE_URL, SUPABASE_KEY)

supabase = init_supabase()

st.title("⚖️ Tracker Pro")

# --- NAVIGAZIONE ---
tab1, tab2, tab3, tab4 = st.tabs(["🚀 Inserimento", "📊 Overview", "📈 Peso", "🍳 Ricette"])

# --- TAB 1: INSERIMENTO ---
with tab1:
    st.header("Registra la giornata")
    log_date = st.date_input("Data", value=date.today())
    
    with st.form("day_type_form"):
        day_type = st.selectbox("Tipo di Giornata (Base)", ["Casa (1900 kcal)", "Ufficio (2200 kcal)"])
        extra_act = st.selectbox("Attività Extra", ["Nessuna", "Padel", "Bici", "Camminata"])
        extra_cals = st.number_input("Kcal Extra", value=0, step=50)
        if st.form_submit_button("Salva Configurazione"):
            base_cals = 2200 if "Ufficio" in day_type else 1900
            base_name = "Ufficio" if "Ufficio" in day_type else "Casa"
            supabase.table("activities").delete().eq("date", str(log_date)).execute()
            supabase.table("activities").insert([
                {"date": str(log_date), "activity_name": base_name, "burned_calories": base_cals},
                {"date": str(log_date), "activity_name": extra_act, "burned_calories": extra_cals} if extra_act != "Nessuna" else {"date": str(log_date), "activity_name": "Nessuna", "burned_calories": 0}
            ]).execute()
            st.success("Configurazione salvata!")

    with st.form("meal_form"):
        m_type = st.selectbox("Pasto", ["Colazione", "Pranzo", "Cena", "Snack"])
        name = st.text_input("Nome Pasto")
        c1, c2, c3, c4 = st.columns(4)
        cals, prot, carbs, fat = c1.number_input("Kcal", value=0), c2.number_input("Pro", value=0), c3.number_input("Carbs", value=0), c4.number_input("Fat", value=0)
        if st.form_submit_button("Aggiungi Pasto"):
            supabase.table("meals").insert({"date": str(log_date), "meal_type": m_type, "name": name, "calories": cals, "protein": prot, "carbs": carbs, "fat": fat}).execute()
            st.success("Pasto aggiunto!")

    if st.button("🔄 Aggiorna Totali Giornalieri"):
        # Logica di calcolo che avevamo già scritto
        meals = supabase.table("meals").select("*").eq("date", str(log_date)).execute().data
        acts = supabase.table("activities").select("*").eq("date", str(log_date)).execute().data
        cals_in = sum(m['calories'] for m in meals)
        cals_out = sum(a['burned_calories'] for a in acts)
        supabase.table("daily_logs").upsert({"date": str(log_date), "calories": cals_in, "burned_calories": cals_out, "calorie_deficit": cals_in - cals_out}, on_conflict="date").execute()
        st.success("Dati aggiornati!")

# --- TAB 2: OVERVIEW ---
with tab2:
    st.header("🎯 Overview Giornaliera")
    today_str = str(date.today())
    today_log = supabase.table("daily_logs").select("*").eq("date", today_str).execute().data
    if today_log:
        row = today_log[0]
        c1, c2, c3 = st.columns(3)
        c1.metric("Ingerite", f"{row.get('calories', 0)} kcal")
        c2.metric("Bruciate", f"{row.get('burned_calories', 0)} kcal")
        c3.metric("Deficit", f"{row.get('calorie_deficit', 0)} kcal")
    else:
        st.info("Nessun dato per oggi. Usa il pulsante 'Aggiorna' nella tab Inserimento!")

# --- TAB 3: PESO ---
with tab3:
    st.header("Analisi Peso")
    w = st.number_input("Peso (kg)", value=82.0, step=0.1)
    if st.button("Salva Peso"):
        supabase.table("daily_logs").upsert({"date": str(date.today()), "weight": w}, on_conflict="date").execute()
        st.success("Peso aggiornato!")
    logs = supabase.table("daily_logs").select("date, weight").execute().data
    if logs:
        st.line_chart(pd.DataFrame(logs).set_index('date')['weight'])

# --- TAB 4: RICETTE ---
with tab4:
    st.header("Ricette")
    recipes = supabase.table("recipes").select("*").execute().data
    st.dataframe(pd.DataFrame(recipes), use_container_width=True)
