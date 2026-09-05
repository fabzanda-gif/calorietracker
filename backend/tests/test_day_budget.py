from datetime import date

from backend.services.day_budget import DayBudgetService


DAY = date(2026, 8, 25)


class FakeMealsRepository:
    def __init__(self, rows):
        self.rows = rows

    def list_for_date_compatible(self, user_id, log_date):
        return self.rows


class FakeActivitiesRepository:
    def __init__(self, rows, history_rows=None):
        self.rows = rows
        self.history_rows = history_rows or []

    def list_for_date(self, user_id, log_date):
        return self.rows

    def list_date_range(self, user_id, start_date, end_date):
        return self.history_rows


class FakeDailyLogsRepository:
    def __init__(self, today=None, history=None):
        self.today = today or {}
        self.history = history or []

    def get_for_date_compatible(self, user_id, log_date):
        return self.today

    def list_date_range(
        self,
        user_id,
        start_date,
        end_date,
        columns=None,
    ):
        return self.history


def service(
    meals=None,
    activities=None,
    history_activities=None,
    daily_log=None,
    daily_log_history=None,
):
    return DayBudgetService(
        meals_repo=FakeMealsRepository(meals or []),
        activities_repo=FakeActivitiesRepository(
            activities or [],
            history_rows=history_activities or [],
        ),
        daily_logs_repo=FakeDailyLogsRepository(
            today=daily_log,
            history=daily_log_history,
        ),
    )


BASE_META = {
    "height": 180,
    "birth_date": "1990-01-01",
    "gender": "Uomo",
}


def test_day_budget_combines_profile_food_and_activity():
    result = service(
        meals=[
            {"calories": 500, "protein": 30},
            {"calories": 700, "protein": 40},
        ],
        activities=[
            {"burned_calories": 450},
        ],
    ).build(
        user_id="u1",
        day_date=DAY,
        metadata={
            **BASE_META,
            "goal_mode": "maintenance",
        },
        current_weight=80,
    )

    assert result["status"] == "ok"
    assert result["actual"]["consumed_kcal"] == 1200
    assert result["actual"]["protein_consumed_g"] == 70
    assert result["actual"]["actual_activity_kcal"] == 450

    budget = result["budget"]
    # Today's activity stays observable but is not added directly
    # to today's calorie target.
    assert budget["maintenance_kcal"] == result["profile"]["bmr"]
    assert budget["available_kcal"] == (
        budget["daily_budget_kcal"] - 1200
    )


def test_loss_goal_flows_into_daily_budget():
    result = service().build(
        user_id="u1",
        day_date=DAY,
        metadata={
            **BASE_META,
            "goal_mode": "loss",
            "goal_adjustment_kcal": 500,
        },
        current_weight=80,
    )

    budget = result["budget"]

    assert budget["goal_mode"] == "loss"
    assert budget["daily_budget_kcal"] == (
        budget["maintenance_kcal"] - 500
    )


def test_gain_goal_flows_into_daily_budget():
    result = service().build(
        user_id="u1",
        day_date=DAY,
        metadata={
            **BASE_META,
            "goal_mode": "gain",
            "goal_adjustment_kcal": 300,
        },
        current_weight=80,
    )

    budget = result["budget"]

    assert budget["goal_mode"] == "gain"
    assert budget["daily_budget_kcal"] == (
        budget["maintenance_kcal"] + 300
    )


def test_legacy_deficit_profile_is_supported():
    result = service().build(
        user_id="u1",
        day_date=DAY,
        metadata={
            **BASE_META,
            "deficit_plan": "medium",
            "deficit_target_kcal": 500,
        },
        current_weight=80,
    )

    assert result["status"] == "ok"
    assert result["budget"]["goal_mode"] == "loss"
    assert result["budget"]["goal_adjustment_kcal"] == 500


def test_protein_goal_is_combined_with_actual_intake():
    result = service(
        meals=[
            {"calories": 600, "protein": 60},
        ]
    ).build(
        user_id="u1",
        day_date=DAY,
        metadata={
            **BASE_META,
            "protein_goal_enabled": True,
            "protein_goal_g": 150,
        },
        current_weight=80,
    )

    budget = result["budget"]

    assert budget["protein_consumed_g"] == 60
    assert budget["protein_target_g"] == 150
    assert budget["protein_remaining_g"] == 90


def test_planned_calories_are_zero_until_planning_is_persisted():
    result = service(
        meals=[
            {"calories": 600, "protein": 30},
        ]
    ).build(
        user_id="u1",
        day_date=DAY,
        metadata=BASE_META,
        current_weight=80,
    )

    assert result["budget"]["planned_kcal"] == 0
    assert (
        result["budget"]["available_kcal"]
        == result["budget"]["unallocated_kcal"]
    )


def test_day_budget_reserves_a_realistic_dinner_until_logged():
    result = service(
        meals=[
            {
                "meal_type": "Pranzo",
                "calories": 1007,
                "protein": 55,
            },
        ]
    ).build(
        user_id="u1",
        day_date=DAY,
        metadata={
            **BASE_META,
            "goal_mode": "loss",
            "goal_adjustment_kcal": 500,
        },
        current_weight=80,
    )

    budget = result["budget"]
    assert 600 <= budget["remaining_meal_reserve_kcal"] <= 750
    assert budget["available_kcal"] >= 600
    assert budget["budget_adapted"] is True


