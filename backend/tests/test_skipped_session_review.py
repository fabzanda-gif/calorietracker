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
