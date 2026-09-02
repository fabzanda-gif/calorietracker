from __future__ import annotations

from datetime import date as Date
from datetime import datetime
import time

from fastapi import APIRouter, Body, Depends, HTTPException, Query, status

from backend.api.dependencies import (
    CurrentUser,
    get_activities_repository,
    get_current_user,
    get_daily_logs_repository,
    get_optional_decision_selections_repository,
    get_meal_prep_repository,
    get_meals_repository,
    get_recipes_repository,
    get_weekly_schedule_repository,
    get_weight_repository,
)
from backend.repositories.activities import ActivitiesRepository
from backend.repositories.base import RepositoryError
from backend.repositories.daily_logs import DailyLogsRepository
from backend.repositories.decision_selections import DecisionSelectionsRepository
from backend.repositories.meal_prep import MealPrepRepository
from backend.repositories.meals import MealsRepository
from backend.repositories.recipes import RecipesRepository
from backend.repositories.weight import WeightRepository
from backend.repositories.weekly_schedule import WeeklyScheduleRepository
from backend.services.day import DayService
from backend.services.day_budget import DayBudgetService
from backend.services.day_briefing import (
    DayBriefingError,
    DayBriefingService,
    build_status_hint,
    fallback_day_briefing,
)
from backend.services.daily_context import (
    DailyContextService,
)
from backend.services.decision_feedback import DecisionFeedbackService
from backend.services.decision_learning_pipeline import DecisionLearningPipelineService
from backend.services.decision_mode import (
    DecisionModeError,
    DecisionModeService,
)
from backend.services.decision_ranking import DecisionRankingService
from backend.services.eating_out_candidates import (
    EatingOutCandidateService,
)
from backend.services.eating_out_personalization import (
    EatingOutPersonalizationService,
)
from backend.services.generic_eating_out_candidates import (
    GenericEatingOutCandidateService,
)
from backend.services.generic_order_candidates import (
    GenericOrderCandidateService,
)
from backend.services.meal_candidates import MealCandidateService
from backend.services.meal_confirmation import (
    MealAlreadyLoggedError,
    MealConfirmationService,
    MealPredictionUnavailableError,
)
from backend.services.meal_decision import MealDecisionService
from backend.services.meal_memory import MealMemoryService
from backend.services.next_meal_replanning import NextMealReplanningService
from backend.services.meal_replanning import MealReplanningService
from backend.services.meal_replanning_context import MealReplanningContextService
from backend.services.order_candidates import OrderCandidateService
from backend.services.order_personalization import (
    OrderPersonalizationService,
)


router = APIRouter(prefix="/days", tags=["days"])


_DAY_BRIEFING_CACHE_TTL_SECONDS = 2 * 60 * 60
_DAY_BRIEFING_CACHE: dict[
    tuple,
    tuple[float, dict],
] = {}


def _briefing_calorie_bucket(
    value: float,
    size: int = 25,
) -> int:
    return int(
        round(float(value) / size) * size
    )


def _is_briefing_training(
    activity: dict,
) -> bool:
    name = str(
        activity.get("activity_name") or ""
    ).strip().lower()

    daily_movement_prefixes = (
        "passi",
        "steps",
        "bici",
        "bicicletta",
    )

    return not any(
        name == prefix
        or name.startswith(f"{prefix} ")
        or name.startswith(f"{prefix} (")
        for prefix in daily_movement_prefixes
    )


def _briefing_activity_signature(
    activities: list[dict],
) -> tuple:
    return tuple(
        sorted(
            (
                str(activity.get("id") or ""),
                str(
                    activity.get(
                        "activity_name"
                    )
                    or ""
                ),
                str(
                    activity.get(
                        "activity_type"
                    )
                    or ""
                ),
                round(
                    float(
                        activity.get(
                            "burned_calories"
                        )
                        or 0
                    ),
                    1,
                ),
                int(
                    activity.get(
                        "duration_seconds"
                    )
                    or 0
                ),
                int(
                    activity.get(
                        "estimated_steps"
                    )
                    or 0
                ),
            )
            for activity in activities
            if _is_briefing_training(activity)
        )
    )


