import streamlit as st
import pandas as pd
from datetime import date, datetime
import requests
from supabase import create_client, Client
from streamlit_cookies_controller import CookieController
import plotly.express as px

# ==============================================================================
# 1. SETUP INIZIALE E CONNESSIONE SUPABASE
# ==============================================================================
SUPABASE_URL = st.secrets["SUPABASE_URL"]
SUPABASE_KEY = st.secrets["SUPABASE_KEY"]

@st.cache_resource
def init_supabase() -> Client:
    return create_client(SUPABASE_URL, SUPABASE_KEY)

supabase = init_supabase()
controller = CookieController()

# --- Rilevamento automatico dell'URL (Locale vs Cloud) ---
try:
    host_url = st.context.headers.get("Host", "localhost:8501")
    REDIRECT_URL = "http://localhost:8501" if "localhost" in host_url else "https://diario-alimentare.streamlit.app"
except Exception:
    REDIRECT_URL = "https://diario-alimentare.streamlit.app"

# --- FUNZIONE CALCOLO BMR ---
def calculate_bmr(weight, height, gender):
    if gender == "Uomo":
        return int((10 * weight) + (6.25 * height) - (5 * 30) + 5)
    else:
        return int((10 * weight) + (6.25 * height) - (5 * 30) - 161)

# ==============================================================================
# 2. GESTIONE AUTENTICAZIONE
# ==============================================================================
if "user" not in st.session_state:
    saved_session = controller.get("supabase_session")
    if saved_session:
        st.session_state["user"] = saved_session
        st.rerun()
    else:
        st.set_page_config(page_title="Accesso - Tracker Pro")
        st.title("🔐 Accesso Tracker Pro")
        
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
                        response = supabase.auth.sign_in_with_password({"email": email, "password": password})
                        
                        # Salvataggio sicuro della sessione senza errori JSON
                        session_data = {
                            "access_token": response.session.access_token,
                            "refresh_token": response.session.refresh_token,
                            "user": {
                                "id": response.user.id,
                                "email": response.user.email,
                                "user_metadata": response.user.user_metadata
                            }
                        }
                        
                        st.session_state["user"] = response
                        controller.set("supabase_session", session_data, max_age=30*24*60*60)
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

# Gestione sicura sia dell'oggetto utente nativo che del dizionario salvato in sessione
if hasattr(user_data, "user"):
    user_id = user_data.user.id
    user_metadata = getattr(user_data.user, 'user_metadata', {})
    user_email = user_data.user.email
else:
    user_id = user_data["user"]["id"]
    user_metadata = user_data["user"].get("user_metadata", {})
    user_email = user_data["user"].get("email", "")

display_name = user_metadata.get('display_name', user_email.split('@')[0] if user_email else "Utente")
user_target_weight = user_metadata.get('target_weight')
user_bmr = user_metadata.get('bmr')

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
# 4. INTERFACCIA E LOGICA APPLICATIVA (TABS)
# ==============================================================================
lang = st.sidebar.selectbox("🌐 Lingua", ["Italiano", "English"])
now = datetime.now()
greeting = f"Ciao {display_name}!"
t = {
    "Italiano": {
        "tab1": "🚀 Inserimento", "tab2": "📊 Overview", "tab3": "📈 Peso", "tab4": "🍳 Ricette",
        "meal": "Tipo di pasto", "meal_name": "Nome pasto", "add_meal": "Aggiungi Pasto",
        "extra_act": "Attività Extra", "extra_cals": "Calorie Bruciate Extra",
        "insert_weight": "Inserisci Peso (kg)", "save_weight": "Salva Peso",
        "recipe_name": "Nome Ricetta", "save_recipe": "Salva Ricetta", "recipe_saved": "✅ Ricetta salvata con successo!"
    },
    "English": {
        "tab1": "🚀 Logging", "tab2": "📊 Overview", "tab3": "📈 Weight", "tab4": "🍳 Recipes",
        "meal": "Meal Type", "meal_name": "Meal Name", "add_meal": "Add Meal",
        "extra_act": "Extra Activity", "extra_cals": "Extra Burned Calories",
        "insert_weight": "Insert Weight (kg)", "save_weight": "Save Weight",
        "recipe_name": "Recipe Name", "save_recipe": "Save Recipe", "recipe_saved": "✅ Recipe saved successfully!"
    }
}[lang]

st.title(greeting)

def search_open_food_facts(query):
    try:
        url = f"https://world.openfoodfacts.org/cgi/search.pl?search_terms={query}&search_simple=1&action=process&json=1"
        res = requests.get(url, headers={"User-Agent": "TrackerPro - Python"})
        if res.status_code == 200:
            products = res.json().get("products", [])
            results = {}
            for p in products[:10]:
                name = p.get("product_name", "Senza nome")
                nutriments = p.get("nutriments", {})
                results[name] = {
                    "name": name,
                    "calories": nutriments.get("energy-kcal_100g", nutriments.get("energy-kcal", 0)),
                    "protein": nutriments.get("proteins_100g", 0),
                    "carbohydrates_100g": nutriments.get("carbohydrates_100g", 0),
                    "fat_100g": nutriments.get("fat_100g", 0)
                }
            return results
    except Exception:
        pass
    return {}

