from datetime import date

from backend.services.activity_suggestion import learn_activity_suggestion


def test_suggests_recurring_office_bike_when_not_logged():
    activities = [
        {
            "date": f"2026-08-{day:02d}",
            "activity_name": "Bici",
            "burned_calories": 70,
            "duration_seconds": 600,
        }
        for day in (4, 11, 18)
    ]
    logs = [
        {"date": item["date"], "day_type": "office"}
        for item in activities
    ]

    result = learn_activity_suggestion(
        day_date=date(2026, 9, 8),
        day_context="office",
        activities=activities,
        daily_logs=logs,
        today_activities=[],
        planned_activities=[],
    )

    assert result is not None
    assert result["activity_name"] == "Bicicletta"
    assert result["duration_minutes"] == 10


def test_does_not_suggest_activity_already_logged():
    repeated = [
        {"date": f"2026-08-{day:02d}", "activity_name": "Bici"}
        for day in (4, 11, 18)
    ]
    result = learn_activity_suggestion(
        day_date=date(2026, 9, 8),
        day_context=None,
        activities=repeated,
        daily_logs=[],
        today_activities=[{"activity_name": "Bicicletta"}],
        planned_activities=[],
    )
    assert result is None
