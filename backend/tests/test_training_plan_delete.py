from backend.api.dependencies import CurrentUser
from backend.api.routers.activities import (
    delete_training_plan,
)


class FakeTrainingPlansRepository:
    def __init__(self):
        self.deleted = None

    def delete(
        self,
        plan_id,
        user_id,
    ):
        self.deleted = (
            plan_id,
            user_id,
        )
        return True


def test_delete_training_plan_uses_current_user():
    repo = FakeTrainingPlansRepository()

    response = delete_training_plan(
        plan_id="plan-1",
        current_user=CurrentUser(
            id="user-1",
            access_token="token",
        ),
        repo=repo,
    )

    assert repo.deleted == (
        "plan-1",
        "user-1",
    )

    assert response == {
        "deleted": True,
        "id": "plan-1",
    }