MEAL_SLOT_TO_TYPE = {
    "breakfast": "Colazione",
    "lunch": "Pranzo",
    "dinner": "Cena",
}


def _validate_slot(meal_slot: str) -> str:
    if meal_slot not in MEAL_SLOT_TO_TYPE:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Unknown meal slot",
        )
    return MEAL_SLOT_TO_TYPE[meal_slot]


def _meal_memory(
    meals_repo: MealsRepository,
    daily_logs_repo: DailyLogsRepository,
) -> MealMemoryService:
    return MealMemoryService(
        meals_repo=meals_repo,
        daily_logs_repo=daily_logs_repo,
    )


def _build_day(
    *,
    user_id: str,
    day_date: Date,
    daily_logs_repo: DailyLogsRepository,
    meals_repo: MealsRepository,
    weekly_schedule_repo: WeeklyScheduleRepository,
) -> dict:
    return DayService(
        daily_logs_repo=daily_logs_repo,
        weekly_schedule_repo=weekly_schedule_repo,
        meal_memory_service=_meal_memory(
            meals_repo,
            daily_logs_repo,
        ),
    ).build_day(
        user_id=user_id,
        day_date=day_date,
    )


def _build_budget(
    *,
    current_user: CurrentUser,
    day_date: Date,
    meals_repo: MealsRepository,
    activities_repo: ActivitiesRepository,
    weight_repo: WeightRepository,
) -> dict:
    latest_weight = weight_repo.latest(current_user.id)
    current_weight = (
        latest_weight.get("weight")
        if latest_weight is not None
        else None
    )

    return DayBudgetService(
        meals_repo=meals_repo,
        activities_repo=activities_repo,
    ).build(
        user_id=current_user.id,
        day_date=day_date,
        metadata=current_user.metadata,
        current_weight=current_weight,
    )


def _history(
    *,
    user_id: str,
    meals_repo: MealsRepository,
) -> list[dict]:
    history, _enhanced = meals_repo.list_history_compatible(
        user_id
    )
    return history


def _build_known_order_candidates(
    *,
    history: list[dict],
    meal_type: str,
    on_date: Date,
) -> list[dict]:
    known = OrderCandidateService().build(
        meals=history,
        meal_type=meal_type,
    )

    return OrderPersonalizationService().enrich(
        candidates=known,
        on_date=on_date,
    )


def _build_eating_out_candidates(
    *,
    history: list[dict],
    meal_type: str,
    on_date: Date,
) -> list[dict]:
    known = EatingOutCandidateService().build(
        meals=history,
        meal_type=meal_type,
    )

    return EatingOutPersonalizationService().enrich(
        candidates=known,
        on_date=on_date,
    )


@router.get("/{day_date}/next-meal")
def get_next_meal(
    day_date: Date,
    current_user: CurrentUser = Depends(get_current_user),
    meals_repo: MealsRepository = Depends(
        get_meals_repository
    ),
):
    try:
        meals = meals_repo.list_for_date_compatible(
            user_id=current_user.id,
            log_date=day_date,
        )

        next_slot = NextMealReplanningService().next_slot(
            logged_meal_types=[
                str(meal.get("meal_type") or "")
                for meal in meals
            ],
        )

        return {
            "date": str(day_date),
            "next_slot": next_slot,
            "next_meal_type": (
                MEAL_SLOT_TO_TYPE[next_slot]
                if next_slot is not None
                else None
            ),
        }

    except RepositoryError as exc:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=str(exc),
        ) from exc


@router.get("/{day_date}/budget")
def get_day_budget(
    day_date: Date,
    current_user: CurrentUser = Depends(get_current_user),
    meals_repo: MealsRepository = Depends(get_meals_repository),
    activities_repo: ActivitiesRepository = Depends(
        get_activities_repository
    ),
    weight_repo: WeightRepository = Depends(
        get_weight_repository
    ),
):
    try:
        return _build_budget(
            current_user=current_user,
            day_date=day_date,
            meals_repo=meals_repo,
            activities_repo=activities_repo,
            weight_repo=weight_repo,
        )
    except RepositoryError as exc:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=str(exc),
        ) from exc


