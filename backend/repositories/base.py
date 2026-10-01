from __future__ import annotations

from typing import Any


class RepositoryError(RuntimeError):
    """Raised when a repository operation fails."""


class BaseRepository:
    """
    Tiny Supabase repository base.

    The Supabase client is injected instead of imported globally. This is the
    key migration step: Streamlit can pass its existing `supabase` client today,
    while FastAPI can inject a request-scoped client tomorrow.
    """

    table_name: str = ""

    def __init__(self, supabase_client: Any):
        if supabase_client is None:
            raise ValueError("supabase_client is required")
        self.supabase = supabase_client
        # Repository objects are request-scoped in FastAPI.
        # Cache identical reads only for the lifetime of this instance,
        # avoiding repeated Supabase round-trips inside one API request.
        self._request_cache: dict[tuple, Any] = {}

    def _cached(
        self,
        key: tuple,
    ):
        return self._request_cache.get(key)

    def _store_cache(
        self,
        key: tuple,
        value,
    ):
        self._request_cache[key] = value
        return value

    @property
    def table(self):
        return self.supabase.table(self.table_name)

    def _data(self, response):
        return getattr(response, "data", None) or []
