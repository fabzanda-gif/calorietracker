from __future__ import annotations

from datetime import date as Date

from fastapi import APIRouter, Depends, HTTPException, Query, status

from backend.api.dependencies import (
    CurrentUser,
    get_activities_repository,
    get_current_user,
    get_daily_logs_repository,
    get_meal_prep_repository,
    get_meals_repository,
    get_recipes_repository,
    get_weight_repository,
)
from backend.repositories.activities import ActivitiesRepository
from backend.repositories.base import RepositoryError
from backend.repositories.daily_logs import DailyLogsRepository
from backend.repositories.meal_prep import MealPrepRepository
from backend.repositories.meals import MealsRepository
from backend.repositories.recipes import RecipesRepository
from backend.repositories.weight import WeightRepository
from backend.services.day import DayService
from backend.services.day_budget import DayBudgetService
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
from backend.services.order_candidates import OrderCandidateService
from backend.services.order_personalization import (
    OrderPersonalizationService,
)


router = APIRouter(prefix="/days", tags=["days"])


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
) -> dict:
    return DayService(
        daily_logs_repo=daily_logs_repo,
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
):
    meal_type = _validate_slot(meal_slot)

    try:
        day = _build_day(
            user_id=current_user.id,
            day_date=day_date,
            daily_logs_repo=daily_logs_repo,
            meals_repo=meals_repo,
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
            ],
        )

        mode_result = DecisionModeService().apply(
            candidates=all_candidates,
            mode=normalized_mode,
        )

        ranked = DecisionRankingService().rank(
            candidates=mode_result["candidates"],
            available_kcal=available_kcal,
            protein_remaining_g=protein_remaining_g,
            mode=mode_result["mode"],
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
            "empty_reason": mode_result["empty_reason"],
            "candidates": mode_result["candidates"],
            **ranked,
        }

    except DecisionModeError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
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
):
    meal_type = _validate_slot(meal_slot)

    try:
        day = _build_day(
            user_id=current_user.id,
            day_date=day_date,
            daily_logs_repo=daily_logs_repo,
            meals_repo=meals_repo,
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
    current_user: CurrentUser = Depends(get_current_user),
    daily_logs_repo: DailyLogsRepository = Depends(
        get_daily_logs_repository
    ),
    meals_repo: MealsRepository = Depends(
        get_meals_repository
    ),
):
    _validate_slot(meal_slot)

    try:
        day = _build_day(
            user_id=current_user.id,
            day_date=day_date,
            daily_logs_repo=daily_logs_repo,
            meals_repo=meals_repo,
        )

        return MealConfirmationService(
            meals_repo
        ).confirm(
            user_id=current_user.id,
            day_date=day_date,
            prediction=day["meals"][meal_slot],
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
):
    try:
        return _build_day(
            user_id=current_user.id,
            day_date=day_date,
            daily_logs_repo=daily_logs_repo,
            meals_repo=meals_repo,
        )
    except RepositoryError as exc:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=str(exc),
        ) from exc
