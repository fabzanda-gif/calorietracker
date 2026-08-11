import streamlit as st
import pandas as pd
from datetime import date, datetime
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

def refresh_daily_logs(log_date):
    meals = supabase.table("meals").select("*").eq("date", str(log_date)).execute().data
    acts = supabase.table("activities").select("*").eq("date", str(log_date)).execute().data
    cals_in = sum(m['calories'] for m in meals) if meals else 0
    cals_out = sum(a['burned_calories'] for a in acts) if acts else 0
    supabase.table("daily_logs").upsert({
        "date": str(log_date), 
        "calories": cals_in, 
        "burned_calories": cals_out, 
        "calorie_deficit": cals_in - cals_out
    }, on_conflict="date").execute()

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
            refresh_daily_logs(log_date)
            st.success("Configurazione salvata!")

    recipes_res = supabase.table("recipes").select("*").execute().data
    recipe_dict = {r['name']: r for r in recipes_res} if recipes_res else {}

    with st.form("meal_form"):
        st.subheader("🍽️ Inserisci Pasto")
        selected_recipe = st.selectbox("Seleziona Ricetta (Opzionale)", [""] + list(recipe_dict.keys()))
        ref = recipe_dict.get(selected_recipe, {})
        m_type = st.selectbox("Pasto", ["Colazione", "Pranzo", "Cena", "Snack"])
        name = st.text_input("Nome Pasto", value=selected_recipe)
        c1, c2, c3, c4 = st.columns(4)
        cals, prot, carbs, fat = c1.number_input("Kcal", value=int(ref.get('calories', 0))), c2.number_input("Pro", value=int(ref.get('protein', 0))), c3.number_input("Carbs", value=int(ref.get('carbs', 0))), c4.number_input("Fat", value=int(ref.get('fat', 0)))
        if st.form_submit_button("Aggiungi Pasto"):
            supabase.table("meals").insert({"date": str(log_date), "meal_type": m_type, "name": name, "calories": cals, "protein": prot, "carbs": carbs, "fat": fat}).execute()
            refresh_daily_logs(log_date)
            st.rerun()

# --- TAB 2: OVERVIEW ---
with tab2:
    st.header("🎯 Overview Giornaliera (Proporzionale all'ora)")
    today_str = str(date.today())
    
    # Preleviamo i pasti di oggi per calcolare le ingerite
    meals_today = supabase.table("meals").select("*").eq("date", today_str).execute().data
    cals_in = sum(m['calories'] for m in meals_today) if meals_today else 0
    
    # Preleviamo le attività/base configurate oggi
    acts_today = supabase.table("activities").select("*").eq("date", today_str).execute().data
    
    # Troviamo la base giornaliera (1900 o 2200), se non impostata usiamo 1900 di default
    base_daily = 1900
    extra_burned = 0
    for a in acts_today:
        if a['activity_name'] in ["Casa", "Ufficio"]:
            base_daily = a['burned_calories']
        elif a['activity_name'] != "Nessuna":
            extra_burned += a['burned_calories']

    # Calcolo proporzionale in base all'ora corrente
    now = datetime.now()
    current_hour = now.hour + (now.minute / 60.0)
    # Evitiamo divisioni strane o ore a zero spaccato
    hours_passed = max(current_hour, 0.1) 
    
    # Bruciate finora = (Base giornaliera / 24 * ore passate) + eventuali attività extra registrate
    proportional_burned = int((base_daily / 24.0) * hours_passed + extra_burned)
    
    # Calcolo del deficit basato sulle ingerite e le bruciate stimate a quest'ora
    current_deficit = cals_in - proportional_burned

    c1, c2, c3 = st.columns(3)
    c1.metric("🔥 Kcal Ingerite", f"{cals_in} kcal")
    c2.metric("⚡ Kcal Bruciate (Stimate ad ora)", f"{proportional_burned} kcal")
    c3.metric("📉 Deficit Attuale", f"{current_deficit} kcal")
    
    if current_deficit < 0:
        st.success("💪 Ottimo lavoro! Sei in deficit calorico, continua così!")
    elif current_deficit > 0:
        st.warning("⚠️ Sei in surplus calorico per il momento della giornata.")
    else:
        st.info("⚖️ Sei in perfetto pareggio.")

# --- TAB 3: PESO ---
with tab3:
    st.header("📈 Analisi Peso")
    
    # Inserimento peso
    w = st.number_input("Inserisci Peso (kg)", value=82.0, step=0.1)
    if st.button("Salva Peso"):
        supabase.table("daily_logs").upsert({"date": str(date.today()), "weight": w}, on_conflict="date").execute()
        st.success("Peso aggiornato!")
    
    # Recupero dati
    logs = supabase.table("daily_logs").select("date, weight").not_.is_("weight", "null").order("date").execute().data
    
    if logs:
        df = pd.DataFrame(logs)
        df['date'] = pd.to_datetime(df['date'])
        df = df.set_index('date')
        
        # 1. Creiamo un range di date completo dal primo al'ultimo log
        idx = pd.date_range(df.index.min(), df.index.max())
        
        # 2. Reindicizziamo e interpoliamo (il valore fittizio)
        df_full = df.reindex(idx)
        df_full['is_real'] = df_full['weight'].notnull() # Segniamo cosa è vero
        df_full['weight'] = df_full['weight'].interpolate() # Creiamo la proiezione
        df_full = df_full.reset_index().rename(columns={'index': 'date'})
        
        # 3. Grafico con Plotly
        import plotly.express as px
        
        # Creiamo un colore/opacità basato su 'is_real'
        fig = px.bar(
            df_full, x='date', y='weight', 
            color='is_real', 
            color_discrete_map={True: '#007BFF', False: '#A0CFFF'}, # Blu scuro per vero, chiaro per proiezione
            title="Trend Peso (con proiezioni)"
        )
        
        # Impostazione range Y (75-90) e linea obiettivo
        fig.update_yaxes(range=[75, 90])
        fig.add_hline(y=78, line_dash="dash", line_color="red", annotation_text="Goal: 78kg")
        
        # Nascondiamo la legenda che non serve
        fig.update_layout(showlegend=False)
        
        st.plotly_chart(fig, use_container_width=True)

# --- TAB 4: RICETTE ---
with tab4:
    st.header("Gestione Ricette")
    with st.form("recipe_add"):
        r_name = st.text_input("Nome Ricetta")
        c1, c2, c3, c4 = st.columns(4)
        if st.form_submit_button("Salva Ricetta"):
            supabase.table("recipes").upsert({"name": r_name, "calories": c1.number_input("Kcal", value=0), "protein": c2.number_input("Pro", value=0), "carbs": c3.number_input("Carbs", value=0), "fat": c4.number_input("Fat", value=0)}, on_conflict="name").execute()
            st.success("Ricetta salvata!")
    recipes = supabase.table("recipes").select("*").execute().data
    if recipes: st.dataframe(pd.DataFrame(recipes), use_container_width=True)
