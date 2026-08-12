import streamlit as st
import pandas as pd
from datetime import date, datetime
import requests
import base64
import secrets
import hashlib
from supabase import create_client
from streamlit_cookies_controller import CookieController
import plotly.express as px

# ==============================================================================
# 1. SETUP INIZIALE E CONFIGURAZIONE PAGINA (QUESTO DEVE ESSERE IL PRIMO COMANDO)
# ==============================================================================
st.set_page_config(
    page_title="Tracker Pro",
    layout="wide",
)

# ==============================================================================
# STYLING CUSTOM (CSS) - FONT HANKEN GROTESK & SIDEBAR FIX
# ==============================================================================
st.markdown("""
    <style>
        /* Importazione del font Hanken Grotesk */
        @import url('https://fonts.googleapis.com/css2?family=Hanken+Grotesk:ital,wght@0,100..900;1,100..900&display=swap');

        html, body, [class*="css"] {
            font-family: 'Hanken Grotesk', sans-serif !important;
        }

        #MainMenu {visibility: hidden;}
        footer {visibility: hidden;}
        
        [data-testid="collapsedControl"] {
            display: block !important;
            color: #ffffff;
            background-color: #161b22;
            border-radius: 50%;
            padding: 8px;
            box-shadow: 0 2px 5px rgba(0,0,0,0.3);
            z-index: 999999;
        }

        /* Sidebar con contrasto e testi ben visibili */
        [data-testid="stSidebar"] {
            background-color: #0d1117;
            border-right: 1px solid #30363d;
            color: #f0f6fc;
        }

        [data-testid="stSidebar"] label, [data-testid="stSidebar"] span {
            color: #f0f6fc !important;
        }

        /* TRASFORMAZIONE TOTALE DEI RADIO BUTTON IN BOTTONI RETTANGOLARI */
        [data-testid="stSidebar"] .stRadio > div {
            gap: 10px;
        }

        [data-testid="stSidebar"] .stRadio label {
            background-color: #161b22;
            border: 1px solid #30363d;
            border-radius: 10px;
            padding: 12px 16px;
            width: 100%;
            display: flex;
            align-items: center;
            cursor: pointer;
            transition: all 0.2s ease;
        }

        [data-testid="stSidebar"] .stRadio label:hover {
            background-color: #21262d;
            border-color: #58a6ff;
        }

        /* Nasconde completamente i cerchietti/pallini nativi dei radio button */
        [data-testid="stSidebar"] .stRadio input[type="radio"] {
            display: none !important;
        }

        /* Nasconde il contenitore del pallino per evitare spazi vuoti */
        [data-testid="stSidebar"] .stRadio div[data-testid="stMarkdownContainer"] {
            margin-left: 0px !important;
        }

        /* Pulsanti standard e Logout */
        .stButton>button {
            border-radius: 10px;
            font-weight: 600;
            background-color: #21262d;
            color: #f0f6fc;
            border: 1px solid #30363d;
            transition: all 0.2s ease;
        }
        
        .stButton>button:hover {
            border-color: #58a6ff;
            color: #58a6ff;
            background-color: #30363d;
        }

        hr {
            margin: 1.5rem 0;
            border-color: #30363d;
        }
    </style>
""", unsafe_allow_html=True)
# ==============================================================================
# SUPABASE URL & KEY SETUP
# ==============================================================================
SUPABASE_URL = st.secrets["SUPABASE_URL"]
SUPABASE_KEY = st.secrets["SUPABASE_KEY"]

if "supabase" not in st.session_state:
    st.session_state["supabase"] = create_client(SUPABASE_URL, SUPABASE_KEY)

supabase = st.session_state["supabase"]
controller = CookieController()

## ==============================================================================
## 2. INITIALIZE SESSION STATE
## ==============================================================================
state_defaults = {
    "user": None,
    "pkce_verifier": None,
    "m_name": "",
    "m_cals": 0,
    "m_prot": 0,
    "m_carbs": 0,
    "m_fat": 0,
    "last_selected": "",
    "form_version": 0,
    "last_source": None,
    "grams_val": 100.0,
    "api_res": {},
    "overview_date": date.today(),
    "last_nav_page": None,
    "selected_recipe": None,
    "prod_select": ""
}

