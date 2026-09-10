from __future__ import annotations

import os
from typing import Any, Literal

from openai import OpenAI
from pydantic import BaseModel, Field


class GroqDayLogInterpreterError(RuntimeError):
    pass


class GroqDayLogIntent(BaseModel):
    kind: Literal["meal", "activity", "weight"]

    # Meal
    text: str | None = None
    meal_type: str | None = None

    # Activity
    activity_name: str | None = None
    activity_type: str | None = None
    duration_seconds: int | None = Field(
        default=None,
        ge=0,
    )
    distance_meters: float | None = Field(
        default=None,
        ge=0,
    )
    burned_calories: int | None = Field(
        default=None,
        ge=0,
    )

    # Weight
    weight_kg: float | None = Field(
        default=None,
        gt=0,
    )

    uncertainty: str | None = None


class GroqDayLogInterpretation(BaseModel):
    intents: list[GroqDayLogIntent]


class GroqDayLogInterpreter:
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

        configured_model = (
            model
            or os.getenv("GROQ_TEXT_MODEL")
        )
        # qwen3.6 was previously documented in .env.example, but it
        # does not support the structured-output request used here.
        # Transparently migrate that legacy setting to a production
        # model with documented structured-output support.
        if configured_model in {
            None,
            "",
            "qwen/qwen3.6-27b",
        }:
            configured_model = "openai/gpt-oss-20b"

        self.model = configured_model

        self._client = client

    def interpret(
        self,
        *,
        text: str,
        default_meal_type: str,
    ) -> dict[str, Any]:
        if not self.api_key:
            raise GroqDayLogInterpreterError(
                "Missing GROQ_API_KEY"
            )

        client = self._client or OpenAI(
            api_key=self.api_key,
            base_url="https://api.groq.com/openai/v1",
        )

        try:
            completion = client.beta.chat.completions.parse(
                model=self.model,
                messages=[
                    {
                        "role": "system",
                        "content": (
                            "Sei il parser di registrazione giornaliera "
                            "di SanoSync. Analizza il messaggio italiano "
                            "dell'utente e separalo in azioni indipendenti. "
                            "Le sole azioni consentite sono meal, activity "
                            "e weight. "
                            "\n\n"
                            "REGOLE PASTI: per kind='meal' inserisci in "
                            "'text' soltanto la parte del messaggio che "
                            "descrive quel pasto. meal_type deve essere "
                            "uno tra Colazione, Pranzo, Snack, Cena. "
                            "Se il tipo non è deducibile usa il tipo "
                            "predefinito fornito. Non stimare qui calorie "
                            "o nutrienti: verranno calcolati da un parser "
                            "nutrizionale dedicato. "
                            "\n\n"
                            "REGOLE ATTIVITA: riconosci soltanto attività "
                            "già svolte o in corso, non programmi futuri. "
                            "Estrai activity_name e activity_type. "
                            "Converti minuti/ore in duration_seconds e km "
                            "in distance_meters. Non inventare durata o "
                            "distanza mancanti. burned_calories deve essere "
                            "compilato SOLO se l'utente dichiara "
                            "esplicitamente le kcal bruciate; altrimenti "
                            "deve essere null. "
                            "\n\n"
                            "REGOLE PESO: usa kind='weight' soltanto quando "
                            "l'utente dichiara chiaramente il proprio peso "
                            "corporeo attuale. weight_kg deve essere il "
                            "valore in kg. "
                            "\n\n"
                            "Un messaggio può produrre più azioni. "
                            "Mantieni l'ordine in cui compaiono. "
                            "Non trasformare desideri, domande o piani "
                            "futuri in registrazioni. Se qualcosa è "
                            "ambiguo valorizza uncertainty."
                        ),
                    },
                    {
                        "role": "user",
                        "content": (
                            f"Tipo pasto predefinito: "
                            f"{default_meal_type}\n"
                            f"Messaggio: {text}"
                        ),
                    },
                ],
                response_format=GroqDayLogInterpretation,
                reasoning_effort="none",
                max_completion_tokens=1400,
            )
        except Exception as exc:
            raise GroqDayLogInterpreterError(
                "Unable to interpret daily log with Groq"
            ) from exc

        try:
            parsed = (
                completion
                .choices[0]
                .message
                .parsed
            )
        except (
            AttributeError,
            IndexError,
            TypeError,
        ) as exc:
            raise GroqDayLogInterpreterError(
                "Groq returned an invalid daily interpretation"
            ) from exc

        if parsed is None:
            raise GroqDayLogInterpreterError(
                "Groq returned an empty daily interpretation"
            )

        return parsed.model_dump()
