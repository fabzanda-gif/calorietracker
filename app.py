import streamlit as st
import pandas as pd
from datetime import date, datetime
import requests
from supabase import create_client, Client

# --- SETUP SUPABASE ---
SUPABASE_URL = "https://inhmvbdujpxrqrlcgmqw.supabase.co"
SUPABASE_KEY = "sb_publishable_1fQpT5dZqjre5D7MXm1aMg_ZQVRMjJq"

@st.cache_resource
def init_supabase() -> Client:
    return create_client(SUPABASE_URL, SUPABASE_KEY)

supabase = init_supabase()

# --- LOGICA DI LOGIN ---
if "user" not in st.session_state:
    st.set_page_config(page_title="Login - Tracker Pro")
    st.title("🔐 Accesso Tracker Pro")
    with st.form("login_form"):
        email = st.text_input("Email")
        password = st.text_input("Password", type="password")
        if st.form_submit_button("Login"):
            try:
                user = supabase.auth.sign_in_with_password({"email": email, "password": password})
                st.session_state["user"] = user
                st.rerun()
            except Exception:
                st.error("Credenziali non valide.")
    st.stop()

# --- RECUPERO DISPLAY NAME ---
user_data = st.session_state["user"]
user_metadata = getattr(user_data.user, 'user_metadata', {})
display_name = user_metadata.get('display_name', user_data.user.email.split('@')[0])

# --- APP PRINCIPALE ---
st.set_page_config(page_title="Tracker Pro", layout="wide")

# --- SELETTORE LINGUA ---
lang = st.sidebar.selectbox("🌐 Lingua / Language", ["Italiano", "English"])

# Dizionario traduzioni
t = {
    "Italiano": {
        "title": f"⚖️ Tracker Pro - Ciao, {display_name}!",
        "tab1": "🚀 Inserimento", "tab2": "📊 Overview", "tab3": "📈 Peso", "tab4": "🍳 Ricette",
        "reg_day": "Registra la giornata", "day_type": "Tipo di Giornata", "extra_act": "Attività Extra",
        "extra_cals": "Kcal Extra", "save_conf": "Salva Configurazione", "conf_saved": "Configurazione salvata!",
        "select_recipe": "Seleziona Ricetta", "meal": "Pasto", "meal_name": "Nome Pasto", "add_meal": "Aggiungi Pasto",
        "meal_added": "Pasto aggiunto!", "overview_title": "🎯 Overview Giornaliera", "eaten": "🔥 Kcal Ingerite",
        "burned": "⚡ Kcal Bruciate (Stimate)", "deficit": "📉 Deficit Attuale", "weight_analysis": "📈 Analisi Peso",
        "insert_weight": "Inserisci Peso (kg)", "save_weight": "Peso aggiornato!", "recipes_title": "🍳 Gestione Ricette",
        "recipe_name": "Nome Ricetta", "save_recipe": "Salva Ricetta", "recipe_saved": "Ricetta salvata!",
        "goal_target": "🎯 Obiettivo Deficit Rimanente", "goal_text": "Kcal totali da bruciare per arrivare a 78kg"
    },
    "English": {
        "title": f"⚖️ Tracker Pro - Hello, {display_name}!",
        "tab1": "🚀 Logging", "tab2": "📊 Overview", "tab3": "📈 Weight", "tab4": "🍳 Recipes",
        "reg_day": "Log the day", "day_type": "Day Type", "extra_act": "Extra Activity",
        "extra_cals": "Extra Cals", "save_conf": "Save Configuration", "conf_saved": "Configuration saved!",
        "select_recipe": "Select Recipe", "meal": "Meal", "meal_name": "Meal Name", "add_meal": "Add Meal",
        "meal_added": "Meal added!", "overview_title": "🎯 Daily Overview", "eaten": "🔥 Calories Eaten",
        "burned": "⚡ Calories Burned (Estimated)", "deficit": "📉 Current Deficit", "weight_analysis": "📈 Weight Analysis",
        "insert_weight": "Insert Weight (kg)", "save_weight": "Weight updated!", "recipes_title": "🍳 Recipe Management",
        "recipe_name": "Recipe Name", "save_recipe": "Save Recipe", "recipe_saved": "Recipe saved!",
        "goal_target": "🎯 Remaining Deficit Target", "goal_text": "Total kcal to burn to reach 78kg"
    }
}[lang]

# --- CSS MODERNO ---
st.markdown("""
    <style>
    .stButton>button { border-radius: 20px; background-color: #007BFF; color: white; width: 100%; }
    .stTextInput>div>div>input, .stSelectbox>div>div>select, .stNumberInput>div>div>input { border-radius: 15px; }
    div[data-testid="stMetricValue"] { font-size: 24px; color: #007BFF; }
    </style>
    """, unsafe_allow_html=True)

