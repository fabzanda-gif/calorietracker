from backend.services.decision_mode import (
    DecisionModeService,
)


def test_order_mode_accepts_generic_order_source():
    result = DecisionModeService().apply(
        candidates=[
            {
                "name": "Poke salmone",
                "source": "generic_order",
            },
            {
                "name": "Meal prep",
                "source": "meal_prep",
            },
        ],
        mode="order",
    )

    assert result["candidate_count"] == 1
    assert result["candidates"][0]["source"] == "generic_order"
