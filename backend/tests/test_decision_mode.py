import pytest

from backend.services.decision_mode import (
    DecisionModeError,
    DecisionModeService,
)


service = DecisionModeService()


CANDIDATES = [
    {"name": "Chili", "source": "meal_prep"},
    {"name": "Pasta", "source": "recipe"},
    {"name": "Routine", "source": "routine"},
    {"name": "Pizza delivery", "source": "delivery"},
    {"name": "Sushi takeaway", "source": "takeaway"},
    {"name": "Restaurant", "source": "restaurant"},
]


def test_auto_keeps_all_candidates():
    result = service.apply(
        candidates=CANDIDATES,
        mode="auto",
    )

    assert result["candidate_count"] == len(CANDIDATES)
    assert result["mode_label"] == "Automatico"


def test_ready_keeps_only_meal_prep():
    result = service.apply(
        candidates=CANDIDATES,
        mode="ready",
    )

    assert [x["source"] for x in result["candidates"]] == [
        "meal_prep"
    ]
    assert result["mode_label"] == "Già pronto"


def test_cook_keeps_recipes_and_routine():
    result = service.apply(
        candidates=CANDIDATES,
        mode="cook",
    )

    assert {x["source"] for x in result["candidates"]} == {
        "recipe",
        "routine",
    }


def test_order_keeps_takeaway_and_delivery():
    result = service.apply(
        candidates=CANDIDATES,
        mode="order",
    )

    assert {x["source"] for x in result["candidates"]} == {
        "takeaway",
        "delivery",
    }


def test_out_keeps_restaurant_sources():
    result = service.apply(
        candidates=CANDIDATES,
        mode="out",
    )

    assert [x["source"] for x in result["candidates"]] == [
        "restaurant"
    ]


def test_empty_order_mode_is_explicit():
    result = service.apply(
        candidates=[
            {"name": "Chili", "source": "meal_prep"}
        ],
        mode="order",
    )

    assert result["candidates"] == []
    assert result["empty_reason"] == "no_known_order_options"


def test_invalid_mode_is_rejected():
    with pytest.raises(DecisionModeError):
        service.apply(
            candidates=CANDIDATES,
            mode="magic",
        )