def refresh_daily_logs(log_date):
    pass

tab1, tab2, tab3, tab4 = st.tabs([t["tab1"], t["tab2"], t["tab3"], t["tab4"]])

# ==============================================================================
# 5. LOGOUT
# ==============================================================================
with st.sidebar:
    st.markdown(f"👤 **{display_name}**")
    if st.button("🚪 Esci (Logout)"):
        controller.set("supabase_session", None, max_age=0)
        for key in list(st.session_state.keys()):
            del st.session_state[key]
        st.rerun()

# ==========================================
# 6. TAB 1: INSERIMENTO (CIBO, RICETTE & ATTIVITÀ)
# ==========================================
with tab1:
    log_date = st.date_input("Date", value=date.today())
    
    st.subheader("🍽️ Inserimento Cibo & Pasti")
    
    input_source = st.radio("Fonte inserimento", ["🔍 Cerca online (Open Food Facts)", "🍳 Da Ricette Salvate"], horizontal=True)
    is_recipe = (input_source == "🍳 Da Ricette Salvate")

    # Inizializzazione dello state
    for key, default in [
        ("m_name", ""), ("m_cals", 0), ("m_prot", 0), ("m_carbs", 0), ("m_fat", 0),
        ("last_selected", ""), ("last_source", input_source), ("grams_val", 100.0), ("form_v", 0)
    ]:
        if key not in st.session_state:
            st.session_state[key] = default

    def reset_or_update(name="", cals=0, prot=0, carbs=0, fat=0, selected="", grams=100.0):
        st.session_state["m_name"] = name
        st.session_state["m_cals"] = float(cals)
        st.session_state["m_prot"] = float(prot)
        st.session_state["m_carbs"] = float(carbs)
        st.session_state["m_fat"] = float(fat)
        st.session_state["grams_val"] = float(grams)
        st.session_state["last_selected"] = selected
        # Incrementando form_v cambiamo la key dei number_input, forzando Streamlit a svuotarli e aggiornarli
        st.session_state["form_v"] += 1

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
                selected=sel_prod,
                grams=100.0
            )
            st.rerun()
    else:
        recipes_data = supabase.table("recipes").select("*").eq("user_id", user_id).execute().data
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
                selected=sel_recipe,
                grams=1.0
            )
            st.rerun()

    v = st.session_state["form_v"]

    meal_options = ["Colazione", "Pranzo", "Cena", "Snack"]
    m_type = st.selectbox(t["meal"], meal_options, key=f"meal_type_input_{v}")

    name = st.text_input(t["meal_name"], value=st.session_state["m_name"], key=f"input_meal_name_{v}")
    
    if not is_recipe:
        grams = st.number_input("Grammi (g)", value=st.session_state["grams_val"], step=10.0, key=f"meal_grams_{v}")
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
                        "user_id": user_id,
                        "date": str(log_date), 
                        "meal_type": m_type, 
                        "name": meal_display_name, 
                        "calories": int(final_cals), 
                        "protein": int(final_prot), 
                        "carbs": int(final_carbs), 
                        "fat": int(final_fat)
                    }).execute()
                    refresh_daily_logs(log_date)
                    
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
                "user_id": user_id,
                "date": str(log_date), 
                "activity_name": extra_act, 
                "burned_calories": int(extra_cals)
            }).execute()
            refresh_daily_logs(log_date)
            st.success("✅ Attività extra salvata con successo!")
            st.rerun()
            
