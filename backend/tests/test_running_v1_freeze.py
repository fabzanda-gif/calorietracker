from datetime import date, timedelta

from backend.services.future_training_nutrition import (
    FutureTrainingNutritionService,
)
from backend.services.planned_activity_outcome import (
    PlannedActivityOutcomeService,
)
from backend.services.running_plan import (
    RunningPlanInput,
    build_running_plan,
)
from backend.services.running_plan_adaptation import (
    RunningPlanAdaptationService,
)


def test_running_v1_plan_contract():
    start = date(2026, 9, 7)
    target = start + timedelta(weeks=12)

    sessions = build_running_plan(
        RunningPlanInput(
            start_date=start,
            target_date=target,
            current_distance_meters=7000,
            current_pace_seconds_per_km=360,
            target_distance_meters=21097,
            target_pace_seconds_per_km=330,
            sessions_per_week=3,
            long_run_weekday=6,
        )
    )

    assert sessions

    allowed_kinds = {
        "easy",
        "recovery",
        "tempo",
        "interval",
        "long",
        "race",
    }

    assert all(
        item["status"] == "planned"
        for item in sessions
    )
    assert all(
        item["session_kind"] in allowed_kinds
        for item in sessions
    )
    assert all(
        item["activity_type"] == "Corsa"
        for item in sessions
    )

    race = sessions[-1]

    assert race["session_kind"] == "race"
    assert race["scheduled_date"] == str(target)
    assert race["distance_meters"] == 21097
    assert race["intensity"] == "race"


def test_running_v1_future_training_drives_nutrition_context():
    today = date(2026, 9, 5)
    tomorrow = today + timedelta(days=1)

    planned = {
        "id": "long-1",
        "scheduled_date": str(tomorrow),
        "status": "planned",
        "training_plan_id": "plan-1",
        "training_week": 5,
        "activity_type": "Corsa",
        "title": "Lungo 14 km",
        "session_kind": "long",
        "distance_meters": 14000,
        "duration_minutes": 90,
    }

    result = FutureTrainingNutritionService().build(
        day_date=today,
        planned_activities=[planned],
    )

    assert result["level"] == "high"
    assert result["carb_focus"] is True
    assert (
        result["primary_session"]["id"]
        == "long-1"
    )


def test_running_v1_actual_to_adaptation_flow():
    source = {
        "id": "source-1",
        "training_plan_id": "plan-1",
        "scheduled_date": "2026-09-06",
        "status": "completed",
        "activity_type": "Corsa",
        "title": "Lungo 10 km",
        "session_kind": "long",
        "training_week": 3,
        "distance_meters": 10000,
        "duration_minutes": 60,
        "intensity": "low",
    }

    actual = {
        "id": "actual-1",
        "date": "2026-09-06",
        "activity_name": "Corsa",
        "activity_type": "Corsa",
        "distance_meters": 7000,
        "duration_seconds": 45 * 60,
        "burned_calories": 500,
    }

    outcome = PlannedActivityOutcomeService().build(
        planned=source,
        actual_activities=[actual],
    )

    assert outcome["outcome"] == "under"
    assert (
        outcome["recommended_action"]
        == "ease_next"
    )

    target = {
        "id": "target-1",
        "training_plan_id": "plan-1",
        "scheduled_date": "2026-09-10",
        "scheduled_time": None,
        "status": "planned",
        "activity_type": "Corsa",
        "title": "Corsa a ritmo",
        "session_kind": "tempo",
        "training_week": 4,
        "distance_meters": 8000,
        "duration_minutes": 48,
        "intensity": "moderate",
    }

    proposal = RunningPlanAdaptationService().build(
        source_session=source,
        outcome=outcome,
        plan_sessions=[source, target],
        adaptation_history=[],
    )

    assert proposal["adaptation_required"] is True
    assert proposal["target"]["id"] == "target-1"
    assert (
        proposal["changes"]["distance_meters"]
        == 7200
    )


def test_running_v1_history_stops_replay():
    source = {
        "id": "source-1",
        "training_plan_id": "plan-1",
        "scheduled_date": "2026-09-06",
        "status": "completed",
        "activity_type": "Corsa",
        "title": "Lungo",
        "session_kind": "long",
        "training_week": 3,
        "distance_meters": 10000,
        "duration_minutes": 60,
        "intensity": "low",
    }

    target = {
        "id": "target-1",
        "training_plan_id": "plan-1",
        "scheduled_date": "2026-09-10",
        "status": "planned",
        "activity_type": "Corsa",
        "title": "Tempo",
        "session_kind": "tempo",
        "training_week": 4,
        "distance_meters": 8000,
        "duration_minutes": 48,
        "intensity": "moderate",
    }

    outcome = {
        "outcome": "under",
        "recommended_action": "ease_next",
    }

    proposal = RunningPlanAdaptationService().build(
        source_session=source,
        outcome=outcome,
        plan_sessions=[source, target],
        adaptation_history=[
            {
                "source_planned_activity_id":
                    "source-1",
                "target_planned_activity_id":
                    "target-1",
                "decision": "applied",
            }
        ],
    )

    assert (
        proposal["adaptation_required"]
        is False
    )


def test_running_v1_race_week_remains_locked():
    source = {
        "id": "source",
        "training_plan_id": "plan",
        "scheduled_date": "2026-09-01",
        "status": "completed",
        "session_kind": "long",
    }

    quality = {
        "id": "quality",
        "training_plan_id": "plan",
        "scheduled_date": "2026-09-08",
        "status": "planned",
        "session_kind": "tempo",
        "distance_meters": 8000,
        "duration_minutes": 45,
        "intensity": "moderate",
    }

    race = {
        "id": "race",
        "training_plan_id": "plan",
        "scheduled_date": "2026-09-14",
        "status": "planned",
        "session_kind": "race",
        "distance_meters": 21097,
        "duration_minutes": 120,
        "intensity": "race",
    }

    proposal = RunningPlanAdaptationService().build(
        source_session=source,
        outcome={
            "outcome": "under",
            "recommended_action": "ease_next",
        },
        plan_sessions=[
            source,
            quality,
            race,
        ],
        adaptation_history=[],
    )

    assert (
        proposal["adaptation_required"]
        is False
    )
    assert "taper" in proposal["message"]
