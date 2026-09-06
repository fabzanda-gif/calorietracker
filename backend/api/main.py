import os
import time
from contextvars import ContextVar
from urllib.parse import urlparse

import httpx
from fastapi.middleware.cors import CORSMiddleware
from fastapi import FastAPI

from backend.api.routers.activities import router as activities_router
from backend.api.routers.daily_logs import router as daily_logs_router
from backend.api.routers.day_history import router as day_history_router
from backend.api.routers.decision_learning import router as decision_learning_router
from backend.api.routers.decision_outcomes import router as decision_outcomes_router
from backend.api.routers.decision_selections import router as decision_selections_router
from backend.api.routers.days import router as days_router
from backend.api.routers.health import router as health_router
from backend.api.routers.ingredients import router as ingredients_router
from backend.api.routers.learned_insights import router as learned_insights_router
from backend.api.routers.meal_prep import router as meal_prep_router
from backend.api.routers.meals import router as meals_router
from backend.api.routers.oura import router as oura_router
from backend.api.routers.pantry import router as pantry_router
from backend.api.routers.recipes import router as recipes_router
from backend.api.routers.progress import router as progress_router
from backend.api.routers.profile import router as profile_router
from backend.api.routers.strength import router as strength_router
from backend.api.routers.weekly_schedule import router as weekly_schedule_router
from backend.api.routers.weight import router as weight_router


app = FastAPI(
    title="SanoSync API",
    version="0.3.0",
)


_CURRENT_API_PATH: ContextVar[str] = ContextVar(
    "sanosync_current_api_path",
    default="-",
)

_ORIGINAL_HTTPX_SEND = httpx.Client.send


def _timed_httpx_send(
    self,
    request,
    *args,
    **kwargs,
):
    supabase_url = os.getenv(
        "SUPABASE_URL",
        "",
    ).strip()

    supabase_host = (
        urlparse(supabase_url).netloc
        if supabase_url
        else ""
    )

    request_url = str(request.url)
    parsed = urlparse(request_url)

    is_supabase = bool(
        supabase_host
        and parsed.netloc == supabase_host
    )

    if not is_supabase:
        return _ORIGINAL_HTTPX_SEND(
            self,
            request,
            *args,
            **kwargs,
        )

    started_at = time.perf_counter()
    response = None

    try:
        response = _ORIGINAL_HTTPX_SEND(
            self,
            request,
            *args,
            **kwargs,
        )
        return response
    finally:
        elapsed_ms = (
            time.perf_counter() - started_at
        ) * 1000

        status_code = (
            response.status_code
            if response is not None
            else "ERR"
        )

        outbound_path = parsed.path

        if parsed.query:
            # Non logghiamo la query string:
            # può contenere filtri o dati utente.
            outbound_path += "?…"

        print(
            f"[DB perf] "
            f"api={_CURRENT_API_PATH.get()} "
            f"{request.method} "
            f"{outbound_path}: "
            f"{elapsed_ms:.0f} ms "
            f"status={status_code}",
            flush=True,
        )


if not getattr(
    httpx.Client.send,
    "_sanosync_perf_wrapped",
    False,
):
    _timed_httpx_send._sanosync_perf_wrapped = True
    httpx.Client.send = _timed_httpx_send


@app.middleware("http")
async def performance_timing_middleware(
    request,
    call_next,
):
    started_at = time.perf_counter()

    token = _CURRENT_API_PATH.set(
        request.url.path,
    )

    try:
        response = await call_next(request)
    finally:
        _CURRENT_API_PATH.reset(token)

    elapsed_ms = (
        time.perf_counter() - started_at
    ) * 1000

    print(
        f"[API perf] {request.method} "
        f"{request.url.path}: "
        f"{elapsed_ms:.0f} ms "
        f"status={response.status_code}",
        flush=True,
    )

    return response

default_origins = [
    "http://localhost:3000",
    "https://ubiquitous-journey-p7g55w4jvrpvfwjp-3000.app.github.dev",
]

configured_origins = [
    origin.strip()
    for origin in os.getenv("CORS_ORIGINS", "").split(",")
    if origin.strip()
]

allowed_origins = configured_origins or default_origins

app.add_middleware(
    CORSMiddleware,
    allow_origins=allowed_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


app.include_router(health_router)
app.include_router(meals_router)
app.include_router(oura_router)
app.include_router(activities_router)
app.include_router(weight_router)
app.include_router(progress_router)
app.include_router(profile_router)
app.include_router(strength_router)
app.include_router(weekly_schedule_router)
app.include_router(daily_logs_router)
app.include_router(day_history_router)
app.include_router(recipes_router)
app.include_router(ingredients_router)
app.include_router(days_router)
app.include_router(meal_prep_router)
app.include_router(pantry_router)
app.include_router(learned_insights_router)
app.include_router(decision_selections_router)
app.include_router(decision_learning_router)
app.include_router(decision_outcomes_router)
