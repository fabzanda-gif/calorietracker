from fastapi import FastAPI

from backend.api.routers.health import router as health_router
from backend.api.routers.meals import router as meals_router
from backend.api.routers.activities import router as activities_router
from backend.api.routers.weight import router as weight_router
from backend.api.routers.daily_logs import router as daily_logs_router


app = FastAPI(
    title="SanoSync API",
    version="0.2.0",
)

app.include_router(health_router)
app.include_router(meals_router)
app.include_router(activities_router)
app.include_router(weight_router)
app.include_router(daily_logs_router)
