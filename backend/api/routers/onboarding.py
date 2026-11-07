from __future__ import annotations

from datetime import datetime, timezone
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field, model_validator

from backend.api.dependencies import (
    CurrentUser,
    get_current_user,
    get_onboarding_repository,
)
from backend.repositories.base import RepositoryError
from backend.repositories.onboarding import OnboardingRepository


router = APIRouter(
    prefix="/onboarding",
    tags=["onboarding"],
)


PrimaryGoal = Literal[
    "hypertrophy",
    "strength",
    "general_fitness",
]

MuscleKey = Literal[
    "chest",
    "back",
    "shoulders",
    "biceps",
    "triceps",
    "glutes",
    "quadriceps",
    "hamstrings",
    "calves",
    "core",
]


class CoreOnboardingUpdate(BaseModel):
    primary_goal: PrimaryGoal
    food_enabled: bool
    training_enabled: bool

    @model_validator(mode="after")
    def validate_modules(self):
        if not self.food_enabled and not self.training_enabled:
            raise ValueError(
                "Select at least one SanoSync module"
            )
        return self


class NutritionSetupRequest(BaseModel):
    weight_strategy: Literal[
        "loss",
        "maintenance",
        "gain",
    ]
    target_weight_kg: float | None = Field(
        default=None,
        gt=0,
    )
    calorie_adjustment_kcal: float = Field(
        default=0,
        ge=0,
        le=1500,
    )
    protein_target_mode: Literal[
        "automatic",
        "manual",
        "disabled",
    ] = "automatic"
    protein_target_g: float | None = Field(
        default=None,
        gt=0,
        le=500,
    )
    macro_tracking_enabled: bool = True

    @model_validator(mode="after")
    def validate_protein_target(self):
        if (
            self.protein_target_mode == "manual"
            and self.protein_target_g is None
        ):
            raise ValueError(
                "Manual protein target requires protein_target_g"
            )
        return self


class TrainingSetupRequest(BaseModel):
    experience_level: Literal[
        "beginner",
        "intermediate",
        "advanced",
    ]
    sessions_per_week: int = Field(
        ge=2,
        le=6,
    )
    session_duration_minutes: int = Field(
        ge=20,
        le=180,
    )
    planning_horizon: Literal[
        "weekly",
        "monthly",
    ]
    environment: Literal[
        "commercial_gym",
    ] = "commercial_gym"
    coach_style: Literal[
        "conservative",
        "balanced",
        "ambitious",
    ] = "balanced"
    feedback_mode: Literal[
        "simple",
        "advanced",
    ] = "simple"
    schedule_flexibility: Literal[
        "fixed",
        "flexible",
    ] = "flexible"
    preferred_days: list[int] = Field(
        default_factory=list,
        max_length=7,
    )
    priority_muscles: list[MuscleKey] = Field(
        default_factory=list,
        max_length=3,
    )

    @model_validator(mode="after")
    def validate_lists(self):
        if len(set(self.preferred_days)) != len(
            self.preferred_days
        ):
            raise ValueError(
                "Preferred training days must be unique"
            )

        if any(
            weekday < 1 or weekday > 7
            for weekday in self.preferred_days
        ):
            raise ValueError(
                "Preferred training days must be between 1 and 7"
            )

        if len(set(self.priority_muscles)) != len(
            self.priority_muscles
        ):
            raise ValueError(
                "Priority muscles must be unique"
            )

        return self


def _legacy_food_complete(
    current_user: CurrentUser,
) -> bool:
    metadata = current_user.metadata or {}

    return bool(
        str(metadata.get("gender") or "").strip()
        and str(
            metadata.get("birth_date") or ""
        ).strip()
        and metadata.get("height") not in (
            None,
            "",
        )
        and (
            str(
                metadata.get("goal_mode") or ""
            ).strip()
            or str(
                metadata.get("deficit_plan") or ""
            ).strip()
        )
    )


def _next_step(
    preferences: dict,
) -> str | None:
    if not preferences.get(
        "core_onboarding_completed"
    ):
        return "core"

    if (
        preferences.get("food_enabled")
        and not preferences.get(
            "food_setup_completed"
        )
    ):
        return "food_setup"

    if (
        preferences.get("training_enabled")
        and not preferences.get(
            "training_setup_completed"
        )
    ):
        return "training_setup"

    return None


def _status_payload(
    *,
    current_user: CurrentUser,
    repo: OnboardingRepository,
) -> dict:
    preferences = repo.get_preferences(
        current_user.id
    )

    if preferences is None:
        if _legacy_food_complete(current_user):
            return {
                "version": 1,
                "source": "legacy",
                "completed": True,
                "next_step": None,
                "preferences": {
                    "primary_goal": None,
                    "food_enabled": True,
                    "training_enabled": False,
                    "core_onboarding_completed": True,
                    "food_setup_completed": True,
                    "training_setup_completed": False,
                },
                "nutrition_profile": None,
                "training_profile": None,
                "preferred_days": [],
                "priority_muscles": [],
            }

        return {
            "version": 2,
            "source": "v2",
            "completed": False,
            "next_step": "core",
            "preferences": None,
            "nutrition_profile": None,
            "training_profile": None,
            "preferred_days": [],
            "priority_muscles": [],
        }

    next_step = _next_step(preferences)

    training_profile = (
        repo.get_training_profile(
            current_user.id
        )
        if preferences.get(
            "training_setup_completed"
        )
        else None
    )

    nutrition_profile = (
        repo.get_nutrition_profile(
            current_user.id
        )
        if preferences.get(
            "food_setup_completed"
        )
        else None
    )

    preferred_days = (
        repo.list_preferred_days(
            current_user.id
        )
        if training_profile
        else []
    )

    priority_muscles = (
        repo.list_muscle_priorities(
            current_user.id
        )
        if training_profile
        else []
    )

    return {
        "version": int(
            preferences.get(
                "onboarding_version"
            )
            or 2
        ),
        "source": "v2",
        "completed": next_step is None,
        "next_step": next_step,
        "preferences": preferences,
        "nutrition_profile": nutrition_profile,
        "training_profile": training_profile,
        "preferred_days": preferred_days,
        "priority_muscles": priority_muscles,
    }


