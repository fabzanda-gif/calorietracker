from __future__ import annotations

import os
from dataclasses import dataclass
from functools import lru_cache

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from supabase import Client, create_client

from backend.repositories.activities import ActivitiesRepository
from backend.repositories.daily_logs import DailyLogsRepository
from backend.repositories.meals import MealsRepository
from backend.repositories.recipes import RecipesRepository
from backend.repositories.weight import WeightRepository


bearer_scheme = HTTPBearer(auto_error=False)


@dataclass(frozen=True)
class CurrentUser:
    id: str
    access_token: str


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
    """
    Anonymous client used for Supabase Auth token validation.
    """
    url, key = _supabase_settings()
    return create_client(url, key)


def get_current_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(
        bearer_scheme
    ),
) -> CurrentUser:
    """
    Validate the Bearer token and resolve the authenticated Supabase user.
    """
    if credentials is None or not credentials.credentials:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing bearer token",
            headers={"WWW-Authenticate": "Bearer"},
        )

    token = credentials.credentials

    try:
        supabase = get_supabase_client()
        response = supabase.auth.get_user(token)
        user = getattr(response, "user", None)

        if user is None or not getattr(user, "id", None):
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid or expired token",
                headers={"WWW-Authenticate": "Bearer"},
            )

        return CurrentUser(
            id=str(user.id),
            access_token=token,
        )

    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired token",
            headers={"WWW-Authenticate": "Bearer"},
        ) from exc


def get_authenticated_supabase(
    current_user: CurrentUser = Depends(get_current_user),
) -> Client:
    """
    Supabase client whose PostgREST requests carry the logged-in user's JWT.
    This is the single place where authenticated database access is created.
    """
    url, key = _supabase_settings()
    client = create_client(url, key)
    client.postgrest.auth(current_user.access_token)
    return client


def get_meals_repository(
    supabase: Client = Depends(get_authenticated_supabase),
) -> MealsRepository:
    return MealsRepository(supabase)


def get_activities_repository(
    supabase: Client = Depends(get_authenticated_supabase),
) -> ActivitiesRepository:
    return ActivitiesRepository(supabase)


def get_weight_repository(
    supabase: Client = Depends(get_authenticated_supabase),
) -> WeightRepository:
    return WeightRepository(supabase)


def get_daily_logs_repository(
    supabase: Client = Depends(get_authenticated_supabase),
) -> DailyLogsRepository:
    return DailyLogsRepository(supabase)


def get_recipes_repository(
    supabase: Client = Depends(get_authenticated_supabase),
) -> RecipesRepository:
    return RecipesRepository(supabase)
