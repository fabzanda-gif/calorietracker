from backend.services.running_plan_adaptation import (
    RunningPlanAdaptationService,
)


def session(**overrides):
    item = {
        "id": "source",
        "training_plan_id": "plan-1",
        "scheduled_date": "2026-09-01",
        "scheduled_time": None,
        "status": "completed",
        "title": "Tempo",
        "session_kind": "tempo",
        "training_week": 3,
        "distance_meters": 8000,
        "duration_minutes": 48,
        "intensity": "hard",
    }
    item.update(overrides)
    return item


def under():
    return {
        "outcome": "under",
        "recommended_action": "ease_next",
    }


def build(history, sessions=None):
    source = session()

    target = session(
        id="target",
        scheduled_date="2026-09-08",
        status="planned",
    )

    return RunningPlanAdaptationService().build(
        source_session=source,
        outcome=under(),
        plan_sessions=(
            sessions
            if sessions is not None
            else [source, target]
        ),
        adaptation_history=history,
    )


def test_same_source_is_not_proposed_twice_after_apply():
    result = build([
        {
            "source_planned_activity_id": "source",
            "target_planned_activity_id": "old-target",
            "decision": "applied",
        }
    ])

    assert result["adaptation_required"] is False


def test_same_source_is_not_proposed_twice_after_keep():
    result = build([
        {
            "source_planned_activity_id": "source",
            "decision": "kept",
        }
    ])

    assert result["adaptation_required"] is False


def test_same_target_is_never_adapted_twice():
    result = build([
        {
            "source_planned_activity_id": "older-source",
            "target_planned_activity_id": "target",
            "decision": "applied",
        }
    ])

    assert result["adaptation_required"] is False


def test_two_consecutive_applies_stop_third_reduction():
    result = build([
        {
            "source_planned_activity_id": "s2",
            "target_planned_activity_id": "t2",
            "decision": "applied",
        },
        {
            "source_planned_activity_id": "s1",
            "target_planned_activity_id": "t1",
            "decision": "applied",
        },
    ])

    assert result["adaptation_required"] is False
    assert "due volte" in result["message"]


def test_kept_decision_breaks_consecutive_apply_chain():
    result = build([
        {
            "source_planned_activity_id": "s3",
            "decision": "kept",
        },
        {
            "source_planned_activity_id": "s2",
            "decision": "applied",
        },
        {
            "source_planned_activity_id": "s1",
            "decision": "applied",
        },
    ])

    assert result["adaptation_required"] is True


def test_final_seven_days_before_race_are_locked():
    source = session()

    target = session(
        id="target",
        scheduled_date="2026-09-08",
        status="planned",
        session_kind="tempo",
    )

    race = session(
        id="race",
        scheduled_date="2026-09-14",
        status="planned",
        session_kind="race",
        intensity="race",
    )

    result = RunningPlanAdaptationService().build(
        source_session=source,
        outcome=under(),
        plan_sessions=[
            source,
            target,
            race,
        ],
        adaptation_history=[],
    )

    assert result["adaptation_required"] is False
    assert "taper" in result["message"]


def test_more_than_seven_days_before_race_can_adapt():
    source = session()

    target = session(
        id="target",
        scheduled_date="2026-09-06",
        status="planned",
        session_kind="tempo",
    )

    race = session(
        id="race",
        scheduled_date="2026-09-14",
        status="planned",
        session_kind="race",
        intensity="race",
    )

    result = RunningPlanAdaptationService().build(
        source_session=source,
        outcome=under(),
        plan_sessions=[
            source,
            target,
            race,
        ],
        adaptation_history=[],
    )

    assert result["adaptation_required"] is True
