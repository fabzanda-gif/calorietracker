from backend.services.running_plan_adaptation import (
    RunningPlanAdaptationService,
)


def session(**overrides):
    item = {
        "id": "session-1",
        "training_plan_id": "plan-1",
        "scheduled_date": "2026-09-06",
        "scheduled_time": None,
        "status": "planned",
        "title": "Tempo 8 km",
        "session_kind": "tempo",
        "training_week": 3,
        "distance_meters": 8000,
        "duration_minutes": 48,
        "intensity": "hard",
    }
    item.update(overrides)
    return item


def outcome(
    kind="under",
    action="ease_next",
):
    return {
        "outcome": kind,
        "recommended_action": action,
    }


def test_under_reduces_next_quality_by_ten_percent():
    source = session(
        id="source",
        scheduled_date="2026-09-01",
        status="completed",
    )

    target = session(
        id="target",
        scheduled_date="2026-09-08",
    )

    result = RunningPlanAdaptationService().build(
        source_session=source,
        outcome=outcome(),
        plan_sessions=[source, target],
    )

    assert result["adaptation_required"] is True
    assert result["target"]["id"] == "target"
    assert result["changes"]["distance_meters"] == 7200
    assert result["changes"]["duration_minutes"] == 43


def test_skipped_reduces_next_quality_by_fifteen_percent():
    source = session(
        id="source",
        scheduled_date="2026-09-01",
        status="skipped",
    )

    target = session(
        id="target",
        scheduled_date="2026-09-08",
    )

    result = RunningPlanAdaptationService().build(
        source_session=source,
        outcome=outcome(
            kind="skipped",
            action="ease_next",
        ),
        plan_sessions=[source, target],
    )

    assert (
        result["changes"]["distance_meters"]
        == 6800
    )


def test_over_reduces_load_and_softens_hard_intensity():
    source = session(
        id="source",
        scheduled_date="2026-09-01",
        status="completed",
    )

    target = session(
        id="target",
        scheduled_date="2026-09-08",
        intensity="hard",
    )

    result = RunningPlanAdaptationService().build(
        source_session=source,
        outcome=outcome(
            kind="over",
            action="recover_next",
        ),
        plan_sessions=[source, target],
    )

    assert result["changes"]["distance_meters"] == 6800
    assert result["changes"]["intensity"] == "moderate"


def test_easy_session_is_skipped_when_choosing_target():
    source = session(
        id="source",
        scheduled_date="2026-09-01",
        status="completed",
    )

    easy = session(
        id="easy",
        scheduled_date="2026-09-03",
        session_kind="easy",
    )

    quality = session(
        id="quality",
        scheduled_date="2026-09-05",
        session_kind="interval",
    )

    result = RunningPlanAdaptationService().build(
        source_session=source,
        outcome=outcome(),
        plan_sessions=[
            source,
            easy,
            quality,
        ],
    )

    assert result["target"]["id"] == "quality"


def test_race_is_not_selected_for_adaptation():
    source = session(
        id="source",
        scheduled_date="2026-09-01",
        status="completed",
    )

    race = session(
        id="race",
        scheduled_date="2026-09-05",
        session_kind="race",
    )

    result = RunningPlanAdaptationService().build(
        source_session=source,
        outcome=outcome(),
        plan_sessions=[source, race],
    )

    assert result["adaptation_required"] is False
    assert result["target"] is None


def test_on_target_does_not_propose_change():
    source = session(
        id="source",
        scheduled_date="2026-09-01",
        status="completed",
    )

    target = session(
        id="target",
        scheduled_date="2026-09-08",
    )

    result = RunningPlanAdaptationService().build(
        source_session=source,
        outcome=outcome(
            kind="on_target",
            action="keep_plan",
        ),
        plan_sessions=[source, target],
    )

    assert result["adaptation_required"] is False
    assert result["changes"] == {}


def test_past_quality_session_is_not_selected():
    source = session(
        id="source",
        scheduled_date="2026-09-10",
        status="completed",
    )

    past = session(
        id="past",
        scheduled_date="2026-09-08",
    )

    future = session(
        id="future",
        scheduled_date="2026-09-12",
    )

    result = RunningPlanAdaptationService().build(
        source_session=source,
        outcome=outcome(),
        plan_sessions=[
            past,
            source,
            future,
        ],
    )

    assert result["target"]["id"] == "future"
