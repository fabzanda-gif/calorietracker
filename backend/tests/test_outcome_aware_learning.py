from backend.services.outcome_aware_learning import (
    OutcomeAwareLearningService,
)


service = OutcomeAwareLearningService()


def item(
    *,
    mode="order",
    lens="taste",
    source="delivery",
    status="not_observed",
):
    return {
        "mode": mode,
        "lens": lens,
        "candidate": {
            "name": "Candidate",
            "source": source,
        },
        "outcome": {
            "status": status,
        },
    }


def test_selection_is_weak_positive_signal():
    result = service.build(
        items=[
            item(
                status="not_observed",
            )
        ]
    )

    assert result["mode_scores"] == {
        "order": 1.0
    }
    assert result["lens_scores"] == {
        "taste": 1.0
    }
    assert result["source_scores"] == {
        "delivery": 1.0
    }


def test_observed_outcome_strengthens_selection():
    result = service.build(
        items=[
            item(
                status="observed",
            )
        ]
    )

    assert result["mode_scores"]["order"] == 2.0
    assert result["lens_scores"]["taste"] == 2.0
    assert result["source_scores"]["delivery"] == 2.0
    assert result["observed_count"] == 1


def test_not_observed_is_not_negative():
    result = service.build(
        items=[
            item(
                mode="order",
                status="not_observed",
            ),
            item(
                mode="home",
                status="observed",
            ),
        ]
    )

    assert result["mode_scores"] == {
        "home": 2.0,
        "order": 1.0,
    }
    assert result["preferred_mode"] == "home"


def test_ambiguous_and_unresolved_remain_selection_only():
    result = service.build(
        items=[
            item(
                mode="order",
                status="ambiguous",
            ),
            item(
                mode="home",
                status="unresolved",
            ),
        ]
    )

    assert result["mode_scores"] == {
        "home": 1.0,
        "order": 1.0,
    }
    assert result["preferred_mode"] is None


def test_observed_history_can_break_selection_tie():
    result = service.build(
        items=[
            item(
                mode="order",
                status="observed",
            ),
            item(
                mode="home",
                status="not_observed",
            ),
        ]
    )

    assert result["preferred_mode"] == "order"


def test_source_learning_uses_candidate_source():
    result = service.build(
        items=[
            item(
                source="delivery",
                status="observed",
            ),
            item(
                source="takeaway",
                status="not_observed",
            ),
        ]
    )

    assert result["preferred_source"] == "delivery"


def test_exact_tie_has_no_preference():
    result = service.build(
        items=[
            item(
                lens="taste",
                status="observed",
            ),
            item(
                lens="protein",
                status="observed",
            ),
        ]
    )

    assert result["preferred_lens"] is None


def test_empty_history_is_safe():
    result = service.build(
        items=[]
    )

    assert result == {
        "item_count": 0,
        "observed_count": 0,
        "mode_scores": {},
        "lens_scores": {},
        "source_scores": {},
        "preferred_mode": None,
        "preferred_lens": None,
        "preferred_source": None,
    }