for key, default in state_defaults.items():
    if key not in st.session_state:
        st.session_state[key] = default

## ==============================================================================
## 3. UTILITY FUNCTIONS
## ==============================================================================
def calculate_bmr(weight, height, gender):
    """Calculate Basal Metabolic Rate using Mifflin-St Jeor equation"""
    if gender == "Uomo":
        return int((10 * weight) + (6.25 * height) - (5 * 30) + 5)
    else:
        return int((10 * weight) + (6.25 * height) - (5 * 30) - 161)

def refresh_daily_logs(log_date):
    """Placeholder for daily log refresh logic"""
    pass

def search_open_food_facts(query):
    """Search Open Food Facts database"""
    query = query.strip()
    if not query:
        return {}
    
    try:
        if query.isdigit():
            url = f"https://world.openfoodfacts.org/api/v2/product/{query}.json"
            response = requests.get(url, timeout=10)
            payload = response.json()
            if payload.get("status") != 1:
                return {}
            products = [payload.get("product", {})]
        else:
            url = "https://world.openfoodfacts.org/cgi/search.pl"
            response = requests.get(
                url, 
                params={
                    "search_terms": query, 
                    "search_simple": 1, 
                    "action": "process", 
                    "json": 1, 
                    "page_size": 20
                }, 
                timeout=10
            )
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
    except Exception as e:
        st.error(f"Errore nella ricerca: {e}")
        return {}

## ==============================================================================
## 4. AUTHENTICATION FUNCTIONS
## ==============================================================================
def generate_pkce_pair():
    """Generate PKCE code_verifier and code_challenge for OAuth security"""
    code_verifier = base64.urlsafe_b64encode(secrets.token_bytes(32)).decode('utf-8').rstrip('=')
    code_challenge = base64.urlsafe_b64encode(
        hashlib.sha256(code_verifier.encode('utf-8')).digest()
    ).decode('utf-8').rstrip('=')
    return code_verifier, code_challenge

def save_authenticated_session(response):
    """Save authenticated user session to state and cookies"""
    try:
        user = response.user if hasattr(response, 'user') and response.user else response.session.user
        st.session_state["user"] = user
        
        if response.session:
            controller.set(
                "supabase_session", 
                {
                    "access_token": response.session.access_token, 
                    "refresh_token": response.session.refresh_token
                }, 
                max_age=30*24*60*60
            )
    except Exception as e:
        st.error(f"Errore nel salvataggio della sessione: {e}")
        print(traceback.format_exc())

def restore_session_from_cookie():
    """Restore user session from stored cookies"""
    try:
        saved = controller.get("supabase_session")
        if not isinstance(saved, dict) or not saved.get("access_token"):
            return False
        
        response = supabase.auth.set_session(saved["access_token"], saved["refresh_token"])
        if response and response.session:
            save_authenticated_session(response)
            return True
        return False
    except Exception as e:
        print(f"Cookie restore error: {e}")
        return False

def handle_oauth_callback():
    """Handle OAuth callback from Google redirect"""
    code = st.query_params.get("code")
    if not code:
        return False
    
    verifier = st.session_state.get("pkce_verifier")
    if not verifier:
        st.error("❌ Sessione scaduta. Per favore accedi di nuovo.")
        return False
    
    try:
        response = supabase.auth.exchange_code_for_session({
            "auth_code": code,
            "code_verifier": verifier
        })
        save_authenticated_session(response)
        st.query_params.clear()
        st.session_state.pkce_verifier = None
        return True
    except Exception as e:
        st.error(f"Login fallito: {str(e)}")
        print(f"OAuth error: {traceback.format_exc()}")
        return False

