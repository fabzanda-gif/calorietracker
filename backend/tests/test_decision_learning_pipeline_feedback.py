from backend.services.decision_feedback import (
    DecisionFeedbackService,
)
from backend.services.decision_learning_pipeline import (
    DecisionLearningPipelineService,
)


def test_pipeline_output_is_directly_compatible_with_feedback_service():
    pipeline = DecisionLearningPipelineService().build(
        selections=[
            {
                "id": "s1",
                "date": "2026-09-01",
                "meal_slot": "dinner",
                "meal_type": "Cena",
                "mode": "order",
                "lens": "taste",
                "candidate": {
                    "name": "Poke",
                    "source": "delivery",
                    "calories": 600,
                },
            },
            {
                "id": "s2",
                "date": "2026-09-02",
                "meal_slot": "dinner",
                "meal_type": "Cena",
                "mode": "order",
                "lens": "taste",
                "candidate": {
                    "name": "Poke",
                    "source": "delivery",
                    "calories": 600,
                },
            },
        ],
        meals=[
            {
                "id": "m1",
                "date": "2026-09-01",
                "meal_type": "Cena",
                "name": "Poke",
                "calories": 600,
            }
        ],
    )

    feedback = DecisionFeedbackService().enrich_candidates(
        candidates=[
            {
                "name": "Poke",
                "source": "delivery",
            },
            {
                "name": "Pizza",
                "source": "takeaway",
            },
        ],
        learned_profile=pipeline["blended_profile"],
        mode="order",
    )

    delivery = feedback["candidates"][0]
    takeaway = feedback["candidates"][1]

    assert delivery["decision_feedback_boost"] > 0
    assert takeaway["decision_feedback_boost"] == 0.0
