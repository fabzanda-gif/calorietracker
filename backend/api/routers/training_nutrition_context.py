from __future__ import annotations

from datetime import date

from fastapi import APIRouter, Depends, HTTPException, Query, status

from backend.api.dependencies import (
    CurrentUser, get_current_user,
    get_meals_repository, get_planned_activities_repository,
    get_strength_workouts_repository, get_strength_workout_logs_repository,
    get_activities_repository, get_weight_repository,
)
from backend.repositories.base import RepositoryError
from backend.repositories.meals import MealsRepository
from backend.repositories.planned_activities import PlannedActivitiesRepository
from backend.repositories.strength_workouts import StrengthWorkoutsRepository
from backend.repositories.strength_logs import StrengthWorkoutLogsRepository
from backend.repositories.activities import ActivitiesRepository
from backend.repositories.weight import WeightRepository
from backend.services.training_nutrition_context import TrainingNutritionContextService

router = APIRouter(prefix="/training-nutrition", tags=["training-nutrition"])


@router.get("/week")
def get_training_nutrition_week(
    start_date: date = Query(...),
    days: int = Query(default=7, ge=1, le=14),
    current_user: CurrentUser = Depends(get_current_user),
    meals_repo: MealsRepository = Depends(get_meals_repository),
    planned_repo: PlannedActivitiesRepository = Depends(get_planned_activities_repository),
    strength_repo: StrengthWorkoutsRepository = Depends(get_strength_workouts_repository),
    logs_repo: StrengthWorkoutLogsRepository = Depends(
        get_strength_workout_logs_repository
    ),
    activities_repo: ActivitiesRepository = Depends(get_activities_repository),
    weight_repo: WeightRepository = Depends(get_weight_repository),
):
    from datetime import timedelta
    end = start_date + timedelta(days=days - 1)
    try:
        user_id = current_user.id
        meals = meals_repo.list_date_range(
            user_id, start_date, end,
            columns="id,date,calories,protein,carbs,fat",
        )
        running = planned_repo.list_range(user_id, start_date, end)
        strength = strength_repo.list_date_range(user_id, start_date, end)
        completed = logs_repo.list_date_range(user_id, start_date, end)
        activities = activities_repo.list_date_range(user_id, start_date, end)
        latest_weight = weight_repo.latest(user_id)
        return TrainingNutritionContextService().build(
            start_date=start_date,
            days=days,
            meals=meals,
            planned_running=running,
            planned_strength=strength,
            completed_strength=completed,
            actual_activities=activities,
            metadata=current_user.metadata or {},
            weight_kg=latest_weight.get("weight") if latest_weight else None,
        )
    except RepositoryError as exc:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=str(exc),
        ) from exc