def show_login_page():
    """Display login/registration page"""
    st.title("🔐 Accesso Tracker Pro")
    
   # ==============================================================================
    # Google OAuth Login con Pulsante Personalizzato e Logo Ufficiale
    # ==============================================================================
    verifier, challenge = generate_pkce_pair()
    st.session_state.pkce_verifier = verifier
    
    try:
        login_url = supabase.auth.sign_in_with_oauth({
            "provider": "google",
            "options": {
                "redirect_to": "https://diario-alimentare.streamlit.app",
                "code_challenge": challenge,
                "code_challenge_method": "s256"
            }
        }).url
    except Exception as e:
        st.error(f"Errore nell'inizializzazione Google login: {e}")
        login_url = "#"
    
    google_button_html = f"""
    <div style="display: flex; justify-content: center; margin: 10px 0 20px 0;">
        <a href="{login_url}" target="_self" style="
            display: flex;
            align-items: center;
            justify-content: center;
            background-color: #ffffff;
            color: #3c4043;
            border: 1px solid #dadce0;
            border-radius: 8px;
            padding: 12px 24px;
            font-family: 'Hanken Grotesk', Roboto, Arial, sans-serif;
            font-size: 16px;
            font-weight: 500;
            text-decoration: none;
            box-shadow: 0 1px 3px rgba(0,0,0,0.08);
            transition: background-color 0.2s, box-shadow 0.2s;
            width: 100%;
        ">
            <svg style="width: 20px; height: 20px; margin-right: 12px;" viewBox="0 0 24 24">
                <path fill="#4285F4" d="M23.745 12.27c0-.7-.06-1.4-.19-2.07H12v4.51h6.6c-.29 1.52-1.14 2.82-2.4 3.68v3.05h3.88c2.27-2.09 3.665-5.17 3.665-9.17z"/>
                <path fill="#34A853" d="M12 24c3.24 0 5.95-1.08 7.93-2.91l-3.88-3.05c-1.08.72-2.45 1.16-4.05 1.16-3.13 0-5.78-2.11-6.73-4.96H1.18v3.15C3.15 21.3 7.22 24 12 24z"/>
                <path fill="#FBBC05" d="M5.27 14.24c-.25-.72-.38-1.49-.38-2.24s.13-1.52.38-2.24V6.61H1.18C.43 8.13 0 9.87 0 12s.43 3.87 1.18 5.39l4.09-3.15z"/>
                <path fill="#EA4335" d="M12 4.75c1.77 0 3.35.61 4.6 1.8l3.42-3.42C17.95 1.19 15.24 0 12 0 7.22 0 3.15 2.7 1.18 6.61l4.09 3.15c.95-2.85 3.6-4.96 6.73-4.96z"/>
            </svg>
            Accedi con Google
        </a>
    </div>
    """
    st.markdown(google_button_html, unsafe_allow_html=True)
    st.markdown("---")
    
    ## Email Authentication
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
            st.markdown("#### 📋 Parametri Fisici Iniziali")
            display_name_input = st.text_input("Display Name", value="")
            gender = st.selectbox(
                "Genere", 
                ["Uomo", "Donna"], 
                index=None, 
                placeholder="Seleziona genere..."
            )
            height = st.number_input(
                "Altezza (cm)", 
                value=175.0, 
                min_value=100.0, 
                max_value=250.0, 
                step=1.0
            )
            current_weight = st.number_input(
                "Peso Attuale (kg)", 
                value=80.0, 
                min_value=20.0, 
                max_value=300.0, 
                step=0.5
            )
            target_weight = st.number_input(
                "Peso Obiettivo (kg)", 
                value=75.0, 
                min_value=20.0, 
                max_value=300.0, 
                step=0.5
            )
        
        submit_label = "Accedi" if auth_mode == "Login" else "Registrati"
        if st.form_submit_button(submit_label):
            try:
                if auth_mode == "Login":
                    response = supabase.auth.sign_in_with_password({
                        "email": email, 
                        "password": password
                    })
                    if response and response.session:
                        save_authenticated_session(response)
                        st.success("Login effettuato!")
                        st.rerun()
                    else:
                        st.error("Credenziali non valide")
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
                                    "display_name": display_name_input or email.split("@")[0],
                                    "target_weight": float(target_weight),
                                    "bmr": calculated_bmr,
                                    "height": float(height),
                                    "gender": gender
                                }
                            }
                        })
                        st.success("✅ Account creato con successo! Effettua il login.")
                        st.rerun()
            except Exception as e:
                st.error(f"Errore durante l'autenticazione: {str(e)}")
                print(traceback.format_exc())

