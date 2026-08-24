from backend.services.decision_outcome_report import (
    DecisionOutcomeReportService,
)
from backend.services.outcome_aware_learning import (
    OutcomeAwareLearningService,
)


def test_reconstructed_observation_strengthens_realized_choice():
    selections = [
        {
            "id": "s1",
            "date": "2026-09-01",
            "meal_slot": "dinner",
            "mode": "order",
            "lens": "taste",
            "candidate": {
                "name": "Poke Salmone",
                "calories": 650,
                "source": "delivery",
            },
        },
        {
            "id": "s2",
            "date": "2026-09-02",
            "meal_slot": "dinner",
            "mode": "home",
            "lens": "protein",
            "candidate": {
                "name": "Pollo e riso",
                "calories": 600,
                "source": "recipe",
            },
        },
    ]

    meals = [
        {
            "id": "m1",
            "date": "2026-09-01",
            "meal_type": "Cena",
            "name": "Poke Salmone",
            "calories": 650,
        }
    ]

    report = DecisionOutcomeReportService().build(
        selections=selections,
        meals=meals,
    )

    learning = OutcomeAwareLearningService().build(
        items=report["items"],
    )

    assert learning["observed_count"] == 1
    assert learning["preferred_mode"] == "order"
    assert learning["preferred_lens"] == "taste"
    assert learning["preferred_source"] == "delivery"
