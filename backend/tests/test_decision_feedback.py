from backend.services.decision_feedback import (
    DecisionFeedbackService,
)


service = DecisionFeedbackService()


def learned_profile(
    *,
    mode="order",
    lens="taste",
    source="delivery",
):
    return {
        "profile": {
            "mode": {
                "preferred": mode,
                "share": 0.8,
                "state": "learned",
            },
            "lens": {
                "preferred": lens,
                "share": 0.75,
                "state": "learned",
            },
            "source": {
                "preferred": source,
                "share": 0.75,
                "state": "learned",
            },
        }
    }


def test_preferred_source_receives_small_boost():
    result = service.enrich_candidates(
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
        learned_profile=learned_profile(),
        mode="order",
    )

    poke = result["candidates"][0]
    pizza = result["candidates"][1]

    assert poke["decision_feedback_boost"] == 0.06
    assert poke["decision_feedback_reason"] == "preferred_source"
    assert pizza["decision_feedback_boost"] == 0.0


def test_unlearned_source_does_not_boost():
    profile = learned_profile()
    profile["profile"]["source"]["state"] = "learning"

    result = service.enrich_candidates(
        candidates=[
            {
                "name": "Poke",
                "source": "delivery",
            }
        ],
        learned_profile=profile,
        mode="order",
    )

    assert (
        result["candidates"][0][
            "decision_feedback_boost"
        ]
        == 0.0
    )


def test_lens_preference_adds_small_score_bonus():
    candidate = {
        "decision_feedback_boost": 0.06,
    }

    score = service.score_boost(
        candidate=candidate,
        lens="taste",
        mode="order",
        preferred_lens="taste",
        preferred_mode=None,
    )

    assert score == 0.09


def test_mode_preference_adds_small_score_bonus():
    score = service.score_boost(
        candidate={
            "decision_feedback_boost": 0.06,
        },
        lens="balanced",
        mode="order",
        preferred_lens=None,
        preferred_mode="order",
    )

    assert score == 0.08


def test_all_feedback_is_capped():
    score = service.score_boost(
        candidate={
            "decision_feedback_boost": 0.2,
        },
        lens="taste",
        mode="order",
        preferred_lens="taste",
        preferred_mode="order",
    )

    assert score == 0.13


def test_learning_profile_exposes_no_preferred_values():
    profile = learned_profile()

    for value in profile["profile"].values():
        value["state"] = "learning"

    result = service.enrich_candidates(
        candidates=[],
        learned_profile=profile,
        mode="order",
    )

    assert result["preferred_mode"] is None
    assert result["preferred_lens"] is None
    assert result["preferred_source"] is None


def test_missing_profile_is_safe():
    result = service.enrich_candidates(
        candidates=[
            {
                "name": "Meal",
                "source": "recipe",
            }
        ],
        learned_profile={},
        mode="cook",
    )

    assert result["candidates"][0]["decision_feedback_boost"] == 0.0