## ==============================================================================
## 5. AUTHENTICATION FLOW
## ==============================================================================
if "user" not in st.session_state or st.session_state["user"] is None:
    if handle_oauth_callback():
        st.rerun()

if "user" not in st.session_state or st.session_state["user"] is None:
    if restore_session_from_cookie():
        st.rerun()

if "user" not in st.session_state or st.session_state["user"] is None:
    show_login_page()
    st.stop()

## ==============================================================================
## 6. USER DATA RETRIEVAL
## ==============================================================================
user = st.session_state["user"]
user_id = user.id
u_meta = user.user_metadata or {}

display_name = u_meta.get("display_name") or user.email.split("@")[0] or "User"
user_target_weight = u_meta.get("target_weight")
user_bmr = u_meta.get("bmr")
user_height = u_meta.get("height")
user_gender = u_meta.get("gender")

## ==============================================================================
## 7. PROFILE COMPLETION CHECK
## ==============================================================================
profile_incomplete = (
    user_target_weight is None or 
    user_bmr is None or 
    user_height is None or 
    user_gender is None
)

if profile_incomplete:
    st.warning("⚠️ Per iniziare, configura i tuoi dati.")
    with st.form("missing_data_form"):
        st.subheader("📋 Configurazione Profilo")
        gen = st.selectbox(
            "Genere", 
            ["Uomo", "Donna"], 
            index=0 if user_gender is None else (0 if user_gender == "Uomo" else 1)
        )
        h_val = st.number_input(
            "Altezza (cm)", 
            value=float(user_height) if user_height else 175.0,
            min_value=100.0,
            max_value=250.0,
            step=1.0
        )
        w_val = st.number_input(
            "Peso Attuale (kg)", 
            value=float(user_target_weight) if user_target_weight else 80.0,
            min_value=20.0,
            max_value=300.0,
            step=0.5
        )
        t_val = st.number_input(
            "Peso Obiettivo (kg)", 
            value=float(user_target_weight) if user_target_weight else 75.0,
            min_value=20.0,
            max_value=300.0,
            step=0.5
        )
        
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
                    user = res.user
                    u_meta = user.user_metadata or {}
                    user_target_weight = u_meta.get("target_weight")
                    user_bmr = u_meta.get("bmr")
                    user_height = u_meta.get("height")
                    user_gender = u_meta.get("gender")
                st.success("✅ Profilo aggiornato!")
                st.rerun()
            except Exception as e:
                st.error(f"Errore: {e}")
                print(traceback.format_exc())
    st.stop()

