from datetime import date

from backend.services.day import DayService


DAY = date(2026, 9, 1)


class FakeDailyLogsRepository:
    def get_for_date_compatible(self, user_id, log_date):
        return {
            "date": str(log_date),
            "day_type": "Ufficio",
            "activity_plan": "Attiva",
        }


class FakeMemoryService:
    def predict_context(self, user_id, day_date):
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

    def predict_activity_plan(self, user_id, day_date):
        return self.predict_context(user_id, day_date)


class FakeMealMemoryService:
    def __init__(self):
        self.calls = []

    def predict_meal(
        self,
        *,
        user_id,
        day_date,
        meal_type,
        day_context=None,
    ):
        self.calls.append(meal_type)
        return {
            "meal_type": meal_type,
            "value": f"{meal_type} Ufficio",
            "state": "predicted",
            "source": "routine",
            "confidence": 1.0,
            "confidence_level": "high",
            "day_context": day_context,
            "estimated_calories": 500,
            "estimated_protein_g": 30,
            "estimated_carbs_g": 50,
            "estimated_fat_g": 15,
            "evidence": {
                "observations": 4,
                "matches": 4,
                "recent_observations": 4,
                "recent_matches": 4,
            },
        }


def test_day_service_predicts_all_three_main_meal_slots():
    meal_memory = FakeMealMemoryService()

    day = DayService(
        daily_logs_repo=FakeDailyLogsRepository(),
        memory_service=FakeMemoryService(),
        meal_memory_service=meal_memory,
    ).build_day(
        user_id="u1",
        day_date=DAY,
    )

    assert day["meals"]["breakfast"]["meal_type"] == "Colazione"
    assert day["meals"]["lunch"]["meal_type"] == "Pranzo"
    assert day["meals"]["dinner"]["meal_type"] == "Cena"

    assert meal_memory.calls == [
        "Colazione",
        "Pranzo",
        "Cena",
    ]


def test_without_meal_memory_all_slots_remain_unknown():
    day = DayService(
        daily_logs_repo=FakeDailyLogsRepository(),
        memory_service=FakeMemoryService(),
    ).build_day(
        user_id="u1",
        day_date=DAY,
    )

    assert day["meals"]["breakfast"]["state"] == "unknown"
    assert day["meals"]["lunch"]["state"] == "unknown"
    assert day["meals"]["dinner"]["state"] == "unknown"
