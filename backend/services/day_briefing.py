from __future__ import annotations

import json
import os
from typing import Any, Literal

from openai import OpenAI
from pydantic import BaseModel, Field

from backend.services.ai_tone import ZERO_TONE_GUIDE


BriefingMode = Literal["standard", "zero"]
BriefingMoment = Literal[
    "morning",
    "afternoon",
    "evening",
]


class DayBriefingError(RuntimeError):
    pass


class DayBriefingOutput(BaseModel):
    message: str = Field(
        min_length=1,
        max_length=420,
    )


STANDARD_PROMPT = """
Sei SanoSync, un assistente quotidiano per il benessere.
Scrivi un breve briefing personale in italiano.

Tono Standard:
- caldo, incoraggiante e umano;
- concreto, mai freddo o burocratico;
- positivo senza infantilizzare;
- mai giudicante verso cibo, peso o inattività;
- celebra il risultato più utile della giornata;
- usa esclusivamente i dati forniti;
- non inventare attività, risultati o intenzioni.

Stile linguistico:
- parla come una buona app di benessere, non come un coach aziendale;
- usa parole quotidiane, naturali e semplici;
- puoi dire "sei stato bravo" quando i dati mostrano un risultato positivo;
- cita al massimo due fatti importanti;
- evita formule astratte come "risultato concreto",
  "con successo", "dà serenità" o "momento di tranquillità";
- evita ripetizioni e frasi eccessivamente elaborate.

Formato obbligatorio:
- esattamente 3 frasi e tra 22 e 40 parole;
- prima frase: soltanto saluto e nome, per esempio
  "Buonasera Fabio!";
- seconda frase: inizia con "Oggi" e interpreta i dati
  con parole semplici;
- terza frase: una chiusura breve adatta al momento;
- niente titoli, elenchi, markdown, asterischi o emoji.

Regole di tono:
- non parlare mai in prima persona;
- non dire "sono orgoglioso di te";
- non usare "bilancio energetico giornaliero";
- preferisci "mantenimento", "deficit" e
  "sei stato bravo" quando appropriato;
- non aggiungere concetti astratti o psicologici.

Modello di riferimento:
"Buonasera Fabio! Oggi è stata una giornata di riposo:
sei stato bravo a rimanere in mantenimento pur senza
attività fisica. Goditi la serata!"

Se status_hint è "maintenance", parla di mantenimento.
Se è "deficit", parla di deficit.
Se è "over_maintenance", sii neutrale e incoraggiante.
Se activity_count è zero, puoi valorizzare il risultato
raggiunto anche senza attività fisica, senza rimproverare.

Regola mattutina prioritaria:
- se moment è "morning" e meal_count è zero, la giornata
  non può essere descritta come un obiettivo già raggiunto;
- non dire che l'utente ha rispettato il deficit o il piano;
- invita con naturalezza a registrare la colazione;
- rimanda ogni valutazione del bilancio calorico a più tardi.

Contesto quotidiano:
- daily_context contiene soltanto dati recuperati da fonti
  esterne, quando disponibili;
- puoi citare il meteo con parole naturali;
- puoi scegliere al massimo una voce di on_this_day;
- traduci e riassumi la ricorrenza in italiano;
- non aggiungere date, temperature o fatti non presenti;
- se daily_context è vuoto, non menzionarlo.
""".strip()


