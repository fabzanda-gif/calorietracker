from __future__ import annotations

import os
from functools import lru_cache

from fastapi import Depends, HTTPException
from supabase import Client, create_client

from backend.repositories.meals import MealsRepository


@lru_cache(maxsize=1)
def get_supabase_client() -> Client:
    """
    Development/API client.

    Reads credentials from environment variables instead of Streamlit secrets.
    Do not hard-code Supabase credentials in the repository.
    """
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

    return create_client(url, key)


def get_meals_repository(
    supabase: Client = Depends(get_supabase_client),
) -> MealsRepository:
    return MealsRepository(supabase)
