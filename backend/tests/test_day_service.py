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
    def __init__(self, context_prediction, activity_prediction=None):
        self.context_prediction = context_prediction
        self.activity_prediction = activity_prediction or UNKNOWN
        self.context_calls = []
        self.activity_calls = []

    def predict_context(self, user_id, day_date):
        self.context_calls.append((user_id, str(day_date)))
        return self.context_prediction

    def predict_activity_plan(self, user_id, day_date):
        self.activity_calls.append((user_id, str(day_date)))
        return self.activity_prediction


UNKNOWN = {
    "value": None,
    "state": "unknown",
    "source": None,
    "confidence": None,
    "confidence_level": None,
    "evidence": {
        "observations": 0,
        "matches": 0,
        "recent_observations": 0,
        "recent_matches": 0,
        "change_detected": False,
    },
}


def predicted(value):
    return {
        "value": value,
        "state": "predicted",
        "source": "routine",
        "confidence": 1.0,
        "confidence_level": "high",
        "evidence": {
            "observations": 4,
            "matches": 4,
            "recent_observations": 4,
            "recent_matches": 4,
            "change_detected": False,
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
        predicted("Casa"),
        predicted("Riposo"),
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
    assert day["activity_plan"] == {
        "value": "Attiva",
        "state": "confirmed",
        "source": "user",
        "confidence": 1.0,
    }

    assert memory.context_calls == []
    assert memory.activity_calls == []


def test_missing_context_can_use_memory_prediction():
    repo = FakeDailyLogsRepository(
        {
            "date": "2026-09-01",
            "activity_plan": "Riposo",
        }
    )
    memory = FakeMemoryService(predicted("Ufficio"))

    day = DayService(repo, memory).build_day(
        user_id="u1",
        day_date=date(2026, 9, 1),
    )

    assert day["context"]["value"] == "Ufficio"
    assert day["context"]["state"] == "predicted"
    assert memory.context_calls == [("u1", "2026-09-01")]


def test_missing_activity_plan_can_use_memory_prediction():
    repo = FakeDailyLogsRepository(
        {
            "date": "2026-09-01",
            "day_type": "Ufficio",
        }
    )
    memory = FakeMemoryService(
        UNKNOWN,
        predicted("Attiva"),
    )

    day = DayService(repo, memory).build_day(
        user_id="u1",
        day_date=date(2026, 9, 1),
    )

    assert day["activity_plan"]["value"] == "Attiva"
    assert day["activity_plan"]["state"] == "predicted"
    assert memory.activity_calls == [("u1", "2026-09-01")]


def test_missing_fields_stay_unknown_when_memory_has_no_prediction():
    repo = FakeDailyLogsRepository(
        {
            "date": "2026-08-25",
            "steps": 0,
        }
    )
    memory = FakeMemoryService(UNKNOWN, UNKNOWN)

    day = DayService(repo, memory).build_day(
        user_id="u1",
        day_date=date(2026, 8, 25),
    )

    assert day["context"]["state"] == "unknown"
    assert day["activity_plan"]["state"] == "unknown"
    assert day["actual"]["steps"] == 0


def test_missing_daily_log_does_not_invent_information():
    repo = FakeDailyLogsRepository(None)
    memory = FakeMemoryService(UNKNOWN, UNKNOWN)

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
