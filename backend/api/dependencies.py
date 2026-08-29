from __future__ import annotations

import os
import hashlib
import threading
import time

import requests
from dataclasses import dataclass, field
from functools import lru_cache
from typing import Any

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from supabase import Client, create_client

from backend.repositories.activities import ActivitiesRepository
from backend.repositories.daily_logs import DailyLogsRepository
from backend.repositories.decision_selections import DecisionSelectionsRepository
from backend.repositories.ingredients import IngredientsRepository
from backend.repositories.meal_ingredients import MealIngredientsRepository
from backend.repositories.meal_prep import MealPrepRepository
from backend.repositories.meals import MealsRepository
from backend.repositories.recipe_ingredients import RecipeIngredientsRepository
from backend.repositories.recipes import RecipesRepository
from backend.repositories.weight import WeightRepository


bearer_scheme = HTTPBearer(auto_error=False)


@dataclass(frozen=True)
class CurrentUser:
    id: str
    access_token: str
    metadata: dict[str, Any] = field(default_factory=dict)


_AUTH_CACHE: dict[str, tuple[float, str, dict]] = {}
_AUTH_CACHE_LOCK = threading.Lock()
_AUTH_CACHE_TTL_SECONDS = 60.0


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

        url, key = _supabase_settings()

        try:
            session = requests.Session()
            session.trust_env = False

            response = None
            last_error = None

            for attempt in range(2):
                try:
                    response = session.get(
                        f"{url.rstrip('/')}/auth/v1/user",
                        headers={
                            "apikey": key,
                            "Authorization": f"Bearer {token}",
                        },
                        timeout=(5, 20),
                    )
                    break
                except requests.Timeout as exc:
                    last_error = exc

                    if attempt == 0:
                        time.sleep(0.25)
                        continue

                    raise HTTPException(
                        status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                        detail="Supabase Auth temporarily unavailable",
                    ) from exc

            if response is None:
                raise HTTPException(
                    status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                    detail="Supabase Auth temporarily unavailable",
                ) from last_error

        except HTTPException:
            raise
        except requests.RequestException as exc:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Unable to reach Supabase Auth",
            ) from exc

        if response.status_code in (401, 403):
            _AUTH_CACHE.pop(token_key, None)

            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid or expired token",
                headers={"WWW-Authenticate": "Bearer"},
            )

        if not response.ok:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Supabase Auth returned an unexpected response",
            )

        try:
            user = response.json()
        except ValueError as exc:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Invalid response from Supabase Auth",
            ) from exc

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


def get_authenticated_supabase(
    current_user: CurrentUser = Depends(get_current_user),
) -> Client:
    url, key = _supabase_settings()
    client = create_client(url, key)
    client.postgrest.auth(current_user.access_token)
    return client


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


def get_meal_prep_repository(
    supabase: Client = Depends(get_authenticated_supabase),
) -> MealPrepRepository:
    return MealPrepRepository(supabase)


def get_ingredients_repository(
    supabase: Client = Depends(get_authenticated_supabase),
) -> IngredientsRepository:
    return IngredientsRepository(supabase)


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

