from datetime import date

from backend.services.order_personalization import (
    OrderPersonalizationService,
)


service = OrderPersonalizationService()
TODAY = date(2026, 9, 1)


def known(
    name,
    *,
    count,
    last_date,
    taste_score=None,
):
    item = {
        "name": name,
        "source": "takeaway",
        "known_order": True,
        "order_count": count,
        "last_ordered_date": last_date,
    }

    if taste_score is not None:
        item["taste_score"] = taste_score

    return item


def generic(name="Generic"):
    return {
        "name": name,
        "source": "generic_order",
        "known_order": False,
        "taste_score": 5.0,
    }


def test_generic_candidate_stays_neutral():
    result = service.enrich(
        candidates=[generic()],
        on_date=TODAY,
    )[0]

    assert result["taste_score"] == 5.0
    assert result["implicit_taste_score"] == 5.0
    assert result["personalization_strength"] == 0.0


def test_frequent_recent_order_gets_strong_signal():
    result = service.enrich(
        candidates=[
            known(
                "Poke",
                count=4,
                last_date="2026-08-29",
            )
        ],
        on_date=TODAY,
    )[0]

    assert result["personalization_strength"] == 1.0
    assert result["implicit_taste_score"] == 9.0
    assert result["taste_score"] == 9.0
    assert (
        result["personalization_reason"]
        == "frequent_and_recent_order"
    )


def test_single_old_order_gets_weak_signal():
    result = service.enrich(
        candidates=[
            known(
                "Old curry",
                count=1,
                last_date="2026-05-01",
            )
        ],
        on_date=TODAY,
    )[0]

    assert result["personalization_strength"] < 0.25
    assert result["taste_score"] < 6.0


def test_recent_order_can_be_personalized_even_if_not_frequent():
    result = service.enrich(
        candidates=[
            known(
                "Sushi",
                count=1,
                last_date="2026-08-30",
            )
        ],
        on_date=TODAY,
    )[0]

    assert result["personalization_reason"] == "recent_order"
    assert result["taste_score"] > 6.0


def test_frequent_but_older_order_keeps_frequency_signal():
    result = service.enrich(
        candidates=[
            known(
                "Pizza",
                count=4,
                last_date="2026-07-10",
            )
        ],
        on_date=TODAY,
    )[0]

    assert result["personalization_reason"] == "frequent_order"
    assert result["taste_score"] > 7.0


def test_explicit_taste_score_remains_dominant():
    result = service.enrich(
        candidates=[
            known(
                "Burger",
                count=4,
                last_date="2026-08-31",
                taste_score=10,
            )
        ],
        on_date=TODAY,
    )[0]

    assert result["implicit_taste_score"] == 9.0
    assert result["taste_score"] > 9.0


def test_missing_or_invalid_date_does_not_break():
    result = service.enrich(
        candidates=[
            known(
                "Unknown recency",
                count=2,
                last_date="not-a-date",
            )
        ],
        on_date=TODAY,
    )[0]

    assert result["personalization_strength"] > 0
    assert result["taste_score"] > 5.0


def test_more_frequent_order_scores_higher_than_less_frequent_same_recency():
    results = service.enrich(
        candidates=[
            known(
                "Frequent",
                count=4,
                last_date="2026-08-20",
            ),
            known(
                "Rare",
                count=1,
                last_date="2026-08-20",
            ),
        ],
        on_date=TODAY,
    )

    frequent = next(
        item
        for item in results
        if item["name"] == "Frequent"
    )
    rare = next(
        item
        for item in results
        if item["name"] == "Rare"
    )

    assert frequent["taste_score"] > rare["taste_score"]