## ==============================================================================
## 8. NAVIGATION & LANGUAGE
## ==============================================================================
with st.sidebar:
    lang = st.selectbox("🌐 Lingua", ["Italiano", "English"])
    translations = {
        "Italiano": {"t1": "🚀 Inserimento", "t2": "📊 Overview", "t3": "📈 Peso", "t4": "⚡ Quick Entries", "meal": "Tipo di pasto", "meal_name": "Nome pasto", "add_meal": "Aggiungi pasto", "extra_act": "Attività extra", "extra_cals": "Calorie bruciate extra", "insert_weight": "Inserisci peso (kg)", "save_weight": "Salva peso", "recipe_name": "Nome ricetta", "save_recipe": "Salva ricetta", "recipe_saved": "✅ Ricetta salvata!"},
        "English": {"t1": "🚀 Logging", "t2": "📊 Overview", "t3": "📈 Weight", "t4": "⚡ Quick Entries", "meal": "Meal type", "meal_name": "Meal name", "add_meal": "Add meal", "extra_act": "Extra activity", "extra_cals": "Extra calories burned", "insert_weight": "Enter weight (kg)", "save_weight": "Save weight", "recipe_name": "Recipe name", "save_recipe": "Save recipe", "recipe_saved": "✅ Recipe saved!"}
    }
    t = translations[lang]
    
    # Inizializza la pagina corrente se non esiste
    if "selected_page" not in st.session_state:
        st.session_state.selected_page = t["t1"]

    st.markdown("### 📍 Navigazione")
    
    # Pulsanti di navigazione personalizzati stile card
    pages = [t["t1"], t["t2"], t["t3"], t["t4"]]
    for page in pages:
        # Se la pagina è quella attiva, diamo un bordo o uno sfondo più chiaro per evidenziarla
        is_active = (st.session_state.selected_page == page)
        btn_type = "primary" if is_active else "secondary"
        
        if st.button(page, key=f"nav_{page}", use_container_width=True):
            st.session_state.selected_page = page
            st.rerun()

    selected_page = st.session_state.selected_page

    st.markdown("---")
    if st.button("🚪 Logout", use_container_width=True):
        supabase.auth.sign_out()
        controller.set("supabase_session", None, max_age=0)
        st.session_state.clear()
        st.rerun()
## ==============================================================================
## 9. PAGE 1: MEAL LOGGING
## ==============================================================================
if selected_page == t["t1"]:
    log_date = st.date_input("📅 Data", value=date.today())
    
    st.subheader("🍽️ Inserimento Cibo & Pasti")
    
    input_source = st.radio(
        "Fonte inserimento", 
        ["🔍 Cerca online (Open Food Facts)", "🍳 Immissione Rapida"], 
        horizontal=True
    )
    
    is_recipe = (input_source == "🍳 Immissione Rapida")
    
    v = st.session_state["form_version"]
    
    def reset_or_update(name="", cals=0, prot=0, carbs=0, fat=0, selected="", grams=100.0):
        st.session_state["m_name"] = name
        st.session_state["m_cals"] = float(cals)
        st.session_state["m_prot"] = float(prot)
        st.session_state["m_carbs"] = float(carbs)
        st.session_state["m_fat"] = float(fat)
        st.session_state["grams_val"] = float(grams)
        st.session_state["last_selected"] = selected
        st.session_state["form_version"] += 1
    
    if st.session_state.get("last_source") != input_source:
        st.session_state["last_source"] = input_source
        reset_or_update()
        st.rerun()
    
    ## Search Mode
    if not is_recipe:
        search_q = st.text_input("🔍 Cerca per Nome o Codice a Barre")
        if st.button("🚀 Cerca"):
            if len(search_q) >= 2:
                with st.spinner('Ricerca in corso...'):
                    st.session_state["api_res"] = search_open_food_facts(search_q)
                st.session_state["prod_select"] = ""
                st.session_state["last_selected"] = ""
                st.rerun()
            else:
                st.warning("Inserisci almeno 2 caratteri o un codice a barre valido.")
        
        api_res = st.session_state.get("api_res", {})
        if api_res:
            sel_prod = st.selectbox(
                "Seleziona dal database", 
                [""] + list(api_res.keys()), 
                key=f"prod_select_{v}"
            )
            
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
    
    ## Recipe Mode
    else:
        try:
            recipes_data = supabase.table("recipes").select("*").eq("user_id", user_id).execute().data
            recipes_dict = {r["name"]: r for r in recipes_data} if recipes_data else {}
            
            if recipes_dict:
                sel_recipe = st.selectbox(
                    "Seleziona una ricetta", 
                    [""] + list(recipes_dict.keys()), 
                    key=f"recipe_select_{v}"
                )
                
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
            else:
                st.info("Nessuna ricetta salvata. Creane una nella sezione ⚡ Quick Entries")
        except Exception as e:
            st.error(f"Errore nel caricamento ricette: {e}")
    
    st.markdown("---")
    
    ## Meal Input Form
    meal_options = ["Colazione", "Pranzo", "Cena", "Snack"]
    m_type = st.selectbox(t["meal"], meal_options, key=f"meal_type_input_{v}")
    name = st.text_input(t["meal_name"], value=st.session_state["m_name"], key=f"input_meal_name_{v}")
    
    if not is_recipe:
        grams = st.number_input(
            "Grammi (g)",
            value=st.session_state["grams_val"],
            min_value=1.0,
            step=10.0,
            key=f"meal_grams_{v}",
        )
        st.session_state["grams_val"] = grams
        
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
        if st.button(t["add_meal"], key=f"submit_meal_btn_{v}", use_container_width=True):
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
                    st.success(f"✅ Pasto aggiunto! ({final_cals} kcal)")
                    st.rerun()
                except Exception as e:
                    st.error(f"Errore nel salvataggio: {e}")
                    print(traceback.format_exc())
    
    with col_btn2:
        if st.button("🗑️ Pulisci", key=f"clear_btn_{v}"):
            reset_or_update()
            st.rerun()
    
    st.markdown("---")
    
    ## Extra Activities
    st.subheader("🏃 Attività Extra")
    with st.form("extra_act_form"):
        extra_act = st.selectbox(
            t["extra_act"], 
            ["Padel", "Bici", "Camminata", "Corsa", "Palestra", "Nuoto", "Altro"]
        )
        extra_cals = st.number_input(
            t["extra_cals"], 
            value=0, 
            min_value=0,
            step=50
        )
        if st.form_submit_button("💾 Salva Attività"):
            try:
                supabase.table("activities").insert({
                    "user_id": user_id,
                    "date": str(log_date),
                    "activity_name": extra_act,
                    "burned_calories": int(extra_cals)
                }).execute()
                refresh_daily_logs(log_date)
                st.success("✅ Attività extra salvata!")
                st.rerun()
            except Exception as e:
                st.error(f"Errore: {e}")
                print(traceback.format_exc())

