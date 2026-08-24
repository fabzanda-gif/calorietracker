from backend.services.decision_learning import (
    DecisionLearningService,
)


service = DecisionLearningService()


def event(
    *,
    mode="order",
    lens="taste",
    source="delivery",
    generic=False,
):
    return {
        "mode": mode,
        "lens": lens,
        "candidate": {
            "source": source,
            "generic_fallback": generic,
        },
    }


def test_empty_history_is_unknown():
    result = service.build(events=[])

    assert result["selection_count"] == 0
    assert result["profile"]["mode"]["state"] == "unknown"
    assert result["learned"] == []
    assert result["learning"] == []


def test_three_dominant_selections_can_be_learned():
    result = service.build(
        events=[
            event(),
            event(),
            event(),
        ]
    )

    mode = result["profile"]["mode"]

    assert mode["preferred"] == "order"
    assert mode["share"] == 1.0
    assert mode["confidence_level"] == "medium"
    assert mode["state"] == "learned"


def test_six_strong_selections_can_reach_high_confidence():
    result = service.build(
        events=[
            event(),
            event(),
            event(),
            event(),
            event(),
            event(mode="cook"),
        ]
    )

    mode = result["profile"]["mode"]

    assert mode["preferred"] == "order"
    assert mode["count"] == 5
    assert mode["share"] == 0.8333
    assert mode["confidence_level"] == "high"
    assert mode["state"] == "learned"


def test_low_dominance_stays_learning():
    result = service.build(
        events=[
            event(mode="order"),
            event(mode="cook"),
            event(mode="out"),
        ]
    )

    mode = result["profile"]["mode"]

    assert mode["confidence_level"] == "low"
    assert mode["state"] == "learning"


def test_learns_preferred_lens():
    result = service.build(
        events=[
            event(lens="balanced"),
            event(lens="balanced"),
            event(lens="balanced"),
            event(lens="taste"),
        ]
    )

    lens = result["profile"]["lens"]

    assert lens["preferred"] == "balanced"
    assert lens["count"] == 3
    assert lens["state"] == "learned"


def test_learns_preferred_source():
    result = service.build(
        events=[
            event(source="meal_prep"),
            event(source="meal_prep"),
            event(source="meal_prep"),
            event(source="recipe"),
        ]
    )

    source = result["profile"]["source"]

    assert source["preferred"] == "meal_prep"
    assert source["share"] == 0.75
    assert source["state"] == "learned"


def test_distribution_is_exposed_for_explainability():
    result = service.build(
        events=[
            event(mode="order"),
            event(mode="order"),
            event(mode="cook"),
        ]
    )

    assert result["profile"]["mode"]["distribution"] == {
        "order": 2,
        "cook": 1,
    }


def test_generic_fallback_share_is_tracked():
    result = service.build(
        events=[
            event(generic=True),
            event(generic=False),
            event(generic=False),
            event(generic=False),
        ]
    )

    generic = result["profile"]["generic_fallback"]

    assert generic["selected_count"] == 1
    assert generic["share"] == 0.25


def test_invalid_events_are_ignored():
    result = service.build(
        events=[
            {},
            {"mode": "order"},
            {
                "mode": "order",
                "lens": "taste",
                "candidate": {},
            },
            event(),
        ]
    )

    assert result["selection_count"] == 1


def test_learned_and_learning_sections_are_separated():
    result = service.build(
        events=[
            event(
                mode="order",
                lens="taste",
                source="delivery",
            ),
            event(
                mode="order",
                lens="taste",
                source="delivery",
            ),
            event(
                mode="order",
                lens="balanced",
                source="takeaway",
            ),
        ]
    )

    learned_kinds = {
        item["kind"]
        for item in result["learned"]
    }
    learning_kinds = {
        item["kind"]
        for item in result["learning"]
    }

    assert "mode" in learned_kinds
    assert "lens" in learned_kinds
    assert "source" in learned_kinds
    assert learned_kinds.isdisjoint(learning_kinds)
