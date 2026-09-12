from datetime import date

from backend.api.dependencies import CurrentUser
from backend.api.routers.activities import (
    RunningTrainingPlanCreate,
    preview_running_training_plan,
)


def test_running_plan_preview_builds_without_persistence():
    request = RunningTrainingPlanCreate(
        start_date=date(2026, 9, 5),
        target_date=date(2027, 3, 5),
        current_distance_meters=5000,
        current_pace_seconds_per_km=360,
        target_distance_meters=21100,
        target_pace_seconds_per_km=300,
        sessions_per_week=3,
        long_run_weekday=6,
    )

    response = preview_running_training_plan(
        request=request,
        current_user=CurrentUser(
            id="user-1",
            access_token="test-token",
        ),
    )

    assert response["preview"] is True
    assert response["total_weeks"] >= 8
    assert response["session_count"] > 0
    assert len(response["sessions"]) == (
        response["session_count"]
    )
