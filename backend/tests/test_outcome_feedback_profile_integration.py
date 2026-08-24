from backend.services.decision_outcome_report import (
    DecisionOutcomeReportService,
)
from backend.services.outcome_aware_learning import (
    OutcomeAwareLearningService,
)
from backend.services.outcome_feedback_profile import (
    OutcomeFeedbackProfileService,
)


def test_observed_outcomes_can_produce_feedback_ready_profile():
    selections = [
        {
            "id": "s1",
            "date": "2026-09-01",
            "meal_slot": "dinner",
            "mode": "order",
            "lens": "taste",
            "candidate": {
                "name": "Poke",
                "source": "delivery",
                "calories": 650,
            },
        },
        {
            "id": "s2",
            "date": "2026-09-02",
            "meal_slot": "dinner",
            "mode": "order",
            "lens": "taste",
            "candidate": {
                "name": "Sushi",
                "source": "delivery",
                "calories": 700,
            },
        },
    ]

    meals = [
        {
            "id": "m1",
            "date": "2026-09-01",
            "meal_type": "Cena",
            "name": "Poke",
            "calories": 650,
        }
    ]

    report = DecisionOutcomeReportService().build(
        selections=selections,
        meals=meals,
    )

    learned = OutcomeAwareLearningService().build(
        items=report["items"],
    )

    profile = OutcomeFeedbackProfileService().build(
        outcome_learning=learned,
    )

    assert profile["profile"]["mode"]["preferred"] == "order"
    assert profile["profile"]["lens"]["preferred"] == "taste"
    assert profile["profile"]["source"]["preferred"] == "delivery"
    assert profile["evidence"]["observed_count"] == 1
