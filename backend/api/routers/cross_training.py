from __future__ import annotations

from datetime import date, timedelta

from fastapi import APIRouter, Depends, HTTPException, Query, status

from backend.api.dependencies import (
    CurrentUser, get_current_user,
    get_planned_activities_repository, get_strength_workouts_repository,
    get_strength_workout_logs_repository, get_activities_repository,
    get_training_coach_preferences_repository,
)
from backend.repositories.activities import ActivitiesRepository
from backend.repositories.base import RepositoryError
from backend.repositories.planned_activities import PlannedActivitiesRepository
from backend.repositories.strength_workouts import StrengthWorkoutsRepository
from backend.repositories.strength_logs import StrengthWorkoutLogsRepository
from backend.repositories.training_coach_preferences import TrainingCoachPreferencesRepository
from backend.services.cross_training import CrossTrainingService

router = APIRouter(prefix="/cross-training", tags=["cross-training"])


@router.get("/timeline")
def get_cross_training_timeline(
    start_date: date = Query(...),
    days: int = Query(default=14, ge=1, le=21),
    current_user: CurrentUser = Depends(get_current_user),
    planned_repo: PlannedActivitiesRepository = Depends(get_planned_activities_repository),
    strength_repo: StrengthWorkoutsRepository = Depends(get_strength_workouts_repository),
    logs_repo: StrengthWorkoutLogsRepository = Depends(get_strength_workout_logs_repository),
    activities_repo: ActivitiesRepository = Depends(get_activities_repository),
    preferences_repo: TrainingCoachPreferencesRepository = Depends(
        get_training_coach_preferences_repository
    ),
):
    end_date = start_date + timedelta(days=days-1)
    try:
        owner = current_user.id
        return CrossTrainingService().build(
            start_date=start_date,
            days=days,
            planned_running=planned_repo.list_range(owner, start_date, end_date),
            planned_strength=strength_repo.list_date_range(owner, start_date, end_date),
            completed_strength=logs_repo.list_date_range(owner, start_date, end_date),
            actual_activities=activities_repo.list_date_range(owner, start_date, end_date),
            priority=preferences_repo.get_priority(owner),
        )
    except RepositoryError as exc:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=str(exc),
        ) from exc
