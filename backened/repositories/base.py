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

    @property
    def table(self):
        return self.supabase.table(self.table_name)

    def _data(self, response):
        return getattr(response, "data", None) or []
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

    @property
    def table(self):
        return self.supabase.table(self.table_name)

    def _data(self, response):
        return getattr(response, "data", None) or []
