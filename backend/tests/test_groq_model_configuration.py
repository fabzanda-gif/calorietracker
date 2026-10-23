from backend.services.groq_day_log_interpreter import (
    GroqDayLogInterpreter,
)
from backend.services.groq_meal_interpreter import (
    GroqMealInterpreter,
)


def test_interpreters_default_to_production_structured_output_model(
    monkeypatch,
):
    monkeypatch.delenv("GROQ_TEXT_MODEL", raising=False)

    assert (
        GroqDayLogInterpreter(api_key="test").model
        == "openai/gpt-oss-20b"
    )
    assert (
        GroqMealInterpreter(api_key="test").model
        == "openai/gpt-oss-20b"
    )


def test_interpreters_migrate_legacy_qwen_36_setting(
    monkeypatch,
):
    monkeypatch.setenv(
        "GROQ_TEXT_MODEL",
        "qwen/qwen3.6-27b",
    )

    assert (
        GroqDayLogInterpreter(api_key="test").model
        == "openai/gpt-oss-20b"
    )
    assert (
        GroqMealInterpreter(api_key="test").model
        == "openai/gpt-oss-20b"
    )


def test_interpreters_preserve_explicit_supported_model():
    model = "qwen/qwen3.8-27b"

    assert (
        GroqDayLogInterpreter(
            api_key="test",
            model=model,
        ).model
        == model
    )
    assert (
        GroqMealInterpreter(
            api_key="test",
            model=model,
        ).model
        == model
    )
