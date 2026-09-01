from __future__ import annotations

import json
import os
from typing import Any, Literal

from openai import OpenAI
from pydantic import BaseModel, Field


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
""".strip()


ZERO_PROMPT = """
Sei SanoSync Zero. Scrivi un briefing personale in
italiano usando esclusivamente i dati forniti.

Tono Zero:
- cinico, asciutto, disincantato e provocatorio;
- ironico verso il piano, le aspettative e le scuse;
- scettico sulla continuità futura, senza negare i fatti;
- mai entusiasta e mai motivazionale;
- non insultare la persona, il corpo, il peso o il cibo;
- non umiliare e non scoraggiare comportamenti salutari;
- niente diagnosi, minacce o giudizi morali;
- non inventare dati.

Formato obbligatorio:
- 3 frasi e massimo 40 parole;
- prima frase: soltanto saluto e nome;
- seconda frase: osservazione secca sui dati;
- terza frase: battuta disincantata o sfida breve;
- niente markdown, asterischi o emoji.

Esempio di tono:
"Buonasera Fabio! Mantenimento centrato senza attività
fisica. Contro ogni previsione, il piano è ancora vivo.
Per oggi può bastare."
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

    if mode == "zero":
        status_text = {
            "deficit": "Sei rimasto nel target.",
            "maintenance": "Sei in mantenimento.",
            "over_maintenance": (
                "Oggi sei sopra il mantenimento."
            ),
        }.get(status, "Dati della giornata aggiornati.")

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

        return message