# --- FUNZIONI API OPEN FOOD FACTS ---
def search_open_food_facts(query):
    if not query or len(query) < 3:
        return {}
    url = f"https://world.openfoodfacts.org/cgi/search.pl?search_terms={query}&search_simple=1&action=process&json=1"
    try:
        response = requests.get(url, timeout=5)
        if response.status_code == 200:
            data = response.json()
            products = data.get("products", [])
            options = {}
            for p in products:
                name = p.get("product_name", "Unknown")
                brands = p.get("brands", "")
                full_name = f"{name} ({brands})" if brands else name
                nutri = p.get("nutriments", {})
                cals = nutri.get("energy-kcal_100g", nutri.get("energy-kcal", 0))
                pro = nutri.get("proteins_100g", 0)
                carbs = nutri.get("carbohydrates_100g", 0)
                fat = nutri.get("fat_100g", 0)
                options[full_name] = {
                    "name": name,
                    "calories": int(cals) if cals else 0,
                    "protein": int(pro) if pro else 0,
                    "carbs": int(carbs) if carbs else 0,
                    "fat": int(fat) if fat else 0
                }
            return options
    except Exception:
        pass
    return {}

def search_by_barcode(barcode):
    if not barcode or len(barcode) < 8:
        return {}
    url = f"https://world.openfoodfacts.org/api/v0/product/{barcode}.json"
    try:
        response = requests.get(url, timeout=5)
        if response.status_code == 200:
            data = response.json()
            if data.get("status") == 1:
                p = data.get("product", {})
                name = p.get("product_name", "Unknown")
                brands = p.get("brands", "")
                full_name = f"{name} ({brands})" if brands else name
                nutri = p.get("nutriments", {})
                cals = nutri.get("energy-kcal_100g", nutri.get("energy-kcal", 0))
                pro = nutri.get("proteins_100g", 0)
                carbs = nutri.get("carbohydrates_100g", 0)
                fat = nutri.get("fat_100g", 0)
                return {
                    "name": full_name,
                    "calories": int(cals) if cals else 0,
                    "protein": int(pro) if pro else 0,
                    "carbs": int(carbs) if carbs else 0,
                    "fat": int(fat) if fat else 0
                }
    except Exception:
        pass
    return {}

def refresh_daily_logs(log_date):
    meals = supabase.table("meals").select("*").eq("date", str(log_date)).execute().data
    acts = supabase.table("activities").select("*").eq("date", str(log_date)).execute().data
    cals_in = sum(m['calories'] for m in meals) if meals else 0
    cals_out = sum(a['burned_calories'] for a in acts) if acts else 0
    supabase.table("daily_logs").upsert({"date": str(log_date), "calories": cals_in, "burned_calories": cals_out, "calorie_deficit": cals_in - cals_out}, on_conflict="date").execute()

st.title(t["title"])
tab1, tab2, tab3, tab4 = st.tabs([t["tab1"], t["tab2"], t["tab3"], t["tab4"]])

with tab1:
    log_date = st.date_input("Data / Date", value=date.today())
    with st.form("day_type_form"):
        day_type = st.selectbox(t["day_type"], ["Casa (1900 kcal)", "Ufficio (2200 kcal)"])
        extra_act = st.selectbox(t["extra_act"], ["Nessuna / None", "Padel", "Bici / Bike", "Camminata / Walk"])
        extra_cals = st.number_input(t["extra_cals"], value=0, step=50)
        if st.form_submit_button(t["save_conf"]):
            base_cals = 2200 if "Ufficio" in day_type else 1900
            base_name = "Ufficio" if "Ufficio" in day_type else "Casa"
            supabase.table("activities").delete().eq("date", str(log_date)).execute()
            supabase.table("activities").insert([{"date": str(log_date), "activity_name": base_name, "burned_calories": base_cals}, {"date": str(log_date), "activity_name": extra_act, "burned_calories": extra_cals} if "Nessuna" not in extra_act else {"date": str(log_date), "activity_name": "Nessuna", "burned_calories": 0}]).execute()
            refresh_daily_logs(log_date)
            st.success(t["conf_saved"])

    with st.form("meal_form"):
        st.subheader("🍽️ Inserisci Pasto")
        barcode_input = st.text_input("📷 Codice a Barre / Barcode (Opzionale)", "")
        barcode_result = search_by_barcode(barcode_input) if barcode_input else {}

        search_query = st.text_input("🔍 Cerca su Open Food Facts", "")
        api_results = search_open_food_facts(search_query) if search_query else {}
        selected_api_product = st.selectbox("Seleziona da Open Food Facts", [""] + list(api_results.keys()))

        if barcode_result:
            ref = barcode_result
        else:
            ref = api_results.get(selected_api_product, {})

        m_type = st.selectbox(t["meal"], ["Colazione / Breakfast", "Pranzo / Lunch", "Cena / Dinner", "Snack"])
        name = st.text_input(t["meal_name"], value=ref.get('name', search_query if not barcode_input else barcode_result.get('name', '')))
        
        c1, c2, c3, c4 = st.columns(4)
        cals = c1.number_input("Kcal", value=int(ref.get('calories', 0)))
        prot = c2.number_input("Pro (g)", value=int(ref.get('protein', 0)))
        carbs = c3.number_input("Carbs (g)", value=int(ref.get('carbs', 0)))
        fat = c4.number_input("Fat (g)", value=int(ref.get('fat', 0)))
        
        if st.form_submit_button(t["add_meal"]):
            supabase.table("meals").insert({"date": str(log_date), "meal_type": m_type, "name": name, "calories": cals, "protein": prot, "carbs": carbs, "fat": fat}).execute()
            refresh_daily_logs(log_date)
            st.success(t["meal_added"])
            st.rerun()

