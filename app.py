import streamlit as st
import pandas as pd
from datetime import date, datetime
import requests
from supabase import create_client, Client
from streamlit_cookies_controller import CookieController
import plotly.express as px

# --- SETUP SUPABASE ---
SUPABASE_URL = "https://inhmvbdujpxrqrlcgmqw.supabase.co"
SUPABASE_KEY = "sb_publishable_1fQpT5dZqjre5D7MXm1aMg_ZQVRMjJq"

@st.cache_resource
def init_supabase() -> Client:
    return create_client(SUPABASE_URL, SUPABASE_KEY)

supabase = init_supabase()
controller = CookieController()

# --- LOGICA DI LOGIN ---
if "user" not in st.session_state:
    saved_session = controller.get("supabase_session")
    if saved_session:
        st.session_state["user"] = saved_session
        st.rerun()
    else:
        st.set_page_config(page_title="Login - Tracker Pro")
        st.title("🔐 Accesso Tracker Pro")
        with st.form("login_form"):
            email = st.text_input("Email")
            password = st.text_input("Password", type="password")
            if st.form_submit_button("Login"):
                try:
                    user = supabase.auth.sign_in_with_password({"email": email, "password": password})
                    st.session_state["user"] = user
                    controller.set("supabase_session", user, max_age=30*24*60*60)
                    st.rerun()
                except Exception: st.error("Credenziali non valide.")
        st.stop()

st.set_page_config(page_title="Tracker Pro", layout="wide")
user_data = st.session_state["user"]
display_name = getattr(user_data.user, 'user_metadata', {}).get('display_name', user_data.user.email.split('@')[0])
lang = st.sidebar.selectbox("🌐 Lingua / Language", ["Italiano", "English"])

t = {
    "Italiano": {"title": f"⚖️ Tracker Pro - Ciao, {display_name}!", "tab1": "🚀 Inserimento", "tab2": "📊 Overview", "tab3": "📈 Peso", "tab4": "🍳 Ricette", "day_type": "Tipo di Giornata", "extra_act": "Attività Extra", "extra_cals": "Kcal Extra", "save_conf": "Salva Configurazione", "conf_saved": "Configurazione salvata!", "meal": "Pasto", "meal_name": "Nome Pasto", "add_meal": "Aggiungi Pasto", "meal_added": "Pasto aggiunto!", "overview_title": "🎯 Overview Giornaliera", "eaten": "🔥 Kcal Ingerite", "burned": "⚡ Kcal Bruciate (Stimate)", "deficit": "📉 Deficit Attuale", "weight_analysis": "📈 Analisi Peso", "insert_weight": "Inserisci Peso (kg)", "save_weight": "Peso aggiornato!", "recipes_title": "🍳 Gestione Ricette", "recipe_name": "Nome Ricetta", "save_recipe": "Salva Ricetta", "recipe_saved": "Ricetta salvata!", "goal_target": "🎯 Obiettivo Deficit Rimanente"},
    "English": {"title": f"⚖️ Tracker Pro - Hello, {display_name}!", "tab1": "🚀 Logging", "tab2": "📊 Overview", "tab3": "📈 Weight", "tab4": "🍳 Recipes", "day_type": "Day Type", "extra_act": "Extra Activity", "extra_cals": "Extra Cals", "save_conf": "Save Configuration", "conf_saved": "Configuration saved!", "meal": "Meal", "meal_name": "Meal Name", "add_meal": "Add Meal", "meal_added": "Meal added!", "overview_title": "🎯 Daily Overview", "eaten": "🔥 Calories Eaten", "burned": "⚡ Calories Burned (Estimated)", "deficit": "📉 Current Deficit", "weight_analysis": "📈 Weight Analysis", "insert_weight": "Insert Weight (kg)", "save_weight": "Weight updated!", "recipes_title": "🍳 Recipe Management", "recipe_name": "Recipe Name", "save_recipe": "Save Recipe", "recipe_saved": "Recipe saved!", "goal_target": "🎯 Remaining Deficit Target"}
}[lang]

def refresh_daily_logs(log_date):
    meals = supabase.table("meals").select("*").eq("date", str(log_date)).execute().data
    acts = supabase.table("activities").select("*").eq("date", str(log_date)).execute().data
    cals_in = sum(m['calories'] for m in meals) if meals else 0
    cals_out = sum(a['burned_calories'] for a in acts) if acts else 0
    supabase.table("daily_logs").upsert({"date": str(log_date), "calories": cals_in, "burned_calories": cals_out, "calorie_deficit": cals_in - cals_out}, on_conflict="date").execute()

st.title(t["title"])
tab1, tab2, tab3, tab4 = st.tabs([t["tab1"], t["tab2"], t["tab3"], t["tab4"]])