## ==============================================================================
## 10. PAGE 2: DAILY OVERVIEW
## ==============================================================================
elif selected_page == t["t2"]:
    st.subheader("📊 Riepilogo Giornaliero")
    
    if "last_nav_page" not in st.session_state or st.session_state.last_nav_page != selected_page:
        st.session_state.overview_date = date.today()
        st.session_state.last_nav_page = selected_page
    
    def update_overview_date():
        st.session_state.overview_date = st.session_state.get("widget_overview_date", date.today())
    
    summary_date = st.date_input(
        "📅 Data riepilogo", 
        value=st.session_state.overview_date, 
        key="widget_overview_date",
        on_change=update_overview_date
    )
    
    try:
        daily_log_res = supabase.table("daily_logs").select("*").eq("date", str(summary_date)).eq("user_id", user_id).execute().data or []
        meals_data = supabase.table("meals").select("*").eq("date", str(summary_date)).eq("user_id", user_id).execute().data or []
        raw_activities = supabase.table("activities").select("activity_name, burned_calories").eq("date", str(summary_date)).eq("user_id", user_id).execute().data or []
    except Exception as e:
        st.error(f"Errore nel caricamento dati: {e}")
        daily_log_res = []
        meals_data = []
        raw_activities = []
    
    ## Filter activities
    activities_data = [a for a in raw_activities if a.get("activity_name")] if raw_activities else []
    
    ## Calculate calories
    total_cals_in = sum(m.get('calories', 0) for m in meals_data) if meals_data else 0
    
    current_weight = None
    if daily_log_res and len(daily_log_res) > 0:
        row = daily_log_res[0]
        current_weight = row.get('weight')
    
    ## Calculate BMR
    now = datetime.now()
    if summary_date == date.today():
        minutes_passed = now.hour * 60 + now.minute
        bmr_so_far = int((user_bmr / (24 * 60)) * minutes_passed)
    else:
        bmr_so_far = user_bmr
    
    extra_burned = sum(a.get('burned_calories', 0) for a in activities_data) if activities_data else 0
    total_burned_finora = bmr_so_far + extra_burned
    deficit = total_cals_in - total_burned_finora
    
    ## Display metrics
    col_c1, col_c2, col_c3, col_c4 = st.columns(4)
    col_c1.metric("Kcal Ingerite", f"{total_cals_in} kcal")
    col_c2.metric("Kcal Bruciate", f"{total_burned_finora} kcal")
    col_c3.metric("Bilancio", f"{deficit:+d} kcal", delta_color="inverse")
    col_c4.metric("Peso", f"{current_weight} kg" if current_weight else "N/D")
    
    st.markdown("---")
    
    ## Meals table
    st.markdown("#### 🍽️ Cibi Inseriti")
    if meals_data:
        df_meals = pd.DataFrame(meals_data)
        df_display = df_meals[["meal_type", "name", "calories", "protein", "carbs", "fat"]].copy()
        df_display.columns = ["Pasto", "Nome", "Kcal", "Pro (g)", "Carbs (g)", "Fat (g)"]
        st.dataframe(df_display, use_container_width=True, hide_index=True)
        
        ## Delete meal functionality
        with st.expander("🗑️ Elimina un pasto"):
            meal_names = [f"{m['meal_type']} - {m['name']}" for m in meals_data]
            meal_to_delete_idx = st.selectbox(
                "Seleziona il pasto da eliminare",
                range(len(meal_names)),
                format_func=lambda i: meal_names[i]
            )
            if st.button("Elimina questo pasto"):
                try:
                    meal_to_delete = meals_data[meal_to_delete_idx]
                    supabase.table("meals").delete().eq("id", meal_to_delete["id"]).execute()
                    st.success("✅ Pasto eliminato!")
                    st.rerun()
                except Exception as e:
                    st.error(f"Errore nell'eliminazione: {e}")
    else:
        st.info("Nessun pasto registrato per questa data.")
    
    st.markdown("---")
    
    ## Activities
    st.markdown("#### 🏃 Calorie Bruciate & Attività")
    rows_acts = [{"Attività": "BMR (Base)", "Kcal Bruciate": bmr_so_far}]
    if activities_data:
        for act in activities_data:
            rows_acts.append({
                "Attività": act.get("activity_name"),
                "Kcal Bruciate": act.get("burned_calories")
            })
    
    df_acts = pd.DataFrame(rows_acts)
    st.dataframe(df_acts, use_container_width=True, hide_index=True)

