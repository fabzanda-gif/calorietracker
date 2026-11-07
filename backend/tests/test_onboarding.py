from __future__ import annotations

from backend.api.dependencies import CurrentUser
from backend.api.core_main import app as core_app
from backend.api.routers import onboarding


class FakeOnboardingRepo:
    def __init__(self):
        self.preferences = None
        self.nutrition = None
        self.training = None
        self.days: list[int] = []
        self.muscles: list[str] = []

    def get_preferences(self, user_id):
        return (
            dict(self.preferences)
            if self.preferences
            else None
        )

    def get_nutrition_profile(self, user_id):
        return (
            dict(self.nutrition)
            if self.nutrition
            else None
        )

    def get_training_profile(self, user_id):
        return (
            dict(self.training)
            if self.training
            else None
        )

    def list_preferred_days(self, user_id):
        return list(self.days)

    def list_muscle_priorities(self, user_id):
        return list(self.muscles)

    def upsert_preferences(self, payload):
        self.preferences = dict(payload)
        return dict(payload)

    def upsert_nutrition_profile(self, payload):
        self.nutrition = dict(payload)
        return dict(payload)

    def upsert_training_profile(self, payload):
        self.training = dict(payload)
        return dict(payload)

    def replace_preferred_days(self, user_id, weekdays):
        self.days = list(weekdays)

    def replace_muscle_priorities(
        self,
        user_id,
        muscle_keys,
    ):
        self.muscles = list(muscle_keys)


def user(metadata=None):
    return CurrentUser(
        id="user-1",
        access_token="token",
        metadata=metadata or {},
    )


def test_new_user_status_starts_at_core():
    result = onboarding.get_onboarding_status(
        current_user=user(),
        repo=FakeOnboardingRepo(),
    )

    assert result["completed"] is False
    assert result["next_step"] == "core"
    assert result["version"] == 2


def test_legacy_food_user_is_grandfathered():
    result = onboarding.get_onboarding_status(
        current_user=user(
            {
                "gender": "male",
                "birth_date": "1990-01-01",
                "height": 180,
                "goal_mode": "maintenance",
            }
        ),
        repo=FakeOnboardingRepo(),
    )

    assert result["completed"] is True
    assert result["source"] == "legacy"
    assert result["preferences"]["food_enabled"] is True
    assert (
        result["preferences"]["training_enabled"]
        is False
    )



def test_v1_preferences_never_force_new_training_setup():
    repo = FakeOnboardingRepo()
    repo.preferences = {
        "user_id": "user-1",
        "onboarding_version": 1,
        "primary_goal": "strength",
        "food_enabled": True,
        "training_enabled": True,
        "core_onboarding_completed": True,
        "food_setup_completed": True,
        "training_setup_completed": False,
        "last_step": "training_setup",
    }

    result = onboarding.get_onboarding_status(
        current_user=user(),
        repo=repo,
    )

    assert result["completed"] is True
    assert result["next_step"] is None

def test_training_only_core_skips_food_setup():
    repo = FakeOnboardingRepo()

    result = onboarding.save_core_onboarding(
        onboarding.CoreOnboardingUpdate(
            primary_goal="strength",
            food_enabled=False,
            training_enabled=True,
        ),
        current_user=user(),
        repo=repo,
    )

    assert result["completed"] is False
    assert result["next_step"] == "training_setup"
    assert repo.preferences["primary_goal"] == "strength"


def test_food_setup_moves_both_user_to_training():
    repo = FakeOnboardingRepo()
    repo.preferences = {
        "user_id": "user-1",
        "onboarding_version": 2,
        "primary_goal": "hypertrophy",
        "food_enabled": True,
        "training_enabled": True,
        "core_onboarding_completed": True,
        "food_setup_completed": False,
        "training_setup_completed": False,
        "last_step": "food_setup",
    }

    result = onboarding.save_nutrition_setup(
        onboarding.NutritionSetupRequest(
            weight_strategy="gain",
            target_weight_kg=82,
            calorie_adjustment_kcal=300,
            protein_target_mode="automatic",
            protein_target_g=None,
            macro_tracking_enabled=True,
        ),
        current_user=user(),
        repo=repo,
    )

    assert result["next_step"] == "training_setup"
    assert repo.preferences["food_setup_completed"] is True
    assert repo.nutrition["weight_strategy"] == "gain"


def test_training_setup_completes_training_only():
    repo = FakeOnboardingRepo()
    repo.preferences = {
        "user_id": "user-1",
        "onboarding_version": 2,
        "primary_goal": "strength",
        "food_enabled": False,
        "training_enabled": True,
        "core_onboarding_completed": True,
        "food_setup_completed": False,
        "training_setup_completed": False,
        "last_step": "training_setup",
    }

    result = onboarding.save_training_setup(
        onboarding.TrainingSetupRequest(
            experience_level="intermediate",
            sessions_per_week=3,
            session_duration_minutes=60,
            planning_horizon="weekly",
            environment="commercial_gym",
            coach_style="balanced",
            feedback_mode="simple",
            schedule_flexibility="fixed",
            preferred_days=[1, 3, 5],
            priority_muscles=[
                "back",
                "shoulders",
            ],
        ),
        current_user=user(),
        repo=repo,
    )

    assert result["completed"] is True
    assert result["next_step"] is None
    assert (
        repo.preferences["training_setup_completed"]
        is True
    )
    assert repo.days == [1, 3, 5]
    assert repo.muscles == [
        "back",
        "shoulders",
    ]


def test_core_backend_exposes_onboarding_routes():
    paths = {
        path
        for route in core_app.routes
        if (path := getattr(route, "path", None))
    }

    assert "/onboarding/status" in paths
    assert "/onboarding/core" in paths
    assert "/onboarding/nutrition" in paths
    assert "/onboarding/training" in paths
