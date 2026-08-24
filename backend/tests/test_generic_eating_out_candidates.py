from backend.services.generic_eating_out_candidates import (
    GenericEatingOutCandidateService,
)


service = GenericEatingOutCandidateService()


def test_new_user_gets_three_generic_dinner_options():
    result = service.build(
        meal_type="Cena",
        known_candidates=[],
    )

    assert len(result) == 3
    assert all(
        item["source"] == "generic_eating_out"
        for item in result
    )
    assert all(
        item["known_eating_out"] is False
        for item in result
    )
    assert all(
        item["nutrition_estimated"] is True
        for item in result
    )


def test_known_history_reduces_generic_fillers():
    result = service.build(
        meal_type="Cena",
        known_candidates=[
            {"name": "Ramen"},
            {"name": "Sushi"},
        ],
    )

    assert len(result) == 1


def test_three_known_options_need_no_fallback():
    result = service.build(
        meal_type="Cena",
        known_candidates=[
            {"name": "Ramen"},
            {"name": "Sushi"},
            {"name": "Steak"},
        ],
    )

    assert result == []


def test_fallback_does_not_duplicate_known_name():
    result = service.build(
        meal_type="Cena",
        known_candidates=[
            {"name": "Ramen"},
        ],
    )

    assert all(
        item["name"] != "Ramen"
        for item in result
    )


def test_unknown_meal_type_has_no_fallback():
    result = service.build(
        meal_type="Snack",
        known_candidates=[],
    )

    assert result == []
