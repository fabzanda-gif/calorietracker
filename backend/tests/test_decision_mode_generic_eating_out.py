from backend.services.decision_mode import (
    DecisionModeService,
)


def test_out_mode_accepts_generic_eating_out():
    result = DecisionModeService().apply(
        candidates=[
            {
                "name": "Ramen",
                "source": "generic_eating_out",
            },
            {
                "name": "Meal prep",
                "source": "meal_prep",
            },
        ],
        mode="out",
    )

    assert result["candidate_count"] == 1
    assert result["candidates"][0]["source"] == "generic_eating_out"
