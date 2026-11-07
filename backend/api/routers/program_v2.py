from __future__ import annotations

from datetime import date

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field

from backend.api.dependencies import (
    CurrentUser,
    get_current_user,
    get_authenticated_supabase,
    get_exercise_library_repository,
    get_strength_plans_repository,
    get_strength_workouts_repository,
    get_strength_workout_exercises_repository,
)
from backend.repositories.base import RepositoryError
from backend.repositories.exercise_library import ExerciseLibraryRepository
from backend.repositories.onboarding import OnboardingRepository
from backend.repositories.strength_plans import StrengthPlansRepository
from backend.repositories.strength_workouts import (
    StrengthWorkoutsRepository,
    StrengthWorkoutExercisesRepository,
)
from backend.repositories.athlete_state import AthleteStateRepository
from backend.services.athlete_state import AthleteStateService
from backend.services.program_generator_v2 import (
    ProgramGeneratorV2, ProgramV2Input,
)
from backend.api.routers.strength import _persist_strength_plan

router = APIRouter(prefix="/strength/plans/v2", tags=["strength-program-v2"])


class ProgramV2Request(BaseModel):
    start_date: date
    goal: str = Field(pattern="^(hypertrophy|strength|general_fitness)$")
    total_weeks: int = Field(default=8, ge=4, le=12)
    allowed_equipment: list[str] = Field(default_factory=list, max_length=20)
    replace_active: bool = False


def get_personalized_context(
    current_user: CurrentUser,
    supabase,
    library_repo: ExerciseLibraryRepository,
    request: ProgramV2Request,
) -> dict:
    training = OnboardingRepository(supabase)
    profile = training.get_training_profile(current_user.id)
    if not profile:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Completa il Training Profile prima di generare il programma v2.",
        )
    days = training.list_preferred_days(current_user.id)
    muscles = training.list_muscle_priorities(current_user.id)
    # The Phase 1 user-specific preference table is required for a safe
    # generator: fail closed rather than ignoring explicit exclusions.
    pref_response = (
        supabase.table("training_exercise_preferences")
        .select("exercise_id,preference")
        .eq("user_id", current_user.id)
        .execute()
    )
    prefs = pref_response.data or []
    excluded = {
        str(x["exercise_id"]) for x in prefs
        if x.get("preference") == "excluded"
    }
    preferred = {
        str(x["exercise_id"]) for x in prefs
        if x.get("preference") == "preferred"
    }
    catalog = library_repo.list_exercises(
        approved_only=True, language="it", limit=200,
    )
    # Descriptive Athlete State, not an automatic load prescription.
    history_repo = AthleteStateRepository(supabase)
    history = history_repo.completed_strength_history(
        current_user.id, as_of=date.today(), days=56,
    )
    athlete = AthleteStateService().build(
        history=history,
        as_of=date.today(),
        profile=profile,
    )
    sessions = int(profile["sessions_per_week"])
    if sessions not in (2, 3, 4):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail="Il Program Generator v2 supporta al momento 2–4 sedute settimanali.",
        )
    config = ProgramV2Input(
        start_date=request.start_date,
        goal=request.goal,
        sessions_per_week=sessions,
        total_weeks=request.total_weeks,
        experience_level=profile["experience_level"],
        session_duration_minutes=int(profile["session_duration_minutes"]),
        preferred_days=tuple(days) if profile.get("schedule_flexibility") == "fixed" else (),
        priority_muscles=tuple(muscles),
        allowed_equipment=tuple(request.allowed_equipment),
    )
    return {
        "config": config,
        "catalog": catalog,
        "excluded_ids": excluded,
        "preferred_ids": preferred,
        "athlete_state": athlete,
    }


def _preview_v2(
    request: ProgramV2Request,
    current_user: CurrentUser,
    supabase,
    library_repo: ExerciseLibraryRepository,
) -> dict:
    try:
        context = get_personalized_context(
            current_user, supabase, library_repo, request,
        )
        return ProgramGeneratorV2().preview(**context)
    except HTTPException:
        raise
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail=str(exc),
        ) from exc
    except RepositoryError as exc:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=str(exc),
        ) from exc
    except Exception as exc:
        # Missing Phase 1 migration must never disable explicit exclusions.
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Training preferences are not available. Verify Phase 1 deployment.",
        ) from exc


@router.post("/preview")
def preview_program_v2(
    request: ProgramV2Request,
    current_user: CurrentUser = Depends(get_current_user),
    supabase=Depends(get_authenticated_supabase),
    library_repo: ExerciseLibraryRepository = Depends(
        get_exercise_library_repository
    ),
):
    return _preview_v2(request, current_user, supabase, library_repo)


@router.post("", status_code=status.HTTP_201_CREATED)
def create_program_v2(
    request: ProgramV2Request,
    current_user: CurrentUser = Depends(get_current_user),
    supabase=Depends(get_authenticated_supabase),
    library_repo: ExerciseLibraryRepository = Depends(
        get_exercise_library_repository
    ),
    plans_repo: StrengthPlansRepository = Depends(
        get_strength_plans_repository
    ),
    workouts_repo: StrengthWorkoutsRepository = Depends(
        get_strength_workouts_repository
    ),
    exercises_repo: StrengthWorkoutExercisesRepository = Depends(
        get_strength_workout_exercises_repository
    ),
):
    if current_user.read_only:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Read-only account",
        )
    preview = _preview_v2(request, current_user, supabase, library_repo)
    if not preview["ready_for_activation"]:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={
                "message": "Catalogo o attrezzatura insufficienti per attivare un programma v2.",
                "warnings": preview["warnings"],
                "missing_movement_patterns": preview["missing_movement_patterns"],
            },
        )
    try:
        active = [
            item for item in plans_repo.list_for_user(current_user.id)
            if item.get("status") == "active"
        ]
        if active and not request.replace_active:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Esiste già un programma attivo. Conferma prima la sostituzione.",
            )
        # Approval state is always re-read on creation, rather than trusting
        # an old client preview or a client-provided list of exercises.
        saved = _persist_strength_plan(
            user_id=current_user.id,
            generated=preview,
            plans_repo=plans_repo,
            workouts_repo=workouts_repo,
            exercises_repo=exercises_repo,
        )
        replaced = []
        if request.replace_active:
            for old in active:
                if old.get("id") != saved["plan"]["id"]:
                    # Never delete a previously active plan: the FK chain
                    # would cascade to workouts, completed logs and sets.
                    # Pause it while retaining the athlete's history.
                    paused = plans_repo.update_status(
                        plan_id=old["id"],
                        user_id=current_user.id,
                        status="paused",
                    )
                    if not paused or paused.get("status") != "paused":
                        raise RepositoryError(
                            "Unable to pause previous plan safely; "
                            "new plan requires manual review."
                        )
                    replaced.append(old["id"])
        return {"created": True, **saved, "replaced_plan_ids": replaced}
    except HTTPException:
        raise
    except RepositoryError as exc:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY, detail=str(exc)
        ) from exc
