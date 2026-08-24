from backend.services.decision_outcome import (
    DecisionOutcomeService,
)


service = DecisionOutcomeService()


def selection(
    *,
    name="Poke Salmone",
    calories=650,
    day_date="2026-09-01",
    meal_slot="dinner",
):
    return {
        "day_date": day_date,
        "meal_slot": meal_slot,
        "candidate": {
            "name": name,
            "calories": calories,
            "source": "delivery",
        },
    }


def meal(
    *,
    meal_id="meal-1",
    name="Poke Salmone",
    base_name=None,
    calories=650,
    day_date="2026-09-01",
    meal_type="Cena",
):
    return {
        "id": meal_id,
        "date": day_date,
        "meal_type": meal_type,
        "name": name,
        "base_name": base_name,
        "calories": calories,
    }


def test_exact_logged_meal_is_observed():
    result = service.evaluate(
        selection=selection(),
        meals=[meal()],
    )

    assert result["status"] == "observed"
    assert result["reason"] == "exact_name_match"
    assert result["confidence"] == 1.0
    assert result["meal"]["id"] == "meal-1"


def test_name_matching_is_normalized():
    result = service.evaluate(
        selection=selection(
            name="  POKE   salmone "
        ),
        meals=[
            meal(
                name="Poke Salmone",
            )
        ],
    )

    assert result["status"] == "observed"


def test_base_name_can_match_selected_candidate():
    result = service.evaluate(
        selection=selection(),
        meals=[
            meal(
                name="Poke Salmone grande",
                base_name="Poke Salmone",
            )
        ],
    )

    assert result["status"] == "observed"


def test_wrong_meal_slot_is_not_observed():
    result = service.evaluate(
        selection=selection(
            meal_slot="dinner"
        ),
        meals=[
            meal(
                meal_type="Pranzo",
            )
        ],
    )

    assert result["status"] == "not_observed"


def test_wrong_date_is_not_observed():
    result = service.evaluate(
        selection=selection(),
        meals=[
            meal(
                day_date="2026-09-02",
            )
        ],
    )

    assert result["status"] == "not_observed"


def test_missing_candidate_name_is_unresolved():
    result = service.evaluate(
        selection={
            "day_date": "2026-09-01",
            "meal_slot": "dinner",
            "candidate": {},
        },
        meals=[],
    )

    assert result == {
        "status": "unresolved",
        "reason": "candidate_name_missing",
        "confidence": 0.0,
        "meal": None,
    }


def test_multiple_exact_matches_use_calorie_proximity():
    result = service.evaluate(
        selection=selection(
            calories=650
        ),
        meals=[
            meal(
                meal_id="meal-1",
                calories=800,
            ),
            meal(
                meal_id="meal-2",
                calories=660,
            ),
        ],
    )

    assert result["status"] == "observed"
    assert result["meal"]["id"] == "meal-2"
    assert (
        result["reason"]
        == "exact_name_and_calorie_match"
    )


def test_multiple_equal_matches_are_ambiguous():
    result = service.evaluate(
        selection=selection(
            calories=650
        ),
        meals=[
            meal(
                meal_id="meal-1",
                calories=640,
            ),
            meal(
                meal_id="meal-2",
                calories=660,
            ),
        ],
    )

    assert result["status"] == "ambiguous"
    assert (
        result["reason"]
        == "multiple_exact_name_matches"
    )


def test_no_match_does_not_claim_rejection():
    result = service.evaluate(
        selection=selection(
            name="Pizza"
        ),
        meals=[
            meal(
                name="Poke Salmone"
            )
        ],
    )

    assert result["status"] == "not_observed"
    assert result["reason"] == "no_matching_logged_meal"
