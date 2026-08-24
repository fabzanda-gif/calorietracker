from backend.services.decision_outcome_report import (
    DecisionOutcomeReportService,
)


service = DecisionOutcomeReportService()


def selection(
    selection_id,
    *,
    name,
    day_date="2026-09-01",
):
    return {
        "id": selection_id,
        "date": day_date,
        "meal_slot": "dinner",
        "meal_type": "Cena",
        "mode": "order",
        "lens": "taste",
        "candidate": {
            "name": name,
            "calories": 650,
            "source": "delivery",
        },
    }


def meal(
    meal_id,
    *,
    name,
    day_date="2026-09-01",
):
    return {
        "id": meal_id,
        "date": day_date,
        "meal_type": "Cena",
        "name": name,
        "calories": 650,
    }


def test_report_reconstructs_observed_and_not_observed():
    result = service.build(
        selections=[
            selection(
                "s1",
                name="Poke Salmone",
            ),
            selection(
                "s2",
                name="Pizza",
            ),
        ],
        meals=[
            meal(
                "m1",
                name="Poke Salmone",
            )
        ],
    )

    assert result["selection_count"] == 2
    assert result["status_counts"] == {
        "observed": 1,
        "not_observed": 1,
        "ambiguous": 0,
        "unresolved": 0,
    }
    assert result["observed_share"] == 0.5


def test_meals_are_matched_only_within_same_date():
    result = service.build(
        selections=[
            selection(
                "s1",
                name="Poke",
                day_date="2026-09-01",
            )
        ],
        meals=[
            meal(
                "m1",
                name="Poke",
                day_date="2026-09-02",
            )
        ],
    )

    assert (
        result["items"][0]["outcome"]["status"]
        == "not_observed"
    )


def test_report_preserves_selection_context():
    result = service.build(
        selections=[
            selection(
                "s1",
                name="Poke",
            )
        ],
        meals=[],
    )

    item = result["items"][0]

    assert item["selection_id"] == "s1"
    assert item["mode"] == "order"
    assert item["lens"] == "taste"
    assert item["candidate"]["name"] == "Poke"


def test_empty_report_is_safe():
    result = service.build(
        selections=[],
        meals=[],
    )

    assert result["selection_count"] == 0
    assert result["observed_share"] == 0.0
    assert result["items"] == []
