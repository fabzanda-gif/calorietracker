import pytest

from backend.services.groq_meal_interpreter import (
    GroqMealInterpreter,
    GroqMealInterpreterError,
)


def test_missing_api_key_fails_cleanly(monkeypatch):
    monkeypatch.delenv("GROQ_API_KEY", raising=False)

    service = GroqMealInterpreter(
        api_key=None,
    )

    with pytest.raises(
        GroqMealInterpreterError,
        match="GROQ_API_KEY",
    ):
        service.interpret(
            text="Ho mangiato una mela",
            meal_type="Spuntino",
        )


def test_interpret_uses_xai_and_returns_structured_data():
    calls = {}

    class FakeCompletions:
        def parse(
            self,
            *,
            model,
            messages,
            response_format,
            reasoning_effort,
            max_completion_tokens,
        ):
            calls["model"] = model
            calls["messages"] = messages
            calls["response_format"] = response_format

            class Message:
                parsed = response_format(
                    meal_type="Pranzo",
                    items=[
                        {
                            "name": "Carbonara",
                            "quantity": 1,
                            "unit": "porzione",
                            "calories": 700,
                            "protein": 30,
                            "carbs": 80,
                            "fat": 28,
                            "estimated": True,
                            "uncertainty": None,
                        }
                    ],
                )

            class Choice:
                message = Message()

            class Completion:
                choices = [Choice()]

            return Completion()

    class FakeChat:
        completions = FakeCompletions()

    class FakeBeta:
        chat = FakeChat()

    class FakeClient:
        beta = FakeBeta()

    service = GroqMealInterpreter(
        api_key="fake-key",
        model="grok-test",
        client=FakeClient(),
    )

    result = service.interpret(
        text="Ho mangiato una carbonara",
        meal_type="Pranzo",
    )

    assert calls["model"] == "grok-test"

    assert result["meal_type"] == "Pranzo"
    assert result["items"][0]["name"] == "Carbonara"
    assert result["items"][0]["calories"] == 700.0


def test_prompt_preserves_requested_meal_type():
    calls = {}

    class FakeCompletions:
        def parse(
            self,
            *,
            model,
            messages,
            response_format,
            reasoning_effort,
            max_completion_tokens,
        ):
            calls["messages"] = messages

            class Message:
                parsed = response_format(
                    meal_type="Cena",
                    items=[],
                )

            class Choice:
                message = Message()

            class Completion:
                choices = [Choice()]

            return Completion()

    class FakeChat:
        completions = FakeCompletions()

    class FakeBeta:
        chat = FakeChat()

    class FakeClient:
        beta = FakeBeta()

    service = GroqMealInterpreter(
        api_key="fake-key",
        client=FakeClient(),
    )

    service.interpret(
        text="Ho mangiato qualcosa",
        meal_type="Cena",
    )

    joined = " ".join(
        str(message["content"])
        for message in calls["messages"]
    )

    assert "Cena" in joined


def test_prompt_requires_portion_nutrition_consistency():
    calls = {}

    class FakeCompletions:
        def parse(
            self,
            *,
            model,
            messages,
            response_format,
            reasoning_effort,
            max_completion_tokens,
        ):
            calls["messages"] = messages

            class Message:
                parsed = response_format(
                    meal_type="Pranzo",
                    items=[],
                )

            class Choice:
                message = Message()

            class Completion:
                choices = [Choice()]

            return Completion()

    class FakeChat:
        completions = FakeCompletions()

    class FakeBeta:
        chat = FakeChat()

    class FakeClient:
        beta = FakeBeta()

    service = GroqMealInterpreter(
        api_key="fake-key",
        client=FakeClient(),
    )

    service.interpret(
        text="Ho mangiato della pasta",
        meal_type="Pranzo",
    )

    system_prompt = calls["messages"][0]["content"]

    assert "same total portion" in system_prompt
    assert "consistent with the estimated macros" in system_prompt
