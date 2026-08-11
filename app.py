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

# --- LOGICA DI LOGIN PERSISTENTE ---
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

# --- CONFIGURAZIONE APP E TRADUZIONI ---
st.set_page_config(page_title="Tracker Pro", layout="wide")
user_data = st.session_state["user"]
display_name = getattr(user_data.user, 'user_metadata', {}).get('display_name', user_data.user.email.split('@')[0])
lang = st.sidebar.selectbox("🌐 Lingua / Language", ["Italiano", "English"])

# Messaggio di saluto dinamico basato su orario e stagione (agosto -> estate calda)
from datetime import datetime
now = datetime.now()
hour = now.hour

if 5 <= hour < 12:
    greeting_it = f"Buongiorno, {display_name}! ☀️ Mattinata estiva calda, carica le energie!"
    greeting_en = f"Good morning, {display_name}! ☀️ Warm summer morning, fuel up!"
elif 12 <= hour < 18:
    greeting_it = f"Buon pomeriggio, {display_name}! 🌤️ Pomeriggio estivo, occhio ai macro!"
    greeting_en = f"Good afternoon, {display_name}! 🌤️ Summer afternoon, watch your macros!"
elif 18 <= hour < 22:
    greeting_it = f"Buonasera, {display_name}! 🌙 Serata estiva, come è andata oggi?"
    greeting_en = f"Good evening, {display_name}! 🌙 Summer evening, how did today go?"
else:
    greeting_it = f"Notte fonda, {display_name}! 🌌 Riposa bene per domani."
    greeting_en = f"Late night, {display_name}! 🌌 Rest well for tomorrow."

t = {
    "Italiano": {"title": greeting_it, "tab1": "🚀 Inserimento", "tab2": "📊 Overview", "tab3": "📈 Peso", "tab4": ""},
    "English": {"title": greeting_en, "tab1": "🚀 Logging", "tab2": "📊 Overview", "tab3": "📈 Weight", "tab4": ""}
}[lang]

# Mostra il titolo dinamico
st.title(t["title"])

# --- FUNZIONI DI SUPPORTO (AGGIORNATE E SICURE) ---
def search_open_food_facts(query):
    """Cerca per nome o direttamente per codice a barre su Open Food Facts"""
    if not query or len(query) < 2: return {}
    
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    }
    
    # Se la query è un codice a barre numerico
    if query.isdigit() and len(query) >= 8:
        url = f"https://world.openfoodfacts.org/api/v0/product/{query}.json"
        try:
            response = requests.get(url, headers=headers, timeout=10)
            if response.status_code == 200:
                data = response.json()
                if data.get("status") == 1:
                    p = data.get("product", {})
                    name = p.get("product_name", "")
                    brands = p.get("brands", "")
                    if name:
                        display = f"[BARCODE] {name} ({brands})" if brands else f"[BARCODE] {name}"
                        nutri = p.get("nutriments", {})
                        return {
                            display: {
                                "name": name, 
                                "calories": float(nutri.get("energy-kcal_100g", 0)), 
                                "protein": float(nutri.get("proteins_100g", 0)), 
                                "carbs": float(nutri.get("carbohydrates_100g", 0)), 
                                "fat": float(nutri.get("fat_100g", 0))
                            }
                        }
        except Exception as e:
            st.error(f"Errore di connessione barcode: {e}")
        return {}
    
    # Ricerca testuale classica
    url = f"https://world.openfoodfacts.org/cgi/search.pl?search_terms={query}&search_simple=1&action=process&json=1"
    try:
        response = requests.get(url, headers=headers, timeout=10)
        if response.status_code == 200:
            data = response.json()
            options = {}
            for p in data.get("products", []):
                name = p.get("product_name", "")
                brands = p.get("brands", "")
                if not name: continue
                display = f"{name} ({brands})" if brands else name
                nutri = p.get("nutriments", {})
                options[display] = {
                    "name": name, 
                    "calories": float(nutri.get("energy-kcal_100g", 0)), 
                    "protein": float(nutri.get("proteins_100g", 0)), 
                    "carbs": float(nutri.get("carbohydrates_100g", 0)), 
                    "fat": float(nutri.get("fat_100g", 0))
                }
            return options
    except Exception as e:
        st.error(f"Errore di connessione: {e}")
    return {}

