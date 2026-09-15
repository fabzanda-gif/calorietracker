from __future__ import annotations

import os
from typing import Any, Literal

from openai import OpenAI
from pydantic import BaseModel, Field


class IngredientAIInterpreterError(RuntimeError):
    pass


MealSlot = Literal[
    "breakfast",
    "lunch",
    "snack",
    "dinner",
]

FoodKind = Literal[
    "ingredient",
    "product",
    "prepared_food",
]


class IngredientAIPreview(BaseModel):
    name: str | None = None

    calories_per_100g: float | None = Field(
        default=None,
        ge=0,
    )
    protein_per_100g: float | None = Field(
        default=None,
        ge=0,
    )
    carbs_per_100g: float | None = Field(
        default=None,
        ge=0,
    )
    fat_per_100g: float | None = Field(
        default=None,
        ge=0,
    )

    kind: FoodKind = "product"
    meal_slots: list[MealSlot] = Field(
        default_factory=list,
    )

    default_unit: str = "g"
    default_quantity: float | None = Field(
        default=None,
        gt=0,
    )
    grams_per_unit: float | None = Field(
        default=None,
        gt=0,
    )

    confidence: Literal[
        "high",
        "medium",
        "low",
    ] = "low"

    estimated: bool = True
    notes: str | None = None


SYSTEM_PROMPT = """
Sei l'assistente nutrizionale di SanoSync.

L'utente vuole creare un alimento nella propria libreria.
Trasforma la descrizione in una PROPOSTA modificabile.

Restituisci valori nutrizionali riferiti a 100 g.

Regole:
- name: nome breve e riconoscibile;
- se l'utente fornisce valori nutrizionali espliciti, usali;
- per prodotti comuni o branded puoi stimare valori plausibili solo
  quando hai sufficiente informazione;
- non fingere precisione: estimated=true quando i macro non derivano
  da dati esplicitamente forniti dall'utente;
- se non puoi stimare in modo ragionevole un macro, usa null;
- calories significa kcal;
- protein, carbs e fat sono grammi per 100 g;
- kind:
  ingredient = componente da cucina/ricetta;
  product = prodotto/alimento acquistato;
  prepared_food = pietanza o alimento già preparato;
- meal_slots suggerisce soltanto i momenti normalmente sensati;
- ingredienti puramente da cucina possono avere meal_slots=[];
- default_quantity è una porzione tipica solo quando sensata;
- grams_per_unit serve per pezzi/vasetti/porzioni quando il peso è noto
  o chiaramente espresso;
- confidence descrive quanto è affidabile la proposta;
- notes deve essere breve e spiegare soprattutto se i valori sono stimati.

Non salvare nulla. Restituisci soltanto lo schema.
""".strip()


class IngredientAIInterpreter:
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

    def interpret(
        self,
        *,
        text: str,
    ) -> dict[str, Any]:
        value = text.strip()

        if not value:
            raise IngredientAIInterpreterError(
                "Descrizione vuota"
            )

        if not self.api_key:
            raise IngredientAIInterpreterError(
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

        try:
            completion = (
                client.beta.chat.completions.parse(
                    model=self.model,
                    messages=[
                        {
                            "role": "system",
                            "content": SYSTEM_PROMPT,
                        },
                        {
                            "role": "user",
                            "content": value,
                        },
                    ],
                    response_format=IngredientAIPreview,
                    reasoning_effort="none",
                    max_completion_tokens=700,
                )
            )

            parsed = (
                completion
                .choices[0]
                .message.parsed
            )
        except Exception as exc:
            raise IngredientAIInterpreterError(
                "Impossibile interpretare l'alimento"
            ) from exc

        if parsed is None:
            raise IngredientAIInterpreterError(
                "Risposta AI vuota"
            )

        result = parsed.model_dump()

        result["ready_for_form"] = bool(
            result.get("name")
            and all(
                result.get(key) is not None
                for key in (
                    "calories_per_100g",
                    "protein_per_100g",
                    "carbs_per_100g",
                    "fat_per_100g",
                )
            )
        )

        return result
