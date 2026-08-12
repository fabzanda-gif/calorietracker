import streamlit as st
import pandas as pd
from datetime import date, datetime
import requests
from supabase import create_client
from streamlit_cookies_controller import CookieController
import plotly.express as px

# ==============================================================================
# 1. SETUP
# ==============================================================================
st.set_page_config(page_title="Tracker Pro", layout="wide")
SUPABASE_URL = st.secrets["SUPABASE_URL"]
SUPABASE_KEY = st.secrets["SUPABASE_KEY"]

if "supabase" not in st.session_state:
    st.session_state["supabase"] = create_client(SUPABASE_URL, SUPABASE_KEY)
supabase = st.session_state["supabase"]
controller = CookieController()

# --- Funzioni di supporto ---
def calculate_bmr(weight, height, gender):
    return int((10 * weight) + (6.25 * height) - (5 * 30) + (5 if gender == "Uomo" else -161))

def refresh_daily_logs(log_date):
    """Funzione placeholder per triggerare il ricalcolo se necessario"""
    pass

def search_open_food_facts(query):
    query = query.strip()
    if not query:
        return {}
    if query.isdigit():
        url = f"https://world.openfoodfacts.org/api/v2/product/{query}.json"
        response = requests.get(url, timeout=10)
        payload = response.json()
        if payload.get("status") != 1:
            return {}
        products = [payload.get("product", {})]
    else:
        url = "https://world.openfoodfacts.org/cgi/search.pl"
        response = requests.get(url, params={"search_terms": query, "search_simple": 1, "action": "process", "json": 1, "page_size": 20}, timeout=10)
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

# ==============================================================================
# 2. AUTENTICAZIONE
# ==============================================================================
def save_authenticated_session(response):
    user = response.user or response.session.user
    st.session_state["user"] = user
    controller.set("supabase_session", {"access_token": response.session.access_token, "refresh_token": response.session.refresh_token}, max_age=30*24*60*60)

def restore_session_from_cookie():
    saved = controller.get("supabase_session")
    if not isinstance(saved, dict) or not saved.get("access_token"):
        return False
    try:
        response = supabase.auth.set_session(saved["access_token"], saved["refresh_token"])
        if response and response.session:
            save_authenticated_session(response)
            return True
        return False
    except Exception:
        return False

def handle_oauth_callback():
    code = st.query_params.get("code")
    if code:
        try:
            response = supabase.auth.exchange_code_for_session({"auth_code": code})
            save_authenticated_session(response)
            st.query_params.clear()
            st.rerun()
        except Exception as e:
            st.error(f"Login fallito: {e}")

if "user" not in st.session_state:
    handle_oauth_callback()
if "user" not in st.session_state:
    restore_session_from_cookie()

if "user" not in st.session_state:
    st.title("🔐 Accesso Tracker Pro")
    login_url = supabase.auth.sign_in_with_oauth({"provider": "google", "options": {"redirect_to": "https://diario-alimentare.streamlit.app"}}).url
    st.link_button("Accedi con Google", login_url)
    
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
            st.markdown("### 📋 Parametri Fisici Iniziali")
            display_name_input = st.text_input("Display Name", value="")
            gender = st.selectbox("Genere", ["Uomo", "Donna"], index=None, placeholder="Seleziona genere...")
            height = st.number_input("Altezza (cm)", value=None, step=1.0, placeholder="Es. 175")
            current_weight = st.number_input("Peso Attuale (kg)", value=None, step=0.5, placeholder="Es. 81.0")
            target_weight = st.number_input("Peso Obiettivo (kg)", value=None, step=0.5, placeholder="Es. 78.0")
        
        submit_label = "Accedi" if auth_mode == "Login" else "Registrati"
        if st.form_submit_button(submit_label):
            try:
                if auth_mode == "Login":
                    response = supabase.auth.sign_in_with_password({"email": email, "password": password})
                    if response and response.session:
                        save_authenticated_session(response)
                        st.rerun()
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
                                    "display_name": display_name_input,
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
# 3. NAVIGAZIONE E PAGINE
# ==============================================================================
user = st.session_state["user"]
user_id = user.id
u_meta = user.user_metadata or {}
display_name = u_meta.get("display_name") or user.email.split("@")[0]
user_target_weight = u_meta.get("target_weight")
user_bmr = u_meta.get("bmr")

# Configurazione profilo mancante (es. dopo login Google)
if user_target_weight is None or user_bmr is None:
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
                if hasattr(res, 'user') and res.user:
                    st.session_state["user"] = res.user
                st.rerun()
            except Exception as e:
                st.error(f"Errore: {e}")
    st.stop()

