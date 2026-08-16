from __future__ import annotations

import os
import random
import re
import unicodedata
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import pandas as pd
import streamlit as st
import streamlit.components.v1 as components
from supabase import Client, create_client


# ============================================================
# CONFIGURAZIONE
# ============================================================

st.set_page_config(page_title="RCD Escanyol Auction Center", layout="wide")

ROLE_LIMITS: dict[str, int] = {
    "P": 3,
    "D": 8,
    "C": 8,
    "A": 6,
}
TOTAL_SLOTS_PER_TEAM = sum(ROLE_LIMITS.values())

# Calibrazione finale per ruolo.
# Derivata dai target richiesti:
# P: 6.7 -> 9.0, D: 8.7 -> 9.2, C: 8.2 -> 8.5, A invariato.
ROLE_RATING_MULTIPLIERS = {
    "P": 9.0 / 6.7,
    "D": 9.2 / 8.7,
    "C": 8.5 / 8.2,
    "A": 1.0,
}


# Valutazione rosa più "netta".
# I giocatori TOP devono incidere più delle riserve/terze fasce.
TEAM_PLAYER_WEIGHTS = {
    "TOP": 2.40,          # >= 9.0
    "PRIMA": 1.70,        # 8.0 - 8.9
    "SECONDA": 1.20,      # 7.0 - 7.9
    "TERZA": 0.85,        # 6.5 - 6.9
    "SOTTO_SOGLIA": 0.55, # < 6.5
}

# Amplifica le differenze fra rose senza alterare i rating individuali.
TEAM_RATING_CENTER = 6.70
TEAM_RATING_SPREAD = 1.35
TOP_PLAYER_BONUS = 0.16
ELITE_PLAYER_BONUS = 0.08
WEAK_PLAYER_PENALTY = 0.10
TEAM_RATING_MIN = 4.0
TEAM_RATING_MAX = 9.5

# Stima iniziale usata solo quando non esistono ancora abbastanza
# precedenti di asta nel database. Appena ci sono acquisti reali,
# la stima viene sostituita dalla mediana dei moltiplicatori osservati.
DEFAULT_AUCTION_MULTIPLIER = 2.5
MIN_HISTORY_FOR_ROLE_ESTIMATE = 2

DRAFT_ORDER = ("P", "D", "C", "A")
ROLE_NAMES = {
    "P": "Portieri",
    "D": "Difensori",
    "C": "Centrocampisti",
    "A": "Attaccanti",
}

# Modificatore portieri:
# tra le tre squadre dei portieri presenti nella rosa, la squadra
# che ha subito meno gol prende +1.0, la seconda 0.0, la terza -1.0.
GOALKEEPER_GOALS_CONCEDED_MODIFIERS = {
    1: 1.0,
    2: 0.0,
    3: -1.0,
}

ROLE_LABELS = {
    "Tutti i ruoli": "ALL",
    "Portieri (P)": "P",
    "Difensori (D)": "D",
    "Centrocampisti (C)": "C",
    "Attaccanti (A)": "A",
}

PLAYER_FIELDS = (
    "id, name, role, team_nfl, list_price, status_titolarita, "
    "rigorista, affidabilita_fisica, propensione_cartellini, "
    "slot_fantacalcio, primo_anno_serie_a"
)

RATING_CONFIG = {
    "base": 6.5,
    "list_price_bonus": (
        (30, 3.5),
        (20, 2.5),
        (10, 1.0),
        (5, 0.5),
    ),
    "titolare": 1.5,
    "riserva": -1.5,
    "rigorista": 1.5,
    "cartellini": -0.3,
    "rookie": -0.2,
    "preferito": 0.8,
}

TEAM_MAP = {
    "Napoli": "NAP", "Juventus": "JUV", "Milan": "MIL", "Inter": "INT",
    "Roma": "ROM", "Lazio": "LAZ", "Atalanta": "ATA", "Fiorentina": "FIO",
    "Torino": "TOR", "Bologna": "BOL", "Genoa": "GEN", "Sassuolo": "SAS",
    "Udinese": "UDI", "Cagliari": "CAG", "Verona": "VER", "Lecce": "LEC",
    "Cremonese": "CRE", "Parma": "PAR", "Como": "COM", "Pisa": "PIS",
}

DATA_DIR = Path(__file__).resolve().parent
STATS_FILE = DATA_DIR / "player_aggregated_stats.csv"
SEASON_FILE = DATA_DIR / "season-2526.csv"


# Tab 4: modifiche manuali persistenti ai giocatori.
# Richiede una tabella Supabase dedicata (SQL fornito sotto).
CUSTOM_MODIFIER_TABLE = "player_custom_modifiers"

# Nome della squadra dell'utente. Vengono tollerati anche i nomi usati
# nelle versioni precedenti, così il codice non dipende da una singola
# stringa hardcoded.
MY_TEAM_NAME = "RCD Escanyol"
MY_TEAM_ALIASES = (
    "RCD Escanyol",
    "Escanyol",
    "RCD Escalnyol",
)

CUSTOM_MODIFIERS = {
    "Nessuna modifica": {"key": None, "value": 0.0},
    "⭐ Preferito (+0.5)": {"key": "preferito", "value": 0.5},
    "🟢 Bonus extra +1.0": {"key": "bonus_1", "value": 1.0},
    "🟢 Bonus extra +0.5": {"key": "bonus_05", "value": 0.5},
    "🟢 Bonus extra +0.3": {"key": "bonus_03", "value": 0.3},
    "🟡 Ballottaggio (-0.3)": {"key": "ballottaggio", "value": -0.3},
    "🟠 Malus -0.5": {"key": "malus_05", "value": -0.5},
    "🔴 Malus -1.0": {"key": "malus_1", "value": -1.0},
    "🔴 Riserva (-1.5)": {"key": "riserva", "value": -1.5},
}


SOUND_URLS = {
    "massive": "https://raw.githubusercontent.com/fabzanda-gif/fantahelper/main/johncenaprankcall_cutted.mp3",
    "great": "https://www.myinstants.com/media/sounds/ta-da.mp3",
    "normal": "https://www.myinstants.com/media/sounds/plop.mp3",
}


@dataclass
class AuctionState:
    bought_player_ids: set[Any]
    team_role_totals: dict[str, dict[str, int]]
    team_total_bought: dict[str, int]
    team_players_map: dict[str, list[dict[str, Any]]]
    team_purchases_map: dict[str, list[dict[str, Any]]]


# ============================================================
# DATABASE
# ============================================================

@st.cache_resource
def get_supabase() -> Client:
    return create_client(
        st.secrets["SUPABASE_URL"],
        st.secrets["SUPABASE_KEY"],
    )


supabase = get_supabase()


@st.cache_data(ttl=5)
def load_teams() -> list[dict[str, Any]]:
    return (
        supabase.table("teams")
        .select("id, name, remaining_budget, initial_budget")
        .execute()
        .data
    )


@st.cache_data(ttl=5)
def load_rosters() -> list[dict[str, Any]]:
    """Carica le rose usando gli FK espliciti e ricostruisce le relazioni.

    Non dipendiamo da `teams(name)` / `players(...)` nella query di rosters:
    se Supabase non espone correttamente una relazione, la vecchia versione
    riceveva `teams=None` o `players=None` e la rosa risultava vuota nella UI
    pur avendo righe reali nella tabella `rosters`.
    """
    roster_rows = (
        supabase.table("rosters")
        .select("id, team_id, player_id, purchase_price")
        .execute()
        .data
    )

    if not roster_rows:
        return []

    team_ids = {row.get("team_id") for row in roster_rows if row.get("team_id") is not None}
    player_ids = {row.get("player_id") for row in roster_rows if row.get("player_id") is not None}

    teams_rows = (
        supabase.table("teams")
        .select("id, name, remaining_budget, initial_budget")
        .in_("id", list(team_ids))
        .execute()
        .data
    ) if team_ids else []

    players_rows = (
        supabase.table("players")
        .select(PLAYER_FIELDS)
        .in_("id", list(player_ids))
        .execute()
        .data
    ) if player_ids else []

    team_by_id = {row["id"]: row for row in teams_rows}
    player_by_id = {row["id"]: row for row in players_rows}

    hydrated = []
    for row in roster_rows:
        hydrated.append({
            "id": row.get("id"),
            "purchase_price": row.get("purchase_price", 0),
            "team_id": row.get("team_id"),
            "player_id": row.get("player_id"),
            "teams": team_by_id.get(row.get("team_id")),
            "players": player_by_id.get(row.get("player_id")),
        })

    return hydrated


@st.cache_data(ttl=5)
def load_players(
    role: str = "ALL",
    team_nfl: str = "ALL",
) -> list[dict[str, Any]]:
    query = supabase.table("players").select(PLAYER_FIELDS)

    if role != "ALL":
        query = query.eq("role", role)

    if team_nfl != "ALL":
        query = query.eq("team_nfl", team_nfl)

    return query.order("name").execute().data


@st.cache_data(ttl=5)
def load_custom_modifiers() -> dict[Any, dict[str, Any]]:
    """Carica le modifiche manuali persistenti dal database."""
    try:
        rows = (
            supabase.table(CUSTOM_MODIFIER_TABLE)
            .select("player_id, modifier_key, modifier_label, modifier_value")
            .execute()
            .data
        )
    except Exception:
        # Se la tabella non è stata ancora creata, l'app continua a funzionare
        # usando il rating standard.
        return {}

    return {
        row["player_id"]: row
        for row in rows
        if row.get("player_id") is not None
    }


def save_custom_modifier(
    player_id: Any,
    modifier_label: str,
) -> tuple[bool, str]:
    """Salva/sostituisce la modifica manuale di un giocatore."""
    config = CUSTOM_MODIFIERS[modifier_label]

    try:
        (
            supabase.table(CUSTOM_MODIFIER_TABLE)
            .delete()
            .eq("player_id", player_id)
            .execute()
        )

        if config["key"] is not None:
            (
                supabase.table(CUSTOM_MODIFIER_TABLE)
                .insert(
                    {
                        "player_id": player_id,
                        "modifier_key": config["key"],
                        "modifier_label": modifier_label,
                        "modifier_value": config["value"],
                    }
                )
                .execute()
            )

        load_custom_modifiers.clear()
        return True, ""
    except Exception as exc:
        return False, str(exc)


def reset_custom_modifier(player_id: Any) -> tuple[bool, str]:
    try:
        (
            supabase.table(CUSTOM_MODIFIER_TABLE)
            .delete()
            .eq("player_id", player_id)
            .execute()
        )
        load_custom_modifiers.clear()
        return True, ""
    except Exception as exc:
        return False, str(exc)


def invalidate_data_cache() -> None:
    load_teams.clear()
    load_rosters.clear()
    load_players.clear()
    load_external_data.clear()
    load_custom_modifiers.clear()


# ============================================================
# UI / AUDIO
# ============================================================

def play_sound(sound_url: str) -> None:
    components.html(
        f"""
        <audio autoplay>
            <source src="{sound_url}" type="audio/mp3">
        </audio>
        """,
        height=0,
        width=0,
    )


def resolve_my_team_name(team_names: list[str]) -> str | None:
    """Trova RCD Escanyol anche con piccole differenze di formattazione."""
    normalized = {normalize_string(name): name for name in team_names if isinstance(name, str)}
    for candidate in (MY_TEAM_NAME, *MY_TEAM_ALIASES):
        hit = normalized.get(normalize_string(candidate))
        if hit:
            return hit
    return None


def is_my_team(team_name: str | None) -> bool:
    if not team_name:
        return False
    return normalize_string(team_name) == normalize_string(MY_TEAM_NAME) or normalize_string(team_name) in {
        normalize_string(alias) for alias in MY_TEAM_ALIASES
    }


def default_team_index(
    team_names: list[str],
    preferred: str = MY_TEAM_NAME,
) -> int:
    if not team_names:
        return 0

    # Prima prova il nome canonico, poi gli alias storici.
    for name in (preferred, *MY_TEAM_ALIASES):
        if name in team_names:
            return team_names.index(name)
    return 0


def queue_purchase_banner(
    team_name: str,
    player_name: str,
    rating: float,
    purchase_price: int,
) -> None:
    """Memorizza il banner prima di st.rerun(), che interrompe subito il run."""
    if not is_my_team(team_name):
        st.session_state.pop("pending_purchase_banner", None)
        return

    if rating >= 8.5:
        level = "massive"
        title = "🔥 MASSIVE COLPO!"
        message = (
            f"Hai preso **{player_name}** (Rating {rating:.1f})! "
            "AND HIS NAME IS JOHN CENA! 🎺🎺🎺"
        )
    elif rating >= 7.5:
        level = "great"
        title = "🎉 Ottimo innesto!"
        message = (
            f"**{player_name}** con rating {rating:.1f}. "
            "Gran bel colpo per l'Escanyol! 🌟"
        )
    else:
        level = "normal"
        title = "✅ Operazione conclusa"
        message = f"Preso **{player_name}** a **{purchase_price}** crediti."

    st.session_state["pending_purchase_banner"] = {
        "level": level,
        "title": title,
        "message": message,
    }


