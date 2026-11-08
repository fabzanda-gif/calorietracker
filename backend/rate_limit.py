from __future__ import annotations

import os
import threading
import time
from collections import defaultdict, deque

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import JSONResponse
from starlette.concurrency import run_in_threadpool
from fastapi import HTTPException
from fastapi.security import HTTPAuthorizationCredentials

from backend.api.dependencies import get_current_user, get_admin_supabase_client


_DEFAULT_AI_PATHS = {
    "/meals/conversational/day-preview",
    "/meals/conversational/recheck",
    "/meals/conversational/preview",
    "/meals/photo/preview",
    "/ingredients/ai-preview",
    "/ingredients/scan-label",
    "/recipes/ai-preview",
    "/activities/comment",
}


class AIRateLimitMiddleware(BaseHTTPMiddleware):
    """
    Per-authenticated-user rolling limits for endpoints that call an LLM.

    Production counters live in Supabase across workers and restarts.
    The explicitly selected memory backend is for local development/tests.
    """

    def __init__(self, app):
        super().__init__(app)
        self._minute_limit = max(
            1,
            int(os.getenv("AI_RATE_LIMIT_PER_MINUTE", "20")),
        )
        self._day_limit = max(
            self._minute_limit,
            int(os.getenv("AI_RATE_LIMIT_PER_DAY", "300")),
        )

        configured_paths = {
            value.strip()
            for value in os.getenv(
                "AI_RATE_LIMIT_PATHS",
                "",
            ).split(",")
            if value.strip()
        }
        self._paths = _DEFAULT_AI_PATHS | configured_paths
        self._events: dict[str, deque[float]] = defaultdict(deque)
        self._lock = threading.Lock()
        self._backend = os.getenv("AI_RATE_LIMIT_BACKEND", "supabase").strip()
        if self._backend not in {"memory", "supabase"}:
            raise ValueError("AI_RATE_LIMIT_BACKEND must be memory or supabase")

    def _is_protected(self, request) -> bool:
        path = request.url.path

        if path in self._paths:
            return request.method == "POST"

        # Day briefings call the LLM and use a date in the route.
        if (
            request.method == "GET"
            and path.startswith("/days/")
            and path.endswith("/briefing")
        ):
            return True

        return False

    def _check_limit(self, key: str) -> tuple[bool, int]:
        if self._backend == "supabase":
            response = get_admin_supabase_client().rpc("consume_ai_rate_limit", {
                "p_user_id": key,
                "p_minute_limit": self._minute_limit,
                "p_day_limit": self._day_limit,
            }).execute()
            result = response.data
            if not isinstance(result, dict) or not isinstance(result.get("allowed"), bool):
                raise RuntimeError("Invalid rate limiter response")
            return result["allowed"], max(0, int(result["retry_after"]))
        return self._check_memory_limit(key)

    def _check_memory_limit(self, key: str) -> tuple[bool, int]:
        now = time.time()
        minute_cutoff = now - 60
        day_cutoff = now - 86_400

        with self._lock:
            events = self._events[key]

            while events and events[0] < day_cutoff:
                events.popleft()

            day_count = len(events)
            minute_events = [
                timestamp
                for timestamp in events
                if timestamp >= minute_cutoff
            ]

            if day_count >= self._day_limit:
                retry_after = max(
                    1,
                    int(events[0] + 86_400 - now),
                )
                return False, retry_after

            if len(minute_events) >= self._minute_limit:
                retry_after = max(
                    1,
                    int(minute_events[0] + 60 - now),
                )
                return False, retry_after

            events.append(now)

            # Opportunistic cleanup keeps the dictionary bounded.
            if len(self._events) > 10_000:
                stale_keys = [
                    stored_key
                    for stored_key, stored_events
                    in self._events.items()
                    if (
                        not stored_events
                        or stored_events[-1] < day_cutoff
                    )
                ]
                for stored_key in stale_keys:
                    self._events.pop(stored_key, None)

        return True, 0

    async def dispatch(self, request, call_next):
        if not self._is_protected(request):
            return await call_next(request)

        try:
            # Honor the same overrides as FastAPI routes in isolated tests.
            override = request.app.dependency_overrides.get(get_current_user)
            if override is not None:
                user = await run_in_threadpool(override)
            else:
                authorization = request.headers.get("authorization", "")
                scheme, _, token = authorization.partition(" ")
                credentials = (
                    HTTPAuthorizationCredentials(scheme="Bearer", credentials=token.strip())
                    if scheme.lower() == "bearer" and token.strip() else None
                )
                user = await run_in_threadpool(get_current_user, credentials)
        except HTTPException as exc:
            return JSONResponse(status_code=exc.status_code,
                                content={"detail": exc.detail}, headers=exc.headers)

        try:
            # Use the authenticated identity, not the demo's effective source ID.
            allowed, retry_after = await run_in_threadpool(
                self._check_limit, getattr(user, "authenticated_id", None) or user.id,
            )
        except Exception:
            # Never bypass spending limits if shared storage is unavailable.
            return JSONResponse(status_code=503, content={
                "detail": "Limite AI temporaneamente non disponibile. Riprova tra poco.",
            }, headers={"Retry-After": "30"})

        if not allowed:
            return JSONResponse(
                status_code=429,
                content={
                    "detail": (
                        "Troppe richieste AI. Riprova tra poco."
                    )
                },
                headers={
                    "Retry-After": str(retry_after),
                },
            )

        response = await call_next(request)
        response.headers["X-AI-RateLimit-Minute"] = str(
            self._minute_limit
        )
        response.headers["X-AI-RateLimit-Day"] = str(
            self._day_limit
        )
        return response