with st.sidebar:
    lang = st.selectbox("🌐 Lingua", ["Italiano", "English"])
    translations = {
        "Italiano": {"t1": "🚀 Registrazione", "t2": "📊 Panoramica", "t3": "📈 Peso", "t4": "🍳 Inserimento Rapido", "meal": "Tipo di pasto", "meal_name": "Nome pasto", "add_meal": "Aggiungi pasto", "extra_act": "Attività extra", "extra_cals": "Calorie bruciate extra", "insert_weight": "Inserisci peso (kg)", "save_weight": "Salva peso", "recipe_name": "Nome Info", "save_recipe": "Salva Informazione", "recipe_saved": "✅  Informazione salvata!"},
        "English": {"t1": "🚀 Logging", "t2": "📊 Overview", "t3": "📈 Weight", "t4": "🍳 Quick Entry", "meal": "Meal type", "meal_name": "Meal name", "add_meal": "Add meal", "extra_act": "Extra activity", "extra_cals": "Extra calories burned", "insert_weight": "Enter weight (kg)", "save_weight": "Save weight", "recipe_name": "Info name", "save_recipe": "Save Info", "recipe_saved": "✅ Info saved!"}
    }
    t = translations[lang]
    selected_page = st.radio("📍 Navigazione", [t["t1"], t["t2"], t["t3"], t["t4"]])
    if st.button("🚪 Logout"):
        supabase.auth.sign_out()
        controller.set("supabase_session", None, max_age=0)
        st.session_state.clear()
        st.rerun()

# ==============================================================================
# RENDER PAGINE
# ==============================================================================
if selected_page == t["t1"]:
    log_date = st.date_input("Date", value=date.today())

    st.subheader("🍽️ Inserimento Cibo & Pasti")

    input_source = st.radio("Fonte inserimento", ["🔍 Cerca online (Open Food Facts)", "🍳 Da Quick Entries"], horizontal=True)
    is_recipe = (input_source == "🍳 Da Ricette Salvate")

    for key, default in [("m_name", ""), ("m_cals", 0), ("m_prot", 0), ("m_carbs", 0), ("m_fat", 0), ("last_selected", ""), ("form_v", 0), ("last_source", input_source), ("grams_val", 100.0)]:
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
                st.session_state.pop("prod_select", None)
                st.session_state["last_selected"] = ""
                st.rerun()
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
                carbs=p_data.get('carbs', 0),
                fat=p_data.get('fat', 0),
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
        def update_grams_callback():
            st.session_state["grams_val"] = st.session_state[f"meal_grams_{v}"]

        grams = st.number_input(
            "Grammi (g)",
            value=st.session_state["grams_val"],
            step=10.0,
            key=f"meal_grams_{v}",
            on_change=update_grams_callback
        )

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

elif selected_page == t["t2"]:
    st.subheader("📊 Riepilogo Giornaliero")
    
    # Logica per forzare la data di oggi all'apertura della tab
    if "last_nav_page" not in st.session_state or st.session_state.last_nav_page != selected_page:
        st.session_state.overview_date = date.today()
        st.session_state.last_nav_page = selected_page

    def update_overview_date():
        st.session_state.overview_date = st.session_state.widget_overview_date

    summary_date = st.date_input(
        "Data riepilogo", 
        value=st.session_state.overview_date, 
        key="widget_overview_date",
        on_change=update_overview_date
    )
    
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

elif selected_page == t["t3"]:
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
        new_target = st.number_input("Aggiorna Peso Obiettivo (kg)", value=float(user_target_weight), step=0.5)
        if st.button("Salva Obiettivo"):
            try:
                res = supabase.auth.update_user({
                    "data": {"target_weight": float(new_target)}
                })
                if res.user:
                    st.session_state["user"] = res.user
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

elif selected_page == t["t4"]:
    st.subheader("⚡ Quick Entries")

    # 1. Visualizzazione Tabella delle entrate esistenti per oggi
    st.markdown("### 📋 Entries di oggi")
    entries = supabase.table("recipes").select("*").eq("user_id", user_id).execute().data
    if entries:
        df_entries = pd.DataFrame(entries)
        # Rinominiamo le colonne per chiarezza
        df_display = df_entries.rename(columns={
            "name": "Nome", "calories": "Kcal", 
            "protein": "Pro", "carbs": "Carbs", "fat": "Fat"
        })
        st.dataframe(df_display[["Nome", "Kcal", "Pro", "Carbs", "Fat"]], use_container_width=True, hide_index=True)
    else:
        st.info("Nessuna entry veloce presente.")

    st.markdown("---")

    # 2. Form per aggiungere una nuova Quick Entry
    with st.form("quick_entry_add"):
        st.markdown("### ➕ Aggiungi nuova Entry")
        r_name = st.text_input(t["recipe_name"])
        c1, c2, c3, c4 = st.columns(4)
        cals = c1.number_input("Kcal", value=0, step=1, key="r_cal")
        prot = c2.number_input("Pro", value=0, step=1, key="r_pro")
        carbs = c3.number_input("Carbs", value=0, step=1, key="r_carbs")
        fat = c4.number_input("Fat", value=0, step=1, key="r_fat")
        
        if st.form_submit_button(t["save_recipe"]):
            if not r_name.strip():
                st.warning("Inserisci un nome valido.")
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
                    st.error(f"Errore: {e}")