def test_dinner_reserve_is_removed_once_dinner_is_logged():
    result = service(
        meals=[
            {
                "meal_type": "Cena",
                "calories": 700,
                "protein": 35,
            },
        ]
    ).build(
        user_id="u1",
        day_date=DAY,
        metadata={
            **BASE_META,
            "goal_mode": "loss",
            "goal_adjustment_kcal": 500,
        },
        current_weight=80,
    )

    assert result["budget"]["remaining_meal_reserve_kcal"] == 0


def test_profile_incomplete_does_not_invent_budget():
    result = service(
        meals=[
            {"calories": 500, "protein": 30},
        ],
        activities=[
            {"burned_calories": 200},
        ],
    ).build(
        user_id="u1",
        day_date=DAY,
        metadata={},
        current_weight=80,
    )

    assert result["status"] == "profile_incomplete"
    assert result["budget"] is None

    # Actual logged data is still returned even when budget cannot be built.
    assert result["actual"]["consumed_kcal"] == 500
    assert result["actual"]["actual_activity_kcal"] == 200


def test_negative_available_balance_is_preserved_end_to_end():
    result = service(
        meals=[
            {"calories": 5000, "protein": 150},
        ]
    ).build(
        user_id="u1",
        day_date=DAY,
        metadata={
            **BASE_META,
            "goal_mode": "maintenance",
        },
        current_weight=80,
    )

    assert result["budget"]["available_kcal"] < 0


def test_day_budget_uses_previous_seven_complete_days():
    result = service(
        history_activities=[
            {"date": "2026-08-18", "burned_calories": 700},
            {"date": "2026-08-19", "burned_calories": 700},
            {"date": "2026-08-22", "burned_calories": 700},
            {"date": "2026-08-24", "burned_calories": 700},
            {"date": "2026-08-25", "burned_calories": 5000},
        ],
        daily_log={
            "date": str(DAY),
            "activity_plan": "Riposo",
        },
    ).build(
        user_id="u1",
        day_date=DAY,
        metadata={
            **BASE_META,
            "goal_mode": "maintenance",
        },
        current_weight=80,
    )

    baseline = result["energy_baseline"]

    assert baseline["average_activity_kcal_7d"] == 400
    assert baseline["activity_buffer_kcal"] == 0
    assert baseline["activity_kcal_for_budget"] == 400

    assert result["budget"]["maintenance_kcal"] == (
        result["profile"]["bmr"] + 400
    )


def test_day_budget_adds_active_day_buffer():
    result = service(
        history_activities=[
            {"date": "2026-08-18", "burned_calories": 350},
            {"date": "2026-08-19", "burned_calories": 350},
            {"date": "2026-08-20", "burned_calories": 350},
            {"date": "2026-08-21", "burned_calories": 350},
            {"date": "2026-08-22", "burned_calories": 350},
            {"date": "2026-08-23", "burned_calories": 350},
            {"date": "2026-08-24", "burned_calories": 350},
        ],
        daily_log={
            "date": str(DAY),
            "activity_plan": "Attiva",
        },
    ).build(
        user_id="u1",
        day_date=DAY,
        metadata={
            **BASE_META,
            "goal_mode": "maintenance",
        },
        current_weight=80,
    )

    baseline = result["energy_baseline"]

    assert baseline["average_activity_kcal_7d"] == 350
    assert baseline["activity_level"] == "Attiva"
    assert baseline["activity_buffer_kcal"] == 300
    assert baseline["activity_kcal_for_budget"] == 650

    assert result["budget"]["maintenance_kcal"] == (
        result["profile"]["bmr"] + 650
    )


def test_day_budget_moderate_buffer_is_150():
    result = service(
        daily_log={
            "date": str(DAY),
            "activity_plan": "Moderatamente attiva",
        },
    ).build(
        user_id="u1",
        day_date=DAY,
        metadata={
            **BASE_META,
            "goal_mode": "maintenance",
        },
        current_weight=80,
    )

    assert (
        result["energy_baseline"]["activity_buffer_kcal"]
        == 150
    )


def test_today_activity_does_not_change_today_budget():
    before = service(
        activities=[],
        daily_log={
            "date": str(DAY),
            "activity_plan": "Riposo",
        },
    ).build(
        user_id="u1",
        day_date=DAY,
        metadata={
            **BASE_META,
            "goal_mode": "maintenance",
        },
        current_weight=80,
    )

    after = service(
        activities=[{"burned_calories": 500}],
        daily_log={
            "date": str(DAY),
            "activity_plan": "Riposo",
        },
    ).build(
        user_id="u1",
        day_date=DAY,
        metadata={
            **BASE_META,
            "goal_mode": "maintenance",
        },
        current_weight=80,
    )

    assert (
        after["actual"]["actual_activity_kcal"]
        == 500
    )
    assert (
        after["budget"]["daily_budget_kcal"]
        == before["budget"]["daily_budget_kcal"]
    )

