from datetime import date

from backend.services.day import DayService


class FakeDailyLogsRepository:
    def __init__(self, row):
        self.row = row
        self.last_get = None

    def get_for_date_compatible(self, user_id, log_date):
        self.last_get = (user_id, str(log_date))
        return self.row


def test_saved_planning_is_confirmed_user_input():
    repo = FakeDailyLogsRepository(
        {
            "date": "2026-08-25",
            "weight": 80.1,
            "steps": 7000,
            "day_type": "Ufficio",
            "activity_plan": "Attiva",
        }
    )

    day = DayService(repo).build_day(
        user_id="u1",
        day_date=date(2026, 8, 25),
    )

    assert repo.last_get == ("u1", "2026-08-25")

    assert day["context"] == {
        "value": "Ufficio",
        "state": "confirmed",
        "source": "user",
        "confidence": 1.0,
    }

    assert day["activity_plan"] == {
        "value": "Attiva",
        "state": "confirmed",
        "source": "user",
        "confidence": 1.0,
    }

    assert day["actual"] == {
        "weight": 80.1,
        "steps": 7000,
    }


def test_missing_planning_is_unknown_not_zero():
    repo = FakeDailyLogsRepository(
        {
            "date": "2026-08-25",
            "steps": 0,
        }
    )

    day = DayService(repo).build_day(
        user_id="u1",
        day_date=date(2026, 8, 25),
    )

    assert day["context"] == {
        "value": None,
        "state": "unknown",
        "source": None,
        "confidence": None,
    }

    assert day["activity_plan"] == {
        "value": None,
        "state": "unknown",
        "source": None,
        "confidence": None,
    }

    assert day["actual"]["steps"] == 0


def test_missing_daily_log_does_not_invent_information():
    repo = FakeDailyLogsRepository(None)

    day = DayService(repo).build_day(
        user_id="u1",
        day_date=date(2026, 8, 25),
    )

    assert day["date"] == "2026-08-25"
    assert day["context"]["state"] == "unknown"
    assert day["activity_plan"]["state"] == "unknown"
    assert day["actual"] == {
        "weight": None,
        "steps": None,
    }
