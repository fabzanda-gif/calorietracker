import streamlit as st
import pandas as pd
from datetime import date, timedelta
from supabase import create_client, Client

# Configurazione della pagina
st.set_page_config(page_title="Tracker Pro", layout="wide")

# Credenziali Supabase
SUPABASE_URL = "https://inhmvbdujpxrqrlcgmqw.supabase.co"
SUPABASE_KEY = "sb_publishable_1fQpT5dZqjre5D7MXm1aMg_ZQVRMjJq"

@st.cache_resource
def init_supabase() -> Client:
    return create_client(SUPABASE_URL, SUPABASE_KEY)

supabase = init_supabase()

st.title("⚖️ Tracker Peso & Macro & Calorie")

# Navigazione
menu = st.sidebar.selectbox("Navigazione", ["Inserimento Pasto & Attività", "Overview Giornaliera & Storico", "Dashboard Peso", "Gestione Ricette"])

# --- PAGINA INSERIMENTO PASTO & ATTIVITÀ ---
if menu == "Inserimento Pasto & Attività":
    st.header("Registra la giornata")
    
    log_date = st.date_input("Data", value=date.today())
    
    st.divider()
    
    # 1. Registrazione Tipo di Giornata (Univoco per data)
    st.subheader("🏠 / 🏢 Tipo di Giornata (Calorie Base)")
    
    # Controlliamo se esiste già un tipo di giornata salvato per questa data
    existing_day_type_res = supabase.table("activities").select("*").eq("date", str(log_date)).execute().data
    current_day_type = "Casa (1900 kcal)"
    for act in existing_day_type_res:
        if act['activity_name'] == "Ufficio":
            current_day_type = "Ufficio (2200 kcal)"
            
    with st.form("day_type_form"):
        day_type_selection = st.selectbox(
            "Seleziona il tipo di giornata", 
            ["Casa (1900 kcal)", "Ufficio (2200 kcal)"],
            index=0 if "Casa" in current_day_type else 1
        )
        submitted_day_type = st.form_submit_button("Imposta Tipo di Giornata")
        
        if submitted_day_type:
            base_cals = 2200 if "Ufficio" in day_type_selection else 1900
            name_type = "Ufficio" if "Ufficio" in day_type_selection else "Casa"
            
            # Rimuoviamo eventuali vecchie voci di Casa/Ufficio per garantire l'univocità
            for act in existing_day_type_res:
                if act['activity_name'] in ["Casa", "Ufficio"]:
                    supabase.table("activities").delete().eq("id", act['id']).execute()
            
            # Inseriamo la nuova voce base univoca
            supabase.table("activities").insert({
                "date": str(log_date), 
                "activity_name": name_type, 
                "burned_calories": base_cals
            }).execute()
            st.success(f"Giornata impostata univocamente come: {name_type} ({base_cals} kcal base)")

    st.divider()
    
    # Sezione Inserimento Pasti
    st.subheader("🍽️ Pasti")
    recipes = supabase.table("recipes").select("*").execute().data
    recipe_dict = {r['name']: r for r in recipes}
    
    with st.form("meal_form"):
        selected_name = st.selectbox("Seleziona Ricetta (o lascia vuoto)", [""] + list(recipe_dict.keys()))
        
        col1, col2 = st.columns(2)
        with col1:
            meal_type = st.selectbox("Pasto", ["Colazione", "Pranzo", "Cena", "Snack"])
            name = st.text_input("Nome", value=selected_name)
        with col2:
            ref = recipe_dict.get(selected_name, {})
            cals = st.number_input("Calorie", value=int(ref.get('calories', 0)))
            prot = st.number_input("Proteine (g)", value=int(ref.get('protein', 0)))
            carbs = st.number_input("Carboidrati (g)", value=int(ref.get('carbs', 0)))
            fat = st.number_input("Grassi (g)", value=int(ref.get('fat', 0)))
        
        submitted_meal = st.form_submit_button("Aggiungi Pasto")
        if submitted_meal:
            supabase.table("meals").insert({
                "date": str(log_date), "meal_type": meal_type, "name": name, 
                "calories": cals, "protein": prot, "carbs": carbs, "fat": fat
            }).execute()
            st.success("Pasto aggiunto con successo!")

    st.divider()

    # Sezione Attività Extra (Padel, Bici, ecc.)
    st.subheader("🏃‍♂️ Attività Extra (Padel, Bici, Camminata...)")
    with st.form("activity_form"):
        col_a1, col_a2 = st.columns(2)
        with col_a1:
            act_name = st.selectbox("Attività Extra", ["Padel", "Bici", "Camminata", "Altro"])
        with col_a2:
            act_cals = st.number_input("Calorie Bruciate Stimate", value=300, step=50)
            
        submitted_act = st.form_submit_button("Aggiungi Attività Extra")
        if submitted_act:
            supabase.table("activities").insert({
                "date": str(log_date), "activity_name": act_name, "burned_calories": int(act_cals)
            }).execute()
            st.success("Attività extra aggiunta!")

    st.divider()

    # Pulsante di ricalcolo blindato
    if st.button("🔄 Aggiorna e Calcola Totali Giornalieri"):
        # 1. Somma pasti
        all_meals = supabase.table("meals").select("*").eq("date", str(log_date)).execute().data
        total_cals_in = sum(m['calories'] for m in all_meals) if all_meals else 0
        total_prot = sum(m['protein'] for m in all_meals) if all_meals else 0
        total_carbs = sum(m['carbs'] for m in all_meals) if all_meals else 0
        total_fat = sum(m['fat'] for m in all_meals) if all_meals else 0
        
        # 2. Somma totale attività (Base Casa/Ufficio + Extra) presenti nella tabella activities per questa data
        all_acts = supabase.table("activities").select("*").eq("date", str(log_date)).execute().data
        total_burned = sum(a['burned_calories'] for a in all_acts) if all_acts else 0
        
        # Se per caso l'utente non ha impostato la base, consideriamo di default 1900 per sicurezza
        has_base = any(a['activity_name'] in ["Casa", "Ufficio"] for a in all_acts)
        if not has_base:
            total_burned += 1900 # Default casa se non specificato
            
        calorie_deficit = total_cals_in - total_burned
        
        # Salvataggio definitivo su daily_logs
        supabase.table("daily_logs").upsert({
            "date": str(log_date), 
            "calories": total_cals_in,
            "protein": total_prot, 
            "carbs": total_carbs, 
            "fat": total_fat,
            "burned_calories": total_burned,
            "calorie_deficit": calorie_deficit
        }, on_conflict="date").execute()
        
        st.success(f"Totali aggiornati! Ingerite: {total_cals_in} kcal | Bruciate totali: {total_burned} kcal")

