from backend.services.generic_order_candidates import (
    GenericOrderCandidateService,
)


service = GenericOrderCandidateService()


def test_new_user_gets_three_generic_dinner_options():
    result = service.build(
        meal_type="Cena",
        known_candidates=[],
    )

    assert len(result) == 3
    assert all(
        item["source"] == "generic_order"
        for item in result
    )
    assert all(
        item["known_order"] is False
        for item in result
    )
    assert all(
        item["nutrition_estimated"] is True
        for item in result
    )


def test_known_orders_reduce_number_of_generic_fillers():
    known = [
        {"name": "Pizza Margherita", "source": "takeaway"},
        {"name": "Thai curry", "source": "delivery"},
    ]

    result = service.build(
        meal_type="Cena",
        known_candidates=known,
    )

    assert len(result) == 1


def test_three_known_orders_need_no_generic_fallback():
    known = [
        {"name": "Pizza", "source": "takeaway"},
        {"name": "Poke", "source": "delivery"},
        {"name": "Sushi", "source": "takeaway"},
    ]

    result = service.build(
        meal_type="Cena",
        known_candidates=known,
    )

    assert result == []


def test_generic_option_does_not_duplicate_known_name():
    result = service.build(
        meal_type="Cena",
        known_candidates=[
            {
                "name": "Pizza Margherita",
                "source": "takeaway",
            }
        ],
    )

    assert all(
        item["name"] != "Pizza Margherita"
        for item in result
    )


def test_unknown_meal_type_has_no_fallback():
    result = service.build(
        meal_type="Snack",
        known_candidates=[],
    )

    assert result == []