with tab1:
    log_date = st.date_input("Date", value=date.today())
    with st.form("day_type_form"):
        day_type = st.selectbox(t["day_type"], ["Casa (1900 kcal)", "Ufficio (2200 kcal)"])
        extra_act = st.selectbox(t["extra_act"], ["Nessuna", "Padel", "Bici", "Camminata"])
        extra_cals = st.number_input(t["extra_cals"], value=0, step=50)
        if st.form_submit_button(t["save_conf"]):
            supabase.table("activities").delete().eq("date", str(log_date)).execute()
            supabase.table("activities").insert([{"date": str(log_date), "activity_name": "Base", "burned_calories": 2200 if "Ufficio" in day_type else 1900}, {"date": str(log_date), "activity_name": extra_act, "burned_calories": extra_cals}]).execute()
            refresh_daily_logs(log_date); st.success(t["conf_saved"])

with tab2:
    st.header(t["overview_title"])
    today_str = str(date.today())
    meals = supabase.table("meals").select("*").eq("date", today_str).execute().data
    acts = supabase.table("activities").select("*").eq("date", today_str).execute().data
    cals_in = sum(m['calories'] for m in meals) if meals else 0
    
    base_cal = 1900
    extra_cal = 0
    for a in acts:
        name = a.get('activity_name', '')
        cals = a.get('burned_calories', 0)
        if name in ["Casa", "Ufficio", "Base"] or "kcal" in name.lower():
            base_cal = cals
        else:
            extra_cal += cals
            
    now = datetime.now()
    est_burned = int((base_cal / 24.0) * (now.hour + now.minute/60) + extra_cal)
    
    c1, c2, c3 = st.columns(3)
    c1.metric(t["eaten"], f"{cals_in} kcal")
    c2.metric(t["burned"], f"{est_burned} kcal")
    latest_w = supabase.table("daily_logs").select("weight").not_.is_("weight", "null").order("date", desc=True).limit(1).execute().data
    curr_w = latest_w[0]['weight'] if latest_w else 80.9
    target = max(0.0, curr_w - 78.0) * 10676
    c3.metric(t["goal_target"], f"{int(target):,} kcal")

with tab3:
    w = st.number_input(t["insert_weight"], value=80.9, step=0.1)
    if st.button(t["save_weight"]): supabase.table("daily_logs").upsert({"date": str(date.today()), "weight": w}, on_conflict="date").execute(); st.rerun()
    logs = supabase.table("daily_logs").select("date, weight").not_.is_("weight", "null").order("date").execute().data
    if logs:
        df = pd.DataFrame(logs)
        df['date'] = pd.to_datetime(df['date'])
        df = df.set_index('date').reindex(pd.date_range(df['date'].min(), df['date'].max()))
        df['is_real'] = df['weight'].notnull()
        df['weight'] = df['weight'].interpolate()
        df = df.reset_index().rename(columns={'index': 'date'})
        df['date_str'] = df['date'].dt.strftime('%d %b %Y')
        df['weight_str'] = df['weight'].round(1).astype(str) + " kg"
        
        fig = px.bar(df, x='date', y='weight', color='is_real', 
                     color_discrete_map={True: '#007BFF', False: 'rgba(0, 123, 255, 0.3)'}, 
                     title="Trend Peso", custom_data=['date_str', 'weight_str'])
        
        fig.update_traces(hovertemplate="<b>📅 %{customdata[0]}</b><br>⚖️ <b>%{customdata[1]}</b><extra></extra>")
        fig.update_yaxes(range=[75, 90])
        
        # Linea del goal con scritta esterna in alto a destra
        fig.add_hline(y=78, line_dash="dot", line_color="#FF4B4B", line_width=2)
        fig.add_annotation(
            xref="paper", yref="y", x=0.98, y=78.3,
            text="<b>🎯 GOAL: 78 kg</b>",
            showarrow=False, font=dict(color="#FF4B4B", size=14),
            align="right"
        )
        
        fig.update_layout(showlegend=False, plot_bgcolor="rgba(0,0,0,0)", paper_bgcolor="rgba(0,0,0,0)")
        st.plotly_chart(fig, use_container_width=True)

with tab4:
    with st.form("recipe_add"):
        r_name = st.text_input(t["recipe_name"])
        c1, c2, c3, c4 = st.columns(4)
        cals, prot, carbs, fat = c1.number_input("Kcal", key="r_cal"), c2.number_input("Pro", key="r_pro"), c3.number_input("Carbs", key="r_carbs"), c4.number_input("Fat", key="r_fat")
        if st.form_submit_button(t["save_recipe"]): supabase.table("recipes").upsert({"name": r_name, "calories": cals, "protein": prot, "carbs": carbs, "fat": fat}, on_conflict="name").execute(); st.rerun()
    recipes = supabase.table("recipes").select("*").execute().data
    if recipes: st.dataframe(pd.DataFrame(recipes), use_container_width=True)