@router.get("/{day_date}/meals/{meal_slot}/options")
def get_ranked_meal_options(
    day_date: Date,
    meal_slot: str,
    mode: str = Query(default="auto"),
    current_user: CurrentUser = Depends(get_current_user),
    daily_logs_repo: DailyLogsRepository = Depends(
        get_daily_logs_repository
    ),
    meals_repo: MealsRepository = Depends(
        get_meals_repository
    ),
    activities_repo: ActivitiesRepository = Depends(
        get_activities_repository
    ),
    weight_repo: WeightRepository = Depends(
        get_weight_repository
    ),
    meal_prep_repo: MealPrepRepository = Depends(
        get_meal_prep_repository
    ),
    recipes_repo: RecipesRepository = Depends(
        get_recipes_repository
    ),
    decision_selections_repo: DecisionSelectionsRepository | None = Depends(
        get_optional_decision_selections_repository
    ),
    weekly_schedule_repo: WeeklyScheduleRepository = Depends(
        get_weekly_schedule_repository
    ),
):
    meal_type = _validate_slot(meal_slot)

    try:
        day = _build_day(
            user_id=current_user.id,
            day_date=day_date,
            daily_logs_repo=daily_logs_repo,
            meals_repo=meals_repo,
            weekly_schedule_repo=weekly_schedule_repo,
        )

        budget_result = _build_budget(
            current_user=current_user,
            day_date=day_date,
            meals_repo=meals_repo,
            activities_repo=activities_repo,
            weight_repo=weight_repo,
        )

        budget = budget_result.get("budget") or {}
        available_kcal = budget.get("available_kcal")
        protein_remaining_g = budget.get(
            "protein_remaining_g"
        )

        normalized_mode = str(mode or "auto").strip().lower()

        history = _history(
            user_id=current_user.id,
            meals_repo=meals_repo,
        )

        known_orders = _build_known_order_candidates(
            history=history,
            meal_type=meal_type,
            on_date=day_date,
        )

        eating_out = _build_eating_out_candidates(
            history=history,
            meal_type=meal_type,
            on_date=day_date,
        )

        generic_orders = []
        if normalized_mode == "order":
            generic_orders = GenericOrderCandidateService().build(
                meal_type=meal_type,
                known_candidates=known_orders,
                target_count=3,
            )

        generic_eating_out = []
        if normalized_mode == "out":
            generic_eating_out = (
                GenericEatingOutCandidateService().build(
                    meal_type=meal_type,
                    known_candidates=eating_out,
                    target_count=3,
                )
            )

        all_candidates = MealCandidateService().build(
            day_date=day_date,
            meal_type=meal_type,
            meal_prep_items=meal_prep_repo.list_available(
                current_user.id
            ),
            routine_prediction=day["meals"][meal_slot],
            recipes=recipes_repo.list_available(
                current_user.id
            ),
            order_candidates=[
                *known_orders,
                *generic_orders,
                *eating_out,
                *generic_eating_out,
            ],
            historical_meals=history,
        )

        mode_result = DecisionModeService().apply(
            candidates=all_candidates,
            mode=normalized_mode,
        )



        selection_events = []

        if decision_selections_repo is not None:
            try:
                selection_events = (
                    decision_selections_repo.list_for_user(
                        current_user.id,
                        limit=100,
                    )
                )
            except RepositoryError:
                selection_events = []

        outcome_meals = []

        if selection_events:
            selection_dates = [
                str(event.get("date"))
                for event in selection_events
                if event.get("date")
            ]

            if selection_dates:
                try:
                    outcome_meals = meals_repo.list_date_range(
                        current_user.id,
                        min(selection_dates),
                        max(selection_dates),
                    )
                except RepositoryError:
                    outcome_meals = []

        learning_pipeline = DecisionLearningPipelineService().build(
            selections=selection_events,
            meals=outcome_meals,
        )
        blended_preferences = learning_pipeline["blended_profile"]

        feedback = DecisionFeedbackService().enrich_candidates(
            candidates=mode_result["candidates"],
            learned_profile=blended_preferences,
            mode=mode_result["mode"],
        )

        ranked = DecisionRankingService().rank(
            candidates=feedback["candidates"],
            available_kcal=available_kcal,
            protein_remaining_g=protein_remaining_g,
            mode=mode_result["mode"],
            preferred_lens=feedback["preferred_lens"],
            preferred_mode=feedback["preferred_mode"],
        )

        routine_candidate = None

        if mode_result["mode"] == "auto":
            routine_candidate = next(
                (
                    candidate
                    for candidate in feedback["candidates"]
                    if candidate.get("source") == "routine"
                ),
                None,
            )

        recommended = MealReplanningService().recommend(
            routine_candidate=routine_candidate,
            ranked_options=ranked["options"],
            available_kcal=available_kcal,
        )

        replanning_context = MealReplanningContextService().build(
            recommendation=recommended,
            actual=budget_result.get("actual"),
            budget=budget,
        )

        return {
            "date": str(day_date),
            "meal_slot": meal_slot,
            "meal_type": meal_type,
            "mode": mode_result["mode"],
            "mode_label": mode_result["mode_label"],
            "all_candidate_count": len(all_candidates),
            "candidate_count": mode_result["candidate_count"],
            "known_order_count": len(known_orders),
            "generic_order_count": len(generic_orders),
            "known_eating_out_count": len(eating_out),
            "generic_eating_out_count": len(generic_eating_out),
            "order_personalization_state": (
                "known"
                if len(known_orders) >= 3
                else "learning"
            ),
            "eating_out_personalization_state": (
                "known"
                if len(eating_out) >= 3
                else "learning"
            ),
            "decision_preferences": {
                "preferred_mode": feedback["preferred_mode"],
                "preferred_lens": feedback["preferred_lens"],
                "preferred_source": feedback["preferred_source"],
                "mode_learning_source": blended_preferences["profile"]["mode"]["learning_source"],
                "lens_learning_source": blended_preferences["profile"]["lens"]["learning_source"],
                "source_learning_source": blended_preferences["profile"]["source"]["learning_source"],
                "outcome_evidence": blended_preferences["outcome_evidence"],
            },
            "empty_reason": mode_result["empty_reason"],
            "candidates": mode_result["candidates"],
            "recommended": recommended,
            "replanning_context": replanning_context,
            **ranked,
        }

    except DecisionModeError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail=str(exc),
        ) from exc
    except RepositoryError as exc:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=str(exc),
        ) from exc