## ==============================================================================
## 11. PAGE 3: WEIGHT TRACKING
## ==============================================================================
elif selected_page == t["t3"]:
    st.subheader("⚖️ Tracciamento Peso")
    
    col_w1, col_w2 = st.columns(2)
    
    with col_w1:
        st.markdown("#### 📥 Registra Peso Oggi")
        w = st.number_input(
            t["insert_weight"], 
            value=80.0, 
            min_value=20.0, 
            max_value=300.0,
            step=0.1
        )
        if st.button(t["save_weight"], use_container_width=True):
            try:
                supabase.table("daily_logs").upsert({
                    "user_id": user_id,
                    "date": str(date.today()),
                    "weight": w
                }, on_conflict="user_id,date").execute()
                st.success("✅ Peso salvato!")
                st.rerun()
            except Exception as e:
                st.error(f"Errore: {e}")
    
    with col_w2:
        st.markdown("#### 🎯 Aggiorna Obiettivo")
        new_target = st.number_input(
            "Peso Obiettivo (kg)", 
            value=float(user_target_weight) if user_target_weight else 75.0,
            min_value=20.0,
            max_value=300.0,
            step=0.5
        )
        if st.button("Salva Obiettivo", use_container_width=True):
            try:
                res = supabase.auth.update_user({
                    "data": {"target_weight": float(new_target)}
                })
                if res.user:
                    st.session_state["user"] = res.user
                st.success("✅ Obiettivo aggiornato!")
                st.rerun()
            except Exception as e:
                st.error(f"Errore: {e}")
                print(traceback.format_exc())
    
    st.markdown("---")
    
    ## Weight chart
    try:
        logs = supabase.table("daily_logs").select("date, weight").eq("user_id", user_id).not_.is_("weight", "null").order("date", desc=False).execute().data
        
        if logs:
            df = pd.DataFrame(logs)
            df['date'] = pd.to_datetime(df['date'])
            
            ## Interpolate missing dates
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
            
            min_weight = min(75, float(user_target_weight) - 3) if user_target_weight else 75
            max_weight = max(90, float(user_target_weight) + 10) if user_target_weight else 90
            fig.update_yaxes(range=[min_weight, max_weight])
            
            fig.add_hline(
                y=float(user_target_weight) if user_target_weight else 75, 
                line_dash="dash", 
                line_color='#FFD700', 
                line_width=3.5
            )
            
            fig.add_annotation(
                xref="paper", yref="y", x=0.98, y=float(user_target_weight) + 2.5 if user_target_weight else 77.5,
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
                barmode='overlay',
                hovermode='x unified'
            )
            st.plotly_chart(fig, use_container_width=True)
        else:
            st.info("📊 Nessun dato di peso registrato ancora. Inizia registrando il tuo peso!")
    except Exception as e:
        st.error(f"Errore nel caricamento grafico: {e}")
        print(traceback.format_exc())

