from datetime import date

from backend.services.skipped_session_review import (
    SkippedSessionReviewService,
)


def test_skipped_sessions_are_returned_for_review():
    alerts = SkippedSessionReviewService().build(
        as_of=date(2026, 11, 7),
        running_sessions=[
            {
                "id": "run-1",
                "scheduled_date": "2026-11-06",
                "status": "skipped",
                "title": "Easy run",
            },
            {
                "id": "run-2",
                "scheduled_date": "2026-11-07",
                "status": "planned",
                "title": "Planned run",
            },
        ],
        strength_workouts=[
            {
                "id": "gym-1",
                "scheduled_date": "2026-11-05",
                "status": "skipped",
                "title": "Lower A",
            },
        ],
    )

    assert {item["session_id"] for item in alerts} == {
        "run-1",
        "gym-1",
    }
    assert all(item["requires_approval"] for item in alerts)


def test_future_skipped_and_invalid_dates_are_ignored():
    alerts = SkippedSessionReviewService().build(
        as_of=date(2026, 11, 7),
        running_sessions=[
            {
                "id": "future",
                "scheduled_date": "2026-11-09",
                "status": "skipped",
            },
            {
                "id": "invalid",
                "scheduled_date": "not-a-date",
                "status": "skipped",
            },
        ],
        strength_workouts=[],
    )
    assert alerts == []


def test_skipped_race_does_not_suggest_automatic_reschedule():
    alerts = SkippedSessionReviewService().build(
        as_of=date(2026, 11, 7),
        running_sessions=[
            {
                "id": "race",
                "scheduled_date": "2026-11-06",
                "session_kind": "race",
                "status": "skipped",
            },
        ],
        strength_workouts=[],
    )

    assert len(alerts) == 1
    assert alerts[0]["requires_approval"] is True
    assert "gara" in alerts[0]["message"].casefold()


def test_recovery_date_avoids_planned_sessions_and_recovery_days():
    alerts = SkippedSessionReviewService().build(
        as_of=date(2026, 11, 7),
        running_sessions=[{
            "id": "skipped-run",
            "scheduled_date": "2026-11-06",
            "status": "skipped",
        }],
        strength_workouts=[],
        upcoming_running=[{
            "id": "planned-run",
            "scheduled_date": "2026-11-09",
            "status": "planned",
        }],
        upcoming_strength=[],
    )
    assert alerts[0]["suggested_date"] == "2026-11-11"


def test_no_recovery_date_when_calendar_is_full():
    alerts = SkippedSessionReviewService().build(
        as_of=date(2026, 11, 7),
        running_sessions=[{
            "id": "skipped-run",
            "scheduled_date": "2026-11-06",
            "status": "skipped",
        }],
        strength_workouts=[],
        upcoming_running=[{
            "id": f"planned-{index}",
            "scheduled_date": date(2026, 11, 8 + index).isoformat(),
            "status": "planned",
        } for index in range(7)],
        upcoming_strength=[],
    )
    assert alerts[0]["suggested_date"] is None


def test_race_has_no_recovery_date():
    alerts = SkippedSessionReviewService().build(
        as_of=date(2026, 11, 7),
        running_sessions=[{
            "id": "race",
            "scheduled_date": "2026-11-06",
            "status": "skipped",
            "session_kind": "race",
        }],
        strength_workouts=[],
    )
    assert alerts[0]["suggested_date"] is None


def test_easy_run_can_use_a_day_next_to_another_easy_run():
    alerts = SkippedSessionReviewService().build(
        as_of=date(2026, 11, 7),
        running_sessions=[{
            "id": "easy-missed",
            "status": "skipped",
            "scheduled_date": "2026-11-06",
            "session_kind": "easy",
            "intensity": "low",
        }],
        strength_workouts=[],
        upcoming_running=[{
            "id": "easy-planned",
            "status": "planned",
            "scheduled_date": "2026-11-09",
            "session_kind": "easy",
            "intensity": "low",
        }],
    )
    assert alerts[0]["suggested_date"] == "2026-11-08"