def render_pending_purchase_banner() -> None:
    """Mostra il banner dell'ultimo acquisto dopo il rerun."""
    banner = st.session_state.get("pending_purchase_banner")
    if not banner:
        return

    # Evita che il banner venga riprodotto ad ogni rerun, ma lo mantiene
    # abbastanza a lungo da poter essere visualizzato anche se la pagina
    # ricostruisce più volte la UI.
    st.session_state.pop("pending_purchase_banner", None)
    level = banner["level"]
    text = f"**{banner['title']}** — {banner['message']}"

    # Banner visivo indipendente dai widget di Streamlit: rimane visibile
    # anche se il browser blocca l'autoplay dell'audio.
    banner_class = {
        "massive": "massive",
        "great": "great",
        "normal": "normal",
    }.get(level, "normal")
    st.markdown(
        f"""
        <div class=\"auction-banner {banner_class}\">
            <div class=\"auction-banner-title\">{banner['title']}</div>
            <div class=\"auction-banner-text\">{banner['message']}</div>
        </div>
        <style>
        .auction-banner {{
            padding: 22px 28px; margin: 12px 0 22px; border-radius: 18px;
            text-align: center; font-size: 1.15rem;
            border: 2px solid rgba(255,255,255,.55);
            box-shadow: 0 10px 30px rgba(0,0,0,.16);
            animation: auctionPulse 1.1s ease-in-out 2;
        }}
        .auction-banner.massive {{ background: linear-gradient(135deg,#ff416c,#ff4b2b); color:white; }}
        .auction-banner.great {{ background: linear-gradient(135deg,#11998e,#38ef7d); color:white; }}
        .auction-banner.normal {{ background: linear-gradient(135deg,#4facfe,#00f2fe); color:white; }}
        .auction-banner-title {{ font-size: 1.8rem; font-weight: 800; margin-bottom: 6px; }}
        .auction-banner-text {{ font-weight: 600; }}
        @keyframes auctionPulse {{
            0%,100% {{ transform: scale(1); }}
            50% {{ transform: scale(1.025); }}
        }}
        </style>
        """,
        unsafe_allow_html=True,
    )

    if level == "massive":
        st.balloons()
        play_sound(SOUND_URLS["massive"])
    elif level == "great":
        st.balloons()
        play_sound(SOUND_URLS["great"])
    else:
        play_sound(SOUND_URLS["normal"])


# ============================================================
# DATI ESTERNI / NORMALIZZAZIONE
# ============================================================

def normalize_string(value: Any) -> str:
    if not isinstance(value, str):
        return ""
    value = unicodedata.normalize("NFKD", value)
    value = "".join(c for c in value if not unicodedata.combining(c))
    value = re.sub(r"[^a-zA-Z0-9\s]", "", value)
    return re.sub(r"\s+", " ", value).strip().lower()


@st.cache_data(ttl=300)
def load_external_data() -> tuple[pd.DataFrame, dict[str, dict[str, float]], dict[str, float]]:
    stats = pd.DataFrame()
    mods: dict[str, dict[str, float]] = {}
    goals_conceded: dict[str, float] = {}

    if STATS_FILE.exists():
        try:
            stats = pd.read_csv(STATS_FILE)
            if "clean_name" not in stats.columns and "name" in stats.columns:
                stats["clean_name"] = stats["name"].map(normalize_string)
            elif "clean_name" in stats.columns:
                stats["clean_name"] = stats["clean_name"].map(normalize_string)
        except (OSError, pd.errors.ParserError) as exc:
            st.warning(f"Impossibile leggere {STATS_FILE.name}: {exc}")

    if not SEASON_FILE.exists():
        return stats, mods, goals_conceded

    try:
        df = pd.read_csv(SEASON_FILE)
        required = {"HomeTeam", "AwayTeam", "FTHG", "FTAG"}
        if not required.issubset(df.columns):
            return stats, mods, goals_conceded

        home = (
            df.groupby("HomeTeam")
            .agg(GF=("FTHG", "sum"), GA=("FTAG", "sum"), M=("FTHG", "count"))
            .reset_index()
            .rename(columns={"HomeTeam": "Team"})
        )
        away = (
            df.groupby("AwayTeam")
            .agg(GF=("FTAG", "sum"), GA=("FTHG", "sum"), M=("FTAG", "count"))
            .reset_index()
            .rename(columns={"AwayTeam": "Team"})
        )
        ts = pd.merge(home, away, on="Team", how="outer").fillna(0)
        ts["Matches"] = ts["M_x"] + ts["M_y"]
        ts["TotalGF"] = ts["GF_x"] + ts["GF_y"]
        ts["TotalGA"] = ts["GA_x"] + ts["GA_y"]

        # Memorizziamo i gol subiti per ogni club/codice Serie A.
        for _, row in ts.iterrows():
            if row["Matches"] > 0:
                code = TEAM_MAP.get(
                    str(row["Team"]),
                    str(row["Team"]).upper()[:3],
                )
                goals_conceded[code] = float(row["TotalGA"])

        total_matches = ts["Matches"].sum()
        if total_matches <= 0:
            return stats, mods, goals_conceded

        avg_gf = ts["TotalGF"].sum() / total_matches
        avg_ga = ts["TotalGA"].sum() / total_matches

        for _, row in ts.iterrows():
            if row["Matches"] <= 0:
                continue
            code = TEAM_MAP.get(str(row["Team"]), str(row["Team"]).upper()[:3])
            mods[code] = {
                "att": round(((row["TotalGF"] / row["Matches"]) - avg_gf) * 0.8, 2),
                "def": round((avg_ga - (row["TotalGA"] / row["Matches"])) * 0.9, 2),
            }
    except (OSError, pd.errors.ParserError, KeyError, ZeroDivisionError) as exc:
        st.warning(f"Impossibile elaborare {SEASON_FILE.name}: {exc}")

    return stats, mods, goals_conceded


STATS, MODS, GOALS_CONCEDED = load_external_data()


def get_goalkeeper_ranking_for_teams(
    team_codes: set[str],
) -> dict[str, int]:
    """
    Classifica SOLO le squadre dei portieri presenti nella rosa.

    1 = meno gol subiti -> +1.0
    2 = seconda -> 0.0
    3 = più gol subiti -> -1.0

    Se sono presenti meno di tre squadre, vengono classificate solo
    quelle disponibili.
    """
    if not team_codes:
        return {}

    rows = [
        (code, GOALS_CONCEDED.get(code))
        for code in team_codes
        if GOALS_CONCEDED.get(code) is not None
    ]
    rows.sort(key=lambda item: (item[1], item[0]))

    return {
        code: position
        for position, (code, _) in enumerate(rows[:3], start=1)
    }


def get_goalkeeper_modifier(
    player: dict[str, Any],
    goalkeeper_ranking: dict[str, int] | None = None,
) -> tuple[float, int | None]:
    """Restituisce modificatore e posizione della squadra del portiere."""
    if player.get("role") != "P" or not goalkeeper_ranking:
        return 0.0, None

    position = goalkeeper_ranking.get(player.get("team_nfl"))
    if position is None:
        return 0.0, None

    return (
        GOALKEEPER_GOALS_CONCEDED_MODIFIERS.get(position, 0.0),
        position,
    )


ALL_GOALKEEPER_RANKING = get_goalkeeper_ranking_for_teams(set(GOALS_CONCEDED))


def get_my_team_name_from_state(state: "AuctionState") -> str | None:
    return resolve_my_team_name(list(state.team_players_map))


def get_my_team_players_and_purchases(
    state: "AuctionState",
) -> tuple[str | None, list[dict[str, Any]], list[dict[str, Any]]]:
    team_name = get_my_team_name_from_state(state)
    if team_name is None:
        return None, [], []
    return (
        team_name,
        state.team_players_map.get(team_name, []),
        state.team_purchases_map.get(team_name, []),
    )


def get_my_team_draft_role(state: "AuctionState") -> str | None:
    """Restituisce il prossimo ruolo della rosa RCD Escanyol secondo PDCA."""
    team_name = get_my_team_name_from_state(state)
    if team_name is None:
        return "P"

    counts = state.team_role_totals.get(team_name, {})
    for role in DRAFT_ORDER:
        if counts.get(role, 0) < ROLE_LIMITS[role]:
            return role
    return None


def role_label(role: str) -> str:
    return {
        "P": "Portieri (P)",
        "D": "Difensori (D)",
        "C": "Centrocampisti (C)",
        "A": "Attaccanti (A)",
    }.get(role, "Tutti i ruoli")