# --- OVERVIEW GIORNALIERA & STORICO ---
elif menu == "Overview Giornaliera & Storico":
    st.header("🎯 Overview Giornaliera (Oggi)")
    
    today_str = str(date.today())
    
    today_log_res = supabase.table("daily_logs").select("*").eq("date", today_str).execute()
    cals_in, cals_burned, deficit = 0, 0, 0
    if today_log_res.data:
        row = today_log_res.data[0]
        cals_in = row.get('calories', 0) or 0
        cals_burned = row.get('burned_calories', 0) or 0
        deficit = row.get('calorie_deficit', 0) or 0

    col1, col2, col3 = st.columns(3)
    col1.metric("🔥 Kcal Ingerite", f"{cals_in} kcal")
    col2.metric("⚡ Kcal Bruciate", f"{cals_burned} kcal")
    col3.metric("📉 Deficit Attuale", f"{deficit} kcal")
    
    if deficit < 0:
        st.success("💪 Ottimo lavoro! Sei in deficit calorico, continua così per raggiungere i tuoi obiettivi!")
    elif deficit > 0:
        st.warning("⚠️ Oggi sei in surplus calorico. Ricorda che la costanza è la chiave, domani è un nuovo giorno!")
    else:
        st.info("⚖️ Sei in perfetto pareggio calorico per oggi.")

    st.divider()

    st.subheader("📋 Dettagli di Oggi")
    col_det1, col_det2 = st.columns(2)
    
    with col_det1:
        st.markdown("### 🍽️ Pasti per Tipo")
        today_meals = supabase.table("meals").select("*").eq("date", today_str).execute().data
        if today_meals:
            df_today_meals = pd.DataFrame(today_meals)
            for m_type in ["Colazione", "Pranzo", "Cena", "Snack"]:
                df_sub = df_today_meals[df_today_meals['meal_type'] == m_type]
                if not df_sub.empty:
                    st.markdown(f"**{m_type}**")
                    for _, row in df_sub.iterrows():
                        st.text(f"• {row['name']} ({row['calories']} kcal | P: {row['protein']}g, C: {row['carbs']}g, F: {row['fat']}g)")
        else:
            st.info("Nessun pasto registrato per oggi.")

    with col_det2:
        st.markdown("### 🏃‍♂️ Attività e Giornata Svolte")
        today_acts = supabase.table("activities").select("*").eq("date", today_str).execute().data
        if today_acts:
            for act in today_acts:
                if act['activity_name'] in ["Casa", "Ufficio"]:
                    st.markdown(f"🏠 **Giornata {act['activity_name']}**: `{act['burned_calories']} kcal base`")
                else:
                    icon = "🎾" if act['activity_name'].lower() == "padel" else "⚡"
                    st.markdown(f"{icon} **{act['activity_name']}**: `{act['burned_calories']} kcal bruciate`")
        else:
            st.info("Nessuna attività registrata per oggi.")

    st.divider()
    
    st.header("📅 Storico degli ultimi 7 giorni (Daily Logs)")
    start_date = date.today() - timedelta(days=7)
    
    logs_res = supabase.table("daily_logs").select("*").gte("date", str(start_date)).order("date", desc=True).execute()
    
    if logs_res.data:
        df_logs = pd.DataFrame(logs_res.data)
        st.dataframe(
            df_logs[['date', 'weight', 'calories', 'burned_calories', 'calorie_deficit', 'protein', 'carbs', 'fat']], 
            use_container_width=True, 
            hide_index=True
        )
    else:
        st.info("Nessun log giornaliero registrato negli ultimi 7 giorni.")

