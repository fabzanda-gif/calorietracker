from backend.services.decision_learning_pipeline import (
    DecisionLearningPipelineService,
)


service = DecisionLearningPipelineService()


def selection(
    selection_id,
    *,
    day_date,
    mode="order",
    lens="taste",
    source="delivery",
    name="Poke",
    calories=600,
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
            "calories": calories,
        },
    }


def meal(
    meal_id,
    *,
    day_date,
    name="Poke",
    calories=600,
):
    return {
        "id": meal_id,
        "date": day_date,
        "meal_type": "Cena",
        "name": name,
        "calories": calories,
    }


def test_empty_pipeline_is_safe():
    result = service.build(
        selections=[],
        meals=[],
    )

    assert result["selection_profile"]["selection_count"] == 0
    assert result["outcome_report"]["selection_count"] == 0
    assert result["outcome_learning"]["item_count"] == 0

    assert (
        result["blended_profile"]["profile"]["mode"][
            "preferred"
        ]
        is None
    )


def test_observed_history_can_drive_final_profile():
    selections = [
        selection(
            "s1",
            day_date="2026-09-01",
        ),
        selection(
            "s2",
            day_date="2026-09-02",
        ),
    ]

    meals = [
        meal(
            "m1",
            day_date="2026-09-01",
        ),
    ]

    result = service.build(
        selections=selections,
        meals=meals,
    )

    blended = result["blended_profile"]["profile"]

    assert blended["mode"]["preferred"] == "order"
    assert blended["lens"]["preferred"] == "taste"
    assert blended["source"]["preferred"] == "delivery"

    assert blended["mode"]["learning_source"] == "outcome"
    assert blended["lens"]["learning_source"] == "outcome"
    assert blended["source"]["learning_source"] == "outcome"


def test_selection_fallback_is_kept_when_outcome_evidence_is_sparse():
    selections = [
        selection(
            "s1",
            day_date="2026-09-01",
            mode="order",
        ),
        selection(
            "s2",
            day_date="2026-09-02",
            mode="order",
        ),
        selection(
            "s3",
            day_date="2026-09-03",
            mode="order",
        ),
    ]

    result = service.build(
        selections=selections,
        meals=[],
    )

    mode = result["blended_profile"]["profile"]["mode"]

    assert mode["preferred"] == "order"
    assert mode["learning_source"] == "outcome"


def test_outcome_can_override_selection_only_preference():
    selections = [
        selection(
            "s1",
            day_date="2026-09-01",
            mode="order",
            lens="taste",
            source="delivery",
            name="Poke",
        ),
        selection(
            "s2",
            day_date="2026-09-02",
            mode="cook",
            lens="balanced",
            source="recipe",
            name="Pasta",
        ),
        selection(
            "s3",
            day_date="2026-09-03",
            mode="cook",
            lens="balanced",
            source="recipe",
            name="Pasta",
        ),
    ]

    meals = [
        meal(
            "m1",
            day_date="2026-09-01",
            name="Poke",
        ),
        meal(
            "m2",
            day_date="2026-09-01",
            name="Poke",
            calories=600,
        ),
    ]

    result = service.build(
        selections=selections,
        meals=meals,
    )

    # The pipeline exposes both layers independently, so callers can inspect
    # whether outcome evidence is strong enough to override selection-only.
    assert (
        result["selection_profile"]["profile"]["mode"][
            "preferred"
        ]
        == "cook"
    )

    assert "blended_profile" in result


def test_pipeline_preserves_outcome_evidence_metadata():
    selections = [
        selection(
            "s1",
            day_date="2026-09-01",
        ),
        selection(
            "s2",
            day_date="2026-09-02",
        ),
    ]

    meals = [
        meal(
            "m1",
            day_date="2026-09-01",
        ),
    ]

    result = service.build(
        selections=selections,
        meals=meals,
    )

    assert result["blended_profile"]["outcome_evidence"] == {
        "item_count": 2,
        "observed_count": 1,
    }


def test_not_observed_never_becomes_negative_evidence():
    result = service.build(
        selections=[
            selection(
                "s1",
                day_date="2026-09-01",
                mode="order",
            )
        ],
        meals=[],
    )

    assert result["outcome_learning"]["mode_scores"] == {
        "order": 1.0,
    }
