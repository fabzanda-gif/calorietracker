from types import SimpleNamespace

import pytest

from backend.services.day_briefing import (
    DayBriefingError,
    DayBriefingService,
    build_status_hint,
    fallback_day_briefing,
)


def _payload():
    return {
        "first_name": "Fabio",
        "moment": "evening",
        "day_type": "free",
        "activity_level": "low",
        "activity_count": 0,
        "meal_count": 3,
        "activity_kcal": 0,
        "consumed_kcal": 1703,
        "daily_budget_kcal": 1202,
        "maintenance_kcal": 1702,
        "available_kcal": -501,
        "status_hint": "maintenance",
    }


def test_status_hint_recognizes_maintenance_tolerance():
    assert build_status_hint(
        consumed_kcal=1703,
        daily_budget_kcal=1202,
        maintenance_kcal=1702,
    ) == "maintenance"


def test_standard_fallback_matches_expected_tone():
    message = fallback_day_briefing(
        _payload(),
        mode="standard",
    )

    assert message.startswith("Buonasera Fabio!")
    assert "giornata di riposo" in message
    assert "rimasto in mantenimento" in message
    assert "pur non avendo fatto attività fisica" in message
    assert message.endswith("Goditi la serata!")


def test_zero_fallback_uses_distinct_tone():
    message = fallback_day_briefing(
        _payload(),
        mode="zero",
    )

    assert message.startswith("Buonasera Fabio!")
    assert "Sei in mantenimento." in message
    assert "bravo" not in message.lower()


def test_ai_generator_uses_structured_output():
    parsed = SimpleNamespace(
        message=(
            "Buonasera Fabio! Ottimo equilibrio oggi. "
            "Goditi la serata!"
        )
    )
    completion = SimpleNamespace(
        choices=[
            SimpleNamespace(
                message=SimpleNamespace(
                    parsed=parsed,
                )
            )
        ]
    )
    parse_calls = []

    class FakeParse:
        def parse(self, **kwargs):
            parse_calls.append(kwargs)
            return completion

    client = SimpleNamespace(
        beta=SimpleNamespace(
            chat=SimpleNamespace(
                completions=FakeParse(),
            )
        )
    )

    message = DayBriefingService(
        api_key="test",
        client=client,
    ).generate(
        _payload(),
        mode="standard",
    )

    assert message.startswith("Buonasera Fabio!")
    assert parse_calls[0]["max_completion_tokens"] == 180
    assert (
        parse_calls[0]["response_format"]
        .__name__
        == "DayBriefingOutput"
    )



def test_morning_without_meals_prompts_for_breakfast():
    payload = {
        **_payload(),
        "moment": "morning",
        "meal_count": 0,
        "consumed_kcal": 0,
        "available_kcal": 1202,
        "status_hint": "deficit",
    }

    message = fallback_day_briefing(
        payload,
        mode="standard",
    )

    assert message.startswith("Buongiorno Fabio!")
    assert "colazione" in message.lower()
    assert "rispettato" not in message.lower()
    assert "sei stato bravo" not in message.lower()


def test_zero_morning_without_meals_is_not_celebratory():
    payload = {
        **_payload(),
        "moment": "morning",
        "meal_count": 0,
        "consumed_kcal": 0,
        "available_kcal": 1202,
        "status_hint": "deficit",
    }

    message = fallback_day_briefing(
        payload,
        mode="zero",
    )

    assert "colazione" in message.lower()
    assert "bravo" not in message.lower()

def test_morning_with_a_logged_meal_is_still_provisional():
    payload = {
        **_payload(),
        "moment": "morning",
        "meal_count": 1,
        "status_hint": "deficit",
    }

    message = fallback_day_briefing(
        payload,
        mode="standard",
    )

    assert message.startswith("Buongiorno Fabio!")
    assert "giornata è ancora in corso" in message
    assert "hai rispettato" not in message
    assert "sei rimasto" not in message
    assert "mantenimento" not in message
    assert "Goditi la serata" not in message


def test_ai_morning_outcome_is_rejected():
    parsed = SimpleNamespace(
        message=(
            "Buongiorno Fabio! Oggi sei rimasto "
            "sotto il target. Buona giornata!"
        )
    )
    completion = SimpleNamespace(
        choices=[
            SimpleNamespace(
                message=SimpleNamespace(
                    parsed=parsed,
                )
            )
        ]
    )

    class FakeParse:
        def parse(self, **kwargs):
            return completion

    client = SimpleNamespace(
        beta=SimpleNamespace(
            chat=SimpleNamespace(
                completions=FakeParse(),
            )
        )
    )

    payload = {
        **_payload(),
        "moment": "morning",
        "meal_count": 0,
    }

    with pytest.raises(
        DayBriefingError,
        match="premature morning outcome",
    ):
        DayBriefingService(
            api_key="test",
            client=client,
        ).generate(
            payload,
            mode="standard",
        )
