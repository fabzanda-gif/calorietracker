from backend.services.decision_feedback_blend import DecisionFeedbackBlendService


service = DecisionFeedbackBlendService()


def profile(*, mode=None, lens=None, source=None, learned=True):
    state = "learned" if learned else "learning"
    return {
        "profile": {
            "mode": {"preferred": mode, "share": 0.8, "state": state},
            "lens": {"preferred": lens, "share": 0.8, "state": state},
            "source": {"preferred": source, "share": 0.8, "state": state},
        }
    }


def test_outcome_profile_has_priority():
    result = service.build(
        selection_profile=profile(mode="order"),
        outcome_profile=profile(mode="out"),
    )

    assert result["profile"]["mode"]["preferred"] == "out"
    assert result["profile"]["mode"]["learning_source"] == "outcome"


def test_selection_profile_is_fallback():
    result = service.build(
        selection_profile=profile(lens="taste"),
        outcome_profile=profile(lens="balanced", learned=False),
    )

    assert result["profile"]["lens"]["preferred"] == "taste"
    assert result["profile"]["lens"]["learning_source"] == "selection"


def test_dimensions_are_blended_independently():
    selection = profile(
        mode="order",
        lens="taste",
        source="takeaway",
    )
    outcome = {
        "profile": {
            "mode": {"preferred": "out", "share": 0.75, "state": "learned"},
            "lens": {"preferred": None, "share": 0.5, "state": "learning"},
            "source": {"preferred": "restaurant", "share": 0.8, "state": "learned"},
        },
        "evidence": {"item_count": 5, "observed_count": 3},
    }

    result = service.build(
        selection_profile=selection,
        outcome_profile=outcome,
    )

    assert result["profile"]["mode"]["preferred"] == "out"
    assert result["profile"]["lens"]["preferred"] == "taste"
    assert result["profile"]["source"]["preferred"] == "restaurant"


def test_no_learned_signal_is_unknown():
    result = service.build(
        selection_profile={},
        outcome_profile={},
    )

    assert result["profile"]["mode"] == {
        "preferred": None,
        "share": 0.0,
        "state": "unknown",
        "learning_source": None,
    }