@router.get("/{day_date}/meals/{meal_slot}/decision")
def get_meal_decision(
    day_date: Date,
    meal_slot: str,
    current_user: CurrentUser = Depends(get_current_user),
    daily_logs_repo: DailyLogsRepository = Depends(
        get_daily_logs_repository
    ),
    meals_repo: MealsRepository = Depends(
        get_meals_repository
    ),
    activities_repo: ActivitiesRepository = Depends(
        get_activities_repository
    ),
    weight_repo: WeightRepository = Depends(
        get_weight_repository
    ),
    meal_prep_repo: MealPrepRepository = Depends(
        get_meal_prep_repository
    ),
    weekly_schedule_repo: WeeklyScheduleRepository = Depends(
        get_weekly_schedule_repository
    ),
):
    meal_type = _validate_slot(meal_slot)

    try:
        day = _build_day(
            user_id=current_user.id,
            day_date=day_date,
            daily_logs_repo=daily_logs_repo,
            meals_repo=meals_repo,
            weekly_schedule_repo=weekly_schedule_repo,
        )

        budget_result = _build_budget(
            current_user=current_user,
            day_date=day_date,
            meals_repo=meals_repo,
            activities_repo=activities_repo,
            weight_repo=weight_repo,
        )

        available_kcal = None
        if budget_result.get("budget") is not None:
            available_kcal = budget_result["budget"].get(
                "available_kcal"
            )

        return MealDecisionService().decide(
            day_date=day_date,
            meal_type=meal_type,
            available_inventory=meal_prep_repo.list_available(
                current_user.id
            ),
            available_kcal=available_kcal,
            routine_prediction=day["meals"][meal_slot],
        )

    except RepositoryError as exc:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=str(exc),
        ) from exc


