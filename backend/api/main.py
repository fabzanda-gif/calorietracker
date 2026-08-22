from fastapi import FastAPI

from backend.api.routers.health import router as health_router
from backend.api.routers.meals import router as meals_router

app = FastAPI(
    title="SanoSync API",
    version="0.2.0",
)

app.include_router(health_router)
app.include_router(meals_router)
