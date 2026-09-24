from __future__ import annotations

import hashlib
import os
import threading
import time
from collections import defaultdict, deque

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import JSONResponse


class AIRateLimitMiddleware(BaseHTTPMiddleware):
    """
    Lightweight per-token/IP rate limiting for expensive AI endpoints.

    This process-local limiter is intentionally simple and fits the current
    single-instance Render deployment. If SanoSync scales to multiple API
    instances, move the counters to a shared store such as Redis.
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
                "/meals/conversational/preview",
            ).split(",")
            if value.strip()
        }
        self._paths = configured_paths
        self._events: dict[str, deque[float]] = defaultdict(deque)
        self._lock = threading.Lock()

    @staticmethod
    def _request_key(request) -> str:
        authorization = request.headers.get("authorization", "")
        if authorization.lower().startswith("bearer "):
            token = authorization.split(" ", 1)[1].strip()
            if token:
                digest = hashlib.sha256(token.encode("utf-8")).hexdigest()
                return f"token:{digest}"

        client_host = (
            request.client.host
            if request.client is not None
            else "unknown"
        )
        return f"ip:{client_host}"

    def _check_limit(self, key: str) -> tuple[bool, int]:
        now = time.time()
        minute_cutoff = now - 60
        day_cutoff = now - 86_400

        with self._lock:
            events = self._events[key]

            while events and events[0] < day_cutoff:
                events.popleft()

            day_count = len(events)
            minute_count = sum(
                1
                for timestamp in events
                if timestamp >= minute_cutoff
            )

            if day_count >= self._day_limit:
                retry_after = max(
                    1,
                    int(events[0] + 86_400 - now),
                )
                return False, retry_after

            if minute_count >= self._minute_limit:
                first_recent = next(
                    timestamp
                    for timestamp in events
                    if timestamp >= minute_cutoff
                )
                retry_after = max(
                    1,
                    int(first_recent + 60 - now),
                )
                return False, retry_after

            events.append(now)

            # Opportunistic cleanup to keep memory bounded.
            if len(self._events) > 10_000:
                empty_or_stale = [
                    stored_key
                    for stored_key, stored_events in self._events.items()
                    if (
                        not stored_events
                        or stored_events[-1] < day_cutoff
                    )
                ]
                for stored_key in empty_or_stale:
                    self._events.pop(stored_key, None)

        return True, 0

    async def dispatch(self, request, call_next):
        if (
            request.method != "POST"
            or request.url.path not in self._paths
        ):
            return await call_next(request)

        allowed, retry_after = self._check_limit(
            self._request_key(request)
        )

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