# ==========================================
# 7. TAB 2: RIEPILOGO GIORNALIERO (OVERVIEW)
# ==========================================
with tab2:
    st.subheader("📊 Riepilogo Giornaliero")
    
    summary_date = st.date_input("Data riepilogo", value=date.today(), key="summary_date_input")
    
    daily_log_res = supabase.table("daily_logs").select("*").eq("date", str(summary_date)).eq("user_id", user_id).execute().data
    meals_data = supabase.table("meals").select("meal_type, name, calories, protein, carbs, fat").eq("date", str(summary_date)).eq("user_id", user_id).execute().data
    
    raw_activities = supabase.table("activities").select("activity_name, burned_calories").eq("date", str(summary_date)).eq("user_id", user_id).execute().data
    activities_data = [a for a in raw_activities if a.get("activity_name") not in ["Ufficio", "Base"]] if raw_activities else []
    
    total_cals_in = sum(m.get('calories', 0) for m in meals_data) if meals_data else 0
    current_weight = None
    if daily_log_res:
        row = daily_log_res[0]
        current_weight = row.get('weight')
        
    now = datetime.now()
    
    if summary_date == date.today():
        bmr_so_far = int((user_bmr / 24.0) * (now.hour + now.minute / 60.0))
    else:
        bmr_so_far = user_bmr
        
    extra_burned = sum(a.get('burned_calories', 0) for a in activities_data) if activities_data else 0
    total_burned_finora = bmr_so_far + extra_burned
    
    deficit = total_burned_finora - total_cals_in

    col_c1, col_c2, col_c3, col_c4 = st.columns(4)
    col_c1.metric("Kcal Ingerite", f"{total_cals_in} kcal")
    col_c2.metric("Kcal Bruciate", f"{total_burned_finora} kcal")
    col_c3.metric("Bilancio / Deficit", f"{deficit:+d} kcal")
    col_c4.metric("Peso", f"{current_weight} kg" if current_weight else "N/D")
        
    st.markdown("---")
    
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
    
    st.markdown("### 🏃 Calorie Bruciate & Attività")
    rows_acts = [{"Attività": "BMR (Base)", "Kcal Bruciate": bmr_so_far}]
    if activities_data:
        for act in activities_data:
            rows_acts.append({
                "Attività": act.get("activity_name"),
                "Kcal Bruciate": act.get("burned_calories")
            })
            
    df_acts = pd.DataFrame(rows_acts)
    st.dataframe(df_acts, use_container_width=True, hide_index=True)

# ==========================================
# 8. TAB 3: MONITORAGGIO PESO & OBIETTIVO
# ==========================================
with tab3:
    col_w1, col_w2 = st.columns(2)
    with col_w1:
        w = st.number_input(t["insert_weight"], value=80.9, step=0.1)
        if st.button(t["save_weight"]): 
            supabase.table("daily_logs").upsert({
                "user_id": user_id,
                "date": str(date.today()), 
                "weight": w
            }, on_conflict="user_id,date").execute()
            st.success("Peso salvato!")
            st.rerun()
            
    with col_w2:
        new_target = st.number_input("Aggiorna Peso Obiettivo (kg)", value=user_target_weight, step=0.5)
        if st.button("Salva Obiettivo"):
            try:
                res = supabase.auth.update_user({
                    "data": {"target_weight": float(new_target)}
                })
                st.session_state["user"] = res
                st.success("Obiettivo aggiornato con successo!")
                st.rerun()
            except Exception as e:
                st.error(f"Errore durante l'aggiornamento: {e}")
        
    logs = supabase.table("daily_logs").select("date, weight").eq("user_id", user_id).not_.is_("weight", "null").order("date").execute().data
    if logs:
        df = pd.DataFrame(logs)
        df['date'] = pd.to_datetime(df['date'])
        
        df_full = df.set_index('date').reindex(pd.date_range(df['date'].min(), df['date'].max())).interpolate().reset_index().rename(columns={'index': 'date'})
        
        real_dates = set(df['date'])
        df_full['is_real'] = df_full['date'].isin(real_dates)
        
        df_full['date_str'] = df_full['date'].dt.strftime('%d %b %Y')
        df_full['weight_str'] = df_full['weight'].round(1).astype(str) + " kg"
        
        df_real = df_full[df_full['is_real']]
        df_interp = df_full[~df_full['is_real']]
        
        fig = px.bar()
        
        fig.add_bar(
            x=df_real['date'], y=df_real['weight'],
            marker_color='#007BFF', marker_opacity=1.0,
            customdata=df_real[['date_str', 'weight_str']],
            hovertemplate="<b>⚖️ %{customdata[0]}</b><br><b>%{customdata[1]}</b><extra></extra>",
            name="Reale"
        )
        
        fig.add_bar(
            x=df_interp['date'], y=df_interp['weight'],
            marker_color='#007BFF', marker_opacity=0.25,
            customdata=df_interp[['date_str', 'weight_str']],
            hovertemplate="<b>⚖️ %{customdata[0]}</b><br><b>%{customdata[1]} (Proiezione)</b><extra></extra>",
            name="Proiezione"
        )
        
        fig.update_yaxes(range=[min(75, user_target_weight - 3), max(90, user_target_weight + 10)])
        
        fig.add_hline(y=user_target_weight, line_dash="dash", line_color="#FFD700", line_width=3.5)
        
        fig.add_annotation(
            xref="paper", yref="y", x=0.98, y=user_target_weight + 2.5, 
            text=f"<b>🎯 GOAL: {user_target_weight} kg</b>", 
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

# ==========================================
# 9. TAB 4: GESTIONE RICETTE PERSONALI
# ==========================================
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
                    supabase.table("recipes").upsert({
                        "name": r_name.strip(), 
                        "calories": int(cals), 
                        "protein": int(prot), 
                        "carbs": int(carbs), 
                        "fat": int(fat),
                        "user_id": user_id
                    }, on_conflict="user_id,name").execute()
                    
                    st.success(t["recipe_saved"])
                    st.rerun()
                except Exception as e:
                    st.error(f"Errore durante il salvataggio: {e}")