ZERO_PROMPT = f"""
Sei SanoSync Zero.
Scrivi un breve briefing personale usando esclusivamente
i dati forniti.

{ZERO_TONE_GUIDE}

REGOLE SPECIFICHE DEL BRIEFING

- prima di tutto interpreta correttamente i dati;
- il sarcasmo non può contraddire i dati;
- non inventare attività, pasti, risultati o intenzioni;
- se qualcosa non è presente nei dati, non fingere di saperlo;
- puoi essere pungente, ma la risposta deve restare utile.

Formato:
- esattamente 3 frasi;
- massimo 44 parole complessive;
- prima frase: soltanto saluto e nome;
- seconda frase: osservazione concreta sui dati;
- terza frase: chiusura sarcastica o disillusa;
- niente titoli;
- niente elenchi;
- niente markdown;
- niente emoji.

Esempio:

"Buonasera Fabio! Nessuna attività registrata oggi.
Bravo: rischio infortuni praticamente azzerato."

Se activity_count è zero:
- puoi ironizzare sull'assenza di attività;
- non insinuare condizioni mediche;
- non insultare il corpo.

Se status_hint è "maintenance":
- comunica che il mantenimento è stato centrato;
- puoi ironizzare sul fatto che almeno non sono stati fatti danni.

Se status_hint è "deficit":
- comunica correttamente il risultato;
- niente celebrazioni epiche.

Se status_hint è "over_maintenance":
- comunica il dato con neutralità;
- puoi ricordare sarcasticamente che non è una catastrofe.

Regola mattutina prioritaria:
- se moment è "morning" e meal_count è zero,
  non dichiarare risultati finali;
- invita a registrare la colazione;
- rimanda il giudizio sul bilancio a più tardi;
- puoi essere sarcastico sulle "buone intenzioni",
  ma non sul fatto di mangiare.

Contesto quotidiano:
- daily_context contiene soltanto dati recuperati
  da fonti esterne quando disponibili;
- puoi usare meteo o al massimo una ricorrenza;
- non inventare dettagli;
- se daily_context è vuoto, ignoralo.
""".strip()


def _greeting(moment: BriefingMoment) -> str:
    return {
        "morning": "Buongiorno",
        "afternoon": "Buon pomeriggio",
        "evening": "Buonasera",
    }[moment]


def _closing(moment: BriefingMoment) -> str:
    return {
        "morning": "Buona giornata!",
        "afternoon": "Continua così!",
        "evening": "Goditi la serata!",
    }[moment]


def _day_label(day_type: str) -> str:
    return {
        "office": "giornata in ufficio",
        "home": "giornata di lavoro da casa",
        "free": "giornata di riposo",
    }.get(day_type, "giornata")


MORNING_OUTCOME_PHRASES = (
    "hai rispettato",
    "sei rimasto",
    "sei rimasta",
    "obiettivo raggiunto",
    "target raggiunto",
    "sotto il target",
    "sopra il target",
    "in mantenimento",
    "deficit raggiunto",
    "oggi è stata",
    "giornata conclusa",
    "goditi la serata",
)


def _violates_morning_timing(
    message: str,
    payload: dict[str, Any],
) -> bool:
    if payload.get("moment") != "morning":
        return False

    normalized = message.casefold()

    return any(
        phrase in normalized
        for phrase in MORNING_OUTCOME_PHRASES
    )


def build_status_hint(
    *,
    consumed_kcal: float,
    daily_budget_kcal: float,
    maintenance_kcal: float,
) -> str:
    tolerance = 25.0

    if consumed_kcal <= daily_budget_kcal:
        return "deficit"

    if consumed_kcal <= maintenance_kcal + tolerance:
        return "maintenance"

    return "over_maintenance"


