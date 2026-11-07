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
