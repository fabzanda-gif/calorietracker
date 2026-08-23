from datetime import date

from backend.services.day import DayService


DAY = date(2026, 9, 1)


class FakeDailyLogsRepository:
    def __init__(self, row):
        self.row = row

    def get_for_date_compatible(self, user_id, log_date):
        return self.row


class FakeMemoryService:
    def __init__(self, context=None, activity=None):
        self.context = context or unknown()
        self.activity = activity or unknown()

    def predict_context(self, user_id, day_date):
        return self.context

    def predict_activity_plan(self, user_id, day_date):
        return self.activity


class FakeMealMemoryService:
    def __init__(self, prediction):
        self.prediction = prediction
        self.calls = []

    def predict_meal(
        self,
        *,
        user_id,
        day_date,
        meal_type,
        day_context=None,
    ):
        self.calls.append(
            {
                "user_id": user_id,
                "date": str(day_date),
                "meal_type": meal_type,
                "day_context": day_context,
            }
        )
        return self.prediction


def unknown():
    return {
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


def predicted_context(value):
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


def breakfast_prediction():
    return {
        "meal_type": "Colazione",
        "value": "Colazione Ufficio",
        "state": "predicted",
        "source": "routine",
        "confidence": 1.0,
        "confidence_level": "high",
        "day_context": "Ufficio",
        "estimated_calories": 310.0,
        "estimated_protein_g": 18.0,
        "evidence": {
            "observations": 4,
            "matches": 4,
            "recent_observations": 4,
            "recent_matches": 4,
        },
    }


def test_confirmed_context_is_used_for_breakfast_prediction():
    meal_memory = FakeMealMemoryService(
        breakfast_prediction()
    )

    service = DayService(
        daily_logs_repo=FakeDailyLogsRepository(
            {
                "date": "2026-09-01",
                "day_type": "Ufficio",
            }
        ),
        memory_service=FakeMemoryService(),
        meal_memory_service=meal_memory,
    )

    day = service.build_day(
        user_id="u1",
        day_date=DAY,
    )

    assert day["meals"]["breakfast"]["value"] == "Colazione Ufficio"
    assert meal_memory.calls[0]["day_context"] == "Ufficio"


def test_predicted_context_can_feed_breakfast_prediction():
    meal_memory = FakeMealMemoryService(
        breakfast_prediction()
    )

    service = DayService(
        daily_logs_repo=FakeDailyLogsRepository(None),
        memory_service=FakeMemoryService(
            context=predicted_context("Ufficio"),
        ),
        meal_memory_service=meal_memory,
    )

    day = service.build_day(
        user_id="u1",
        day_date=DAY,
    )

    assert day["context"]["state"] == "predicted"
    assert meal_memory.calls[0]["day_context"] == "Ufficio"


def test_unknown_context_still_allows_weekday_only_prediction():
    prediction = breakfast_prediction()
    prediction = {
        **prediction,
        "day_context": None,
    }
    meal_memory = FakeMealMemoryService(prediction)

    service = DayService(
        daily_logs_repo=FakeDailyLogsRepository(None),
        memory_service=FakeMemoryService(),
        meal_memory_service=meal_memory,
    )

    day = service.build_day(
        user_id="u1",
        day_date=DAY,
    )

    assert meal_memory.calls[0]["day_context"] is None
    assert day["meals"]["breakfast"]["state"] == "predicted"


def test_without_meal_memory_breakfast_stays_unknown():
    service = DayService(
        daily_logs_repo=FakeDailyLogsRepository(None),
        memory_service=FakeMemoryService(),
    )

    day = service.build_day(
        user_id="u1",
        day_date=DAY,
    )

    breakfast = day["meals"]["breakfast"]

    assert breakfast["state"] == "unknown"
    assert breakfast["value"] is None


def test_prediction_is_not_written_into_actual_fields():
    meal_memory = FakeMealMemoryService(
        breakfast_prediction()
    )

    service = DayService(
        daily_logs_repo=FakeDailyLogsRepository(
            {
                "date": "2026-09-01",
                "weight": 80.0,
                "steps": 7000,
                "day_type": "Ufficio",
            }
        ),
        memory_service=FakeMemoryService(),
        meal_memory_service=meal_memory,
    )

    day = service.build_day(
        user_id="u1",
        day_date=DAY,
    )

    assert day["meals"]["breakfast"]["state"] == "predicted"
    assert day["actual"] == {
        "weight": 80.0,
        "steps": 7000,
    }