## ==============================================================================
## 12. PAGE 4: QUICK ENTRIES
## ==============================================================================
elif selected_page == t["t4"]:
    st.subheader("⚡ Quick Entries - Ricette Salvate")
    
    st.markdown("#### 📋 Le tue ricette")
    try:
        entries = supabase.table("recipes").select("*").eq("user_id", user_id).order("name").execute().data
        
        if entries:
            df_entries = pd.DataFrame(entries)
            df_display = df_entries[["name", "calories", "protein", "carbs", "fat"]].copy()
            df_display.columns = ["Nome", "Kcal", "Pro (g)", "Carbs (g)", "Fat (g)"]
            st.dataframe(df_display, use_container_width=True, hide_index=True)
            
            ## Delete recipe
            with st.expander("🗑️ Elimina una ricetta"):
                recipe_names = df_entries["name"].tolist()
                recipe_to_delete_idx = st.selectbox(
                    "Seleziona ricetta da eliminare",
                    range(len(recipe_names)),
                    format_func=lambda i: recipe_names[i]
                )
                if st.button("Elimina ricetta"):
                    try:
                        recipe_id = df_entries.iloc[recipe_to_delete_idx].get("id")
                        supabase.table("recipes").delete().eq("id", recipe_id).execute()
                        st.success("✅ Ricetta eliminata!")
                        st.rerun()
                    except Exception as e:
                        st.error(f"Errore: {e}")
        else:
            st.info("Nessuna ricetta salvata ancora.")
    except Exception as e:
        st.error(f"Errore nel caricamento ricette: {e}")
        print(traceback.format_exc())
    
    st.markdown("---")
    
    st.markdown("#### ➕ Aggiungi Nuova Ricetta")
    with st.form("quick_entry_add"):
        r_name = st.text_input(t["recipe_name"], placeholder="Es. Pasta al pomodoro")
        c1, c2, c3, c4 = st.columns(4)
        cals = c1.number_input("Kcal", value=0, min_value=0, step=1)
        prot = c2.number_input("Pro (g)", value=0, min_value=0, step=1)
        carbs = c3.number_input("Carbs (g)", value=0, min_value=0, step=1)
        fat = c4.number_input("Fat (g)", value=0, min_value=0, step=1)
        
        if st.form_submit_button(t["save_recipe"], use_container_width=True):
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
                    print(traceback.format_exc())