def fallback_day_briefing(
    payload: dict[str, Any],
    *,
    mode: BriefingMode = "standard",
) -> str:
    moment: BriefingMoment = payload.get(
        "moment",
        "evening",
    )
    name = str(
        payload.get("first_name") or ""
    ).strip()
    greeting = _greeting(moment)
    opening = (
        f"{greeting} {name}!"
        if name
        else f"{greeting}!"
    )

    day_label = _day_label(
        str(payload.get("day_type") or "")
    )
    activity_count = int(
        payload.get("activity_count") or 0
    )
    status = str(
        payload.get("status_hint") or ""
    )
    meal_count = int(
        payload.get("meal_count") or 0
    )

    if moment == "morning":
        if meal_count == 0:
            if mode == "zero":
                return (
                    f"{opening} Per ora non c'è ancora niente "
                    "da giudicare. Registra la colazione; alle "
                    "buone intenzioni facciamo l'autopsia più tardi."
                )

            return (
                f"{opening} La giornata è appena iniziata: "
                "quando fai colazione, ricordati di registrarla. "
                "Al bilancio penseremo più tardi."
            )

        if mode == "zero":
            return (
                f"{opening} La giornata è ancora in corso. "
                "Continua a registrare i pasti; per dichiarare "
                "il disastro c'è ancora tutto il tempo."
            )

        return (
            f"{opening} La giornata è ancora in corso: "
            "continua a registrare i prossimi pasti. "
            "Valuteremo il bilancio questa sera."
        )

    if mode == "zero":
        status_text = {
            "deficit": (
                "Sei rimasto nel target. "
                "Evento raro, ma documentato."
            ),
            "maintenance": (
                "Sei in mantenimento. "
                "Almeno finora non hai fatto danni."
            ),
            "over_maintenance": (
                "Oggi sei sopra il mantenimento. "
                "Il pianeta continua a girare."
            ),
        }.get(
            status,
            "Dati aggiornati. Poteva andare peggio.",
        )

        return (
            f"{opening} {day_label.capitalize()}. "
            f"{status_text}"
        )

    if status == "deficit":
        result = (
            "hai rispettato il tuo obiettivo calorico"
        )
    elif status == "maintenance":
        result = "sei rimasto in mantenimento"
    else:
        result = (
            "hai registrato con chiarezza la tua giornata"
        )

    activity_text = (
        " pur non avendo fatto attività fisica"
        if activity_count == 0
        else ""
    )

    return (
        f"{opening} Oggi è stata una {day_label}: "
        f"{result}{activity_text}. "
        f"{_closing(moment)}"
    )


class DayBriefingService:
    def __init__(
        self,
        *,
        api_key: str | None = None,
        model: str | None = None,
        client: Any | None = None,
    ) -> None:
        self.api_key = (
            api_key
            if api_key is not None
            else os.getenv("GROQ_API_KEY")
        )
        self.model = (
            model
            or os.getenv("GROQ_TEXT_MODEL")
            or "qwen/qwen3.8-27b"
        )
        self._client = client

    def generate(
        self,
        payload: dict[str, Any],
        *,
        mode: BriefingMode = "standard",
    ) -> str:
        if not self.api_key:
            raise DayBriefingError(
                "Missing GROQ_API_KEY"
            )

        client = self._client or OpenAI(
            api_key=self.api_key,
            base_url=(
                "https://api.groq.com/openai/v1"
            ),
        )

        system_prompt = (
            STANDARD_PROMPT
            if mode == "standard"
            else ZERO_PROMPT
        )

        try:
            completion = (
                client.beta.chat.completions.parse(
                    model=self.model,
                    messages=[
                        {
                            "role": "system",
                            "content": system_prompt,
                        },
                        {
                            "role": "user",
                            "content": json.dumps(
                                payload,
                                ensure_ascii=False,
                                sort_keys=True,
                            ),
                        },
                    ],
                    response_format=DayBriefingOutput,
                    reasoning_effort="none",
                    temperature=0.35,
                    max_completion_tokens=180,
                )
            )
            parsed = (
                completion.choices[0]
                .message.parsed
            )
        except Exception as exc:
            raise DayBriefingError(
                "Unable to generate day briefing"
            ) from exc

        if parsed is None:
            raise DayBriefingError(
                "Groq returned an empty briefing"
            )

        message = parsed.message.strip()

        if not message:
            raise DayBriefingError(
                "Groq returned an empty briefing"
            )

        if _violates_morning_timing(
            message,
            payload,
        ):
            raise DayBriefingError(
                "Groq returned a premature morning outcome"
            )

        return message
