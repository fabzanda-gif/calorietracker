from __future__ import annotations

import os
import hashlib
import threading
import time

import requests
import httpx
from dataclasses import dataclass, field
from functools import lru_cache
from typing import Any

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from supabase import Client, create_client
from supabase.client import ClientOptions

from backend.repositories.activities import ActivitiesRepository
from backend.repositories.daily_logs import DailyLogsRepository
from backend.repositories.day_briefings import DayBriefingsRepository
from backend.repositories.decision_selections import DecisionSelectionsRepository
from backend.repositories.ingredients import IngredientsRepository
from backend.repositories.meal_ingredients import MealIngredientsRepository
from backend.repositories.meal_prep import MealPrepRepository
from backend.repositories.meals import MealsRepository
from backend.repositories.pantry import PantryRepository
from backend.repositories.planned_activities import (
    PlannedActivitiesRepository,
)
from backend.repositories.oura_connections import (
    OuraConnectionsRepository,
)
from backend.repositories.recipe_ingredients import RecipeIngredientsRepository
from backend.repositories.recipes import RecipesRepository
from backend.repositories.training_plans import (
    TrainingPlansRepository,
)
from backend.repositories.strength_plans import (
    StrengthPlansRepository,
)
from backend.repositories.strength_workouts import (
    StrengthWorkoutsRepository,
    StrengthWorkoutExercisesRepository,
)
from backend.repositories.strength_logs import (
    StrengthSetLogsRepository,
    StrengthWorkoutLogsRepository,
)
from backend.repositories.strength_progression_history import (
    StrengthProgressionHistoryRepository,
)
from backend.repositories.training_plan_adaptations import (
    TrainingPlanAdaptationsRepository,
)
from backend.repositories.weight import WeightRepository
from backend.repositories.weekly_schedule import WeeklyScheduleRepository


bearer_scheme = HTTPBearer(auto_error=False)


@dataclass(frozen=True)
class CurrentUser:
    id: str
    access_token: str
    metadata: dict[str, Any] = field(default_factory=dict)


_AUTH_CACHE: dict[str, tuple[float, str, dict]] = {}
_AUTH_CACHE_LOCK = threading.Lock()
_AUTH_CACHE_TTL_SECONDS = 60.0


# Shared transport only:
# every authenticated Supabase client remains request-scoped,
# but TCP/TLS connections can be reused across requests.
_SHARED_SUPABASE_HTTP = httpx.Client(
    timeout=httpx.Timeout(
        20.0,
        connect=10.0,
    ),
    limits=httpx.Limits(
        max_connections=40,
        max_keepalive_connections=20,
        keepalive_expiry=30.0,
    ),
)


def _supabase_settings() -> tuple[str, str]:
    url = os.getenv("SUPABASE_URL")
    key = (
        os.getenv("SUPABASE_ANON_KEY")
        or os.getenv("SUPABASE_KEY")
    )

    if not url or not key:
        raise RuntimeError(
            "Missing SUPABASE_URL and SUPABASE_ANON_KEY "
            "(or SUPABASE_KEY) environment variables."
        )

    return url, key


@lru_cache(maxsize=1)
def get_supabase_client() -> Client:
    url, key = _supabase_settings()
    return create_client(url, key)


