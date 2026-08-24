from backend.services.insight_presentation import (
    InsightPresentationService,
)


service = InsightPresentationService()


def test_context_insight_becomes_ui_card():
    result = service.present(
        {
            "generated_for": "2026-09-01",
            "learned": [
                {
                    "kind": "day_context",
                    "weekday_name": "Tuesday",
                    "value": "Ufficio",
                    "confidence_level": "high",
                    "confidence": 1.0,
                    "evidence": {"observations": 4},
                }
            ],
            "learning": [],
        }
    )

    card = result["learned"][0]

    assert card["title"] == "Martedì → Ufficio"
    assert "Di solito" in card["text"]
    assert card["icon"] == "calendar"


def test_activity_insight_becomes_ui_card():
    result = service.present(
        {
            "learned": [
                {
                    "kind": "activity_plan",
                    "weekday_name": "Tuesday",
                    "value": "Attiva",
                    "confidence_level": "high",
                }
            ],
            "learning": [],
        }
    )

    card = result["learned"][0]

    assert card["title"] == "Martedì → Attiva"
    assert card["icon"] == "activity"


def test_meal_insight_keeps_context():
    result = service.present(
        {
            "learned": [
                {
                    "kind": "meal",
                    "weekday_name": "Tuesday",
                    "meal_type": "Colazione",
                    "day_context": "Ufficio",
                    "value": "Colazione Ufficio",
                    "confidence_level": "high",
                }
            ],
            "learning": [],
        }
    )

    card = result["learned"][0]

    assert card["title"] == (
        "Martedì · Colazione → Colazione Ufficio"
    )
    assert "modalità Ufficio" in card["text"]
    assert card["icon"] == "meal"


def test_learning_card_uses_uncertain_language():
    result = service.present(
        {
            "learned": [],
            "learning": [
                {
                    "kind": "day_context",
                    "weekday_name": "Friday",
                    "value": "Ufficio",
                    "confidence_level": "low",
                }
            ],
        }
    )

    card = result["learning"][0]

    assert "Sto ancora capendo" in card["text"]
    assert card["confidence_level"] == "low"


def test_raw_insight_is_preserved():
    insight = {
        "kind": "day_context",
        "weekday_name": "Tuesday",
        "value": "Ufficio",
        "confidence_level": "high",
    }

    result = service.present(
        {
            "learned": [insight],
            "learning": [],
        }
    )

    assert result["learned"][0]["raw"] == insight