@router.get("/status")
def get_onboarding_status(
    current_user: CurrentUser = Depends(
        get_current_user
    ),
    repo: OnboardingRepository = Depends(
        get_onboarding_repository
    ),
):
    try:
        return _status_payload(
            current_user=current_user,
            repo=repo,
        )
    except RepositoryError as exc:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=str(exc),
        ) from exc


@router.put("/core")
def save_core_onboarding(
    payload: CoreOnboardingUpdate,
    current_user: CurrentUser = Depends(
        get_current_user
    ),
    repo: OnboardingRepository = Depends(
        get_onboarding_repository
    ),
):
    try:
        existing = (
            repo.get_preferences(
                current_user.id
            )
            or {}
        )

        food_done = bool(
            existing.get(
                "food_setup_completed"
            )
        )
        training_done = bool(
            existing.get(
                "training_setup_completed"
            )
        )

        if payload.food_enabled and not food_done:
            next_step = "food_setup"
        elif (
            payload.training_enabled
            and not training_done
        ):
            next_step = "training_setup"
        else:
            next_step = "complete"

        repo.upsert_preferences(
            {
                "user_id": current_user.id,
                "onboarding_version": 2,
                "primary_goal":
                    payload.primary_goal,
                "food_enabled":
                    payload.food_enabled,
                "training_enabled":
                    payload.training_enabled,
                "core_onboarding_completed":
                    True,
                "food_setup_completed":
                    food_done,
                "training_setup_completed":
                    training_done,
                "last_step": next_step,
                "updated_at": datetime.now(
                    timezone.utc
                ).isoformat(),
            }
        )

        return _status_payload(
            current_user=current_user,
            repo=repo,
        )

    except RepositoryError as exc:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=str(exc),
        ) from exc


@router.put("/nutrition")
def save_nutrition_setup(
    payload: NutritionSetupRequest,
    current_user: CurrentUser = Depends(
        get_current_user
    ),
    repo: OnboardingRepository = Depends(
        get_onboarding_repository
    ),
):
    try:
        preferences = repo.get_preferences(
            current_user.id
        )

        if not preferences or not preferences.get(
            "core_onboarding_completed"
        ):
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Complete the core onboarding first",
            )

        if not preferences.get("food_enabled"):
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Food module is not enabled",
            )

        repo.upsert_nutrition_profile(
            {
                "user_id": current_user.id,
                **payload.model_dump(),
                "updated_at": datetime.now(
                    timezone.utc
                ).isoformat(),
            }
        )

        training_pending = bool(
            preferences.get("training_enabled")
            and not preferences.get(
                "training_setup_completed"
            )
        )

        repo.upsert_preferences(
            {
                **preferences,
                "user_id": current_user.id,
                "food_setup_completed": True,
                "last_step": (
                    "training_setup"
                    if training_pending
                    else "complete"
                ),
                "updated_at": datetime.now(
                    timezone.utc
                ).isoformat(),
            }
        )

        return _status_payload(
            current_user=current_user,
            repo=repo,
        )

    except HTTPException:
        raise
    except RepositoryError as exc:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=str(exc),
        ) from exc


@router.put("/training")
def save_training_setup(
    payload: TrainingSetupRequest,
    current_user: CurrentUser = Depends(
        get_current_user
    ),
    repo: OnboardingRepository = Depends(
        get_onboarding_repository
    ),
):
    try:
        preferences = repo.get_preferences(
            current_user.id
        )

        if not preferences or not preferences.get(
            "core_onboarding_completed"
        ):
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Complete the core onboarding first",
            )

        if not preferences.get(
            "training_enabled"
        ):
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Training module is not enabled",
            )

        profile_payload = payload.model_dump(
            exclude={
                "preferred_days",
                "priority_muscles",
            }
        )

        repo.upsert_training_profile(
            {
                "user_id": current_user.id,
                **profile_payload,
                "updated_at": datetime.now(
                    timezone.utc
                ).isoformat(),
            }
        )

        repo.replace_preferred_days(
            current_user.id,
            sorted(payload.preferred_days),
        )
        repo.replace_muscle_priorities(
            current_user.id,
            list(payload.priority_muscles),
        )

        repo.upsert_preferences(
            {
                **preferences,
                "user_id": current_user.id,
                "training_setup_completed": True,
                "last_step": "complete",
                "updated_at": datetime.now(
                    timezone.utc
                ).isoformat(),
            }
        )

        return _status_payload(
            current_user=current_user,
            repo=repo,
        )

    except HTTPException:
        raise
    except RepositoryError as exc:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=str(exc),
        ) from exc
