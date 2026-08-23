from datetime import date

from backend.services.day import DayService


class FakeDailyLogsRepository:
    def __init__(self, row):
        self.row = row
        self.last_get = None

    def get_for_date_compatible(self, user_id, log_date):
        self.last_get = (user_id, str(log_date))
        return self.row


class FakeMemoryService:
    def __init__(self, prediction):
        self.prediction = prediction
        self.calls = []

    def predict_context(self, user_id, day_date):
        self.calls.append((user_id, str(day_date)))
        return self.prediction


UNKNOWN = {
    "value": None,
    "state": "unknown",
    "source": None,
    "confidence": None,
    "confidence_level": None,
    "evidence": {
        "observations": 0,
        "matches": 0,
    },
}


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
    memory = FakeMemoryService(
        {
            "value": "Casa",
            "state": "predicted",
            "source": "routine",
            "confidence": 1.0,
            "confidence_level": "high",
            "evidence": {"observations": 4, "matches": 4},
        }
    )

    day = DayService(repo, memory).build_day(
        user_id="u1",
        day_date=date(2026, 8, 25),
    )

    assert day["context"] == {
        "value": "Ufficio",
        "state": "confirmed",
        "source": "user",
        "confidence": 1.0,
    }

    # Explicit user data wins, so memory is not even consulted.
    assert memory.calls == []


def test_missing_context_can_use_memory_prediction():
    repo = FakeDailyLogsRepository(
        {
            "date": "2026-09-01",
            "steps": 0,
        }
    )
    prediction = {
        "value": "Ufficio",
        "state": "predicted",
        "source": "routine",
        "confidence": 1.0,
        "confidence_level": "high",
        "evidence": {
            "observations": 4,
            "matches": 4,
        },
    }
    memory = FakeMemoryService(prediction)

    day = DayService(repo, memory).build_day(
        user_id="u1",
        day_date=date(2026, 9, 1),
    )

    assert day["context"] == prediction
    assert memory.calls == [("u1", "2026-09-01")]


def test_missing_planning_stays_unknown_when_memory_has_no_prediction():
    repo = FakeDailyLogsRepository(
        {
            "date": "2026-08-25",
            "steps": 0,
        }
    )
    memory = FakeMemoryService(UNKNOWN)

    day = DayService(repo, memory).build_day(
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
    memory = FakeMemoryService(UNKNOWN)

    day = DayService(repo, memory).build_day(
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
