from backend.services.training_activity_review import (
    TrainingActivityReviewService,
)


def test_flags_big_run_close_to_race():
    result = TrainingActivityReviewService().build(
        activity={
            "date": "2026-09-12",
            "activity_type": "Corsa",
            "distance_meters": 10000,
            "duration_seconds": 3000,
        },
        planned={
            "session_kind": "easy",
            "distance_meters": 6000,
            "duration_minutes": 40,
        },
        plan={
            "target_date": "2026-09-14",
            "target_distance_meters": 21097,
            "target_pace_seconds_per_km": 300,
        },
    )

    assert result["available"] is True
    assert result["race"]["days_to_race"] == 2

    assert (
        "substantial_run_close_to_race"
        in result["signals"]
    )

    assert (
        "over_planned_load"
        in result["signals"]
    )


def test_flags_easy_run_faster_than_goal_pace():
    result = TrainingActivityReviewService().build(
        activity={
            "date": "2026-09-01",
            "activity_type": "Corsa",
            "distance_meters": 10000,
            "duration_seconds": 2900,
        },
        planned={
            "session_kind": "easy",
            "distance_meters": 10000,
        },
        plan={
            "target_date": "2026-10-01",
            "target_pace_seconds_per_km": 300,
        },
    )

    assert (
        "too_fast_for_easy_session"
        in result["signals"]
    )


def test_non_running_activity_has_no_running_review():
    result = TrainingActivityReviewService().build(
        activity={
            "date": "2026-09-12",
            "activity_type": "Padel",
        }
    )

    assert result == {
        "available": False,
        "reason": "not_running",
    }
