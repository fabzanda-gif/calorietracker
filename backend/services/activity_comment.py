from __future__ import annotations

import json
import os
from typing import Any, Literal

from openai import OpenAI
from pydantic import BaseModel, Field

from backend.services.ai_tone import (
    ZERO_TONE_GUIDE,
)


ActivityCommentMode = Literal[
    "standard",
    "zero",
]


class ActivityCommentError(RuntimeError):
    pass


class ActivityCommentOutput(BaseModel):
    comment: str = Field(
        min_length=1,
        max_length=280,
    )


STANDARD_PROMPT = """
Sei SanoSync, un assistente fitness e benessere.

Devi commentare UNA singola attività fisica
registrata dall'utente.

Tono Standard:
- positivo;
- competente;
- motivante;
- energico senza essere teatrale;
- simile a una buona app fitness premium;
- mai giudicante;
- mai paternalistico.

Regole:
- usa esclusivamente i dati forniti;
- non inventare performance, velocità o intensità;
- non diagnosticare condizioni fisiche;
- non fare confronti con altri utenti;
- non trasformare calorie o esercizio in punizione;
- se ci sono pochi dati, commenta soltanto
  ciò che è realmente disponibile;
- una buona attività può essere valorizzata,
  ma evita superlativi ingiustificati.

Formato:
- una o due frasi;
- massimo 34 parole;
- niente titoli;
- niente elenchi;
- niente markdown;
- niente emoji.

Esempi di registro:
"Una sessione solida: durata e continuità
aggiungono un buon contributo alla tua settimana."

"Attività registrata. Un altro tassello utile
per mantenere costante la tua routine."
""".strip()


ZERO_PROMPT = f"""
Sei SanoSync Zero.

Devi commentare UNA singola attività fisica
registrata dall'utente usando esclusivamente
i dati forniti.

{ZERO_TONE_GUIDE}

REGOLE SPECIFICHE

- prima comunica o interpreta correttamente
  ciò che è successo;
- poi, se funziona, aggiungi una battuta secca;
- non inventare intensità, velocità o risultati;
- non deridere corpo, peso, salute o capacità;
- non trasformare l'attività in compensazione
  per il cibo;
- niente motivazione da poster;
- niente dialetto.

Formato:
- una o due frasi;
- massimo 30 parole;
- niente titoli;
- niente elenchi;
- niente markdown;
- niente emoji.

Registro di riferimento:
"Attività registrata. Le prove esistono."

"Sessione completata. A quanto pare oggi
il divano ha perso."

"Buona durata. Non montarti la testa,
ma almeno è successo davvero."
""".strip()


def fallback_activity_comment(
    payload: dict[str, Any],
    *,
    mode: ActivityCommentMode = "standard",
) -> str:
    name = str(
        payload.get("activity_name")
        or "Attività"
    ).strip()

    duration = int(
        payload.get("duration_seconds")
        or 0
    )

    distance = float(
        payload.get("distance_meters")
        or 0
    )

    calories = int(
        payload.get("burned_calories")
        or 0
    )

    if mode == "zero":
        if duration >= 3600:
            return (
                f"{name}: più di un’ora registrata. "
                "A quanto pare oggi il divano ha perso."
            )

        if distance >= 5000:
            return (
                f"{name}: distanza rispettabile. "
                "Non farne subito una personalità."
            )

        if calories > 0:
            return (
                f"{name} registrata. "
                "Le prove, purtroppo, esistono."
            )

        return (
            f"{name} registrata. "
            "È successo davvero, a quanto pare."
        )

    if duration >= 3600:
        return (
            f"{name}: una sessione consistente "
            "che aggiunge volume utile alla tua routine."
        )

    if distance >= 5000:
        return (
            f"{name}: una buona dose di movimento "
            "e un contributo concreto alla tua routine."
        )

    if calories > 0:
        return (
            f"{name} registrata. "
            "Un altro tassello utile per mantenere "
            "costante la tua routine attiva."
        )

    return (
        f"{name} registrata. "
        "La continuità parte anche da qui."
    )


class ActivityCommentService:
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
        mode: ActivityCommentMode = "standard",
    ) -> str:
        if not self.api_key:
            raise ActivityCommentError(
                "Missing GROQ_API_KEY"
            )

        client = (
            self._client
            or OpenAI(
                api_key=self.api_key,
                base_url=(
                    "https://api.groq.com/"
                    "openai/v1"
                ),
            )
        )

        prompt = (
            ZERO_PROMPT
            if mode == "zero"
            else STANDARD_PROMPT
        )

        try:
            completion = (
                client.beta.chat.completions.parse(
                    model=self.model,
                    messages=[
                        {
                            "role": "system",
                            "content": prompt,
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
                    response_format=(
                        ActivityCommentOutput
                    ),
                    reasoning_effort="none",
                    temperature=0.45,
                    max_completion_tokens=120,
                )
            )

            parsed = (
                completion
                .choices[0]
                .message.parsed
            )

        except Exception as exc:
            raise ActivityCommentError(
                "Unable to generate "
                "activity comment"
            ) from exc

        if parsed is None:
            raise ActivityCommentError(
                "Groq returned an empty comment"
            )

        comment = parsed.comment.strip()

        if not comment:
            raise ActivityCommentError(
                "Groq returned an empty comment"
            )

        return comment
