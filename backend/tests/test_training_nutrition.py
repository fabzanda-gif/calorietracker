from datetime import date, datetime

from backend.services.training_nutrition import (
    TrainingNutritionService,
)


def test_half_marathon_today_prioritises_pre_race_carbs():
    result = TrainingNutritionService().build(
        day_date=date(2026, 9, 12),
        planned_activities=[
            {
                "scheduled_date": "2026-09-12",
                "scheduled_time": "14:00",
                "status": "planned",
                "title": "Mezza maratona",
                "activity_type": "Corsa",
                "session_kind": "race",
                "distance_meters": 21097,
            }
        ],
        actual_activities=[],
        weight_kg=70,
        now=datetime(
            2026, 9, 12, 11, 0
        ),
    )

    assert result["phase"] == "pre_race"
    assert result["priority"] == "race"
    assert result["hours_to_start"] == 3.0
    assert result["carbs_target_g"] == {
        "min": 140,
        "max": 210,
    }


def test_completed_long_run_switches_to_recovery():
    result = TrainingNutritionService().build(
        day_date=date(2026, 9, 12),
        planned_activities=[],
        actual_activities=[
            {
                "date": "2026-09-12",
                "activity_name": "Long run",
                "activity_type": "Corsa",
                "distance_meters": 18000,
                "duration_seconds": 6000,
            }
        ],
        weight_kg=70,
    )

    assert result["phase"] == "recovery"
    assert result["carb_focus"] is True
    assert result["protein_focus"] is True

    assert result["carbs_target_g"] == {
        "min": 70,
        "max": 84,
    }

    assert result["protein_target_g"] == {
        "min": 18,
        "max": 21,
    }


def test_race_tomorrow_prepares_today():
    result = TrainingNutritionService().build(
        day_date=date(2026, 9, 12),
        planned_activities=[
            {
                "scheduled_date": "2026-09-13",
                "status": "planned",
                "title": "10 km race",
                "activity_type": "Corsa",
                "session_kind": "race",
                "distance_meters": 10000,
            }
        ],
        actual_activities=[],
        weight_kg=70,
    )

    assert result["phase"] == "tomorrow_prep"
    assert result["priority"] == "race"
    assert result["carb_focus"] is True
    assert result["carbs_target_g"] == {
        "min": 280,
        "max": 420,
    }


def test_rest_day_has_normal_context():
    result = TrainingNutritionService().build(
        day_date=date(2026, 9, 12),
        planned_activities=[],
        actual_activities=[],
        weight_kg=70,
    )

    assert result["phase"] == "normal"
    assert result["session"] is None
    assert result["carb_focus"] is False
