from datetime import date, datetime, timezone

import pytest

from backend.services.decision_selection import (
    DecisionSelectionError,
    DecisionSelectionService,
)


service = DecisionSelectionService()


def candidate(**overrides):
    item = {
        "id": "delivery:poke",
        "source": "delivery",
        "source_id": None,
        "name": "Poke Salmone",
        "calories": 650,
        "protein_g": 40,
        "carbs_g": 70,
        "fat_g": 20,
        "taste_score": 9,
        "waste_risk": None,
        "known_order": True,
        "personalization_strength": 1.0,
        "personalization_reason": (
            "frequent_and_recent_order"
        ),
    }
    item.update(overrides)
    return item


def test_builds_structured_selection_event():
    result = service.build_event(
        user_id="u1",
        day_date=date(2026, 9, 1),
        meal_slot="dinner",
        meal_type="Cena",
        mode="order",
        lens="taste",
        candidate=candidate(),
        option_index=2,
        available_kcal=900,
        protein_remaining_g=60,
        selected_at=datetime(
            2026,
            9,
            1,
            18,
            30,
            tzinfo=timezone.utc,
        ),
    )

    assert result["user_id"] == "u1"
    assert result["date"] == "2026-09-01"
    assert result["mode"] == "order"
    assert result["lens"] == "taste"
    assert result["option_index"] == 2
    assert result["selected_at"] == "2026-09-01T18:30:00Z"


def test_preserves_candidate_provenance():
    result = service.build_event(
        user_id="u1",
        day_date=date(2026, 9, 1),
        meal_slot="dinner",
        meal_type="Cena",
        mode="order",
        lens="balanced",
        candidate=candidate(),
        option_index=1,
    )

    selected = result["candidate"]

    assert selected["source"] == "delivery"
    assert selected["name"] == "Poke Salmone"
    assert selected["known_order"] is True
    assert selected["personalization_strength"] == 1.0
    assert (
        selected["personalization_reason"]
        == "frequent_and_recent_order"
    )


def test_preserves_generic_fallback_provenance():
    result = service.build_event(
        user_id="u1",
        day_date=date(2026, 9, 1),
        meal_slot="dinner",
        meal_type="Cena",
        mode="out",
        lens="calorie",
        candidate=candidate(
            id="generic_eating_out:sushi",
            source="generic_eating_out",
            name="Sushi",
            known_order=None,
            known_eating_out=False,
            generic_fallback=True,
            personalization_strength=None,
            personalization_reason=None,
        ),
        option_index=0,
    )

    selected = result["candidate"]

    assert selected["source"] == "generic_eating_out"
    assert selected["generic_fallback"] is True
    assert selected["known_eating_out"] is False


def test_decision_context_is_snapshotted():
    result = service.build_event(
        user_id="u1",
        day_date=date(2026, 9, 1),
        meal_slot="lunch",
        meal_type="Pranzo",
        mode="ready",
        lens="balanced",
        candidate=candidate(
            source="meal_prep",
            name="Chili",
        ),
        option_index=0,
        available_kcal=725.5,
        protein_remaining_g=48,
    )

    assert result["decision_context"] == {
        "available_kcal": 725.5,
        "protein_remaining_g": 48.0,
    }


def test_invalid_mode_is_rejected():
    with pytest.raises(DecisionSelectionError):
        service.build_event(
            user_id="u1",
            day_date=date(2026, 9, 1),
            meal_slot="dinner",
            meal_type="Cena",
            mode="magic",
            lens="taste",
            candidate=candidate(),
            option_index=0,
        )


def test_invalid_lens_is_rejected():
    with pytest.raises(DecisionSelectionError):
        service.build_event(
            user_id="u1",
            day_date=date(2026, 9, 1),
            meal_slot="dinner",
            meal_type="Cena",
            mode="order",
            lens="cheap",
            candidate=candidate(),
            option_index=0,
        )


def test_negative_option_index_is_rejected():
    with pytest.raises(DecisionSelectionError):
        service.build_event(
            user_id="u1",
            day_date=date(2026, 9, 1),
            meal_slot="dinner",
            meal_type="Cena",
            mode="order",
            lens="taste",
            candidate=candidate(),
            option_index=-1,
        )


def test_candidate_name_is_required():
    with pytest.raises(DecisionSelectionError):
        service.build_event(
            user_id="u1",
            day_date=date(2026, 9, 1),
            meal_slot="dinner",
            meal_type="Cena",
            mode="order",
            lens="taste",
            candidate=candidate(name=""),
            option_index=0,
        )


def test_candidate_source_is_required():
    with pytest.raises(DecisionSelectionError):
        service.build_event(
            user_id="u1",
            day_date=date(2026, 9, 1),
            meal_slot="dinner",
            meal_type="Cena",
            mode="order",
            lens="taste",
            candidate=candidate(source=""),
            option_index=0,
        )


def test_naive_datetime_is_normalized_to_utc():
    result = service.build_event(
        user_id="u1",
        day_date=date(2026, 9, 1),
        meal_slot="dinner",
        meal_type="Cena",
        mode="order",
        lens="taste",
        candidate=candidate(),
        option_index=0,
        selected_at=datetime(
            2026,
            9,
            1,
            20,
            0,
        ),
    )

    assert result["selected_at"] == "2026-09-01T20:00:00Z"
