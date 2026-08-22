from fastapi import FastAPI

from backend.api.routers.health import router as health_router


app = FastAPI(
    title="SanoSync API",
    version="0.1.0",
)


app.include_router(health_router)
