from fastapi.middleware.cors import CORSMiddleware
from fastapi import FastAPI

from backend.api.routers.activities import router as activities_router
from backend.api.routers.daily_logs import router as daily_logs_router
from backend.api.routers.decision_learning import router as decision_learning_router
from backend.api.routers.decision_outcomes import router as decision_outcomes_router
from backend.api.routers.decision_selections import router as decision_selections_router
from backend.api.routers.days import router as days_router
from backend.api.routers.health import router as health_router
from backend.api.routers.learned_insights import router as learned_insights_router
from backend.api.routers.meal_prep import router as meal_prep_router
from backend.api.routers.meals import router as meals_router
from backend.api.routers.recipes import router as recipes_router
from backend.api.routers.weight import router as weight_router


app = FastAPI(
    title="SanoSync API",
    version="0.3.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "https://glowing-cod-wv9qq5pr677pcqrj-3000.app.github.dev",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


app.include_router(health_router)
app.include_router(meals_router)
app.include_router(activities_router)
app.include_router(weight_router)
app.include_router(daily_logs_router)
app.include_router(recipes_router)
app.include_router(days_router)
app.include_router(meal_prep_router)
app.include_router(learned_insights_router)
app.include_router(decision_selections_router)
app.include_router(decision_learning_router)
app.include_router(decision_outcomes_router)
