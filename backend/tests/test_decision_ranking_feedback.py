from backend.services.decision_ranking import (
    DecisionRankingService,
)


service = DecisionRankingService()


def candidate(name, source, kcal, protein, taste, boost=0.0):
    return {
        "id": name,
        "name": name,
        "source": source,
        "calories": kcal,
        "protein_g": protein,
        "taste_score": taste,
        "decision_feedback_boost": boost,
    }


def test_feedback_can_break_close_tie():
    result = service.rank(
        candidates=[
            candidate(
                "Preferred delivery",
                "delivery",
                500,
                35,
                7,
                boost=0.08,
            ),
            candidate(
                "Other takeaway",
                "takeaway",
                500,
                35,
                7,
                boost=0.0,
            ),
        ],
        available_kcal=800,
        protein_remaining_g=50,
        mode="order",
    )

    assert (
        result["options"][0]["candidate"]["name"]
        == "Preferred delivery"
    )


def test_feedback_does_not_reinstate_over_budget_candidate():
    result = service.rank(
        candidates=[
            candidate(
                "Too large",
                "delivery",
                1000,
                40,
                10,
                boost=0.08,
            ),
            candidate(
                "Compatible",
                "takeaway",
                500,
                30,
                6,
            ),
        ],
        available_kcal=700,
        protein_remaining_g=50,
        mode="order",
        preferred_lens="taste",
        preferred_mode="order",
    )

    assert all(
        option["candidate"]["name"] != "Too large"
        for option in result["options"]
    )


def test_preferred_lens_adds_bonus_only_to_that_lens():
    candidates = [
        candidate(
            "A",
            "delivery",
            500,
            30,
            7,
        ),
        candidate(
            "B",
            "takeaway",
            520,
            30,
            7,
        ),
    ]

    no_pref = service.rank(
        candidates=candidates,
        available_kcal=800,
        protein_remaining_g=50,
        mode="order",
    )

    with_pref = service.rank(
        candidates=candidates,
        available_kcal=800,
        protein_remaining_g=50,
        mode="order",
        preferred_lens="taste",
    )

    no_pref_taste = next(
        x for x in no_pref["options"]
        if x["lens"] == "taste"
    )
    with_pref_taste = next(
        x for x in with_pref["options"]
        if x["lens"] == "taste"
    )

    assert with_pref_taste["score"] > no_pref_taste["score"]