def get_current_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(
        bearer_scheme
    ),
) -> CurrentUser:
    if credentials is None or not credentials.credentials:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing bearer token",
            headers={"WWW-Authenticate": "Bearer"},
        )

    token = credentials.credentials
    token_key = hashlib.sha256(token.encode("utf-8")).hexdigest()
    now = time.monotonic()

    cached = _AUTH_CACHE.get(token_key)
    if cached and cached[0] > now:
        print(
            "[SUPA perf] auth cache hit",
            flush=True,
        )
        return CurrentUser(
            id=cached[1],
            access_token=token,
            metadata=dict(cached[2]),
        )

    # Una sola richiesta remota alla volta:
    # le chiamate parallele della Home aspettano la prima validazione.
    with _AUTH_CACHE_LOCK:
        now = time.monotonic()

        cached = _AUTH_CACHE.get(token_key)
        if cached and cached[0] > now:
            return CurrentUser(
                id=cached[1],
                access_token=token,
                metadata=dict(cached[2]),
            )

        try:
            auth_started_at = time.perf_counter()
            auth_response = get_supabase_client().auth.get_user(
                token
            )
            auth_elapsed_ms = (
                time.perf_counter() - auth_started_at
            ) * 1000

            print(
                f"[SUPA perf] auth remote: "
                f"{auth_elapsed_ms:.0f} ms",
                flush=True,
            )
        except Exception as exc:
            _AUTH_CACHE.pop(token_key, None)

            print(
                "AUTH DEBUG:",
                type(exc).__name__,
                str(exc),
                flush=True,
            )

            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid or expired token",
                headers={"WWW-Authenticate": "Bearer"},
            ) from exc

        user_obj = getattr(auth_response, "user", None)

        if user_obj is None:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid or expired token",
                headers={"WWW-Authenticate": "Bearer"},
            )

        user = {
            "id": getattr(user_obj, "id", None),
            "user_metadata": getattr(
                user_obj,
                "user_metadata",
                None,
            ),
        }

        user_id = user.get("id")

        if not user_id:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid or expired token",
                headers={"WWW-Authenticate": "Bearer"},
            )

        metadata = user.get("user_metadata") or {}

        _AUTH_CACHE[token_key] = (
            time.monotonic() + _AUTH_CACHE_TTL_SECONDS,
            str(user_id),
            dict(metadata),
        )

        # Pulizia minima delle entry scadute
        expired = [
            key_
            for key_, value in _AUTH_CACHE.items()
            if value[0] <= time.monotonic()
        ]
        for key_ in expired:
            _AUTH_CACHE.pop(key_, None)

        return CurrentUser(
            id=str(user_id),
            access_token=token,
            metadata=dict(metadata),
        )


@lru_cache(maxsize=1)
def get_admin_supabase_client() -> Client:
    url, _ = _supabase_settings()
    secret_key = os.getenv(
        "SUPABASE_SERVICE_ROLE_KEY"
    )

    if not secret_key:
        raise RuntimeError(
            "Missing SUPABASE_SERVICE_ROLE_KEY"
        )

    return create_client(
        url,
        secret_key,
    )


def get_authenticated_supabase(
    current_user: CurrentUser = Depends(get_current_user),
) -> Client:
    url, key = _supabase_settings()

    create_started_at = time.perf_counter()

    client = create_client(
        url,
        key,
        options=ClientOptions(
            httpx_client=_SHARED_SUPABASE_HTTP,
            auto_refresh_token=False,
            persist_session=False,
        ),
    )

    create_elapsed_ms = (
        time.perf_counter() - create_started_at
    ) * 1000

    auth_started_at = time.perf_counter()
    client.postgrest.auth(current_user.access_token)
    postgrest_auth_elapsed_ms = (
        time.perf_counter() - auth_started_at
    ) * 1000

    print(
        f"[SUPA perf] client create: "
        f"{create_elapsed_ms:.0f} ms "
        f"postgrest-auth: "
        f"{postgrest_auth_elapsed_ms:.0f} ms",
        flush=True,
    )

    return client


def get_oura_connections_repository(
    supabase: Client = Depends(
        get_admin_supabase_client
    ),
) -> OuraConnectionsRepository:
    return OuraConnectionsRepository(
        supabase
    )


def get_meals_repository(
    supabase: Client = Depends(get_authenticated_supabase),
) -> MealsRepository:
    return MealsRepository(supabase)


def get_meal_ingredients_repository(
    supabase: Client = Depends(get_authenticated_supabase),
) -> MealIngredientsRepository:
    return MealIngredientsRepository(supabase)


def get_activities_repository(
    supabase: Client = Depends(get_authenticated_supabase),
) -> ActivitiesRepository:
    return ActivitiesRepository(supabase)


def get_planned_activities_repository(
    supabase: Client = Depends(get_authenticated_supabase),
) -> PlannedActivitiesRepository:
    return PlannedActivitiesRepository(supabase)


