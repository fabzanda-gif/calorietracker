from backend.services.decision_feedback import (
    DecisionFeedbackService,
)
from backend.services.decision_learning_pipeline import (
    DecisionLearningPipelineService,
)


def selection(
    selection_id,
    *,
    day_date,
    mode="order",
    lens="taste",
    source="delivery",
    name="Poke",
):
    return {
        "id": selection_id,
        "date": day_date,
        "meal_slot": "dinner",
        "meal_type": "Cena",
        "mode": mode,
        "lens": lens,
        "candidate": {
            "name": name,
            "source": source,
            "calories": 600,
        },
    }


def meal(
    meal_id,
    *,
    day_date,
    name="Poke",
):
    return {
        "id": meal_id,
        "date": day_date,
        "meal_type": "Cena",
        "name": name,
        "calories": 600,
    }


def test_end_to_end_learning_contract():
    pipeline = DecisionLearningPipelineService().build(
        selections=[
            selection(
                "s1",
                day_date="2026-09-01",
            ),
            selection(
                "s2",
                day_date="2026-09-02",
            ),
        ],
        meals=[
            meal(
                "m1",
                day_date="2026-09-01",
            )
        ],
    )

    blended = pipeline["blended_profile"]

    assert blended["profile"]["mode"]["preferred"] == "order"
    assert blended["profile"]["lens"]["preferred"] == "taste"
    assert blended["profile"]["source"]["preferred"] == "delivery"

    assert blended["profile"]["mode"]["learning_source"] == "outcome"
    assert blended["profile"]["lens"]["learning_source"] == "outcome"
    assert blended["profile"]["source"]["learning_source"] == "outcome"

    assert blended["outcome_evidence"] == {
        "item_count": 2,
        "observed_count": 1,
    }

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
        learned_profile=blended,
        mode="order",
    )

    preferred = next(
        item
        for item in feedback["candidates"]
        if item["source"] == "delivery"
    )

    other = next(
        item
        for item in feedback["candidates"]
        if item["source"] == "takeaway"
    )

    assert preferred["decision_feedback_boost"] > 0
    assert other["decision_feedback_boost"] == 0.0


def test_missing_outcomes_never_create_negative_feedback():
    pipeline = DecisionLearningPipelineService().build(
        selections=[
            selection(
                "s1",
                day_date="2026-09-01",
            ),
        ],
        meals=[],
    )

    assert pipeline["outcome_report"]["status_counts"] == {
        "observed": 0,
        "not_observed": 1,
        "ambiguous": 0,
        "unresolved": 0,
    }

    assert pipeline["outcome_learning"]["mode_scores"] == {
        "order": 1.0,
    }


def test_empty_learning_contract_is_stable():
    pipeline = DecisionLearningPipelineService().build(
        selections=[],
        meals=[],
    )

    blended = pipeline["blended_profile"]

    assert blended["profile"]["mode"]["preferred"] is None
    assert blended["profile"]["lens"]["preferred"] is None
    assert blended["profile"]["source"]["preferred"] is None

    assert blended["outcome_evidence"] == {
        "item_count": 0,
        "observed_count": 0,
    }
