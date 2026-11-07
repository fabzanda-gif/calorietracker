from __future__ import annotations

import base64
import os
from typing import Any, Literal

from openai import OpenAI
from pydantic import BaseModel, Field


class NutritionLabelVisionError(
    RuntimeError
):
    pass


class NutritionLabelResult(BaseModel):
    name: str | None = None

    basis: Literal[
        "per_100g",
        "per_serving",
        "unknown",
    ] = "unknown"

    serving_size_g: float | None = Field(
        default=None,
        gt=0,
    )

    calories: float | None = Field(
        default=None,
        ge=0,
    )
    protein: float | None = Field(
        default=None,
        ge=0,
    )
    carbs: float | None = Field(
        default=None,
        ge=0,
    )
    fat: float | None = Field(
        default=None,
        ge=0,
    )

    confidence: Literal[
        "high",
        "medium",
        "low",
    ] = "low"

    notes: str | None = None


SYSTEM_PROMPT = """
Analizza una fotografia di un'etichetta nutrizionale.

Obiettivo:
estrarre SOLO i valori leggibili e restituire dati strutturati.

Regole fondamentali:
- non inventare valori;
- se un dato non è leggibile, usa null;
- identifica se i valori sono per 100 g oppure per porzione;
- se esistono entrambe le colonne, preferisci SEMPRE i valori per 100 g;
- se i dati sono solo per porzione, estrai anche serving_size_g se
  il peso della porzione è chiaramente indicato;
- non convertire da porzione a 100 g se serving_size_g non è leggibile;
- calories significa kcal, non kJ;
- protein, carbs e fat sono grammi;
- ignora sale, zuccheri, fibre e micronutrienti per questa versione;
- name deve essere il nome del prodotto solo se visibile o chiaramente
  leggibile nella foto;
- confidence valuta soltanto la qualità dell'estrazione.

Niente testo libero fuori dallo schema.
""".strip()


def normalize_to_100g(
    result: NutritionLabelResult,
) -> dict[str, Any]:
    data = result.model_dump()

    if result.basis == "per_100g":
        data["ready_for_form"] = all(
            value is not None
            for value in (
                result.calories,
                result.protein,
                result.carbs,
                result.fat,
            )
        )
        return data

    if (
        result.basis == "per_serving"
        and result.serving_size_g
        and result.serving_size_g > 0
    ):
        factor = 100 / result.serving_size_g

        for key in (
            "calories",
            "protein",
            "carbs",
            "fat",
        ):
            value = data.get(key)

            if value is not None:
                data[key] = round(
                    float(value) * factor,
                    2,
                )

        data["basis"] = "per_100g"
        data["ready_for_form"] = all(
            data.get(key) is not None
            for key in (
                "calories",
                "protein",
                "carbs",
                "fat",
            )
        )
        return data

    data["ready_for_form"] = False
    return data


class NutritionLabelVisionService:
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
            or os.getenv("GROQ_VISION_MODEL")
            or os.getenv("GROQ_TEXT_MODEL")
            or "qwen/qwen3.8-27b"
        )

        self._client = client

    def analyze(
        self,
        *,
        image_bytes: bytes,
        mime_type: str,
    ) -> dict[str, Any]:
        if not self.api_key:
            raise NutritionLabelVisionError(
                "Missing GROQ_API_KEY"
            )

        if not image_bytes:
            raise NutritionLabelVisionError(
                "Empty image"
            )

        if mime_type not in {
            "image/jpeg",
            "image/png",
            "image/webp",
        }:
            raise NutritionLabelVisionError(
                "Unsupported image type"
            )

        encoded = base64.b64encode(
            image_bytes
        ).decode("utf-8")

        data_url = (
            f"data:{mime_type};base64,{encoded}"
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
                            "content": [
                                {
                                    "type": "text",
                                    "text": (
                                        "Leggi questa "
                                        "etichetta "
                                        "nutrizionale."
                                    ),
                                },
                                {
                                    "type":
                                        "image_url",
                                    "image_url": {
                                        "url":
                                            data_url,
                                    },
                                },
                            ],
                        },
                    ],
                    response_format=(
                        NutritionLabelResult
                    ),
                    reasoning_effort="none",
                    max_completion_tokens=600,
                )
            )

            parsed = (
                completion
                .choices[0]
                .message.parsed
            )

        except Exception as exc:
            raise NutritionLabelVisionError(
                "Unable to analyze "
                "nutrition label"
            ) from exc

        if parsed is None:
            raise NutritionLabelVisionError(
                "Groq returned an empty result"
            )

        return normalize_to_100g(parsed)