def auction_history_ratios(
    rosters: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    """Estrae i moltiplicatori prezzo pagato/listino dagli acquisti reali."""
    history = []
    for roster in rosters:
        player = roster.get("players") or {}
        list_price = float(player.get("list_price") or 0)
        paid = float(roster.get("purchase_price") or 0)
        if list_price <= 0 or paid <= 0:
            continue
        ratio = paid / list_price
        # Evitiamo che un errore/outlier renda inutile la mediana.
        ratio = max(0.5, min(8.0, ratio))
        history.append({
            "role": player.get("role"),
            "list_price": list_price,
            "paid": paid,
            "ratio": ratio,
            "name": player.get("name", ""),
        })
    return history


def estimate_auction_price(
    player: dict[str, Any],
    rosters: list[dict[str, Any]],
    budget: int | None = None,
    slots_left_after_purchase: int = 0,
) -> dict[str, Any]:
    """Stima il prezzo d'asta usando i moltiplicatori osservati nel draft."""
    history = auction_history_ratios(rosters)
    role = player.get("role")
    list_price = float(player.get("list_price") or 1)

    role_history = [h for h in history if h["role"] == role]
    similar_history = [
        h for h in role_history
        if 0.5 * list_price <= h["list_price"] <= 1.5 * list_price
    ]

    if len(similar_history) >= MIN_HISTORY_FOR_ROLE_ESTIMATE:
        sample = similar_history
        source = "precedenti dello stesso ruolo e fascia di listino"
    elif len(role_history) >= MIN_HISTORY_FOR_ROLE_ESTIMATE:
        sample = role_history
        source = "precedenti dello stesso ruolo"
    elif len(history) >= MIN_HISTORY_FOR_ROLE_ESTIMATE:
        sample = history
        source = "precedenti generali dell'asta"
    else:
        sample = []
        source = "baseline: non ci sono ancora abbastanza precedenti"

    if sample:
        ratios = sorted(h["ratio"] for h in sample)
        multiplier = float(pd.Series(ratios).median())
    else:
        multiplier = DEFAULT_AUCTION_MULTIPLIER

    estimated = max(1, int(round(list_price * multiplier)))
    feasible = True
    budget_note = ""
    max_bid = None

    if budget is not None:
        reserve = max(0, int(slots_left_after_purchase))
        max_bid = max(1, int(budget) - reserve)
        if estimated > max_bid:
            feasible = False
            budget_note = (
                f"Budget massimo sostenibile: {max_bid} cr; "
                f"la stima di mercato è {estimated} cr."
            )

    return {
        "multiplier": round(multiplier, 2),
        "estimated_price": estimated,
        "source": source,
        "sample_size": len(sample),
        "feasible": feasible,
        "budget_note": budget_note,
        "max_bid": max_bid,
    }


RECOMMENDATION_TIERS = {
    "TOP": {"min_rating": 9.0, "max_rating": 10.0},
    "Prima Fascia": {"min_rating": 8.0, "max_rating": 8.9},
    "Seconda Fascia": {"min_rating": 7.0, "max_rating": 7.9},
    "Terza Fascia": {"min_rating": 6.5, "max_rating": 6.9},
}
RECOMMENDATION_TIER_OPTIONS = list(RECOMMENDATION_TIERS.keys())

def get_recommendation_tier(rating: float) -> str | None:
    r = float(rating)
    if r >= 9.0: return "TOP"
    if r >= 8.0: return "Prima Fascia"
    if r >= 7.0: return "Seconda Fascia"
    if r >= 6.5: return "Terza Fascia"
    return None

def get_price_value_score(rating: float, estimated_price: int, list_price: int) -> float:
    """Punteggio qualità/prezzo: privilegia rating alto a costo d'asta contenuto."""
    price=max(1.0,float(estimated_price)); lp=max(1.0,float(list_price)); r=float(rating)
    rating_per_100=(r/price)*100.0
    list_efficiency=lp/price
    quality_bonus=max(0.0,r-7.0)
    return round(rating_per_100*0.68 + list_efficiency*4.0 + quality_bonus*0.90,3)

def calculate_value_per_credit(rating: float, estimated_price: int) -> float:
    """Rating ottenibile ogni 10 crediti stimati."""
    return round((float(rating)/max(1,estimated_price))*10.0,3)


def build_next_player_recommendations(
    state: "AuctionState",
    rosters: list[dict[str, Any]],
    preferred_players: set[Any],
    custom_modifiers: dict[Any, dict[str, Any]],
    role: str | None,
    limit: int = 5,
) -> list[dict[str, Any]]:
    """Restituisce i migliori obiettivi acquistabili nel ruolo corrente."""
    if not role:
        return []

    team_name = get_my_team_name_from_state(state)
    if team_name is None:
        return []

    # Il consiglio è costruito sul budget RCD e sugli slot ancora disponibili.
    # Cerchiamo il budget nello stato tramite le rose/teams in main e lo passiamo
    # indirettamente in una variabile di sessione, se presente.
    budget = st.session_state.get("my_team_budget")
    role_count = state.team_role_totals.get(team_name, {}).get(role, 0)
    total_count = state.team_total_bought.get(team_name, 0)
    # Dopo questo acquisto bisogna comunque conservare almeno 1 credito
    # per ogni slot della rosa che resterà da completare, indipendentemente dal ruolo.
    slots_after = max(0, TOTAL_SLOTS_PER_TEAM - total_count - 1)

    goalkeeper_ranking = build_current_goalkeeper_ranking(state)
    candidates = [
        player for player in load_players(role=role)
        if player.get("id") not in state.bought_player_ids
    ]

    selected_tier = st.session_state.get("recommendation_tier", "TOP")
    rows = []
    for player in candidates:
        details = calculate_player_rating_detailed(
            player, preferred_players, custom_modifiers, goalkeeper_ranking
        )
        rating = float(details["final_rating"])
        tier = get_recommendation_tier(rating)
        if tier is None or tier != selected_tier:
            continue
        estimate = estimate_auction_price(
            player, rosters, budget=budget,
            slots_left_after_purchase=slots_after,
        )
        list_price = int(player.get("list_price") or 1)
        score = get_price_value_score(
            rating, estimate["estimated_price"], list_price
        )
        rows.append({
            "player": player,
            "details": details,
            "estimate": estimate,
            "score": score,
            "tier": tier,
            "rating_per_10_cr": calculate_value_per_credit(
                rating, estimate["estimated_price"]
            ),
        })

    feasible_rows = [row for row in rows if row["estimate"]["feasible"]]
    if feasible_rows:
        rows = feasible_rows

    # Il rating determina la fascia; il prezzo determina il miglior affare
    # SOLO all'interno della fascia selezionata.
    rows.sort(
        key=lambda row: (
            row["score"],
            row["details"]["final_rating"],
            -row["estimate"]["estimated_price"],
        ),
        reverse=True,
    )
    return rows[:limit]



def describe_goalkeeper_strategy(players: list[dict[str, Any]]) -> str:
    """Valuta la strategia P senza chiedere di correggere un reparto già chiuso."""
    keepers=[p for p in players if p.get("role")=="P"]
    if not keepers: return ""
    clubs=[p.get("team_nfl") for p in keepers if p.get("team_nfl")]
    unique_clubs=list(dict.fromkeys(clubs))
    club_goal_data=[(c,GOALS_CONCEDED.get(c)) for c in unique_clubs if GOALS_CONCEDED.get(c) is not None]
    ranking=build_current_goalkeeper_ranking_from_players(keepers)
    details=[calculate_player_rating_detailed(p,st.session_state.preferred_players,load_custom_modifiers(),ranking) for p in keepers]
    avg_rating=sum(d["final_rating"] for d in details)/len(details)
    if len(unique_clubs)==1:
        diversification=f"Hai scelto {len(keepers)}/{len(keepers)} portieri della stessa squadra ({unique_clubs[0]}): strategia molto concentrata, ma non è un difetto in sé se la difesa è affidabile."
    elif len(unique_clubs)==len(keepers):
        diversification=f"Hai scelto {len(keepers)} portieri di {len(unique_clubs)} squadre diverse: ottima diversificazione e minore dipendenza da una singola difesa."
    else:
        diversification=f"Hai {len(keepers)} portieri distribuiti su {len(unique_clubs)} squadre: diversificazione parziale."
    if club_goal_data:
        avg_ga=sum(v for _,v in club_goal_data)/len(club_goal_data)
        vals=list(GOALS_CONCEDED.values()); median=float(pd.Series(vals).median()) if vals else avg_ga
        if avg_ga <= median-4: defense="Le squadre scelte prendono pochi gol: la scelta è particolarmente solida."
        elif avg_ga >= median+4: defense="Le squadre scelte prendono molti gol: hai accettato un rischio che va compensato soprattutto nei difensori."
        else: defense="Le squadre scelte sono nella fascia media per gol subiti."
    else: defense="Non ho abbastanza dati sui gol subiti per giudicare le difese."
    quality=(f"Rating medio portieri {avg_rating:.1f}: reparto di alto livello." if avg_rating>=8 else f"Rating medio portieri {avg_rating:.1f}: reparto competitivo." if avg_rating>=7 else f"Rating medio portieri {avg_rating:.1f}: reparto sotto il livello ideale.")
    if len(keepers)>=ROLE_LIMITS["P"]:
        return f"{diversification} {defense} {quality} Portieri completati: non c'è nulla da correggere qui. Ora sposterei attenzione e budget sui difensori."
    return f"{diversification} {defense} {quality} Finché il reparto non è completo, privilegia il valore per credito e non il solo rating."


def build_current_goalkeeper_ranking_from_players(
    players: list[dict[str, Any]],
) -> dict[str, int]:
    clubs = {p.get("team_nfl") for p in players if p.get("team_nfl")}
    return get_goalkeeper_ranking_for_teams(clubs)


def build_draft_strategy_text(
    state: "AuctionState",
    rosters: list[dict[str, Any]],
    teams_df: pd.DataFrame,
    ratings: dict[str, float],
) -> tuple[str, str, str]:
    """Restituisce fase, valutazione e consiglio per il prossimo ruolo."""
    team_name, players, _ = get_my_team_players_and_purchases(state)
    if team_name is None or not players:
        return "", "", ""

    counts = state.team_role_totals.get(team_name, {})
    current_role = get_my_team_draft_role(state)
    completed = [role for role in DRAFT_ORDER if counts.get(role, 0) >= ROLE_LIMITS[role]]

    sections = []
    if counts.get("P", 0) > 0:
        sections.append("**Portieri:** " + describe_goalkeeper_strategy(players))

    if counts.get("D", 0) > 0:
        defenders = [p for p in players if p.get("role") == "D"]
        d_ratings = [calculate_player_rating_detailed(p, st.session_state.preferred_players, load_custom_modifiers(), build_current_goalkeeper_ranking(state))["final_rating"] for p in defenders]
        d_avg = sum(d_ratings) / len(d_ratings) if d_ratings else 0
        if d_avg >= 8.0:
            d_text = "Difesa molto forte: hai già una base di alto livello."
        elif d_avg >= 7.0:
            d_text = "Difesa competitiva, ma puoi ancora alzare il livello con 1-2 profili forti."
        else:
            d_text = "Difesa sotto il livello desiderabile: spingerei di più sui prossimi difensori."
        sections.append(f"**Difesa:** rating medio {d_avg:.1f}. {d_text}")

    if counts.get("C", 0) > 0:
        midfielders = [p for p in players if p.get("role") == "C"]
        c_details = [calculate_player_rating_detailed(p, st.session_state.preferred_players, load_custom_modifiers(), build_current_goalkeeper_ranking(state)) for p in midfielders]
        c_avg = sum(d["final_rating"] for d in c_details) / len(c_details) if c_details else 0
        bonus_flags = sum(
            bool(p.get("rigorista")) or bool((p.get("list_price") or 0) >= 25)
            for p in midfielders
        )
        if bonus_flags < max(1, len(midfielders) // 3):
            c_text = "Hai pochi profili ad alto potenziale bonus: qui conviene spingere."
        elif c_avg >= 8.0:
            c_text = "Centrocampo molto forte e con buon potenziale bonus."
        else:
            c_text = "Centrocampo discreto: cerca ancora qualità e giocatori con bonus."
        sections.append(f"**Centrocampo:** rating medio {c_avg:.1f}. {c_text}")

    if counts.get("A", 0) > 0:
        attackers = [p for p in players if p.get("role") == "A"]
        a_details = [calculate_player_rating_detailed(p, st.session_state.preferred_players, load_custom_modifiers(), build_current_goalkeeper_ranking(state)) for p in attackers]
        a_avg = sum(d["final_rating"] for d in a_details) / len(a_details) if a_details else 0
        if a_avg >= 8.0:
            a_text = "Attacco di livello alto: la fase offensiva è una forza della rosa."
        elif a_avg >= 7.0:
            a_text = "Attacco competitivo: manca ancora un profilo che faccia davvero la differenza."
        else:
            a_text = "Attacco debole: qui va concentrata una parte importante del budget."
        sections.append(f"**Attacco:** rating medio {a_avg:.1f}. {a_text}")

    if current_role:
        next_name = ROLE_NAMES[current_role]
        if current_role == "P":
            advice = "Stai costruendo i portieri: privilegia il rapporto rating/costo e, a parità di valore, preferisci squadre che concedono pochi gol."
        elif current_role == "D":
            advice = "I portieri sono chiusi: ora cerca difensori con rating alto ma soprattutto con buon rapporto rating/costo. Se i P sono concentrati su una squadra, una difesa solida di quella squadra aumenta la coerenza della strategia."
        elif current_role == "C":
            advice = "Portieri e difensori sono acquisiti: cerca centrocampisti ad alto valore per credito, con titolarità, rigoristi e potenziale bonus. Non inseguire automaticamente il rating massimo."
        else:
            advice = "Sugli attaccanti puoi concentrare più budget sui profili forti, ma continua a confrontare rating, stima d'asta e crediti residui: un 9.0 molto costoso non è sempre migliore di un 8.6 a metà prezzo."
        phase = f"Fase draft: **{next_name}** ({counts.get(current_role, 0)}/{ROLE_LIMITS[current_role]})."
    else:
        phase = "🎉 Draft completato."
        advice = "Ora valuta il rapporto qualità/prezzo complessivo e le eventuali correzioni di rosa."

    return phase, " ".join(sections), advice


# ============================================================
# RATING
# ============================================================

def calculate_player_rating_detailed(
    player: dict[str, Any],
    preferred_players: set[Any] | None = None,
    custom_modifiers: dict[Any, dict[str, Any]] | None = None,
    goalkeeper_ranking: dict[str, int] | None = None,
) -> dict[str, Any]:
    preferred_players = preferred_players or set()
    if custom_modifiers is None:
        custom_modifiers = load_custom_modifiers()
    role = player.get("role", "D")
    player_name = normalize_string(player.get("name", ""))

    base = 5.0
    real_stats = False
    goals = assists = matches = 0

    if not STATS.empty and player_name and "clean_name" in STATS.columns:
        exact = STATS[STATS["clean_name"] == player_name]
        match = exact
        if match.empty:
            escaped = re.escape(player_name)
            match = STATS[STATS["clean_name"].str.contains(escaped, na=False, regex=True)]
        if not match.empty:
            row = match.iloc[0]
            goals = int(row.get("goals", 0) or 0)
            assists = int(row.get("assists", 0) or 0)
            matches = int(row.get("matches", 0) or 0)
            if matches > 3:
                base = float(row.get("avg_vote", 6.0) or 6.0)
                if role in {"A", "C"}:
                    base += goals * 0.12 + assists * 0.08
                else:
                    base += goals * 0.15 + assists * 0.10
                real_stats = True

    if not real_stats:
        fallback = {"A": 5.0, "P": 5.0, "C": 4.8, "D": 4.5}.get(role, 4.5)
        base = fallback + (float(player.get("list_price") or 1) * 0.04)

    titolarita_mod = {
        "Titolare": 0.4,
        "Ballottaggio": -0.3,
        "Riserva": -1.5,
    }.get(player.get("status_titolarita"), 0.0)

    team_mods = MODS.get(player.get("team_nfl"), {"att": 0.0, "def": 0.0})

    # Portieri: il modificatore difensivo standard viene sostituito
    # dal criterio richiesto basato sui gol subiti delle tre squadre.
    goalkeeper_mod, goalkeeper_rank = get_goalkeeper_modifier(
        player,
        goalkeeper_ranking,
    )
    team_mod = (
        goalkeeper_mod
        if role == "P"
        else team_mods["att"]
        if role in {"A", "C"}
        else team_mods["def"]
    )

    rigorista_mod = 0.8 if player.get("rigorista") else 0.0
    cartellini_mod = -0.3 if player.get("propensione_cartellini") == "A rischio malus" else 0.0
    rookie_mod = -0.3 if player.get("primo_anno_serie_a") else 0.0
    # Il preferito proveniente dalla sessione resta compatibile.
    # Se il preferito è salvato nella nuova tabella, viene letto da lì.
    db_modifier = custom_modifiers.get(player.get("id"), {})
    custom_mod = float(db_modifier.get("modifier_value") or 0.0)
    db_modifier_key = db_modifier.get("modifier_key")

    preferred_mod = (
        0.5
        if (
            player.get("id") in preferred_players
            and db_modifier_key != "preferito"
        )
        else 0.0
    )

    # Rating grezzo prima della calibrazione per ruolo.
    raw_rating = (
        base
        + titolarita_mod
        + team_mod
        + rigorista_mod
        + cartellini_mod
        + rookie_mod
        + preferred_mod
        + custom_mod
    )

    # Calibrazione richiesta per rendere confrontabili i ruoli senza
    # penalizzare portieri, difensori e centrocampisti rispetto agli attaccanti.
    role_multiplier = ROLE_RATING_MULTIPLIERS.get(role, 1.0)
    calibrated_rating = raw_rating * role_multiplier

    final = round(
        max(1.0, min(10.0, calibrated_rating)),
        1,
    )

    if (
        (cartellini_mod < 0 or rookie_mod < 0 or player.get("status_titolarita") in {"Ballottaggio", "Riserva"})
        and final >= 10.0
    ):
        final = 9.0

    return {
        "final_rating": final,
        "raw_rating": round(raw_rating, 2),
        "role_multiplier": round(role_multiplier, 3),
        "calibrated_rating": round(calibrated_rating, 2),
        "base": round(base, 2),
        "team_mod": team_mod,
        "goalkeeper_mod": goalkeeper_mod,
        "goalkeeper_rank": goalkeeper_rank,
        "tit": titolarita_mod,
        "rig": rigorista_mod,
        "cart": cartellini_mod,
        "rook": rookie_mod,
        "pref": preferred_mod,
        "custom_mod": custom_mod,
        "custom_label": db_modifier.get("modifier_label", "Nessuna modifica"),
        "g": goals,
        "a": assists,
        "m": matches,
    }


def calculate_player_rating(
    player: dict[str, Any],
    preferred_players: set[Any] | None = None,
    custom_modifiers: dict[Any, dict[str, Any]] | None = None,
    goalkeeper_ranking: dict[str, int] | None = None,
) -> float:
    return calculate_player_rating_detailed(
        player,
        preferred_players,
        custom_modifiers,
        goalkeeper_ranking,
    )["final_rating"]



def build_current_goalkeeper_ranking(
    state: "AuctionState",
) -> dict[str, int]:
    """Classifica le squadre dei portieri attualmente presenti nelle rose."""
    goalkeeper_teams: set[str] = set()

    for players in state.team_players_map.values():
        for player in players:
            if player.get("role") == "P" and player.get("team_nfl"):
                goalkeeper_teams.add(player["team_nfl"])

    return get_goalkeeper_ranking_for_teams(goalkeeper_teams)


# ============================================================
# STATO ASTA
# ============================================================

def build_auction_state(
    teams: list[dict[str, Any]],
    rosters: list[dict[str, Any]],
) -> AuctionState:
    bought_player_ids: set[Any] = set()
    team_role_totals = {
        team["name"]: {role: 0 for role in ROLE_LIMITS}
        for team in teams
    }
    team_total_bought = {team["name"]: 0 for team in teams}
    team_players_map = {team["name"]: [] for team in teams}
    team_purchases_map = {team["name"]: [] for team in teams}

    for roster in rosters:
        player = roster.get("players")
        team = roster.get("teams")

        if not player or not team:
            continue

        player_id = player.get("id")
        team_name = team.get("name")
        role = player.get("role")

        if player_id is not None:
            bought_player_ids.add(player_id)

        if team_name not in team_players_map:
            continue

        team_players_map[team_name].append(player)
        team_purchases_map[team_name].append(roster)

        if role in ROLE_LIMITS:
            team_role_totals[team_name][role] += 1
            team_total_bought[team_name] += 1

    return AuctionState(
        bought_player_ids=bought_player_ids,
        team_role_totals=team_role_totals,
        team_total_bought=team_total_bought,
        team_players_map=team_players_map,
        team_purchases_map=team_purchases_map,
    )


def player_team_weight(rating: float) -> float:
    """Peso del giocatore nella valutazione della rosa."""
    if rating >= 9.0:
        return TEAM_PLAYER_WEIGHTS["TOP"]
    if rating >= 8.0:
        return TEAM_PLAYER_WEIGHTS["PRIMA"]
    if rating >= 7.0:
        return TEAM_PLAYER_WEIGHTS["SECONDA"]
    if rating >= 6.5:
        return TEAM_PLAYER_WEIGHTS["TERZA"]
    return TEAM_PLAYER_WEIGHTS["SOTTO_SOGLIA"]


def calculate_single_team_rating(
    players: list[dict[str, Any]],
    preferred_players: set[Any],
    custom_modifiers: dict[Any, dict[str, Any]] | None = None,
    goalkeeper_ranking: dict[str, int] | None = None,
) -> float:
    """
    Rating rosa non lineare.

    - I TOP pesano molto più degli altri.
    - I giocatori sotto 6.5 incidono negativamente.
    - Le differenze attorno alla fascia media vengono amplificate.
    """
    if not players:
        return 0.0

    player_ratings = [
        calculate_player_rating(
            player,
            preferred_players,
            custom_modifiers,
            goalkeeper_ranking,
        )
        for player in players
    ]

    weights = [player_team_weight(rating) for rating in player_ratings]
    weighted_avg = sum(
        rating * weight
        for rating, weight in zip(player_ratings, weights)
    ) / max(0.001, sum(weights))

    top_count = sum(rating >= 9.0 for rating in player_ratings)
    elite_count = sum(8.5 <= rating < 9.0 for rating in player_ratings)
    weak_count = sum(rating < 6.5 for rating in player_ratings)

    # Amplificazione attorno al centro: due rose simili non finiscono
    # automaticamente tutte nello stesso intervallo 5.5-5.9.
    amplified = (
        TEAM_RATING_CENTER
        + (weighted_avg - TEAM_RATING_CENTER) * TEAM_RATING_SPREAD
    )

    # La presenza di veri TOP cambia il potenziale di una rosa.
    star_bonus = min(
        1.10,
        top_count * TOP_PLAYER_BONUS
        + elite_count * ELITE_PLAYER_BONUS,
    )

    # Profili deboli continuano a pesare, ma meno dei TOP in positivo.
    weak_penalty = min(1.20, weak_count * WEAK_PLAYER_PENALTY)

    final = amplified + star_bonus - weak_penalty

    return round(
        max(TEAM_RATING_MIN, min(TEAM_RATING_MAX, final)),
        1,
    )


def calculate_team_ratings(
    state: AuctionState,
    preferred_players: set[Any],
    custom_modifiers: dict[Any, dict[str, Any]] | None = None,
    goalkeeper_ranking: dict[str, int] | None = None,
) -> dict[str, float]:
    return {
        team_name: calculate_single_team_rating(
            players,
            preferred_players,
            custom_modifiers,
            goalkeeper_ranking,
        )
        for team_name, players in state.team_players_map.items()
    }


def calculate_completed_roles(
    state: AuctionState,
) -> list[str]:
    completed = []

    for role, limit in ROLE_LIMITS.items():
        if all(
            counts[role] >= limit
            for counts in state.team_role_totals.values()
        ):
            completed.append(role)

    return completed


def is_auction_finished(state: AuctionState) -> bool:
    return all(
        bought >= TOTAL_SLOTS_PER_TEAM
        for bought in state.team_total_bought.values()
    )


# ============================================================
# ANALISI SQUADRA
# ============================================================

def get_credit_rank(
    teams_df: pd.DataFrame,
    team_name: str,
) -> tuple[int, int]:
    sorted_df = (
        teams_df.sort_values("remaining_budget", ascending=False)
        .reset_index(drop=True)
    )
    row = sorted_df[sorted_df["name"] == team_name]

    if row.empty:
        return 0, 0

    return int(row.index[0] + 1), int(row.iloc[0]["remaining_budget"])


def get_team_risk_counts(players: list[dict[str, Any]]) -> dict[str, int]:
    movement_players = [
        player for player in players
        if player.get("role") != "P"
    ]

    club_counts: dict[str, int] = {}
    for player in movement_players:
        club = player.get("team_nfl")
        if club:
            club_counts[club] = club_counts.get(club, 0) + 1

    return {
        "max_block": max(club_counts.values(), default=0),
        "ballottaggio": sum(
            player.get("status_titolarita") == "Ballottaggio"
            for player in players
        ),
        "cartellini": sum(
            player.get("propensione_cartellini") == "A rischio malus"
            for player in players
        ),
        "rookie": sum(
            bool(player.get("primo_anno_serie_a"))
            for player in players
        ),
    }


def risk_label(
    count: int,
    good_threshold: int,
    warning_threshold: int,
    good: str,
    warning: str,
    bad: str,
) -> str:
    if count < good_threshold:
        return good
    if count < warning_threshold:
        return warning
    return bad


def render_team_analysis(
    teams_df: pd.DataFrame,
    state: AuctionState,
    ratings: dict[str, float],
) -> None:
    st.sidebar.divider()
    st.sidebar.subheader("🔮 Analisi Asta & Valutazione")

    team_names = teams_df["name"].tolist()
    if not team_names:
        st.sidebar.info("Nessuna squadra configurata.")
        return

    selected_team = st.sidebar.selectbox(
        "Analizza squadra",
        team_names,
        index=default_team_index(team_names),
        key="sidebar_team_analysis",
    )

    players = state.team_players_map.get(selected_team, [])
    bought_count = len(players)
    credit_rank, budget = get_credit_rank(teams_df, selected_team)
    slots_left = max(0, TOTAL_SLOTS_PER_TEAM - bought_count)

    if players:
        avg_score = ratings[selected_team]
        rating_position = sorted(
            ratings,
            key=ratings.get,
            reverse=True,
        ).index(selected_team) + 1

        st.sidebar.metric(
            "Rating Rosa",
            f"{avg_score:.1f} / 10.0",
            delta=f"Posizione: {rating_position}/{len(ratings)}",
            delta_color="off",
        )

        if avg_score >= 8:
            st.sidebar.success("Rosa da Scudetto!")
        elif avg_score >= 6.5:
            st.sidebar.info("Rosa competitiva.")
        else:
            st.sidebar.warning("Rosa da rinforzare.")
    else:
        st.sidebar.metric("Rating Rosa", "N/D")
        st.sidebar.info("Assegna giocatori per calcolare il rating.")

    st.sidebar.markdown(
        f"💰 **Posizione Crediti:** {credit_rank}° su {len(team_names)} "
        f"({budget} cr residui)"
    )

    if slots_left:
        avg_spendable = budget / slots_left
        st.sidebar.caption(
            f"Spesa media potenziale: **{avg_spendable:.1f} cr/slot** "
            f"({slots_left} slot liberi)"
        )

    st.sidebar.markdown("---")
    st.sidebar.markdown("**📊 Cruscotto Rischi Rosa:**")

    risks = get_team_risk_counts(players)

    block_status = (
        "👍 Ottimale" if risks["max_block"] < 4
        else "👎 Rischio Blocco"
    )
    st.sidebar.write(
        f"🚨 **Blocco Squadra:** {risks['max_block']} max | {block_status}"
    )

    ballot_status = risk_label(
        risks["ballottaggio"], 3, 6,
        "👍 Ottimale", "🟡 Moderato", "👎 Troppi",
    )
    st.sidebar.write(
        f"⚠️ **Ballottaggi:** {risks['ballottaggio']} giocatori | "
        f"{ballot_status}"
    )

    card_status = risk_label(
        risks["cartellini"], 2, 4,
        "👍 Pulita", "🟡 Attenzione", "👎 Troppi Malus",
    )
    st.sidebar.write(
        f"🟨 **A rischio malus:** {risks['cartellini']} | {card_status}"
    )

    rookie_status = risk_label(
        risks["rookie"], 2, 4,
        "👍 Esperti", "🟡 Equilibrato", "👎 Troppi Rookie",
    )
    st.sidebar.write(
        f"👶 **Primo anno in A:** {risks['rookie']} | {rookie_status}"
    )


# ============================================================
# TOP 5
# ============================================================

def render_top5(
    role: str,
    bought_player_ids: set[Any],
    preferred_players: set[Any],
    state: AuctionState | None = None,
) -> None:
    st.sidebar.subheader("🔥 Top 5 Liberi (Ranking)")

    players = load_players(role=role)

    available = [
        player for player in players
        if player["id"] not in bought_player_ids
    ]

    goalkeeper_ranking = build_current_goalkeeper_ranking(state) if state else ALL_GOALKEEPER_RANKING
    custom_modifiers = load_custom_modifiers()
    available.sort(
        key=lambda player: calculate_player_rating(
            player,
            preferred_players,
            custom_modifiers,
            goalkeeper_ranking,
        ),
        reverse=True,
    )

    with st.sidebar.container(border=True):
        if not available:
            st.info("Nessun giocatore disponibile.")
            return

        for index, player in enumerate(available[:5], start=1):
            rating = calculate_player_rating(
                player,
                preferred_players,
                custom_modifiers,
                goalkeeper_ranking,
            )
            star = " ⭐" if player["id"] in preferred_players else ""

            st.markdown(
                f"**{index}. {player['name']}**{star} "
                f"`[{player['role']}]` ({player['team_nfl']}) — "
                f"⭐️ **{rating}** | 💎 **{player['list_price']} cr**"
            )


# ============================================================
# AUTOCOMPILAZIONE
# ============================================================

def simulate_autofill(
    teams: list[dict[str, Any]],
    state: AuctionState,
    role_filter: str,
) -> tuple[list[dict[str, Any]], dict[str, int]]:
    players = load_players()
    free_players = [
        player for player in players
        if player["id"] not in state.bought_player_ids
    ]

    if role_filter != "Tutti":
        free_players = [
            player for player in free_players
            if player["role"] == role_filter
        ]

    random.shuffle(free_players)

    sim_bought = state.team_total_bought.copy()
    sim_roles = {
        team: counts.copy()
        for team, counts in state.team_role_totals.items()
    }
    sim_budgets = {
        team["name"]: int(team["remaining_budget"])
        for team in teams
    }
    team_id_map = {
        team["name"]: team["id"]
        for team in teams
    }

    inserts = []

    for player in free_players:
        role = player["role"]
        if role not in ROLE_LIMITS:
            continue

        valid_teams = [
            team_name
            for team_name in sim_bought
            if (
                sim_bought[team_name] < TOTAL_SLOTS_PER_TEAM
                and sim_roles[team_name][role] < ROLE_LIMITS[role]
            )
        ]

        if not valid_teams:
            continue

        def team_score(team_name: str) -> float:
            slots_left = TOTAL_SLOTS_PER_TEAM - sim_bought[team_name]
            return (
                sim_budgets[team_name] / slots_left
                if slots_left > 0
                else -1
            )

        chosen_team = max(valid_teams, key=team_score)
        slots_left = TOTAL_SLOTS_PER_TEAM - sim_bought[chosen_team]
        current_budget = sim_budgets[chosen_team]

        base_price = max(1, int(player.get("list_price") or 1))

        if slots_left == 1:
            purchase_price = max(1, current_budget)
        else:
            avg_allowed = current_budget / slots_left
            purchase_price = max(
                1,
                int((base_price + avg_allowed) / 2),
            )

            max_allowed = current_budget - (slots_left - 1)
            purchase_price = min(
                purchase_price,
                max(1, int(max_allowed)),
            )

        inserts.append(
            {
                "team_id": team_id_map[chosen_team],
                "player_id": player["id"],
                "purchase_price": purchase_price,
            }
        )

        sim_bought[chosen_team] += 1
        sim_roles[chosen_team][role] += 1
        sim_budgets[chosen_team] -= purchase_price

    return inserts, sim_budgets


def perform_autofill(
    teams: list[dict[str, Any]],
    state: AuctionState,
    role_filter: str,
) -> bool:
    inserts, budgets = simulate_autofill(
        teams,
        state,
        role_filter,
    )

    if not inserts:
        return False

    supabase.table("rosters").insert(inserts).execute()

    team_id_map = {
        team["name"]: team["id"]
        for team in teams
    }

    for team_name, budget in budgets.items():
        supabase.table("teams").update(
            {"remaining_budget": max(0, int(budget))}
        ).eq(
            "id",
            team_id_map[team_name],
        ).execute()

    return True


# ============================================================
# ADMIN
# ============================================================

def reset_auction(teams_df: pd.DataFrame) -> None:
    supabase.table("rosters").delete().gt("purchase_price", -1).execute()

    for _, row in teams_df.iterrows():
        supabase.table("teams").update(
            {"remaining_budget": int(row["initial_budget"])}
        ).eq("id", row["id"]).execute()


def render_admin_tools(
    teams_df: pd.DataFrame,
    state: AuctionState,
) -> None:
    st.sidebar.divider()
    st.sidebar.subheader("🛠️ Strumenti Mockup & Admin")

    role_filter = st.sidebar.selectbox(
        "Completa ruolo (Mockup)",
        ["Tutti"] + list(ROLE_LIMITS),
    )

    if st.sidebar.button("🎲 Autocompila rose (Intermedio)"):
        if perform_autofill(
            teams_df.to_dict("records"),
            state,
            role_filter,
        ):
            st.sidebar.success("Rose autocompilate con successo!")
            invalidate_data_cache()
            st.rerun()
        else:
            st.sidebar.warning(
                "Nessun inserimento possibile o limiti già raggiunti."
            )

    if st.sidebar.button(
        "🗑️ Svuota tutte le rose (Reset)",
        type="primary",
    ):
        st.session_state["confirm_reset"] = True

    if st.session_state.get("confirm_reset"):
        st.sidebar.warning(
            "Questa operazione cancellerà tutti gli acquisti e "
            "ripristinerà i budget iniziali."
        )

        confirm_col, cancel_col = st.sidebar.columns(2)

        with confirm_col:
            if st.button("Conferma reset", key="confirm_reset_button"):
                reset_auction(teams_df)
                st.session_state["confirm_reset"] = False
                invalidate_data_cache()
                st.sidebar.success("Asta resettata.")
                st.rerun()

        with cancel_col:
            if st.button("Annulla", key="cancel_reset_button"):
                st.session_state["confirm_reset"] = False
                st.rerun()


# ============================================================
# ACQUISTO MANUALE
# ============================================================

def execute_purchase(
    teams_df: pd.DataFrame,
    state: AuctionState,
    selected_player: dict[str, Any],
    purchase_price: int,
    target_team: str,
) -> tuple[bool, str]:
    team_row = teams_df[teams_df["name"] == target_team]

    if team_row.empty:
        return False, "Seleziona una squadra valida."

    team = team_row.iloc[0]
    role = selected_player["role"]
    role_count = state.team_role_totals[target_team][role]
    role_limit = ROLE_LIMITS.get(role, TOTAL_SLOTS_PER_TEAM)

    if role_count >= role_limit:
        return (
            False,
            f"❌ Limite raggiunto! {target_team} ha completato "
            f"il ruolo {role} ({role_count}/{role_limit}).",
        )

    if state.team_total_bought[target_team] >= TOTAL_SLOTS_PER_TEAM:
        return (
            False,
            f"❌ La squadra {target_team} ha completato la rosa "
            f"({TOTAL_SLOTS_PER_TEAM}/{TOTAL_SLOTS_PER_TEAM}).",
        )

    current_budget = int(team["remaining_budget"])

    if purchase_price > current_budget:
        return (
            False,
            f"❌ Budget insufficiente per {target_team}: "
            f"{current_budget} crediti residui.",
        )

    supabase.table("rosters").insert(
        {
            "team_id": team["id"],
            "player_id": selected_player["id"],
            "purchase_price": purchase_price,
        }
    ).execute()

    supabase.table("teams").update(
        {"remaining_budget": current_budget - purchase_price}
    ).eq("id", team["id"]).execute()

    return True, ""


def render_manual_purchase(
    teams_df: pd.DataFrame,
    state: AuctionState,
    current_role: str,
    rosters: list[dict[str, Any]],
) -> str:
    """Renderizza il pannello di acquisto manuale in una griglia allineata."""
    if is_auction_finished(state):
        return current_role

    players_for_filter = load_players()

    available_nfl_teams = sorted(
        {
            player["team_nfl"]
            for player in players_for_filter
            if player.get("team_nfl")
        }
    )

    # Tutti i controlli restano sulla stessa riga: evita lo sfalsamento
    # causato da colonne vuote usate come spaziatori.
    col1, col2, col3, col4, col5 = st.columns(
        [1.25, 1.45, 2.8, 1.0, 1.55],
        gap="small",
    )

    with col1:
        my_team_name = get_my_team_name_from_state(state)
        my_counts = state.team_role_totals.get(my_team_name or "", {})
        role_options = {
            label: role
            for label, role in ROLE_LABELS.items()
            if role == "ALL"
            or my_counts.get(role, 0) < ROLE_LIMITS[role]
        }
        role_labels = list(role_options)
        current_label = next(
            (label for label, role in role_options.items() if role == current_role),
            role_labels[0],
        )
        selected_role_label = st.selectbox(
            "1. Seleziona Ruolo",
            role_labels,
            index=role_labels.index(current_label),
            key="main_role_select",
        )
        current_role = role_options[selected_role_label]

    with col2:
        nfl_filter_label = st.selectbox(
            "2. Filtra per Squadra Serie A",
            ["Tutte le squadre"] + available_nfl_teams,
            key="manual_nfl_filter",
        )
        team_filter = (
            "ALL"
            if nfl_filter_label == "Tutte le squadre"
            else nfl_filter_label
        )

    players = load_players(role=current_role, team_nfl=team_filter)
    available_players = [
        player
        for player in players
        if player["id"] not in state.bought_player_ids
    ]

    if not available_players:
        st.warning("Nessun giocatore disponibile trovato con questi filtri.")
        return current_role

    player_options = {
        (
            f"{player['name']} [{player['role']}] "
            f"({player['team_nfl']} - {int(player.get('list_price') or 0)} cr. - "
            f"{calculate_player_rating_detailed(player, st.session_state.preferred_players, load_custom_modifiers(), build_current_goalkeeper_ranking(state))['final_rating']:.1f})"
        ): player
        for player in available_players
    }

    with col3:
        selected_label = st.selectbox(
            "3. Seleziona Giocatore",
            list(player_options),
            key="manual_player_select",
        )
        selected_player = player_options[selected_label]

    with col4:
        default_price = max(1, int(selected_player.get("list_price") or 1))
        purchase_price = st.number_input(
            "4. Costo",
            min_value=1,
            max_value=500,
            value=default_price,
            step=1,
            key="manual_purchase_price",
        )

    with col5:
        role = selected_player["role"]
        active_teams = [
            team_name
            for team_name in teams_df["name"].tolist()
            if (
                state.team_total_bought[team_name] < TOTAL_SLOTS_PER_TEAM
                and state.team_role_totals[team_name][role] < ROLE_LIMITS[role]
            )
        ]
        team_names = active_teams or teams_df["name"].tolist()

        target_team = st.selectbox(
            "5. Squadra Acquirente",
            team_names,
            index=default_team_index(team_names, MY_TEAM_NAME),
            key="manual_target_team",
        )

    # Valutazione immediata del giocatore selezionato.
    current_custom = load_custom_modifiers()
    goalkeeper_ranking = build_current_goalkeeper_ranking(state)
    player_details = calculate_player_rating_detailed(
        selected_player,
        st.session_state.preferred_players,
        current_custom,
        goalkeeper_ranking,
    )
    estimate = estimate_auction_price(
        selected_player,
        rosters,
        budget=st.session_state.get("my_team_budget"),
        slots_left_after_purchase=max(
            0,
            TOTAL_SLOTS_PER_TEAM
            - state.team_total_bought.get(get_my_team_name_from_state(state) or "", 0)
            - 1,
        ),
    )

    selected_value_score = get_price_value_score(
        player_details["final_rating"], estimate["estimated_price"], int(selected_player.get("list_price") or 1)
    )
    selected_rating_per_10 = calculate_value_per_credit(
        player_details["final_rating"], estimate["estimated_price"]
    )
    st.markdown(
        f"💰 **Stima asta:** circa **{estimate['estimated_price']} cr** "
        f"(**x{estimate['multiplier']:.2f}** del listino) · "
        f"{estimate['source']} · campione {estimate['sample_size']} acquisti."
    )
    st.caption(
        f"📊 **Valore stimato:** {selected_rating_per_10:.2f} rating ogni 10 cr · "
        f"Value Score **{selected_value_score:.2f}** · "
        "la priorità premia rating alto + costo stimato contenuto."
    )

    if estimate["budget_note"]:
        st.caption(f"⚠️ {estimate['budget_note']}")
    elif estimate.get("max_bid") is not None:
        st.caption(f"Budget massimo sostenibile mantenendo 1 credito per ogni slot futuro: **{estimate['max_bid']} cr**.")

    if not st.button(
        "Conferma Acquisto",
        type="primary",
        key="confirm_manual_purchase",
    ):
        return current_role

    success, error = execute_purchase(
        teams_df,
        state,
        selected_player,
        int(purchase_price),
        target_team,
    )

    if not success:
        st.error(error)
        return current_role

    rating = player_details["final_rating"]

    # IMPORTANTE: st.rerun() interrompe immediatamente l'esecuzione del run.
    # Per questo il banner deve essere salvato in session_state PRIMA del rerun.
    if is_my_team(target_team):
        queue_purchase_banner(
            MY_TEAM_NAME,
            selected_player["name"],
            rating,
            int(purchase_price),
        )
    else:
        st.session_state.pop("pending_purchase_banner", None)

    invalidate_data_cache()
    st.rerun()
    return current_role


# ============================================================ SQUADRE
# ============================================================

def build_team_alerts(
    players: list[dict[str, Any]],
    bought: int,
) -> list[dict[str, str]]:
    alerts: list[dict[str, str]] = []

    club_players: dict[str, list[str]] = {}
    for player in players:
        if player.get("role") == "P":
            continue

        club = player.get("team_nfl")
        if club:
            club_players.setdefault(club, []).append(
                f"{player.get('name')} [{player.get('role')}]"
            )

    for club, names in club_players.items():
        if len(names) >= 4:
            alerts.append(
                {
                    "text": (
                        f"🚨 **Rischio Blocco:** {len(names)} "
                        f"giocatori di movimento su {club}"
                    ),
                    "help": (
                        f"Giocatori di movimento del club {club}:\n- "
                        + "\n- ".join(names)
                    ),
                }
            )

    ballotaggio = [
        f"{player.get('name')} [{player.get('role')}]"
        for player in players
        if player.get("status_titolarita") == "Ballottaggio"
    ]
    if bought >= 5 and len(ballotaggio) >= bought * 0.4:
        alerts.append(
            {
                "text": f"⚠️ **Troppi Ballottaggi:** {len(ballotaggio)} giocatori",
                "help": "Giocatori in ballottaggio:\n- "
                + "\n- ".join(ballotaggio),
            }
        )

    cartellini = [
        f"{player.get('name')} [{player.get('role')}]"
        for player in players
        if player.get("propensione_cartellini") == "A rischio malus"
    ]
    if len(cartellini) >= 3:
        alerts.append(
            {
                "text": f"🟨 **Rischio Malus:** {len(cartellini)} a rischio cartellino",
                "help": "Giocatori a rischio malus:\n- "
                + "\n- ".join(cartellini),
            }
        )

    rookies = [
        f"{player.get('name')} [{player.get('role')}]"
        for player in players
        if player.get("primo_anno_serie_a")
    ]
    if len(rookies) >= 3:
        alerts.append(
            {
                "text": f"👶 **Rischio Rookie:** {len(rookies)} al primo anno in A",
                "help": "Giocatori al primo anno in Serie A:\n- "
                + "\n- ".join(rookies),
            }
        )

    return alerts


def render_team_overview(
    teams_df: pd.DataFrame,
    state: AuctionState,
    ratings: dict[str, float],
) -> None:
    st.divider()
    st.subheader("📊 Panoramica Squadre & Alert Strategici")

    if teams_df.empty:
        st.info("Nessuna squadra configurata.")
        return

    summaries = []

    for _, team in teams_df.iterrows():
        name = team["name"]
        remaining_budget = int(team["remaining_budget"])
        players = state.team_players_map[name]
        bought = state.team_total_bought[name]
        spent = sum(
            purchase.get("purchase_price", 0)
            for purchase in state.team_purchases_map[name]
        )

        slots_left = max(0, TOTAL_SLOTS_PER_TEAM - bought)
        avg_price = (
            round(remaining_budget / slots_left, 1)
            if slots_left
            else 0
        )
        avg_spent = (
            round(spent / bought, 1)
            if bought
            else 0.0
        )
        total_listino = sum(int(player.get("list_price") or 0) for player in players)
        auction_multiplier = round(spent / total_listino, 2) if total_listino > 0 else 0.0

        alerts = build_team_alerts(players, bought)

        top_players = sum(
            player.get("slot_fantacalcio") == "1° Slot"
            or (player.get("list_price") or 0) >= 25
            for player in players
        )

        if bought == 0:
            status = "📭 Rosa ancora vuota."
        else:
            count = len(alerts)
            risk_text = (
                "pochi rischi"
                if count == 0
                else "1 rischio potenziale"
                if count == 1
                else f"{count} criticità da monitorare"
            )
            status = (
                f"✨ Rating: **{ratings[name]:.1f}** "
                f"({top_players} Top) — {risk_text}."
            )

        summaries.append(
            {
                "team": team,
                "bought": bought,
                "slots_left": slots_left,
                "avg_price": avg_price,
                "avg_spent": avg_spent,
                "auction_multiplier": auction_multiplier,
                "role_counts": state.team_role_totals[name],
                "alerts": alerts,
                "status": status,
            }
        )

    summaries.sort(
        key=lambda item: (
            -item["avg_price"],
            -int(item["team"]["remaining_budget"]),
            item["team"]["name"],
        )
    )

    for start in range(0, len(summaries), 4):
        cols = st.columns(4)

        for offset, col in enumerate(cols):
            if start + offset >= len(summaries):
                continue

            item = summaries[start + offset]
            team = item["team"]
            name = team["name"]
            bought = item["bought"]
            remaining = int(team["remaining_budget"])
            initial = max(1, int(team["initial_budget"]))
            roles = item["role_counts"]

            role_string = (
                f"**P** {roles['P']}/{ROLE_LIMITS['P']} | "
                f"**D** {roles['D']}/{ROLE_LIMITS['D']} | "
                f"**C** {roles['C']}/{ROLE_LIMITS['C']} | "
                f"**A** {roles['A']}/{ROLE_LIMITS['A']}"
            )

            with col:
                title = (
                    f"**{name}** — ⭐️ {ratings[name]:.1f}"
                    if bought
                    else f"**{name}**"
                )
                st.markdown(title)

                if bought < TOTAL_SLOTS_PER_TEAM:
                    delta = (
                        f"{item['avg_spent']} cr/giocatore · x{item['auction_multiplier']:.2f} listino"
                        if bought
                        else "N/A"
                    )
                    st.metric(
                        "Budget",
                        f"{remaining} cr",
                        delta=delta,
                        delta_color="off",
                    )
                    st.markdown(role_string)
                    st.text(
                        f"Media max/giocatore: {item['avg_price']} cr"
                    )
                    st.progress(
                        max(0.0, min(1.0, remaining / initial))
                    )
                else:
                    st.success(
                        f"✅ Rosa Completata "
                        f"({TOTAL_SLOTS_PER_TEAM}/{TOTAL_SLOTS_PER_TEAM})"
                    )

                st.markdown(f"*{item['status']}*")

                for alert in item["alerts"]:
                    st.markdown(
                        alert["text"],
                        help=alert["help"],
                    )

                st.markdown("---")


# ============================================================
# TAB 2 — ROSE E PAGELLE
# ============================================================

def build_roster_dataframe(
    rosters: list[dict[str, Any]],
    preferred_players: set[Any],
) -> pd.DataFrame:
    rows = []

    for roster in rosters:
        team = roster.get("teams")
        player = roster.get("players")

        if not team or not player:
            continue

        list_price = player.get("list_price") or 1

        rows.append(
            {
                "⭐ Preferito": player["id"] in preferred_players,
                "Squadra": team["name"],
                "Giocatore": player["name"],
                "Ruolo": player["role"],
                "Rating": calculate_player_rating(
                    player,
                    preferred_players,
                ),
                "Club Serie A": player.get("team_nfl"),
                "Listino": list_price,
                "Pagato": roster.get("purchase_price", 0),
                "Moltiplicatore Asta": round(
                    float(roster.get("purchase_price", 0)) / float(list_price)
                    if float(list_price) > 0 else 0.0,
                    2,
                ),
                "Differenza": (
                    roster.get("purchase_price", 0) - list_price
                ),
                "Slot": player.get(
                    "slot_fantacalcio",
                    "Scommessa",
                ),
                "Titolarità": player.get(
                    "status_titolarita",
                    "Titolare",
                ),
                "Rigorista": "Sì" if player.get("rigorista") else "No",
                "Fisico": player.get(
                    "affidabilita_fisica",
                    "Integro",
                ),
                "Cartellini": player.get(
                    "propensione_cartellini",
                    "Normale",
                ),
                "1° Anno A": (
                    "Sì"
                    if player.get("primo_anno_serie_a")
                    else "No"
                ),
                "_player_id": player["id"],
            }
        )

    return pd.DataFrame(rows)


def calculate_market_efficiency(
    purchases: list[dict[str, Any]],
    all_rosters: list[dict[str, Any]],
) -> tuple[float, float]:
    """
    Confronta quanto una squadra ha pagato rispetto al mercato reale dell'asta.

    Ritorna:
    - bonus/malus economico [-1.0, +1.0]
    - moltiplicatore medio pagato dalla squadra

    Il confronto usa il moltiplicatore mediano osservato nell'asta, non
    'listino - prezzo pagato', che in un fanta a 12 penalizzerebbe quasi tutti.
    """
    market_ratios = []
    for roster in all_rosters:
        player = roster.get("players") or {}
        list_price = float(player.get("list_price") or 0)
        paid = float(roster.get("purchase_price") or 0)
        if list_price > 0 and paid > 0:
            market_ratios.append(paid / list_price)

    market_multiplier = (
        float(pd.Series(market_ratios).median())
        if market_ratios
        else DEFAULT_AUCTION_MULTIPLIER
    )

    team_ratios = []
    for purchase in purchases:
        player = purchase.get("players") or {}
        list_price = float(player.get("list_price") or 0)
        paid = float(purchase.get("purchase_price") or 0)
        if list_price > 0 and paid > 0:
            team_ratios.append(paid / list_price)

    if not team_ratios:
        return 0.0, 0.0

    team_multiplier = sum(team_ratios) / len(team_ratios)

    # Se paghi meno del mercato hai bonus; se paghi più del mercato hai malus.
    relative = market_multiplier / max(team_multiplier, 0.01)
    economic_bonus = (relative - 1.0) * 2.5
    economic_bonus = max(-1.0, min(1.0, economic_bonus))

    return round(economic_bonus, 2), round(team_multiplier, 2)


def calculate_auction_grades(
    teams: list[dict[str, Any]],
    state: AuctionState,
    ratings: dict[str, float],
) -> pd.DataFrame:
    grades = []

    all_rosters = [
        purchase
        for purchases in state.team_purchases_map.values()
        for purchase in purchases
    ]

    for team in teams:
        name = team["name"]
        players = state.team_players_map[name]
        purchases = state.team_purchases_map[name]

        if not players:
            grades.append(
                {
                    "Squadra": name,
                    "Voto Asta": 0.0,
                    "Rating Rosa": 0.0,
                    "TOP (>=9)": 0,
                    "Moltiplicatore Pagato": 0.0,
                    "Efficienza Mercato": 0.0,
                    "Criticità Rilevate": 0,
                }
            )
            continue

        player_scores = [
            calculate_player_rating(
                player,
                st.session_state.preferred_players,
                load_custom_modifiers(),
                build_current_goalkeeper_ranking(state),
            )
            for player in players
        ]

        top_count = sum(score >= 9.0 for score in player_scores)

        alerts = build_team_alerts(players, len(players))
        criticality = len(alerts)

        economic_bonus, team_multiplier = calculate_market_efficiency(
            purchases,
            all_rosters,
        )

        # Il cuore del voto è la qualità della rosa.
        # L'economia può spostare il voto, ma non schiacciare tutte le squadre.
        quality = ratings[name]

        # Un numero elevato di TOP ha un ulteriore piccolo premio nel voto asta.
        top_bonus = min(0.50, top_count * 0.07)

        # Criticità strategiche restano rilevanti, ma non dominanti.
        risk_penalty = min(0.80, criticality * 0.18)

        grade = (
            quality * 0.88
            + economic_bonus * 0.65
            + top_bonus
            - risk_penalty
        )

        # Piccola espansione finale per rendere più leggibile la classifica.
        grade = 6.4 + (grade - 6.4) * 1.12
        grade = round(max(3.5, min(9.7, grade)), 1)

        grades.append(
            {
                "Squadra": name,
                "Voto Asta": grade,
                "Rating Rosa": round(quality, 1),
                "TOP (>=9)": top_count,
                "Moltiplicatore Pagato": team_multiplier,
                "Efficienza Mercato": economic_bonus,
                "Criticità Rilevate": criticality,
            }
        )

    return (
        pd.DataFrame(grades)
        .sort_values("Voto Asta", ascending=False)
        .reset_index(drop=True)
        .rename_axis("Posizione")
    )


def render_rosters_tab(
    teams: list[dict[str, Any]],
    teams_df: pd.DataFrame,
    rosters: list[dict[str, Any]],
    state: AuctionState,
    ratings: dict[str, float],
) -> None:
    st.subheader("📋 Tutte le Rose & Pagelle Post-Asta")
    st.markdown(
        "In questa sezione puoi visionare tutte le rose completate e "
        "l'**Analisi Voto Asta** basata su ranking, risparmio/overpaying "
        "sui listini e criticità complessive."
    )

    if not rosters:
        st.info("Nessun giocatore ancora acquistato in questa sessione d'asta.")
        return

    df_rosters = build_roster_dataframe(
        rosters,
        st.session_state.preferred_players,
    )

    team_names = teams_df["name"].tolist()
    filter_options = ["Tutte"] + team_names

    selected_filter = st.selectbox(
        "Filtra per Squadra",
        filter_options,
        index=default_team_index(filter_options),
        key="table_team_filter_tab2",
    )

    display_df = df_rosters.copy()
    if selected_filter != "Tutte":
        display_df = display_df[
            display_df["Squadra"] == selected_filter
        ]

    edited_df = st.data_editor(
        display_df,
        column_config={
            "_player_id": None,
            "Moltiplicatore Asta": st.column_config.NumberColumn(
                "Moltiplicatore Asta",
                format="x%.2f",
            ),
            "⭐ Preferito": st.column_config.CheckboxColumn(
                "⭐ Preferito",
                help="Dai un bonus di rating al giocatore.",
                default=False,
            ),
        },
        use_container_width=True,
        hide_index=True,
    )

    for _, row in edited_df.iterrows():
        player_id = row["_player_id"]
        if row["⭐ Preferito"]:
            st.session_state.preferred_players.add(player_id)
        else:
            st.session_state.preferred_players.discard(player_id)

    st.divider()
    st.subheader("🏆 Classifica e Voto Asta per Squadra")
    st.markdown(
        "Il voto dell'asta privilegia la **qualità reale della rosa**: "
        "i giocatori TOP pesano più degli altri. La gestione economica viene "
        "valutata rispetto ai prezzi realmente osservati nell'asta, mentre "
        "le criticità strategiche applicano penalità moderate."
    )

    grades_df = calculate_auction_grades(
        teams,
        state,
        ratings,
    )
    st.dataframe(
        grades_df,
        use_container_width=True,
    )


# ============================================================
# TAB 3 — TUTTI I GIOCATORI / RATING
# ============================================================

def render_all_players_tab() -> None:
    st.subheader("⭐️ Tutti i Giocatori — Rating Dettagliato")
    st.caption(
        "Il rating combina statistiche stagionali, listino, titolarità, "
        "modificatore squadra, rigoristi, rischio cartellini, rookie e preferiti. "
        "Per i portieri, il modificatore difensivo è sostituito dal criterio "
        "gol subiti: 1ª squadra +1.0, 2ª 0.0, 3ª -1.0."
    )

    all_players = load_players()
    custom_modifiers = load_custom_modifiers()
    if not all_players:
        st.info("Nessun giocatore trovato nel database.")
        return

    rows = []
    bought_ids = set()
    for roster in load_rosters():
        player = roster.get("players")
        if player and player.get("id") is not None:
            bought_ids.add(player["id"])

    for player in all_players:
        details = calculate_player_rating_detailed(
            player,
            st.session_state.preferred_players,
            custom_modifiers,
            ALL_GOALKEEPER_RANKING,
        )
        rows.append(
            {
                "⭐ Preferito": player["id"] in st.session_state.preferred_players,
                "Giocatore": player.get("name", ""),
                "Ruolo": player.get("role", ""),
                "Rating ⭐️": details["final_rating"],
                "Moltiplicatore ruolo": details.get("role_multiplier", 1.0),
                "Rating pre-calibrazione": details.get("raw_rating", details["final_rating"]),
                "Base/Fantamedia": details["base"],
                "Mod Squadra": details["team_mod"],
                "Mod. Portiere": details.get("goalkeeper_mod", 0.0),
                "Pos. Difesa": details.get("goalkeeper_rank"),
                "Titolarità": details["tit"],
                "Rigorista": details["rig"],
                "Cartellini": details["cart"],
                "Rookie": details["rook"],
                "Bonus/Malus manuale": details["custom_label"],
                "Mod. manuale": details["custom_mod"],
                "Gol": details["g"],
                "Ass": details["a"],
                "Presenze": details["m"],
                "Club": player.get("team_nfl", ""),
                "Listino": player.get("list_price", 0),
                "Stato": "Acquistato" if player["id"] in bought_ids else "Libero",
                "_player_id": player["id"],
            }
        )

    df = pd.DataFrame(rows)

    col1, col2, col3 = st.columns(3)
    with col1:
        role_filter = st.selectbox(
            "Filtra per Ruolo",
            ["Tutti", "P", "D", "C", "A"],
            key="tab3_role_filter",
        )
    with col2:
        status_filter = st.selectbox(
            "Filtra per Stato",
            ["Tutti", "Libero", "Acquistato"],
            key="tab3_status_filter",
        )
    with col3:
        search_name = st.text_input(
            "Cerca Giocatore",
            key="tab3_search_name",
        )

    filtered = df.copy()
    if role_filter != "Tutti":
        filtered = filtered[filtered["Ruolo"] == role_filter]
    if status_filter != "Tutti":
        filtered = filtered[filtered["Stato"] == status_filter]
    if search_name:
        needle = re.escape(search_name)
        filtered = filtered[
            filtered["Giocatore"].astype(str).str.contains(
                needle,
                case=False,
                na=False,
                regex=True,
            )
        ]

    filtered = filtered.sort_values(
        ["Rating ⭐️", "Giocatore"],
        ascending=[False, True],
    )

    st.dataframe(
        filtered.drop(columns=["_player_id"]),
        use_container_width=True,
        hide_index=True,
        column_config={
            "⭐ Preferito": st.column_config.CheckboxColumn(
                "⭐ Preferito",
                help="Aggiunge +0.5 al rating del giocatore.",
            ),
            "Rating ⭐️": st.column_config.NumberColumn(
                "Rating ⭐️",
                format="%.1f",
            ),
            "Moltiplicatore ruolo": st.column_config.NumberColumn(
                "Moltiplicatore ruolo",
                format="x%.3f",
            ),
            "Rating pre-calibrazione": st.column_config.NumberColumn(
                "Rating pre-calibrazione",
                format="%.1f",
            ),
            "Mod. manuale": st.column_config.NumberColumn(
                "Mod. manuale",
                format="%+.1f",
            ),
        },
    )


# ============================================================
# TAB 4 — GESTIONE BONUS / MALUS
# ============================================================

def render_player_modifiers_tab() -> None:
    st.subheader("🛠️ Gestione Bonus / Malus Giocatori")
    st.caption(
        "Le modifiche inserite qui vengono salvate in Supabase e "
        "si sommano al rating calcolato automaticamente. "
        "Il reset elimina solo la modifica manuale, senza toccare i dati originali del giocatore."
    )

    all_players = load_players()
    if not all_players:
        st.info("Nessun giocatore trovato nel database.")
        return

    modifiers = load_custom_modifiers()

    rows = []
    for player in all_players:
        current = modifiers.get(player["id"], {})
        rows.append(
            {
                "_player_id": player["id"],
                "Giocatore": player.get("name", ""),
                "Ruolo": player.get("role", ""),
                "Club": player.get("team_nfl", ""),
                "Modifica attuale": current.get(
                    "modifier_label",
                    "Nessuna modifica",
                ),
                "Valore": float(current.get("modifier_value") or 0.0),
            }
        )

    df = pd.DataFrame(rows)

    c1, c2, c3 = st.columns(3)
    with c1:
        role_filter = st.selectbox(
            "Ruolo",
            ["Tutti", "P", "D", "C", "A"],
            key="tab4_role_filter",
        )
    with c2:
        modifier_filter = st.selectbox(
            "Stato modifica",
            ["Tutti", "Con bonus/malus", "Senza modifica"],
            key="tab4_modifier_filter",
        )
    with c3:
        search = st.text_input(
            "Cerca giocatore",
            key="tab4_search",
        )

    filtered = df.copy()

    if role_filter != "Tutti":
        filtered = filtered[filtered["Ruolo"] == role_filter]

    if modifier_filter == "Con bonus/malus":
        filtered = filtered[filtered["Valore"] != 0]
    elif modifier_filter == "Senza modifica":
        filtered = filtered[filtered["Valore"] == 0]

    if search:
        filtered = filtered[
            filtered["Giocatore"].astype(str).str.contains(
                re.escape(search),
                case=False,
                na=False,
                regex=True,
            )
        ]

    st.markdown("### Modifica singolo giocatore")

    if filtered.empty:
        st.info("Nessun giocatore corrisponde ai filtri.")
        return

    player_labels = {
        f"{row['Giocatore']} [{row['Ruolo']}] — {row['Club']}": row["_player_id"]
        for _, row in filtered.iterrows()
    }

    selected_label = st.selectbox(
        "Giocatore",
        list(player_labels),
        key="tab4_selected_player",
    )
    selected_id = player_labels[selected_label]

    current = modifiers.get(selected_id, {})
    current_label = current.get(
        "modifier_label",
        "Nessuna modifica",
    )

    modifier_options = list(CUSTOM_MODIFIERS)
    current_index = (
        modifier_options.index(current_label)
        if current_label in modifier_options
        else 0
    )

    selected_modifier = st.selectbox(
        "Bonus / Malus",
        modifier_options,
        index=current_index,
        key=f"tab4_modifier_{selected_id}",
        help=(
            "La modifica viene aggiunta al rating. "
            "Esempio: se Audero è indicato come Titolare ma tu ritieni "
            "che sia in ballottaggio, seleziona 'Ballottaggio (-0.3)'."
        ),
    )

    player = next(
        player for player in all_players
        if player["id"] == selected_id
    )

    base_details = calculate_player_rating_detailed(
        player,
        st.session_state.preferred_players,
        modifiers,
    )
    new_value = CUSTOM_MODIFIERS[selected_modifier]["value"]
    current_rating = base_details["final_rating"]
    # Il rating attuale include già la modifica esistente.
    rating_without_current_custom = current_rating - float(
        current.get("modifier_value") or 0.0
    )
    preview_rating = round(
        max(
            1.0,
            min(10.0, rating_without_current_custom + new_value),
        ),
        1,
    )

    p1, p2, p3 = st.columns(3)
    with p1:
        st.metric("Rating senza modifica manuale", f"{rating_without_current_custom:.1f}")
    with p2:
        st.metric("Modifica scelta", f"{new_value:+.1f}")
    with p3:
        st.metric("Rating finale previsto", f"{preview_rating:.1f}")

    b1, b2 = st.columns(2)

    with b1:
        if st.button(
            "💾 Salva bonus/malus",
            type="primary",
            use_container_width=True,
        ):
            ok, error = save_custom_modifier(
                selected_id,
                selected_modifier,
            )
            if ok:
                st.success(
                    f"Modifica salvata per **{player['name']}**."
                )
                invalidate_data_cache()
                st.rerun()
            else:
                st.error(
                    "Impossibile salvare la modifica. "
                    "Controlla che la tabella Supabase "
                    f"`{CUSTOM_MODIFIER_TABLE}` esista.\n\n{error}"
                )

    with b2:
        if st.button(
            "♻️ Reset modifica giocatore",
            use_container_width=True,
        ):
            ok, error = reset_custom_modifier(selected_id)
            if ok:
                st.success(
                    f"Modifica rimossa da **{player['name']}**."
                )
                invalidate_data_cache()
                st.rerun()
            else:
                st.error(f"Impossibile effettuare il reset: {error}")

    st.divider()
    st.markdown("### 📋 Modifiche attualmente salvate")

    active = df[df["Valore"] != 0].copy()
    if active.empty:
        st.info("Nessun bonus/malus personalizzato salvato.")
    else:
        st.dataframe(
            active.drop(columns=["_player_id"]),
            use_container_width=True,
            hide_index=True,
            column_config={
                "Valore": st.column_config.NumberColumn(
                    "Valore",
                    format="%+.1f",
                ),
            },
        )

    with st.expander("⚠️ Reset di tutte le modifiche manuali"):
        st.warning(
            "Cancella tutti i bonus/malus personalizzati della tabella. "
            "Non modifica i dati originali dei giocatori."
        )
        if st.button(
            "🗑️ Cancella TUTTI i bonus/malus",
            type="secondary",
            key="tab4_reset_all",
        ):
            try:
                saved = (
                    supabase.table(CUSTOM_MODIFIER_TABLE)
                    .select("player_id")
                    .execute()
                    .data
                )
                for row in saved:
                    (
                        supabase.table(CUSTOM_MODIFIER_TABLE)
                        .delete()
                        .eq("player_id", row["player_id"])
                        .execute()
                    )
                invalidate_data_cache()
                st.success("Tutte le modifiche manuali sono state cancellate.")
                st.rerun()
            except Exception as exc:
                st.error(
                    f"Reset globale non riuscito: {exc}"
                )


# ============================================================
# TAB 1 — VALUTAZIONE E ROSA RCD ESCANYOL
# ============================================================

def render_my_team_evaluation(
    teams_df: pd.DataFrame,
    state: AuctionState,
    ratings: dict[str, float],
    rosters: list[dict[str, Any]],
) -> None:
    """Valuta RCD Escanyol in modo progressivo seguendo il draft PDCA."""
    team_name, players, purchases = get_my_team_players_and_purchases(state)
    if team_name is None or not players:
        # A rosa vuota non mostriamo valutazioni generiche: l'utente ha chiesto
        # che la strategia inizi dal primo acquisto dei portieri.
        return

    team_row = teams_df[teams_df["name"] == team_name]
    bought = len(players)
    remaining = int(team_row.iloc[0]["remaining_budget"]) if not team_row.empty else 0
    initial = int(team_row.iloc[0]["initial_budget"]) if not team_row.empty else 0
    spent = sum(int(p.get("purchase_price") or 0) for p in purchases)
    listino = sum(int((p.get("players") or {}).get("list_price") or 1) for p in purchases)
    slots_left = max(0, TOTAL_SLOTS_PER_TEAM - bought)
    rating = ratings.get(team_name, 0.0)
    counts = state.team_role_totals.get(team_name, {})
    current_role = get_my_team_draft_role(state)

    grades = calculate_auction_grades(
        teams_df.to_dict("records"),
        state,
        ratings,
    )
    grade_row = grades[grades["Squadra"] == team_name]
    auction_grade = float(grade_row.iloc[0]["Voto Asta"]) if not grade_row.empty else 0.0

    phase, assessment, advice = build_draft_strategy_text(
        state,
        rosters,
        teams_df,
        ratings,
    )

    st.markdown("### 🧠 Valutazione progressiva RCD Escanyol")
    if phase:
        st.markdown(f"**{phase}**")

    c1, c2, c3, c4, c5 = st.columns(5)
    c1.metric("⭐ Rating Rosa", f"{rating:.1f}/10")
    c2.metric("🏆 Voto Asta", f"{auction_grade:.1f}/10")
    c3.metric("💰 Budget residuo", f"{remaining} cr")
    c4.metric("👥 Giocatori", f"{bought}/{TOTAL_SLOTS_PER_TEAM}")
    c5.metric("📊 Speso / Listino", f"{spent}/{listino} cr")

    role_text = " · ".join(
        f"**{role}** {counts.get(role, 0)}/{ROLE_LIMITS[role]}"
        for role in DRAFT_ORDER
    )
    st.markdown(role_text)

    if assessment:
        st.info(assessment)
    if advice:
        st.success(f"💡 **Consiglio:** {advice}")

    # Suggerimenti per il prossimo acquisto, limitati al ruolo attualmente draftato.
    if current_role:
        st.markdown(f"### 🎯 Prossimi obiettivi — {ROLE_NAMES[current_role]}")
        history = auction_history_ratios(rosters)
        if history:
            median_multiplier = float(pd.Series([h["ratio"] for h in history]).median())
            st.caption(
                f"📈 Mercato osservato finora: moltiplicatore mediano **x{median_multiplier:.2f}** "
                f"su {len(history)} acquisti con listino disponibile."
            )
        # Budget corrente salvato per la funzione di raccomandazione.
        st.session_state["my_team_budget"] = remaining

        recommendation_tier = st.selectbox(
            "🎯 Fascia dei giocatori consigliati",
            RECOMMENDATION_TIER_OPTIONS,
            index=RECOMMENDATION_TIER_OPTIONS.index(
                st.session_state.get("recommendation_tier", "TOP")
            ),
            key="recommendation_tier",
            help=(
                "TOP ≥ 9.0 · Prima Fascia 8.0–8.9 · "
                "Seconda Fascia 7.0–7.9 · Terza Fascia 6.5–6.9. "
                "Sotto 6.5 non vengono mai consigliati."
            ),
        )
        tier_min = RECOMMENDATION_TIERS[recommendation_tier]["min_rating"]
        tier_max = RECOMMENDATION_TIERS[recommendation_tier]["max_rating"]
        st.caption(
            f"Filtro: **{recommendation_tier}** · Rating "
            f"{tier_min:.1f}" + (f"–{tier_max:.1f}" if tier_max < 10 else "+") +
            ". Il costo viene usato per trovare il miglior affare dentro la fascia."
        )

        recommendations = build_next_player_recommendations(
            state,
            rosters,
            st.session_state.preferred_players,
            load_custom_modifiers(),
            current_role,
            limit=5,
        )
        if recommendations:
            best = recommendations[0]
            best_player = best["player"]
            best_details = best["details"]
            best_estimate = best["estimate"]
            st.success(
                f"🎯 **Miglior rapporto qualità/prezzo nella {recommendation_tier}:** {best_player.get('name', '')} "
                f"— Rating **{best_details['final_rating']:.1f}**, "
                f"listino **{int(best_player.get('list_price') or 0)} cr**, "
                f"stima asta **{best_estimate['estimated_price']} cr** "
                f"(x{best_estimate['multiplier']:.2f}) · "
                f"**{best.get('rating_per_10_cr', 0.0):.2f} rating / 10 cr**."
            )
            rec_rows = []
            for index, row in enumerate(recommendations, start=1):
                player = row["player"]
                details = row["details"]
                estimate = row["estimate"]
                rec_rows.append({
                    "#": index,
                    "Giocatore": player.get("name", ""),
                    "Fascia": row.get("tier", recommendation_tier),
                    "Rating": details["final_rating"],
                    "Listino": int(player.get("list_price") or 0),
                    "Moltiplicatore": f"x{estimate['multiplier']:.2f}",
                    "Stima asta": estimate["estimated_price"],
                    "Rating / 10 cr": row.get("rating_per_10_cr", 0.0),
                    "Valore Score": row.get("score", 0.0),
                    "Club": player.get("team_nfl", "—"),
                })
            st.dataframe(
                pd.DataFrame(rec_rows),
                use_container_width=True,
                hide_index=True,
                column_config={
                    "Rating": st.column_config.NumberColumn(format="%.1f"),
                    "Listino": st.column_config.NumberColumn(format="%d cr"),
                    "Stima asta": st.column_config.NumberColumn(format="%d cr"),
                    "Rating / 10 cr": st.column_config.NumberColumn(format="%.2f"),
                    "Valore Score": st.column_config.NumberColumn(format="%.2f"),
                },
            )
        else:
            st.caption("Non ci sono obiettivi compatibili disponibili per questo ruolo.")

    # Classifica portieri solo quando almeno un portiere è stato acquistato.
    ranking = build_current_goalkeeper_ranking(state)
    if counts.get("P", 0) > 0 and ranking:
        goalkeeper_rows = []
        for code, position in sorted(ranking.items(), key=lambda item: item[1]):
            goalkeeper_rows.append({
                "Pos.": position,
                "Squadra": code,
                "Gol subiti": GOALS_CONCEDED.get(code, 0),
                "Mod. P": GOALKEEPER_GOALS_CONCEDED_MODIFIERS.get(position, 0.0),
            })
        with st.expander("🧤 Strategia portieri / difese scelte"):
            st.dataframe(
                pd.DataFrame(goalkeeper_rows),
                use_container_width=True,
                hide_index=True,
                column_config={
                    "Mod. P": st.column_config.NumberColumn(format="%+.1f"),
                },
            )


def render_my_roster(
    state: AuctionState,
) -> None:
    """Mostra la rosa RCD Escanyol divisa P-D-C-A."""
    team_name = resolve_my_team_name(list(state.team_players_map))

    st.markdown("### 👕 Rosa RCD Escanyol")
    if team_name is None:
        st.warning(
            "⚠️ La squadra **RCD Escanyol** non è presente tra le squadre configurate."
        )
        return

    players = state.team_players_map.get(team_name, [])
    if not players:
        st.info("La rosa è ancora vuota.")
        return

    custom_modifiers = load_custom_modifiers()
    goalkeeper_ranking = build_current_goalkeeper_ranking(state)
    purchases = state.team_purchases_map.get(team_name, [])
    purchase_by_player = {
        purchase.get("players", {}).get("id"): purchase
        for purchase in purchases
        if purchase.get("players")
    }

    # In build_auction_state players e purchases provengono dalla stessa query,
    # quindi usiamo anche la posizione per sicurezza nel caso l'id non sia presente.
    rows_by_role = {role: [] for role in ["P", "D", "C", "A"]}
    for player in players:
        details = calculate_player_rating_detailed(
            player,
            st.session_state.preferred_players,
            custom_modifiers,
            goalkeeper_ranking,
        )
        purchase = purchase_by_player.get(player.get("id"), {})
        manual_value = details.get("custom_mod", 0.0)
        manual_label = details.get("custom_label", "Nessuna modifica")
        bonus_malus = (
            f"{manual_label} ({manual_value:+.1f})"
            if manual_value
            else "—"
        )
        rows_by_role.setdefault(player.get("role", "D"), []).append(
            {
                "Nome": player.get("name", ""),
                "Rating": details["final_rating"],
                "Squadra": player.get("team_nfl", "—"),
                "Crediti Spesi": int(purchase.get("purchase_price") or 0),
                "Crediti Dichiarati": int(player.get("list_price") or 0),
                "Moltiplicatore Asta": round(
                    int(purchase.get("purchase_price") or 0) / max(1, int(player.get("list_price") or 0)),
                    2,
                ),
                "Bonus/Malus": bonus_malus,
                "_sort_rating": details["final_rating"],
            }
        )

    role_titles = {
        "P": "🧤 Portieri",
        "D": "🛡️ Difensori",
        "C": "🎯 Centrocampisti",
        "A": "⚡ Attaccanti",
    }

    for role in ["P", "D", "C", "A"]:
        role_rows = sorted(
            rows_by_role.get(role, []),
            key=lambda row: (-row["_sort_rating"], row["Nome"]),
        )
        st.markdown(f"#### {role_titles[role]} ({len(role_rows)}/{ROLE_LIMITS[role]})")
        if not role_rows:
            st.caption("Nessun giocatore acquistato in questo ruolo.")
            continue

        display = pd.DataFrame(role_rows).drop(columns=["_sort_rating"])
        st.dataframe(
            display,
            use_container_width=True,
            hide_index=True,
            column_config={
                "Rating": st.column_config.NumberColumn(format="%.1f"),
                "Crediti Spesi": st.column_config.NumberColumn(format="%d cr"),
                "Crediti Dichiarati": st.column_config.NumberColumn(format="%d cr"),
                "Moltiplicatore Asta": st.column_config.NumberColumn(format="x%.2f"),
            },
        )


# ============================================================
# MAIN
# ============================================================

def main() -> None:
    st.title("⚽ RCD Escanyol - Live Auction Assistant")

    teams = load_teams()
    rosters = load_rosters()

    teams_df = pd.DataFrame(teams)
    state = build_auction_state(teams, rosters)

    if "preferred_players" not in st.session_state:
        st.session_state.preferred_players = set()

    preferred_players = st.session_state.preferred_players
    custom_modifiers = load_custom_modifiers()
    goalkeeper_ranking = build_current_goalkeeper_ranking(state)
    ratings = calculate_team_ratings(
        state,
        preferred_players,
        custom_modifiers,
        goalkeeper_ranking,
    )

    completed_roles = calculate_completed_roles(state)
    auction_finished = is_auction_finished(state)


    tab1, tab2, tab3, tab4 = st.tabs(
        [
            "🎯 Live Asta",
            "📋 Rose & Analisi",
            "⭐️ Tutti i Giocatori (Rating)",
            "🛠️ Bonus / Malus",
        ]
    )

    with tab1:
        st.subheader("🎯 Assegnazione Guidata Giocatore")

        refresh_col, _ = st.columns([1, 5])
        with refresh_col:
            if st.button("🔄 Aggiorna dati", key="refresh_live_data"):
                invalidate_data_cache()
                st.rerun()

        # Mostrato dopo il rerun dell'acquisto.
        render_pending_purchase_banner()

        resolved_my_team = resolve_my_team_name(teams_df["name"].tolist())
        if resolved_my_team and resolved_my_team != "RCD Escanyol":
            st.caption(
                f"ℹ️ RCD Escanyol collegata alla squadra Supabase **{resolved_my_team}**."
            )

        if auction_finished:
            st.success(
                "🎉 **ASTA CONCLUSA!** Tutte le squadre hanno completato "
                "le proprie rose."
            )
            current_role = "ALL"
        else:
            current_role = "ALL"

        # Il pannello contiene tutti e 5 i dropdown/controlli sulla stessa riga.
        my_team_name = get_my_team_name_from_state(state)
        my_team_row = teams_df[teams_df["name"] == my_team_name] if my_team_name else pd.DataFrame()
        st.session_state["my_team_budget"] = int(my_team_row.iloc[0]["remaining_budget"]) if not my_team_row.empty else 0

        draft_role = get_my_team_draft_role(state)
        if draft_role:
            draft_label = role_label(draft_role)
            valid_role_labels = [
                label for label, role in ROLE_LABELS.items()
                if role == "ALL" or role == draft_role or (
                    role in DRAFT_ORDER and state.team_role_totals.get(my_team_name or "", {}).get(role, 0) < ROLE_LIMITS[role]
                )
            ]
            if st.session_state.get("main_role_select") not in valid_role_labels:
                st.session_state["main_role_select"] = draft_label
            current_role = draft_role
        else:
            current_role = "ALL"

        current_role = render_manual_purchase(
            teams_df,
            state,
            current_role,
            rosters,
        )

        render_top5(
            current_role,
            state.bought_player_ids,
            preferred_players,
            state,
        )

        render_team_analysis(
            teams_df,
            state,
            ratings,
        )

        render_admin_tools(
            teams_df,
            state,
        )

        resolved_my_team = resolve_my_team_name(teams_df["name"].tolist())
        if resolved_my_team:
            db_team_count = sum(
                1 for roster in rosters
                if roster.get("teams", {}).get("name") == resolved_my_team
                and roster.get("players")
            )
            if db_team_count != state.team_total_bought.get(resolved_my_team, 0):
                st.warning(
                    "⚠️ Incoerenza nei dati caricati: "
                    f"Supabase contiene {db_team_count} giocatori per **{resolved_my_team}**, "
                    f"ma lo stato dell'asta ne ha caricati {state.team_total_bought.get(resolved_my_team, 0)}. "
                    "La query delle rose è stata resa esplicita tramite team_id/player_id per evitare questo problema."
                )

        render_my_team_evaluation(
            teams_df,
            state,
            ratings,
            rosters,
        )

        render_my_roster(state)

    with tab2:
        render_team_overview(
            teams_df,
            state,
            ratings,
        )
        st.divider()
        render_rosters_tab(
            teams,
            teams_df,
            rosters,
            state,
            ratings,
        )

    with tab3:
        render_all_players_tab()

    with tab4:
        render_player_modifiers_tab()


if __name__ == "__main__":
    main()