# --- DASHBOARD PESO ---
elif menu == "Dashboard Peso":
    st.header("Analisi Peso")
    with st.form("weight_form"):
        w = st.number_input("Peso di oggi (kg)", value=82.0, step=0.1)
        if st.form_submit_button("Aggiorna Peso"):
            supabase.table("daily_logs").upsert({"date": str(date.today()), "weight": w}, on_conflict="date").execute()
            st.success("Peso salvato!")
            
    logs = supabase.table("daily_logs").select("date, weight").not_.is_("weight", "null").execute().data
    if logs:
        df = pd.DataFrame(logs)
        st.line_chart(df.set_index('date')['weight'])

# --- GESTIONE RICETTE ---
elif menu == "Gestione Ricette":
    st.header("Gestione Ricette")
    with st.form("recipe_add"):
        r_name = st.text_input("Nome Ricetta")
        c1, c2, c3, c4 = st.columns(4)
        r_cal = c1.number_input("Kcal", value=0)
        r_pro = c2.number_input("Pro", value=0)
        r_car = c3.number_input("Carbs", value=0)
        r_fat = c4.number_input("Fat", value=0)
        
        if st.form_submit_button("Salva Ricetta"):
            supabase.table("recipes").upsert({
                "name": r_name, "calories": r_cal, "protein": r_pro, "carbs": r_car, "fat": r_fat
            }, on_conflict="name").execute()
            st.success("Ricetta salvata o aggiornata!")