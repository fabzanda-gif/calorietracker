from __future__ import annotations

import base64
import os
from typing import Any

from openai import OpenAI
from pydantic import BaseModel


class GroqMealVisionInterpreterError(RuntimeError):
    pass


class GroqMealVisionItem(BaseModel):
    name: str
    quantity: float
    unit: str = "g"
    calories: float
    protein: float = 0
    carbs: float = 0
    fat: float = 0
    estimated: bool = True
    uncertainty: str | None = "photo"
    notes: str | None = None


class GroqMealVisionInterpretation(BaseModel):
    meal_type: str
    items: list[GroqMealVisionItem]


class GroqMealVisionInterpreter:
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
            or "qwen/qwen3.6-27b"
        )

        self._client = client

    def interpret(
        self,
        *,
        image_bytes: bytes,
        mime_type: str,
        meal_type: str,
    ) -> dict[str, Any]:
        if not self.api_key:
            raise GroqMealVisionInterpreterError(
                "Missing GROQ_API_KEY"
            )

        if not image_bytes:
            raise GroqMealVisionInterpreterError(
                "Empty image"
            )

        image_b64 = base64.b64encode(
            image_bytes
        ).decode("utf-8")
        data_url = (
            f"data:{mime_type};base64,{image_b64}"
        )

        client = self._client or OpenAI(
            api_key=self.api_key,
            base_url="https://api.groq.com/openai/v1",
        )

        prompt = (
            "Analizza la foto del pasto e restituisci "
            "una stima nutrizionale realistica. "
            "Ogni item deve rappresentare una quantità "
            "totale visibile nella foto. "
            "Usa grammi come unità quando possibile. "
            "Non inventare precisione per ingredienti "
            "non chiaramente visibili. "
            "Calories e macros devono riferirsi alla "
            "stessa quantità totale."
        )

        try:
            completion = client.beta.chat.completions.parse(
                model=self.model,
                messages=[
                    {
                        "role": "user",
                        "content": [
                            {
                                "type": "text",
                                "text": (
                                    f"Tipo pasto: {meal_type}\n"
                                    f"{prompt}"
                                ),
                            },
                            {
                                "type": "image_url",
                                "image_url": {
                                    "url": data_url,
                                },
                            },
                        ],
                    }
                ],
                response_format=GroqMealVisionInterpretation,
                reasoning_effort="none",
                max_completion_tokens=1200,
            )
        except Exception as exc:
            raise GroqMealVisionInterpreterError(
                "Unable to interpret meal photo with Groq"
            ) from exc

        try:
            parsed = completion.choices[0].message.parsed
        except (
            AttributeError,
            IndexError,
            TypeError,
        ) as exc:
            raise GroqMealVisionInterpreterError(
                "Groq returned an invalid photo interpretation"
            ) from exc

        if parsed is None:
            raise GroqMealVisionInterpreterError(
                "Groq returned an empty photo interpretation"
            )

        return parsed.model_dump()
