from types import SimpleNamespace

from backend.services.groq_meal_vision_interpreter import (
    GroqMealVisionInterpretation,
    GroqMealVisionInterpreter,
)


class FakeCompletions:
    def parse(self, **kwargs):
        parsed = GroqMealVisionInterpretation(
            meal_type="Pranzo",
            items=[
                {
                    "name": "Pasta al pomodoro",
                    "quantity": 250,
                    "unit": "g",
                    "calories": 420,
                    "protein": 14,
                    "carbs": 72,
                    "fat": 9,
                    "estimated": True,
                    "uncertainty": "photo",
                    "notes": "Porzione stimata dalla foto",
                }
            ],
        )

        return SimpleNamespace(
            choices=[
                SimpleNamespace(
                    message=SimpleNamespace(
                        parsed=parsed
                    )
                )
            ]
        )


class FakeClient:
    def __init__(self):
        self.beta = SimpleNamespace(
            chat=SimpleNamespace(
                completions=FakeCompletions()
            )
        )


def test_vision_interpreter_returns_conversational_shape():
    result = GroqMealVisionInterpreter(
        api_key="test-key",
        client=FakeClient(),
    ).interpret(
        image_bytes=b"fake-image",
        mime_type="image/jpeg",
        meal_type="Pranzo",
    )

    assert result["meal_type"] == "Pranzo"
    assert len(result["items"]) == 1

    item = result["items"][0]
    assert item["name"] == "Pasta al pomodoro"
    assert item["quantity"] == 250
    assert item["unit"] == "g"
    assert item["calories"] == 420
