from backend.services.outcome_feedback_profile import (
    OutcomeFeedbackProfileService,
)


service = OutcomeFeedbackProfileService()


def learning(
    *,
    mode_scores=None,
    lens_scores=None,
    source_scores=None,
    item_count=0,
    observed_count=0,
):
    return {
        "item_count": item_count,
        "observed_count": observed_count,
        "mode_scores": mode_scores or {},
        "lens_scores": lens_scores or {},
        "source_scores": source_scores or {},
    }


def test_empty_profile_is_unknown():
    result = service.build(
        outcome_learning=learning()
    )

    assert result["profile"]["mode"] == {
        "preferred": None,
        "share": 0.0,
        "state": "unknown",
        "weighted_evidence": 0.0,
        "distribution": {},
    }


def test_three_weighted_points_can_learn_clear_preference():
    result = service.build(
        outcome_learning=learning(
            mode_scores={
                "order": 3.0,
            },
            item_count=2,
            observed_count=1,
        )
    )

    mode = result["profile"]["mode"]

    assert mode["preferred"] == "order"
    assert mode["share"] == 1.0
    assert mode["state"] == "learned"


def test_sparse_evidence_stays_learning():
    result = service.build(
        outcome_learning=learning(
            mode_scores={
                "order": 2.0,
            },
            item_count=1,
            observed_count=1,
        )
    )

    mode = result["profile"]["mode"]

    assert mode["preferred"] is None
    assert mode["state"] == "learning"


def test_weak_dominance_stays_learning():
    result = service.build(
        outcome_learning=learning(
            source_scores={
                "delivery": 3.0,
                "takeaway": 2.5,
            },
            item_count=4,
            observed_count=2,
        )
    )

    source = result["profile"]["source"]

    assert source["preferred"] is None
    assert source["share"] < 0.60
    assert source["state"] == "learning"


def test_clear_source_preference_becomes_learned():
    result = service.build(
        outcome_learning=learning(
            source_scores={
                "delivery": 4.0,
                "takeaway": 1.0,
            },
            item_count=3,
            observed_count=2,
        )
    )

    source = result["profile"]["source"]

    assert source["preferred"] == "delivery"
    assert source["share"] == 0.8
    assert source["state"] == "learned"


def test_exact_tie_never_becomes_learned():
    result = service.build(
        outcome_learning=learning(
            lens_scores={
                "taste": 3.0,
                "balanced": 3.0,
            },
            item_count=4,
            observed_count=2,
        )
    )

    lens = result["profile"]["lens"]

    assert lens["preferred"] is None
    assert lens["state"] == "learning"


def test_evidence_metadata_is_preserved():
    result = service.build(
        outcome_learning=learning(
            item_count=5,
            observed_count=3,
        )
    )

    assert result["evidence"] == {
        "item_count": 5,
        "observed_count": 3,
    }


def test_invalid_scores_are_ignored():
    result = service.build(
        outcome_learning=learning(
            mode_scores={
                "order": "3",
                "cook": "bad",
                "out": -1,
            },
        )
    )

    mode = result["profile"]["mode"]

    assert mode["distribution"] == {
        "order": 3.0,
    }