def test_hard_run_needs_more_space_from_planned_training():
    alerts = SkippedSessionReviewService().build(
        as_of=date(2026, 11, 7),
        running_sessions=[{
            "id": "tempo-missed",
            "status": "skipped",
            "scheduled_date": "2026-11-06",
            "session_kind": "tempo",
            "intensity": "hard",
        }],
        strength_workouts=[],
        upcoming_strength=[{
            "id": "gym-planned",
            "status": "planned",
            "scheduled_date": "2026-11-09",
            "focus": "lower",
        }],
    )
    assert alerts[0]["recovery_days"] == 2
    assert alerts[0]["suggested_date"] == "2026-11-12"


def test_planned_intense_run_requires_extra_separation():
    alerts = SkippedSessionReviewService().build(
        as_of=date(2026, 11, 7),
        running_sessions=[{
            "id": "missed",
            "status": "skipped",
            "scheduled_date": "2026-11-06",
        }],
        strength_workouts=[],
        upcoming_running=[{
            "id": "interval-planned",
            "status": "planned",
            "scheduled_date": "2026-11-10",
            "session_kind": "intervals",
        }],
    )
    assert alerts[0]["suggested_date"] == "2026-11-13"


def test_skipped_lower_workout_uses_more_recovery_than_upper():
    common = {
        "as_of": date(2026, 11, 7),
        "running_sessions": [],
        "upcoming_running": [{
            "id": "planned-easy",
            "status": "planned",
            "scheduled_date": "2026-11-10",
            "intensity": "low",
        }],
    }
    service = SkippedSessionReviewService()
    lower = service.build(**common, strength_workouts=[{
        "id": "lower",
        "scheduled_date": "2026-11-06",
        "status": "skipped",
        "focus": "lower",
    }])[0]
    upper = service.build(**common, strength_workouts=[{
        "id": "upper",
        "scheduled_date": "2026-11-06",
        "status": "skipped",
        "focus": "upper",
    }])[0]
    assert lower["recovery_days"] == 2
    assert upper["recovery_days"] == 1


def test_recorded_hard_run_blocks_next_day_recovery():
    alerts = SkippedSessionReviewService().build(
        as_of=date(2026, 11, 7),
        running_sessions=[{
            "id": "missed",
            "status": "skipped",
            "scheduled_date": "2026-11-06",
            "session_kind": "easy",
            "intensity": "low",
        }],
        strength_workouts=[],
        recent_events=[{
            "date": "2026-11-07",
            "modality": "running",
            "scope": "lower",
            "intensity": "high",
            "load_score": 140,
        }],
    )
    assert alerts[0]["suggested_date"] == "2026-11-10"


def test_completed_hard_lower_workout_delays_light_run():
    alerts = SkippedSessionReviewService().build(
        as_of=date(2026, 11, 7),
        running_sessions=[{
            "id": "missed",
            "status": "skipped",
            "scheduled_date": "2026-11-05",
            "session_kind": "easy",
            "intensity": "low",
        }],
        strength_workouts=[],
        recent_events=[{
            "date": "2026-11-07",
            "modality": "strength",
            "scope": "lower",
            "intensity": "high",
            "load_score": 125,
        }],
    )
    assert alerts[0]["suggested_date"] == "2026-11-10"


def test_upper_body_workout_does_not_delay_light_run():
    alerts = SkippedSessionReviewService().build(
        as_of=date(2026, 11, 7),
        running_sessions=[{
            "id": "missed",
            "status": "skipped",
            "scheduled_date": "2026-11-06",
            "session_kind": "easy",
            "intensity": "low",
        }],
        strength_workouts=[],
        recent_events=[{
            "date": "2026-11-07",
            "modality": "strength",
            "scope": "upper",
            "intensity": "high",
            "load_score": 125,
        }],
    )
    assert alerts[0]["suggested_date"] == "2026-11-08"


def test_draft_and_missing_training_events_have_no_effect():
    alerts = SkippedSessionReviewService().build(
        as_of=date(2026, 11, 7),
        running_sessions=[{
            "id": "missed",
            "status": "skipped",
            "scheduled_date": "2026-11-06",
            "session_kind": "easy",
            "intensity": "low",
        }],
        strength_workouts=[],
        recent_events=[{
            "date": "not-a-date",
            "scope": "lower",
            "intensity": "high",
        }],
    )
    assert alerts[0]["suggested_date"] == "2026-11-08"
