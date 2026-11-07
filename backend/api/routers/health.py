from fastapi import APIRouter, HTTPException, status

from backend.api.dependencies import get_admin_supabase_client


router = APIRouter(
    prefix="/health",
    tags=["health"],
)


def _live_payload() -> dict[str, str]:
    return {
        "status": "ok",
        "service": "SanoSync API",
    }


@router.get("")
def health():
    """Backward-compatible liveness endpoint used by Render."""
    return _live_payload()


@router.get("/live")
def live():
    """Process-level liveness check."""
    return _live_payload()


@router.get("/ready")
def ready():
    """
    Readiness check for dependencies required by production features.

    Uses the server-only Supabase client so this verifies both configuration
    and database connectivity without exposing user data.
    """
    try:
        (
            get_admin_supabase_client()
            .table("daily_logs")
            .select("id")
            .limit(1)
            .execute()
        )
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Supabase dependency unavailable",
        ) from exc

    return {
        **_live_payload(),
        "dependencies": {
            "supabase": "ok",
        },
    }