@router.post("/{day_date}/meals/{meal_slot}/confirm")
def confirm_meal_prediction(
    day_date: Date,
    meal_slot: str,
    body: dict | None = Body(default=None),
    current_user: CurrentUser = Depends(get_current_user),
    daily_logs_repo: DailyLogsRepository = Depends(
        get_daily_logs_repository
    ),
    meals_repo: MealsRepository = Depends(
        get_meals_repository
    ),
    weekly_schedule_repo: WeeklyScheduleRepository = Depends(
        get_weekly_schedule_repository
    ),
):
    meal_type = _validate_slot(meal_slot)

    try:
        day = _build_day(
            user_id=current_user.id,
            day_date=day_date,
            daily_logs_repo=daily_logs_repo,
            meals_repo=meals_repo,
            weekly_schedule_repo=weekly_schedule_repo,
        )

        prediction = day["meals"][meal_slot]

        recommendation = (
            body.get("recommendation")
            if isinstance(body, dict)
            else None
        )

        if isinstance(recommendation, dict):
            name = recommendation.get("name")

            if name:
                prediction = {
                    **prediction,
                    "meal_type": meal_type,
                    "value": str(name),
                    "state": "predicted",
                    "source": "replanning",
                    "estimated_quantity": recommendation.get(
                        "quantity"
                    ),
                    "estimated_calories": recommendation.get(
                        "calories"
                    ),
                    "estimated_protein_g": recommendation.get(
                        "protein_g"
                    ),
                    "estimated_carbs_g": recommendation.get(
                        "carbs_g"
                    ),
                    "estimated_fat_g": recommendation.get(
                        "fat_g"
                    ),
                }

        return MealConfirmationService(
            meals_repo
        ).confirm(
            user_id=current_user.id,
            day_date=day_date,
            prediction=prediction,
        )

    except (
        MealPredictionUnavailableError,
        MealAlreadyLoggedError,
    ) as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=str(exc),
        ) from exc
    except RepositoryError as exc:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=str(exc),
        ) from exc