def get_training_plans_repository(
    supabase: Client = Depends(get_authenticated_supabase),
) -> TrainingPlansRepository:
    return TrainingPlansRepository(supabase)



def get_strength_plans_repository(
    supabase: Client = Depends(
        get_authenticated_supabase
    ),
) -> StrengthPlansRepository:
    return StrengthPlansRepository(
        supabase
    )


def get_strength_workouts_repository(
    supabase: Client = Depends(
        get_authenticated_supabase
    ),
) -> StrengthWorkoutsRepository:
    return StrengthWorkoutsRepository(
        supabase
    )


def get_strength_workout_exercises_repository(
    supabase: Client = Depends(
        get_authenticated_supabase
    ),
) -> StrengthWorkoutExercisesRepository:
    return StrengthWorkoutExercisesRepository(
        supabase
    )



def get_strength_workout_logs_repository(
    supabase: Client = Depends(
        get_authenticated_supabase
    ),
) -> StrengthWorkoutLogsRepository:
    return StrengthWorkoutLogsRepository(
        supabase
    )


def get_strength_set_logs_repository(
    supabase: Client = Depends(
        get_authenticated_supabase
    ),
) -> StrengthSetLogsRepository:
    return StrengthSetLogsRepository(
        supabase
    )



def get_strength_progression_history_repository(
    supabase: Client = Depends(
        get_authenticated_supabase
    ),
) -> StrengthProgressionHistoryRepository:
    return StrengthProgressionHistoryRepository(
        supabase
    )


def get_training_plan_adaptations_repository(
    supabase: Client = Depends(get_authenticated_supabase),
) -> TrainingPlanAdaptationsRepository:
    return TrainingPlanAdaptationsRepository(
        supabase
    )


def get_weight_repository(
    supabase: Client = Depends(get_authenticated_supabase),
) -> WeightRepository:
    return WeightRepository(supabase)


def get_daily_logs_repository(
    supabase: Client = Depends(get_authenticated_supabase),
) -> DailyLogsRepository:
    return DailyLogsRepository(supabase)


def get_day_briefings_repository(
    supabase: Client = Depends(get_authenticated_supabase),
) -> DayBriefingsRepository:
    return DayBriefingsRepository(supabase)


def get_recipes_repository(
    supabase: Client = Depends(get_authenticated_supabase),
) -> RecipesRepository:
    return RecipesRepository(supabase)


def get_meal_prep_repository(
    supabase: Client = Depends(get_authenticated_supabase),
) -> MealPrepRepository:
    return MealPrepRepository(supabase)


def get_ingredients_repository(
    supabase: Client = Depends(get_authenticated_supabase),
) -> IngredientsRepository:
    return IngredientsRepository(supabase)


def get_pantry_repository(
    supabase: Client = Depends(get_authenticated_supabase),
) -> PantryRepository:
    return PantryRepository(supabase)


def get_recipe_ingredients_repository(
    supabase: Client = Depends(get_authenticated_supabase),
) -> RecipeIngredientsRepository:
    return RecipeIngredientsRepository(supabase)

def get_decision_selections_repository(
    supabase: Client = Depends(get_authenticated_supabase),
) -> DecisionSelectionsRepository:
    return DecisionSelectionsRepository(supabase)


def get_optional_decision_selections_repository(
    current_user: CurrentUser = Depends(get_current_user),
) -> DecisionSelectionsRepository | None:
    """
    Best-effort dependency for non-critical ranking personalization.

    The core /options endpoint must remain usable even when decision-learning
    persistence is not configured or temporarily unavailable. Strict
    persistence endpoints continue using get_decision_selections_repository.
    """
    try:
        supabase = get_authenticated_supabase(current_user)
    except RuntimeError:
        return None

    return DecisionSelectionsRepository(supabase)

def get_weekly_schedule_repository(
    supabase: Client = Depends(get_authenticated_supabase),
) -> WeeklyScheduleRepository:
    return WeeklyScheduleRepository(supabase)
