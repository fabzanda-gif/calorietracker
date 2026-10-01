from backend.services.planned_activity_outcome import (
    PlannedActivityOutcomeService,
)


def planned(**overrides):
    item = {
        "id": "planned-1",
        "training_plan_id": "plan-1",
        "training_week": 4,
        "session_kind": "long",
        "scheduled_date": "2026-09-06",
        "activity_type": "Corsa",
        "status": "completed",
        "distance_meters": 10000,
        "duration_minutes": 60,
    }
    item.update(overrides)
    return item


def actual(
    *,
    distance=10000,
    duration_minutes=60,
):
    return {
        "id": "actual-1",
        "date": "2026-09-06",
        "activity_name": "Corsa",
        "activity_type": "Corsa",
        "distance_meters": distance,
        "duration_seconds": (
            duration_minutes * 60
        ),
        "burned_calories": 650,
    }


def test_on_target_keeps_plan():
    result = PlannedActivityOutcomeService().build(
        planned=planned(),
        actual_activities=[
            actual(distance=9800),
        ],
    )

    assert result["outcome"] == "on_target"
    assert (
        result["recommended_action"]
        == "keep_plan"
    )


def test_under_target_eases_next_load():
    result = PlannedActivityOutcomeService().build(
        planned=planned(),
        actual_activities=[
            actual(distance=7000),
        ],
    )

    assert result["outcome"] == "under"
    assert (
        result["recommended_action"]
        == "ease_next"
    )


def test_over_target_protects_recovery():
    result = PlannedActivityOutcomeService().build(
        planned=planned(),
        actual_activities=[
            actual(distance=13000),
        ],
    )

    assert result["outcome"] == "over"
    assert (
        result["recommended_action"]
        == "recover_next"
    )


def test_skipped_session_needs_no_actual_activity():
    result = PlannedActivityOutcomeService().build(
        planned=planned(status="skipped"),
        actual_activities=[],
    )

    assert result["outcome"] == "skipped"
    assert (
        result["recommended_action"]
        == "ease_next"
    )


def test_missing_actual_is_unmatched():
    result = PlannedActivityOutcomeService().build(
        planned=planned(),
        actual_activities=[],
    )

    assert result["outcome"] == "unmatched"
    assert (
        result["recommended_action"]
        == "review"
    )


def test_duration_used_when_distance_missing():
    result = PlannedActivityOutcomeService().build(
        planned=planned(
            distance_meters=None,
            duration_minutes=60,
        ),
        actual_activities=[
            actual(
                distance=0,
                duration_minutes=45,
            ),
        ],
    )

    assert result["outcome"] == "under"
    assert result["load_ratio"] == 0.75
