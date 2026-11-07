from backend.services.training_load import (
    TrainingLoadService,
)


def test_long_run_is_high_lower_load():
    event = TrainingLoadService().activity_event(
        activity={
            "id": 10,
            "date": "2026-11-07",
            "activity_name": "Corsa 10 km",
            "activity_type": "Corsa",
            "duration_seconds": 3600,
            "distance_meters": 10000,
            "burned_calories": 650,
        }
    )

    assert event is not None
    assert event["modality"] == "running"
    assert event["scope"] == "lower"
    assert event["intensity"] == "high"


def test_planned_easy_run_stays_low():
    event = TrainingLoadService().activity_event(
        activity={
            "id": 11,
            "date": "2026-11-07",
            "activity_name": "Corsa facile",
            "activity_type": "running",
            "duration_seconds": 2400,
            "distance_meters": 6000,
            "burned_calories": 350,
        },
        planned={
            "intensity": "low",
        },
    )

    assert event is not None
    assert event["intensity"] == "low"


def test_lower_strength_with_many_sets_is_high():
    event = TrainingLoadService().strength_event(
        workout={
            "id": "workout-1",
            "title": "Lower A",
            "focus": "lower",
            "workout_kind": "planned",
        },
        workout_log={
            "status": "completed",
            "performed_date": "2026-11-07",
            "duration_minutes": 70,
        },
        exercises=[
            {
                "movement_pattern": "squat",
            }
        ],
        set_logs=[
            {
                "reps": 8,
                "load_kg": 100,
                "feeling": "right",
            }
            for _ in range(12)
        ],
    )

    assert event is not None
    assert event["modality"] == "strength"
    assert event["scope"] == "lower"
    assert event["intensity"] == "high"


def test_free_strength_scope_is_inferred():
    event = TrainingLoadService().strength_event(
        workout={
            "id": "free-1",
            "title": "Extra",
            "focus": "free",
            "workout_kind": "free",
        },
        workout_log={
            "status": "completed",
            "performed_date": "2026-11-07",
            "duration_minutes": 40,
        },
        exercises=[
            {
                "movement_pattern": "squat",
            },
            {
                "movement_pattern":
                    "horizontal_push",
            },
        ],
        set_logs=[
            {
                "reps": 10,
                "load_kg": 50,
                "feeling": "right",
            }
            for _ in range(8)
        ],
    )

    assert event is not None
    assert event["scope"] == "full_body"
    assert event["workout_kind"] == "free"