def refresh_daily_logs(log_date):
    """Aggiorna il bilancio calorico giornaliero su Supabase gestendo in sicurezza qualsiasi formato di data"""
    date_str = str(log_date)
    meals = supabase.table("meals").select("*").eq("date", date_str).execute().data
    acts = supabase.table("activities").select("*").eq("date", date_str).execute().data
    cals_in = sum(m['calories'] for m in meals) if meals else 0
    cals_out = sum(a['burned_calories'] for a in acts) if acts else 0
    supabase.table("daily_logs").upsert({
        "date": date_str, 
        "calories": cals_in, 
        "burned_calories": cals_out, 
        "calorie_deficit": cals_in - cals_out
    }, on_conflict="date").execute()

st.title(t["title"])
tab1, tab2, tab3, tab4 = st.tabs([t["tab1"], t["tab2"], t["tab3"], t["tab4"]])

# --- TAB 1: INSERIMENTO (Cibo, Ricette & Attività Extra) ---
with tab1:
    log_date = st.date_input("Date", value=date.today())
    
    st.subheader("🍽️ Inserimento Cibo & Pasti")
    
    input_source = st.radio("Fonte inserimento", ["🔍 Cerca online (Open Food Facts)", "🍳 Da Ricette Salvate"], horizontal=True)
    is_recipe = (input_source == "🍳 Da Ricette Salvate")

    # Inizializzazione dello state di base
    for key, default in [("m_name", ""), ("m_cals", 0), ("m_prot", 0), ("m_carbs", 0), ("m_fat", 0), ("last_selected", ""), ("form_v", 0), ("last_source", input_source)]:
        if key not in st.session_state:
            st.session_state[key] = default

    # Funzione per pulire o aggiornare i dati e forzare il refresh dei widget
    def reset_or_update(name="", cals=0, prot=0, carbs=0, fat=0, selected=""):
        st.session_state["m_name"] = name
        st.session_state["m_cals"] = int(cals)
        st.session_state["m_prot"] = int(prot)
        st.session_state["m_carbs"] = int(carbs)
        st.session_state["m_fat"] = int(fat)
        st.session_state["last_selected"] = selected
        st.session_state["form_v"] += 1

    # Se cambia la fonte (Radio button), puliamo tutto
    if st.session_state["last_source"] != input_source:
        st.session_state["last_source"] = input_source
        reset_or_update()
        st.rerun()

    if not is_recipe:
        search_q = st.text_input("Cerca per Nome o inserisci Codice a Barre", key="search_box")
        if st.button("🚀 Cerca"):
            if len(search_q) >= 2:
                with st.spinner('Ricerca in corso...'):
                    st.session_state["api_res"] = search_open_food_facts(search_q)
            else:
                st.warning("Inserisci almeno 2 caratteri o un codice a barre valido.")

        api_res = st.session_state.get("api_res", {})
        sel_prod = st.selectbox("Seleziona dal database", [""] + list(api_res.keys()), key="prod_select")
        
        if sel_prod and sel_prod != st.session_state.get("last_selected"):
            p_data = api_res[sel_prod]
            reset_or_update(
                name=p_data.get('name', ''),
                cals=p_data.get('calories', 0),
                prot=p_data.get('protein', 0),
                carbs=p_data.get('carbohydrates_100g', p_data.get('carbs', 0)),
                fat=p_data.get('fat_100g', p_data.get('fat', 0)),
                selected=sel_prod
            )
            st.rerun()
    else:
        recipes_data = supabase.table("recipes").select("*").execute().data
        recipes_dict = {r["name"]: r for r in recipes_data} if recipes_data else {}
        
        sel_recipe = st.selectbox("Seleziona una ricetta", [""] + list(recipes_dict.keys()), key="recipe_select")
        
        if sel_recipe and sel_recipe != st.session_state.get("last_selected"):
            r_obj = recipes_dict[sel_recipe]
            reset_or_update(
                name=r_obj.get('name', ''),
                cals=r_obj.get('calories', 0),
                prot=r_obj.get('protein', 0),
                carbs=r_obj.get('carbs', 0),
                fat=r_obj.get('fat', 0),
                selected=sel_recipe
            )
            st.rerun()

    v = st.session_state["form_v"]

    meal_options = ["Colazione", "Pranzo", "Cena", "Snack"]
    m_type = st.selectbox(t["meal"], meal_options, key=f"meal_type_input_{v}")

    name = st.text_input(t["meal_name"], value=st.session_state["m_name"], key=f"input_meal_name_{v}")
    
    if not is_recipe:
        grams = st.number_input("Grammi (g)", value=100.0, step=10.0, key=f"meal_grams_{v}")
        factor = grams / 100.0
        meal_display_name = f"{name} ({grams}g)"
        
        calc_cals = int(st.session_state["m_cals"] * factor)
        calc_prot = int(st.session_state["m_prot"] * factor)
        calc_carbs = int(st.session_state["m_carbs"] * factor)
        calc_fat = int(st.session_state["m_fat"] * factor)
    else:
        meal_display_name = name
        calc_cals = int(st.session_state["m_cals"])
        calc_prot = int(st.session_state["m_prot"])
        calc_carbs = int(st.session_state["m_carbs"])
        calc_fat = int(st.session_state["m_fat"])
    
    c1, c2, c3, c4 = st.columns(4)
    final_cals = c1.number_input("Kcal", value=calc_cals, step=1, key=f"input_cals_{v}")
    final_prot = c2.number_input("Pro (g)", value=calc_prot, step=1, key=f"input_prot_{v}")
    final_carbs = c3.number_input("Carbs (g)", value=calc_carbs, step=1, key=f"input_carbs_{v}")
    final_fat = c4.number_input("Fat (g)", value=calc_fat, step=1, key=f"input_fat_{v}")
    
    col_btn1, col_btn2 = st.columns([3, 1])
    with col_btn1:
        if st.button(t["add_meal"], key=f"submit_meal_btn_{v}"):
            if not name.strip():
                st.warning("Inserisci un nome valido per il pasto.")
            else:
                try:
                    supabase.table("meals").insert({
                        "date": str(log_date), 
                        "meal_type": m_type, 
                        "name": meal_display_name, 
                        "calories": int(final_cals), 
                        "protein": int(final_prot), 
                        "carbs": int(final_carbs), 
                        "fat": int(final_fat)
                    }).execute()
                    refresh_daily_logs(log_date)
                    
                    # Pulisce automaticamente i campi e resetta lo stato
                    reset_or_update()
                    st.success(f"✅ Pasto aggiunto con successo! ({final_cals} kcal)")
                    st.rerun()
                except Exception as e:
                    st.error(f"Errore nel salvataggio: {e}")
    with col_btn2:
        if st.button("Pulisci", key=f"clear_btn_{v}"):
            reset_or_update()
            st.rerun()

    st.markdown("---")
    st.subheader("🏃 Attività Extra (es. Padel, Bici)")
    with st.form("extra_act_form"):
        extra_act = st.selectbox(t["extra_act"], ["Padel", "Bici", "Camminata", "Altro"])
        extra_cals = st.number_input(t["extra_cals"], value=0, step=50)
        if st.form_submit_button("Salva Attività Extra"):
            supabase.table("activities").insert({
                "date": str(log_date), 
                "activity_name": extra_act, 
                "burned_calories": int(extra_cals)
            }).execute()
            refresh_daily_logs(log_date)
            st.success("✅ Attività extra salvata con successo!")
            st.rerun()
            
            