@router.get("/{day_date}/briefing")
def get_day_briefing(
    day_date: Date,
    moment: str = Query(
        default="evening",
        pattern="^(morning|afternoon|evening)$",
    ),
    mode: str = Query(
        default="standard",
        pattern="^(standard|zero)$",
    ),
    hour: int | None = Query(
        default=None,
        ge=0,
        le=23,
    ),
    current_user: CurrentUser = Depends(get_current_user),
    daily_logs_repo: DailyLogsRepository = Depends(
        get_daily_logs_repository
    ),
    meals_repo: MealsRepository = Depends(
        get_meals_repository
    ),
    activities_repo: ActivitiesRepository = Depends(
        get_activities_repository
    ),
    weekly_schedule_repo: WeeklyScheduleRepository = Depends(
        get_weekly_schedule_repository
    ),
    weight_repo: WeightRepository = Depends(
        get_weight_repository
    ),
):
    try:
        day = _build_day(
            user_id=current_user.id,
            day_date=day_date,
            daily_logs_repo=daily_logs_repo,
            meals_repo=meals_repo,
            weekly_schedule_repo=weekly_schedule_repo,
        )
        budget_result = _build_budget(
            current_user=current_user,
            day_date=day_date,
            meals_repo=meals_repo,
            activities_repo=activities_repo,
            weight_repo=weight_repo,
        )
    except RepositoryError as exc:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=str(exc),
        ) from exc

    actual = budget_result.get("actual") or {}
    budget = budget_result.get("budget") or {}

    try:
        day_activities = (
            activities_repo.list_for_date(
                current_user.id,
                day_date,
            )
        )
    except RepositoryError as exc:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=str(exc),
        ) from exc

    training_activities = [
        activity
        for activity in day_activities
        if _is_briefing_training(activity)
    ]

    consumed_kcal = float(
        budget.get(
            "consumed_kcal",
            actual.get("consumed_kcal", 0),
        )
        or 0
    )
    daily_budget_kcal = float(
        budget.get("daily_budget_kcal", 0) or 0
    )
    maintenance_kcal = float(
        budget.get("maintenance_kcal", 0) or 0
    )

    metadata = current_user.metadata or {}
    full_name = (
        metadata.get("first_name")
        or metadata.get("name")
        or metadata.get("full_name")
        or ""
    )
    first_name = str(full_name).strip().split(" ")[0]
    city = str(
        metadata.get("city") or ""
    ).strip()

    daily_context = {}

    if moment == "morning" and city:
        daily_context = DailyContextService(
            timeout=2.0,
        ).build(
            city=city,
            day_date=day_date,
        )

    payload = {
        "first_name": first_name,
        "moment": moment,
        "daily_context": daily_context,
        "day_type": day.get("context", {}).get("value"),
        "activity_level": (
            day.get("activity_plan", {}).get("value")
        ),
        "meal_count": int(
            actual.get("meal_count", 0) or 0
        ),
        "activity_count": len(
            training_activities
        ),
        "activity_kcal": sum(
            float(
                activity.get(
                    "burned_calories"
                )
                or 0
            )
            for activity in training_activities
        ),
        "consumed_kcal": consumed_kcal,
        "daily_budget_kcal": daily_budget_kcal,
        "maintenance_kcal": maintenance_kcal,
        "available_kcal": float(
            budget.get("available_kcal", 0) or 0
        ),
        "status_hint": build_status_hint(
            consumed_kcal=consumed_kcal,
            daily_budget_kcal=daily_budget_kcal,
            maintenance_kcal=maintenance_kcal,
        ),
    }

    effective_hour = (
        hour
        if hour is not None
        else datetime.now().hour
    )

    activity_signature = (
        _briefing_activity_signature(
            training_activities
        )
    )

    cache_key = (
        current_user.id,
        str(day_date),
        mode,
        moment,
        effective_hour,
        payload["day_type"],
        payload["activity_level"],
        payload["status_hint"],
        payload["meal_count"],
        repr(payload["daily_context"]),
        _briefing_calorie_bucket(
            payload["available_kcal"]
        ),
        _briefing_calorie_bucket(
            payload["consumed_kcal"]
        ),
        activity_signature,
    )

    cached_entry = _DAY_BRIEFING_CACHE.get(
        cache_key
    )

    if cached_entry is not None:
        expires_at, cached_response = (
            cached_entry
        )

        if expires_at > time.monotonic():
            return {
                **cached_response,
                "cached": True,
            }

        _DAY_BRIEFING_CACHE.pop(
            cache_key,
            None,
        )

    try:
        message = DayBriefingService().generate(
            payload,
            mode=mode,
        )
        source = "ai"
    except DayBriefingError:
        message = fallback_day_briefing(
            payload,
            mode=mode,
        )
        source = "fallback"

    response = {
        "date": str(day_date),
        "mode": mode,
        "message": message,
        "source": source,
        "cached": False,
    }

    if len(_DAY_BRIEFING_CACHE) >= 512:
        _DAY_BRIEFING_CACHE.clear()

    _DAY_BRIEFING_CACHE[cache_key] = (
        time.monotonic()
        + _DAY_BRIEFING_CACHE_TTL_SECONDS,
        response,
    )
    return response


@router.get("/{day_date}")
def get_day(
    day_date: Date,
    current_user: CurrentUser = Depends(get_current_user),
    daily_logs_repo: DailyLogsRepository = Depends(
        get_daily_logs_repository
    ),
    meals_repo: MealsRepository = Depends(
        get_meals_repository
    ),
    weekly_schedule_repo: WeeklyScheduleRepository = Depends(
        get_weekly_schedule_repository
    ),
):
    try:
        return _build_day(
            user_id=current_user.id,
            day_date=day_date,
            daily_logs_repo=daily_logs_repo,
            meals_repo=meals_repo,
            weekly_schedule_repo=weekly_schedule_repo,
        )
    except RepositoryError as exc:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=str(exc),
        ) from exc
