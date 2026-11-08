import pytest


# ---------------------------------------------------------------------------
# Test-only Supabase isolation
# ---------------------------------------------------------------------------

class _FakeSupabaseClient:
    def table(self, *args, **kwargs):
        raise AssertionError(
            "A test attempted to access Supabase directly. "
            "Override the corresponding repository dependency instead."
        )


def _override_supabase_client():
    return _FakeSupabaseClient()


@pytest.fixture(autouse=True)
def restore_supabase_override():
    from backend.api.main import app
    from backend.api.dependencies import get_authenticated_supabase

    app.dependency_overrides[get_authenticated_supabase] = (
        _override_supabase_client
    )

    yield

    app.dependency_overrides.pop(
        get_authenticated_supabase,
        None,
    )


@pytest.fixture(autouse=True)
def local_rate_limit_storage(monkeypatch):
    monkeypatch.setenv("AI_RATE_LIMIT_BACKEND", "memory")
    from backend.api.main import app
    from backend.rate_limit import AIRateLimitMiddleware

    middleware = app.middleware_stack
    while middleware is not None:
        if isinstance(middleware, AIRateLimitMiddleware):
            middleware._events.clear()
        middleware = getattr(middleware, "app", None)