# --- TAB 2: RIEPILOGO GIORNALIERO ---
with tab2:
    st.subheader("📊 Riepilogo Giornaliero")
    
    summary_date = st.date_input("Data riepilogo", value=date.today(), key="summary_date_input")
    
    # Recuperiamo i dati in modo sicuro
    daily_log_res = supabase.table("daily_logs").select("*").eq("date", str(summary_date)).execute().data
    meals_data = supabase.table("meals").select("meal_type, name, calories, protein, carbs, fat").eq("date", str(summary_date)).execute().data
    
    raw_activities = supabase.table("activities").select("activity_name, burned_calories").eq("date", str(summary_date)).execute().data
    activities_data = [a for a in raw_activities if a.get("activity_name") not in ["Ufficio", "Base"]] if raw_activities else []
    
    # Calcolo delle calorie ingerite totali
    total_cals_in = sum(m.get('calories', 0) for m in meals_data) if meals_data else 0
    
    # Valore base di riferimento (default a 1900 se manca il log giornaliero)
    bmr_base = 1900
    current_weight = None
    if daily_log_res:
        row = daily_log_res[0]
        if row.get('calories_out'):
            bmr_base = row.get('calories_out')
        current_weight = row.get('weight')
        
    from datetime import datetime
    now = datetime.now()
    
    # Calcolo proporzionale del BMI (BMR / 24 * ora del giorno) finora
    if summary_date == date.today():
        bmi_so_far = int((bmr_base / 24.0) * (now.hour + now.minute / 60.0))
    else:
        bmi_so_far = bmr_base
        
    # Somma delle attività extra
    extra_burned = sum(a.get('burned_calories', 0) for a in activities_data) if activities_data else 0
    total_burned_finora = bmi_so_far + extra_burned
    
    # Calcolo del bilancio / deficit
    deficit = total_burned_finora - total_cals_in

    # --- COUNTER IN CIMA ---
    col_c1, col_c2, col_c3, col_c4 = st.columns(4)
    col_c1.metric("Kcal Ingerite", f"{total_cals_in} kcal")
    col_c2.metric("Kcal Bruciate", f"{total_burned_finora} kcal")
    col_c3.metric("Bilancio / Deficit", f"{deficit:+d} kcal")
    col_c4.metric("Peso", f"{current_weight} kg" if current_weight else "N/D")
        
    st.markdown("---")
    
    # --- TABELLA CIBI ---
    st.markdown("### 🍽️ Cibi inseriti")
    if meals_data:
        df_meals = pd.DataFrame(meals_data)
        df_meals = df_meals.rename(columns={
            "meal_type": "Pasto",
            "name": "Nome",
            "calories": "Kcal",
            "protein": "Pro (g)",
            "carbs": "Carbs (g)",
            "fat": "Fat (g)"
        })
        st.dataframe(df_meals, use_container_width=True, hide_index=True)
    else:
        st.info("Nessun pasto registrato per questa data.")
        
    st.markdown("---")
    
    # --- TABELLA ATTIVITÀ (Solo BMI proporzionale + attività extra) ---
    st.markdown("### 🏃 Calorie Bruciate & Attività")
    
    rows_acts = [{"Attività": "BMI", "Kcal Bruciate": bmi_so_far}]
    if activities_data:
        for act in activities_data:
            rows_acts.append({
                "Attività": act.get("activity_name"),
                "Kcal Bruciate": act.get("burned_calories")
            })
            
    df_acts = pd.DataFrame(rows_acts)
    st.dataframe(df_acts, use_container_width=True, hide_index=True)
    
