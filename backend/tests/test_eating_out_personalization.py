from datetime import date

from backend.services.eating_out_personalization import (
    EatingOutPersonalizationService,
)


service = EatingOutPersonalizationService()
TODAY = date(2026, 9, 1)


def known(
    name,
    *,
    count,
    last_date,
):
    return {
        "name": name,
        "source": "restaurant",
        "known_eating_out": True,
        "visit_count": count,
        "last_visited_date": last_date,
    }


def test_frequent_recent_place_gets_strong_signal():
    result = service.enrich(
        candidates=[
            known(
                "Ramen",
                count=4,
                last_date="2026-08-30",
            )
        ],
        on_date=TODAY,
    )[0]

    assert result["personalization_strength"] == 1.0
    assert result["taste_score"] == 9.0
    assert (
        result["personalization_reason"]
        == "frequent_and_recent_eating_out"
    )


def test_single_old_visit_gets_weak_signal():
    result = service.enrich(
        candidates=[
            known(
                "Old place",
                count=1,
                last_date="2026-05-01",
            )
        ],
        on_date=TODAY,
    )[0]

    assert result["taste_score"] < 6.0


def test_recent_visit_can_be_personalized():
    result = service.enrich(
        candidates=[
            known(
                "Sushi",
                count=1,
                last_date="2026-08-31",
            )
        ],
        on_date=TODAY,
    )[0]

    assert (
        result["personalization_reason"]
        == "recent_eating_out"
    )
    assert result["taste_score"] > 6.0
