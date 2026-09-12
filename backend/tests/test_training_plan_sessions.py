from backend.api.dependencies import CurrentUser
from backend.api.routers.activities import (
    list_training_plan_sessions,
)


class FakePlannedActivitiesRepository:
    def __init__(self):
        self.called_with = None

    def list_for_training_plan(
        self,
        user_id,
        plan_id,
    ):
        self.called_with = (
            user_id,
            plan_id,
        )

        return [
            {
                "id": "session-1",
                "training_plan_id": plan_id,
                "training_week": 1,
                "session_kind": "easy",
                "scheduled_date": "2026-09-08",
            },
            {
                "id": "session-2",
                "training_plan_id": plan_id,
                "training_week": 1,
                "session_kind": "long",
                "scheduled_date": "2026-09-13",
            },
        ]


def test_list_training_plan_sessions_uses_current_user():
    repo = FakePlannedActivitiesRepository()

    response = list_training_plan_sessions(
        plan_id="plan-1",
        current_user=CurrentUser(
            id="user-1",
            access_token="token",
        ),
        repo=repo,
    )

    assert repo.called_with == (
        "user-1",
        "plan-1",
    )

    assert response["count"] == 2
    assert len(response["items"]) == 2
    assert response["items"][0][
        "training_week"
    ] == 1
