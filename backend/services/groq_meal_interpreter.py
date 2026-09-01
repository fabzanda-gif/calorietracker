from __future__ import annotations

import os
from typing import Any

from openai import OpenAI
from pydantic import BaseModel


class GroqMealInterpreterError(RuntimeError):
    pass


class GroqMealItem(BaseModel):
    name: str
    quantity: float
    unit: str
    quantity_g: float
    calories: float
    protein: float = 0
    carbs: float = 0
    fat: float = 0
    estimated: bool = True
    uncertainty: str | None = None


class GroqMealInterpretation(BaseModel):
    meal_type: str
    items: list[GroqMealItem]


class GroqMealInterpreter:
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
            or "qwen/qwen3.6-27b"
        )

        self._client = client

    def interpret(
        self,
        *,
        text: str,
        meal_type: str,
    ) -> dict[str, Any]:
        if not self.api_key:
            raise GroqMealInterpreterError(
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
                            "Interpreta il pasto descritto dall'utente. "
                            "Restituisci alimenti e stime nutrizionali "
                            "realistiche. Non inventare precisione: se "
                            "una quantità non è esplicita, usa una stima "
                            "ragionevole e imposta uncertainty='quantity'. "
                            "Quantity, calories and macros must always refer "
                            "to the same total portion. Always estimate the "
                            "total weight in grams as quantity_g, even when "
                            "the user gives pieces or portions. Keep calories "
                            "consistent with the estimated macros and portion."
                        ),
                    },
                    {
                        "role": "user",
                        "content": (
                            f"Tipo pasto: {meal_type}\n"
                            f"Descrizione: {text}"
                        ),
                    },
                ],
                response_format=GroqMealInterpretation,
                reasoning_effort="none",
                max_completion_tokens=1200,
            )
        except Exception as exc:
            raise GroqMealInterpreterError(
                "Unable to interpret meal with Groq"
            ) from exc

        try:
            parsed = completion.choices[0].message.parsed
        except (AttributeError, IndexError, TypeError) as exc:
            raise GroqMealInterpreterError(
                "Groq returned an invalid interpretation"
            ) from exc

        if parsed is None:
            raise GroqMealInterpreterError(
                "Groq returned an empty interpretation"
            )

        return parsed.model_dump()