# --- TAB 3: PESO ---
with tab3:
    w = st.number_input(t["insert_weight"], value=80.9, step=0.1)
    if st.button(t["save_weight"]): 
        supabase.table("daily_logs").upsert({"date": str(date.today()), "weight": w}, on_conflict="date").execute()
        st.rerun()
        
    logs = supabase.table("daily_logs").select("date, weight").not_.is_("weight", "null").order("date").execute().data
    if logs:
        df = pd.DataFrame(logs)
        df['date'] = pd.to_datetime(df['date'])
        
        # Creiamo il range completo e interpoliamo
        df_full = df.set_index('date').reindex(pd.date_range(df['date'].min(), df['date'].max())).interpolate().reset_index().rename(columns={'index': 'date'})
        
        # Identifichiamo quali sono reali e quali interpolati
        real_dates = set(df['date'])
        df_full['is_real'] = df_full['date'].isin(real_dates)
        
        df_full['date_str'] = df_full['date'].dt.strftime('%d %b %Y')
        df_full['weight_str'] = df_full['weight'].round(1).astype(str) + " kg"
        
        # Dividiamo in due DataFrame separati per gestire perfettamente la trasparenza
        df_real = df_full[df_full['is_real']]
        df_interp = df_full[~df_full['is_real']]
        
        fig = px.bar()
        
        # Aggiungiamo le barre reali (piene)
        fig.add_bar(
            x=df_real['date'], y=df_real['weight'],
            marker_color='#007BFF', marker_opacity=1.0,
            customdata=df_real[['date_str', 'weight_str']],
            hovertemplate="<b>⚖️ %{customdata[0]}</b><br><b>%{customdata[1]}</b><extra></extra>",
            name="Reale"
        )
        
        # Aggiungiamo le barre interpolate/proiettate (trasparenti)
        fig.add_bar(
            x=df_interp['date'], y=df_interp['weight'],
            marker_color='#007BFF', marker_opacity=0.25,
            customdata=df_interp[['date_str', 'weight_str']],
            hovertemplate="<b>⚖️ %{customdata[0]}</b><br><b>%{customdata[1]} (Proiezione)</b><extra></extra>",
            name="Proiezione"
        )
        
        fig.update_yaxes(range=[75, 90])
        
        # Linea del target in Giallo Oro brillante (#FFD700)
        fig.add_hline(y=78, line_dash="dash", line_color="#FFD700", line_width=3.5)
        
        # Testo del goal in Giallo Oro brillante posizionato in alto a destra
        fig.add_annotation(
            xref="paper", yref="y", x=0.98, y=88.5, 
            text="<b>🎯 GOAL: 78 kg</b>", 
            showarrow=False, 
            font=dict(color="#FFD700", size=16, family="sans-serif"), 
            align="right",
            bgcolor="rgba(0,0,0,0.5)",
            borderpad=4
        )
        
        fig.update_layout(
            showlegend=False, 
            plot_bgcolor="rgba(0,0,0,0)", 
            paper_bgcolor="rgba(0,0,0,0)",
            barmode='overlay'
        )
        st.plotly_chart(fig, use_container_width=True)
# --- TAB 4: RICETTE ---
with tab4:
    with st.form("recipe_add"):
        r_name = st.text_input(t["recipe_name"])
        c1, c2, c3, c4 = st.columns(4)
        cals = c1.number_input("Kcal", value=0, step=1, key="r_cal")
        prot = c2.number_input("Pro", value=0, step=1, key="r_pro")
        carbs = c3.number_input("Carbs", value=0, step=1, key="r_carbs")
        fat = c4.number_input("Fat", value=0, step=1, key="r_fat")
        
        if st.form_submit_button(t["save_recipe"]):
            if not r_name.strip():
                st.warning("Inserisci un nome valido per la ricetta.")
            else:
                try:
                    user_id = st.session_state["user"].user.id
                    
                    supabase.table("recipes").upsert({
                        "name": r_name.strip(), 
                        "calories": int(cals), 
                        "protein": int(prot), 
                        "carbs": int(carbs), 
                        "fat": int(fat),
                        "user_id": user_id
                    }, on_conflict="name").execute()
                    
                    st.success(t["recipe_saved"])
                    st.rerun()
                except Exception as e:
                    st.error(f"Errore durante il salvataggio: {e}")
