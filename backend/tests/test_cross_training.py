from __future__ import annotations

from datetime import date

from backend.api.dependencies import CurrentUser
from backend.api.main import app
from backend.api.routers.cross_training import get_cross_training_timeline
from backend.services.cross_training import CrossTrainingService


def timeline(**kwargs):
    args = {
        "start_date": date(2026, 11, 9),
        "days": 7,
        "planned_running": [],
        "planned_strength": [],
        "actual_activities": [],
        "completed_strength": [],
    }
    args.update(kwargs)
    return CrossTrainingService().build(**args)


def test_completed_linked_run_does_not_double_count_planned_run():
    result = timeline(
        planned_running=[
            {"id": "run-1", "scheduled_date": "2026-11-09",
             "status": "planned", "activity_type": "running",
             "session_kind": "tempo", "intensity": "hard"},
        ],
        actual_activities=[
            {"id": "actual-1", "date": "2026-11-09",
             "activity_type": "running", "planned_activity_id": "run-1",
             "duration_seconds": 3600, "distance_meters": 12000},
        ],
    )
    assert result["summary"]["running_sessions"] == 1
    assert result["timeline"][0]["events"][0]["status"] == "completed"


def test_completed_gym_does_not_double_count_planned_gym():
    result = timeline(
        planned_strength=[
            {"id": "gym-1", "scheduled_date": "2026-11-09",
             "status": "planned", "focus": "lower"},
        ],
        completed_strength=[
            {"id": "log-1", "strength_workout_id": "gym-1",
             "performed_date": "2026-11-09", "status": "completed"},
        ],
    )
    assert result["summary"]["strength_sessions"] == 1
    assert result["timeline"][0]["events"][0]["status"] == "completed"


def test_lower_gym_and_quality_run_same_day_flagged_without_auto_changes():
    result = timeline(
        planned_strength=[
            {"id": "gym-1", "scheduled_date": "2026-11-09",
             "status": "planned", "focus": "lower"},
        ],
        planned_running=[
            {"id": "run-1", "scheduled_date": "2026-11-09",
             "status": "planned", "activity_type": "running",
             "session_kind": "interval", "intensity": "hard"},
        ],
        priority="running",
    )
    assert result["summary"]["potential_conflicts"] == 1
    conflict = result["conflicts"][0]
    assert conflict["severity"] == "high"
    assert conflict["gap_days"] == 0
    assert conflict["requires_confirmation"] is True
    assert result["policy"]["auto_rescheduled"] is False
    assert result["policy"]["auto_changed_load"] is False


def test_upper_gym_and_easy_run_not_flagged():
    result = timeline(
        planned_strength=[
            {"id": "gym-1", "scheduled_date": "2026-11-09",
             "status": "planned", "focus": "upper"},
        ],
        planned_running=[
            {"id": "run-1", "scheduled_date": "2026-11-09",
             "status": "planned", "activity_type": "running",
             "session_kind": "easy", "intensity": "low"},
        ],
    )
    assert result["conflicts"] == []



def test_completed_lower_gym_near_planned_quality_run_is_flagged():
    result = timeline(
        completed_strength=[
            {"id": "log", "performed_date": "2026-11-09",
             "strength_workout_id": "gym-1", "status": "completed"},
        ],
        planned_strength=[
            {"id": "gym-1", "scheduled_date": "2026-11-09",
             "status": "completed", "focus": "lower",
             "title": "Lower A"},
        ],
        planned_running=[
            {"id": "run-1", "scheduled_date": "2026-11-10",
             "status": "planned", "activity_type": "running",
             "session_kind": "tempo", "intensity": "hard"},
        ],
    )
    assert result["summary"]["strength_sessions"] == 1
    assert result["conflicts"][0]["severity"] == "moderate"


def test_unverified_completed_gym_scope_is_not_assumed_to_be_lower_body():
    result = timeline(
        completed_strength=[
            {"id": "log", "performed_date": "2026-11-09",
             "strength_workout_id": "unknown", "status": "completed"},
        ],
        planned_running=[
            {"id": "run-1", "scheduled_date": "2026-11-09",
             "status": "planned", "activity_type": "running",
             "session_kind": "interval", "intensity": "hard"},
        ],
    )
    assert result["conflicts"] == []
    assert result["summary"]["strength_sessions"] == 1


def test_malformed_running_numbers_do_not_crash_timeline():
    result = timeline(actual_activities=[
        {"id": "run-1", "date": "2026-11-09",
         "activity_type": "running", "duration_seconds": "oops",
         "distance_meters": None},
    ])
    assert result["summary"]["running_sessions"] == 1
    assert result["timeline"][0]["events"][0]["quality"] is False


def test_race_is_protected_and_gym_is_only_reviewable_target():
    result = timeline(
        planned_strength=[
            {"id": "gym-1", "scheduled_date": "2026-11-10",
             "status": "planned", "focus": "lower"},
        ],
        planned_running=[
            {"id": "race", "scheduled_date": "2026-11-11",
             "status": "planned", "activity_type": "running",
             "session_kind": "race", "intensity": "race"},
        ],
    )
    assert result["conflicts"][0]["race_protected"] is True
    assert result["conflicts"][0]["suggested_action"] == "review_gym_schedule"
    assert result["policy"]["races_unchanged"] is True


def test_skipped_cancelled_non_running_and_unknown_gym_are_not_false_conflicts():
    result = timeline(
        planned_strength=[
            {"id": "gym-1", "scheduled_date": "2026-11-09",
             "status": "cancelled", "focus": "lower"},
        ],
        planned_running=[
            {"id": "run-1", "scheduled_date": "2026-11-09",
             "status": "skipped", "activity_type": "running",
             "session_kind": "race"},
            {"id": "bike-1", "scheduled_date": "2026-11-09",
             "status": "planned", "activity_type": "cycling",
             "intensity": "hard"},
        ],
        actual_activities=[
            {"id": "steps", "date": "2026-11-09",
             "activity_type": "steps"},
        ],
        completed_strength=[
            {"id": "log", "performed_date": "2026-11-09",
             "status": "completed"},
        ],
    )
    assert result["summary"] == {
        "running_sessions": 0, "strength_sessions": 1,
        "potential_conflicts": 0,
    }


class FakeRangeRepo:
    def __init__(self):
        self.calls = []

    def list_date_range(self, owner, start, end):
        self.calls.append((owner, str(start), str(end)))
        return []

    def list_range(self, owner, start, end):
        self.calls.append((owner, str(start), str(end)))
        return []


class FakePriority:
    def get_priority(self, owner):
        assert owner == "user-1"
        return "gym"


def test_route_is_owner_scoped_and_read_only():
    planned, strength, actual, logs = (FakeRangeRepo() for _ in range(4))
    result = get_cross_training_timeline(
        start_date=date(2026, 11, 9),
        days=7,
        current_user=CurrentUser(id="user-1", access_token="token"),
        planned_repo=planned,
        strength_repo=strength,
        activities_repo=actual,
        logs_repo=logs,
        preferences_repo=FakePriority(),
    )
    assert result["priority"] == "gym"
    assert len(result["timeline"]) == 7
    assert result["policy"]["read_only"] is True
    assert "/cross-training/timeline" in app.openapi()["paths"]
    for repo in (planned, strength, actual, logs):
        assert repo.calls == [("user-1", "2026-11-09", "2026-11-15")]
