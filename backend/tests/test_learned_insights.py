from datetime import date

from backend.services.learned_insights import LearnedInsightsService


ON_DATE = date(2026, 9, 1)


class DummyDailyLogsRepository:
    pass


class DummyMealsRepository:
    pass


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
        },
    }


def predicted(value, level, confidence=1.0):
    return {
        "value": value,
        "state": "predicted",
        "source": "routine",
        "confidence": confidence,
        "confidence_level": level,
        "evidence": {
            "observations": 4,
            "matches": 4,
        },
    }


class FakeMemoryService:
    def __init__(
        self,
        *,
        context_by_weekday=None,
        activity_by_weekday=None,
    ):
        self.context_by_weekday = (
            context_by_weekday or {}
        )
        self.activity_by_weekday = (
            activity_by_weekday or {}
        )

    def predict_context(self, user_id, day_date):
        return self.context_by_weekday.get(
            day_date.weekday(),
            unknown(),
        )

    def predict_activity_plan(
        self,
        user_id,
        day_date,
    ):
        return self.activity_by_weekday.get(
            day_date.weekday(),
            unknown(),
        )


class FakeMealMemoryService:
    def __init__(self, predictions=None):
        self.predictions = predictions or {}
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
                "weekday": day_date.weekday(),
                "meal_type": meal_type,
                "day_context": day_context,
            }
        )

        key = (
            day_date.weekday(),
            meal_type,
        )

        item = self.predictions.get(key)
        if item is None:
            return {
                "meal_type": meal_type,
                "value": None,
                "state": "unknown",
                "confidence": None,
                "confidence_level": None,
                "day_context": day_context,
                "estimated_calories": None,
                "estimated_protein_g": None,
                "evidence": {
                    "observations": 0,
                    "matches": 0,
                },
            }

        return {
            "meal_type": meal_type,
            "state": "predicted",
            "source": "routine",
            "day_context": day_context,
            **item,
        }


def service(memory=None, meals=None):
    return LearnedInsightsService(
        daily_logs_repo=DummyDailyLogsRepository(),
        meals_repo=DummyMealsRepository(),
        memory_service=memory or FakeMemoryService(),
        meal_memory_service=meals or FakeMealMemoryService(),
    )


def test_no_predictions_returns_empty_sections():
    result = service().build(
        user_id="u1",
        on_date=ON_DATE,
    )

    assert result["learned"] == []
    assert result["learning"] == []
    assert result["learned_count"] == 0


def test_medium_context_is_considered_learned():
    memory = FakeMemoryService(
        context_by_weekday={
            1: predicted(
                "Ufficio",
                "medium",
                0.75,
            )
        }
    )

    result = service(memory=memory).build(
        user_id="u1",
        on_date=ON_DATE,
    )

    context = [
        item
        for item in result["learned"]
        if item["kind"] == "day_context"
    ]

    assert len(context) == 1
    assert context[0]["weekday"] == 1
    assert context[0]["weekday_name"] == "Tuesday"
    assert context[0]["value"] == "Ufficio"


def test_high_activity_is_considered_learned():
    memory = FakeMemoryService(
        activity_by_weekday={
            1: predicted("Attiva", "high")
        }
    )

    result = service(memory=memory).build(
        user_id="u1",
        on_date=ON_DATE,
    )

    activity = [
        item
        for item in result["learned"]
        if item["kind"] == "activity_plan"
    ]

    assert activity[0]["value"] == "Attiva"


def test_low_confidence_pattern_stays_in_learning():
    memory = FakeMemoryService(
        context_by_weekday={
            4: predicted(
                "Ufficio",
                "low",
                1.0,
            )
        }
    )

    result = service(memory=memory).build(
        user_id="u1",
        on_date=ON_DATE,
    )

    assert result["learned"] == []
    assert result["learning_count"] == 1
    assert result["learning"][0]["weekday"] == 4


def test_meal_prediction_receives_inferred_context():
    memory = FakeMemoryService(
        context_by_weekday={
            1: predicted("Ufficio", "high")
        }
    )

    meals = FakeMealMemoryService(
        {
            (1, "Colazione"): {
                "value": "Colazione Ufficio",
                "confidence": 1.0,
                "confidence_level": "high",
                "estimated_calories": 310,
                "estimated_protein_g": 18,
                "evidence": {
                    "observations": 4,
                    "matches": 4,
                },
            }
        }
    )

    result = service(
        memory=memory,
        meals=meals,
    ).build(
        user_id="u1",
        on_date=ON_DATE,
    )

    breakfast = [
        item
        for item in result["learned"]
        if (
            item["kind"] == "meal"
            and item["meal_type"] == "Colazione"
        )
    ][0]

    assert breakfast["value"] == "Colazione Ufficio"
    assert breakfast["day_context"] == "Ufficio"

    matching_call = [
        call
        for call in meals.calls
        if (
            call["weekday"] == 1
            and call["meal_type"] == "Colazione"
        )
    ][0]

    assert matching_call["day_context"] == "Ufficio"


def test_meal_insight_keeps_nutrition_estimate():
    meals = FakeMealMemoryService(
        {
            (4, "Cena"): {
                "value": "Pizza takeaway",
                "confidence": 1.0,
                "confidence_level": "high",
                "estimated_calories": 850,
                "estimated_protein_g": 32,
                "evidence": {
                    "observations": 4,
                    "matches": 4,
                },
            }
        }
    )

    result = service(meals=meals).build(
        user_id="u1",
        on_date=ON_DATE,
    )

    dinner = [
        item
        for item in result["learned"]
        if (
            item["kind"] == "meal"
            and item["weekday"] == 4
        )
    ][0]

    assert dinner["value"] == "Pizza takeaway"
    assert dinner["estimated_calories"] == 850
    assert dinner["estimated_protein_g"] == 32


def test_same_day_weekday_uses_next_week_not_today():
    memory = FakeMemoryService(
        context_by_weekday={
            ON_DATE.weekday(): predicted(
                "Ufficio",
                "high",
            )
        }
    )

    result = service(memory=memory).build(
        user_id="u1",
        on_date=ON_DATE,
    )

    assert any(
        item["weekday"] == ON_DATE.weekday()
        for item in result["learned"]
    )