with tab2:
    st.header(t["overview_title"])
    today_str = str(date.today())
    meals_today = supabase.table("meals").select("*").eq("date", today_str).execute().data
    cals_in = sum(m['calories'] for m in meals_today) if meals_today else 0
    acts_today = supabase.table("activities").select("*").eq("date", today_str).execute().data
    base_daily, extra_burned = 1900, 0
    for a in acts_today:
        if a['activity_name'] in ["Casa", "Ufficio"]: base_daily = a['burned_calories']
        elif "Nessuna" not in a['activity_name']: extra_burned += a['burned_calories']
    now = datetime.now()
    current_hour = now.hour + (now.minute / 60.0)
    proportional_burned = int((base_daily / 24.0) * max(current_hour, 0.1) + extra_burned)
    
    c1, c2, c3 = st.columns(3)
    c1.metric(t["eaten"], f"{cals_in} kcal")
    c2.metric(t["burned"], f"{proportional_burned} kcal")
    c3.metric(t["deficit"], f"{cals_in - proportional_burned} kcal")
    
    st.divider()
    
    latest_weight_res = supabase.table("daily_logs").select("weight").not_.is_("weight", "null").order("date", desc=True).limit(1).execute().data
    current_weight = latest_weight_res[0]['weight'] if latest_weight_res else 80.9
    kg_to_lose = max(0.0, current_weight - 78.0)
    total_kcal_target = kg_to_lose * 10676
    
    st.metric(t["goal_target"], f"{int(total_kcal_target):,} kcal", help=f"Kg to 78kg: {kg_to_lose:.1f} kg")

with tab3:
    st.header(t["weight_analysis"])
    w = st.number_input(t["insert_weight"], value=80.9, step=0.1)
    if st.button(t["save_weight"]):
        supabase.table("daily_logs").upsert({"date": str(date.today()), "weight": w}, on_conflict="date").execute()
        st.success(t["save_weight"])
    logs = supabase.table("daily_logs").select("date, weight").not_.is_("weight", "null").order("date").execute().data
    if logs:
        df = pd.DataFrame(logs)
        df['date'] = pd.to_datetime(df['date'])
        df = df.set_index('date')
        idx = pd.date_range(df.index.min(), df.index.max())
        df_full = df.reindex(idx)
        df_full['is_real'] = df_full['weight'].notnull()
        df_full['weight'] = df_full['weight'].interpolate()
        df_full = df_full.reset_index().rename(columns={'index': 'date'})
        df_full['date_str'] = df_full['date'].dt.strftime('%d %b %Y')
        df_full['weight_str'] = df_full['weight'].round(1).astype(str) + " kg"
        import plotly.express as px
        fig = px.bar(df_full, x='date', y='weight', color='is_real', color_discrete_map={True: '#007BFF', False: '#A0CFFF'}, title="Trend Peso", custom_data=['date_str', 'weight_str'])
        fig.update_traces(hovertemplate="<b>📅 %{customdata[0]}</b><br>⚖️ <b>%{customdata[1]}</b><extra></extra>")
        fig.update_yaxes(range=[75, 90])
        fig.add_hline(y=78, line_dash="dot", line_color="white", line_width=4, annotation_text="<span style='color:white; font-size:20px;'><b>🎯 GOAL: 78 kg</b></span>")
        fig.update_layout(showlegend=False, plot_bgcolor="rgba(0,0,0,0)", paper_bgcolor="rgba(0,0,0,0)")
        st.plotly_chart(fig, use_container_width=True)

with tab4:
    st.header(t["recipes_title"])
    with st.form("recipe_add"):
        r_name = st.text_input(t["recipe_name"])
        c1, c2, c3, c4 = st.columns(4)
        if st.form_submit_button(t["save_recipe"]):
            supabase.table("recipes").upsert({"name": r_name, "calories": c1.number_input("Kcal", value=0), "protein": c2.number_input("Pro (g)", value=0), "carbs": c3.number_input("Carbs (g)", value=0), "fat": c4.number_input("Fat (g)", value=0)}, on_conflict="name").execute()
            st.success(t["recipe_saved"])
            st.rerun()
    recipes = supabase.table("recipes").select("*").execute().data
    if recipes: st.dataframe(pd.DataFrame(recipes), use_container_width=True)
