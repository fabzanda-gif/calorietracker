from __future__ import annotations

import os
from typing import Any, Literal

from openai import OpenAI
from pydantic import BaseModel, Field


class RecipeAIInterpreterError(RuntimeError):
    pass


Confidence = Literal[
    "high",
    "medium",
    "low",
]


class RecipeAIIngredient(BaseModel):
    name: str = Field(min_length=1)

    quantity: float = Field(gt=0)
    unit: str = Field(min_length=1)
    quantity_g: float = Field(gt=0)

    calories_per_100g: float = Field(ge=0)
    protein_per_100g: float = Field(ge=0)
    carbs_per_100g: float = Field(ge=0)
    fat_per_100g: float = Field(ge=0)

    confidence: Confidence = "low"
    estimated: bool = True
    notes: str | None = None


class RecipeAIInterpretation(BaseModel):
    name: str | None = None
    servings: float | None = Field(
        default=None,
        gt=0,
    )
    final_weight_g: float | None = Field(
        default=None,
        gt=0,
    )

    ingredients: list[RecipeAIIngredient] = Field(
        min_length=1,
    )


SYSTEM_PROMPT = """
Sei SanoSync AI e stai aiutando l'utente a creare una ricetta.

Devi trasformare il testo in una PREVIEW modificabile.
Non salvare nulla.

Regole:
- separa sempre i singoli ingredienti;
- non unire ingredienti diversi in una sola voce;
- mantieni quantity e unit vicini a quanto scritto dall'utente;
- quantity_g deve essere il peso in grammi usato nella ricetta;
- se l'utente usa pezzi, cucchiai, cucchiaini, confezioni o porzioni,
  stima quantity_g solo quando ragionevole;
- i valori nutrizionali devono essere SEMPRE riferiti a 100 g
  dell'ingrediente;
- calories_per_100g significa kcal per 100 g;
- protein_per_100g, carbs_per_100g e fat_per_100g sono grammi per 100 g;
- se i valori nutrizionali non sono esplicitamente forniti,
  usa stime realistiche e imposta estimated=true;
- confidence deve riflettere quanto è affidabile la stima;
- notes deve essere breve e indicare eventuali assunzioni importanti;
- final_weight_g rappresenta il peso FINALE della ricetta preparata:
  valorizzalo SOLO se l'utente lo indica esplicitamente;
- non dedurre final_weight_g dalla somma degli ingredienti;
- servings va valorizzato solo se il numero di porzioni è indicato
  chiaramente;
- name è il nome della ricetta, se ricavabile dal testo.

Esempio concettuale:
"Pollo al curry: 500 g pollo, 200 g riso, 20 g olio.
Peso finale 1100 g, 4 porzioni."

Deve produrre tre ingredienti distinti, final_weight_g=1100,
servings=4.

Restituisci soltanto lo schema richiesto.
""".strip()


class RecipeAIInterpreter:
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
    ) -> dict[str, Any]:
        value = text.strip()

        if not value:
            raise RecipeAIInterpreterError(
                "Descrizione ricetta vuota"
            )

        if not self.api_key:
            raise RecipeAIInterpreterError(
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
                    response_format=RecipeAIInterpretation,
                    reasoning_effort="low",
                    max_completion_tokens=1800,
                )
            )

            parsed = (
                completion
                .choices[0]
                .message.parsed
            )
        except Exception as exc:
            raise RecipeAIInterpreterError(
                "Impossibile interpretare la ricetta"
            ) from exc

        if parsed is None:
            raise RecipeAIInterpreterError(
                "Risposta AI vuota"
            )

        result = parsed.model_dump()
        ingredients = result["ingredients"]

        ingredient_weight_g = round(
            sum(
                float(item["quantity_g"])
                for item in ingredients
            ),
            2,
        )

        totals = {
            nutrient: round(
                sum(
                    float(item[f"{nutrient}_per_100g"])
                    * float(item["quantity_g"])
                    / 100
                    for item in ingredients
                ),
                2,
            )
            for nutrient in (
                "calories",
                "protein",
                "carbs",
                "fat",
            )
        }

        explicit_final_weight = result.get(
            "final_weight_g"
        )

        calculation_weight_g = (
            float(explicit_final_weight)
            if explicit_final_weight
            else ingredient_weight_g
        )

        per_100g = {
            nutrient: round(
                totals[nutrient]
                * 100
                / calculation_weight_g,
                2,
            )
            for nutrient in (
                "calories",
                "protein",
                "carbs",
                "fat",
            )
        }

        servings = result.get("servings")

        per_serving = (
            {
                nutrient: round(
                    totals[nutrient]
                    / float(servings),
                    2,
                )
                for nutrient in (
                    "calories",
                    "protein",
                    "carbs",
                    "fat",
                )
            }
            if servings
            else None
        )

        result.update(
            {
                "ingredient_weight_g":
                    ingredient_weight_g,
                "calculation_weight_g":
                    calculation_weight_g,
                "weight_source": (
                    "explicit_final_weight"
                    if explicit_final_weight
                    else "ingredients_sum"
                ),
                "totals": totals,
                "per_100g": per_100g,
                "per_serving": per_serving,
                "needs_final_weight_confirmation":
                    explicit_final_weight is None,
                "needs_review": any(
                    bool(item.get("estimated"))
                    or item.get("confidence") != "high"
                    for item in ingredients
                ),
                "requires_confirmation": True,
            }
        )

        return result
