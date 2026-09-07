from __future__ import annotations

from datetime import date
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, Field

from backend.services.conversational_meal_logging import (
    ConversationalMealLoggingService,
)
from backend.services.conversational_meal_confirmation import (
    ConversationalMealConfirmationService,
)
from backend.services.meal_text_interpreter import (
    MealTextInterpreter,
)
from backend.services.groq_meal_interpreter import (
    GroqMealInterpreter,
)
from backend.services.groq_day_log_interpreter import (
    GroqDayLogInterpreter,
    GroqDayLogInterpreterError,
)
from backend.services.activity_movement import (
    estimated_gpx_calories,
    normalize_activity_type,
)
from backend.services.groq_meal_vision_interpreter import (
    GroqMealVisionInterpreter,
)

from backend.api.dependencies import (
    CurrentUser,
    get_current_user,
    get_ingredients_repository,
    get_meal_ingredients_repository,
    get_meal_prep_repository,
    get_meals_repository,
    get_recipe_ingredients_repository,
    get_recipes_repository,
    get_weight_repository,
    get_pantry_repository,
)
from backend.repositories.base import RepositoryError
from backend.repositories.ingredients import IngredientsRepository
from backend.repositories.meal_ingredients import (
    MealIngredientsRepository,
)
from backend.repositories.meal_prep import MealPrepRepository
from backend.repositories.meals import MealsRepository
from backend.repositories.recipe_ingredients import (
    RecipeIngredientsRepository,
)
from backend.repositories.recipes import RecipesRepository
from backend.repositories.weight import WeightRepository
from backend.repositories.pantry import PantryRepository
from backend.services.structured_meal import (
    StructuredMealError,
    StructuredMealService,
)


router = APIRouter(prefix="/meals", tags=["meals"])


class StructuredMealIngredient(BaseModel):
    ingredient_id: str
    quantity: float = Field(gt=0)
    unit: str = "g"
    quantity_g: float = Field(gt=0)


class MealCreate(BaseModel):
    date: date
    meal_type: str = Field(min_length=1)
    name: str = Field(min_length=1)

    calories: float = 0
    protein: float = 0
    carbs: float = 0
    fat: float = 0
    structured_ingredients: list[StructuredMealIngredient] | None = None

    base_name: str | None = None
    quantity: float | None = None
    is_per_100g: bool | None = None

    base_calories: float | None = None
    base_protein: float | None = None
    base_carbs: float | None = None
    base_fat: float | None = None

    notes: str | None = None
    category: str | None = None
    is_reusable: bool | None = None
    ingredients_json: Any | None = None
    recipe_servings: float | None = None
    is_shared: bool | None = None
    image_url: str | None = None


def interpret_meal_text(
    *,
    text: str,
    meal_type: str,
) -> dict:
    return GroqMealInterpreter().interpret(
        text=text,
        meal_type=meal_type,
    )


def interpret_day_log_text(
    *,
    text: str,
    default_meal_type: str,
) -> dict:
    return GroqDayLogInterpreter().interpret(
        text=text,
        default_meal_type=default_meal_type,
    )


class ConversationalMealPreviewRequest(BaseModel):
    text: str = Field(min_length=1)
    meal_type: str



class ConversationalDayPreviewRequest(BaseModel):
    text: str = Field(min_length=1)
    default_meal_type: str = "Pranzo"


class PhotoMealPreviewRequest(BaseModel):
    image_base64: str = Field(min_length=1)
    mime_type: str = "image/jpeg"
    meal_type: str
class ConversationalMealItem(BaseModel):
    name: str = Field(min_length=1)
    quantity: float = Field(gt=0)
    unit: str = Field(min_length=1)
    quantity_g: float = Field(gt=0)
    calories: float = Field(ge=0)
    protein: float = Field(default=0, ge=0)
    carbs: float = Field(default=0, ge=0)
    fat: float = Field(default=0, ge=0)


class ConversationalMealConfirmRequest(BaseModel):
    date: date
    meal_type: str = Field(min_length=1)
    items: list[ConversationalMealItem] = Field(min_length=1)


class MealUpdate(BaseModel):
    meal_type: str | None = None
    name: str | None = None

    calories: float | None = None
    protein: float | None = None
    carbs: float | None = None
    fat: float | None = None
    structured_ingredients: list[StructuredMealIngredient] | None = None

    base_name: str | None = None
    quantity: float | None = None
    is_per_100g: bool | None = None

    base_calories: float | None = None
    base_protein: float | None = None
    base_carbs: float | None = None
    base_fat: float | None = None

    notes: str | None = None
    category: str | None = None
    is_reusable: bool | None = None
    ingredients_json: Any | None = None
    recipe_servings: float | None = None
    is_shared: bool | None = None
    image_url: str | None = None


# ------------------------------------------------------------------
# Historical/list endpoints.
# IMPORTANT: keep these BEFORE /{meal_date}, otherwise strings such as
# "history" or "range" could be interpreted as the dynamic date route.
# ------------------------------------------------------------------

@router.post("/conversational/day-preview")
def preview_conversational_day(
    request: ConversationalDayPreviewRequest,
    current_user: CurrentUser = Depends(get_current_user),
    weight_repo: WeightRepository = Depends(
        get_weight_repository
    ),
):
    try:
        interpretation = interpret_day_log_text(
            text=request.text,
            default_meal_type=request.default_meal_type,
        )
    except GroqDayLogInterpreterError as exc:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=str(exc),
        ) from exc

    intents = list(
        interpretation.get("intents")
        or []
    )

    if not intents:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail=(
                "Non ho trovato pasti, attività o peso "
                "da registrare."
            ),
        )

    latest_weight = None

    if any(
        item.get("kind") == "activity"
        for item in intents
    ):
        try:
            latest_weight = weight_repo.latest(
                current_user.id
            )
        except RepositoryError:
            # La preview resta utilizzabile. Senza peso,
            # la stima usa il profilo standard dell'attività.
            latest_weight = None

    actions: list[dict[str, Any]] = []

    valid_meal_types = {
        "Colazione",
        "Pranzo",
        "Snack",
        "Cena",
    }

    for intent in intents:
        kind = str(
            intent.get("kind")
            or ""
        ).strip()

        if kind == "meal":
            meal_text = str(
                intent.get("text")
                or request.text
            ).strip()

            if not meal_text:
                continue

            meal_type = str(
                intent.get("meal_type")
                or request.default_meal_type
            ).strip()

            if meal_type not in valid_meal_types:
                meal_type = request.default_meal_type

            if meal_type not in valid_meal_types:
                meal_type = "Pranzo"

            raw_meal = interpret_meal_text(
                text=meal_text,
                meal_type=meal_type,
            )

            normalized = MealTextInterpreter().normalize(
                raw_meal
            )

            meal_preview = (
                ConversationalMealLoggingService()
                .build_preview(
                    text=meal_text,
                    meal_type=normalized["meal_type"],
                    interpreted_items=normalized["items"],
                )
            )

            actions.append(
                {
                    "id": (
                        f"action-{len(actions) + 1}"
                    ),
                    "kind": "meal",
                    "text": meal_text,
                    "meal_type": (
                        meal_preview["meal_type"]
                    ),
                    "items": meal_preview["items"],
                    "totals": meal_preview["totals"],
                    "needs_review": bool(
                        meal_preview["needs_review"]
                        or intent.get("uncertainty")
                    ),
                    "requires_confirmation": True,
                }
            )
            continue

        if kind == "activity":
            activity_name = str(
                intent.get("activity_name")
                or intent.get("activity_type")
                or "Attività"
            ).strip()

            activity_type = normalize_activity_type(
                intent.get("activity_type")
                or activity_name
            )

            duration_raw = intent.get(
                "duration_seconds"
            )
            duration_seconds = (
                max(0, int(duration_raw))
                if duration_raw is not None
                else None
            )

            distance_raw = intent.get(
                "distance_meters"
            )
            distance_meters = (
                max(0.0, float(distance_raw))
                if distance_raw is not None
                else None
            )

            explicit_calories = intent.get(
                "burned_calories"
            )

            calories_estimated = (
                explicit_calories is None
            )

            if explicit_calories is None:
                burned_calories = (
                    estimated_gpx_calories(
                        activity_type=activity_type,
                        duration_seconds=duration_seconds,
                        distance_meters=distance_meters,
                        weight_kg=(
                            (latest_weight or {})
                            .get("weight")
                        ),
                    )
                )
            else:
                burned_calories = max(
                    0,
                    round(
                        float(explicit_calories)
                    ),
                )

            needs_review = bool(
                intent.get("uncertainty")
                or calories_estimated
                or burned_calories <= 0
            )

            actions.append(
                {
                    "id": (
                        f"action-{len(actions) + 1}"
                    ),
                    "kind": "activity",
                    "activity_name": activity_name,
                    "activity_type": activity_type,
                    "duration_seconds": duration_seconds,
                    "distance_meters": distance_meters,
                    "burned_calories": burned_calories,
                    "calories_estimated": (
                        calories_estimated
                    ),
                    "needs_review": needs_review,
                    "requires_confirmation": True,
                }
            )
            continue

        if kind == "weight":
            weight_raw = intent.get(
                "weight_kg"
            )

            if weight_raw is None:
                continue

            weight_kg = float(weight_raw)

            if weight_kg <= 0:
                continue

            actions.append(
                {
                    "id": (
                        f"action-{len(actions) + 1}"
                    ),
                    "kind": "weight",
                    "weight_kg": weight_kg,
                    "needs_review": bool(
                        intent.get("uncertainty")
                    ),
                    "requires_confirmation": True,
                }
            )

    if not actions:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail=(
                "Non ho trovato dati sufficienti "
                "da registrare."
            ),
        )

    return {
        "status": "preview",
        "original_text": request.text,
        "actions": actions,
        "needs_review": any(
            bool(action.get("needs_review"))
            for action in actions
        ),
        "requires_confirmation": True,
    }


@router.post("/conversational/preview")
def preview_conversational_meal(
    request: ConversationalMealPreviewRequest,
    current_user: CurrentUser = Depends(get_current_user),
):
    raw_interpretation = interpret_meal_text(
        text=request.text,
        meal_type=request.meal_type,
    )

    normalized = MealTextInterpreter().normalize(
        raw_interpretation
    )

    return ConversationalMealLoggingService().build_preview(
        text=request.text,
        meal_type=normalized["meal_type"],
        interpreted_items=normalized["items"],
    )



@router.post("/photo/preview")
def preview_photo_meal(
    request: PhotoMealPreviewRequest,
    current_user: CurrentUser = Depends(get_current_user),
):
    import base64

    try:
        image_bytes = base64.b64decode(
            request.image_base64,
            validate=True,
        )
    except Exception as exc:
        raise HTTPException(
            status_code=422,
            detail="Invalid image_base64",
        ) from exc

    raw_interpretation = (
        GroqMealVisionInterpreter().interpret(
            image_bytes=image_bytes,
            mime_type=request.mime_type,
            meal_type=request.meal_type,
        )
    )

    normalized = MealTextInterpreter().normalize(
        raw_interpretation
    )

    return ConversationalMealLoggingService().build_preview(
        text="[photo]",
        meal_type=normalized["meal_type"],
        interpreted_items=normalized["items"],
    )
@router.post(
    "/conversational/confirm",
    status_code=status.HTTP_201_CREATED,
)
def confirm_conversational_meal(
    request: ConversationalMealConfirmRequest,
    current_user: CurrentUser = Depends(get_current_user),
    repo: MealsRepository = Depends(get_meals_repository),
    ingredients_repo: IngredientsRepository = Depends(
        get_ingredients_repository
    ),
    meal_ingredients_repo: MealIngredientsRepository = Depends(
        get_meal_ingredients_repository
    ),
    pantry_repo: PantryRepository = Depends(
        get_pantry_repository
    ),
):
    items = [item.model_dump() for item in request.items]
    meal_name = " + ".join(item["name"] for item in items)

    try:
        result = ConversationalMealConfirmationService(
            meals_repo=repo,
            ingredients_repo=ingredients_repo,
            meal_ingredients_repo=meal_ingredients_repo,
            pantry_repo=pantry_repo,
        ).confirm(
            user_id=current_user.id,
            meal_payload={
                "date": str(request.date),
                "meal_type": request.meal_type,
                "name": meal_name or "Pasto registrato",
                "is_reusable": False,
            },
            items=items,
        )
    except (StructuredMealError, ValueError) as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail=str(exc),
        ) from exc
    except RepositoryError as exc:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=str(exc),
        ) from exc

    return {
        "created": True,
        "structured": True,
        "item": result["meal"],
        "meal_ingredients": result["meal_ingredients"],
        "pantry_consumption": result.get(
            "pantry_consumption",
            [],
        ),
    }


@router.get("/history")
def get_meal_history(
    current_user: CurrentUser = Depends(get_current_user),
    repo: MealsRepository = Depends(get_meals_repository),
):
    try:
        meals, _enhanced = repo.list_history_compatible(current_user.id)

        return {
            "count": len(meals),
            "items": meals,
        }

    except RepositoryError as exc:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=str(exc),
        ) from exc


@router.get("/range")
def get_meals_for_range(
    start_date: date = Query(...),
    end_date: date = Query(...),
    current_user: CurrentUser = Depends(get_current_user),
    repo: MealsRepository = Depends(get_meals_repository),
):
    if end_date < start_date:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="end_date must be on or after start_date",
        )

    try:
        meals = repo.list_date_range(
            user_id=current_user.id,
            start_date=start_date,
            end_date=end_date,
            columns=(
                "id,date,meal_type,name,base_name,quantity,is_per_100g,"
                "base_calories,base_protein,base_carbs,base_fat,"
                "calories,protein,carbs,fat,notes,category,is_reusable,"
                "ingredients_json,recipe_servings,is_shared,image_url"
            ),
        )

        return {
            "start_date": str(start_date),
            "end_date": str(end_date),
            "count": len(meals),
            "items": meals,
        }

    except RepositoryError as exc:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=str(exc),
        ) from exc


@router.get("/by-type/{meal_type}")
def get_meals_by_type(
    meal_type: str,
    current_user: CurrentUser = Depends(get_current_user),
    repo: MealsRepository = Depends(get_meals_repository),
):
    try:
        meals = repo.list_by_meal_type_compatible(
            current_user.id,
            meal_type,
        )

        return {
            "meal_type": meal_type,
            "count": len(meals),
            "items": meals,
        }

    except RepositoryError as exc:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=str(exc),
        ) from exc


@router.get("/item/{meal_id}")
def get_meal(
    meal_id: str,
    current_user: CurrentUser = Depends(get_current_user),
    repo: MealsRepository = Depends(get_meals_repository),
    meal_ingredients_repo: MealIngredientsRepository = Depends(
        get_meal_ingredients_repository
    ),
    recipes_repo: RecipesRepository = Depends(
        get_recipes_repository
    ),
    recipe_ingredients_repo: RecipeIngredientsRepository = Depends(
        get_recipe_ingredients_repository
    ),
):
    """
    Load one meal and its editable structured components.

    Legacy meals may predate meal_ingredients. When possible,
    recover their editable composition from a matching recipe.
    The fallback is read-only until the user saves: PATCH then
    materializes real meal_ingredients snapshots.
    """
    try:
        item = repo.get_by_id(
            meal_id,
            current_user.id,
        )

        if item is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Meal not found",
            )

        structured = (
            meal_ingredients_repo.list_for_meal(
                meal_id
            )
        )

        structured_origin = (
            "meal"
            if structured
            else None
        )

        source_recipe = None

        if not structured:
            recipe_name = (
                item.get("base_name")
                or item.get("name")
                or ""
            )

            source_recipe = (
                recipes_repo.get_available_by_name(
                    recipe_name,
                    current_user.id,
                )
            )

            if source_recipe is not None:
                recipe_components = (
                    recipe_ingredients_repo.list_for_recipe(
                        source_recipe["id"]
                    )
                )

                structured = []

                for component in recipe_components:
                    ingredient = (
                        component.get("ingredients")
                        or {}
                    )

                    quantity_g = float(
                        component.get("quantity_g")
                        or 0
                    )

                    factor = quantity_g / 100.0

                    structured.append(
                        {
                            "recipe_ingredient_id": (
                                component.get("id")
                            ),
                            "ingredient_id": (
                                component.get(
                                    "ingredient_id"
                                )
                            ),
                            "name_snapshot": (
                                ingredient.get("name")
                                or "Ingrediente"
                            ),
                            "quantity": component.get(
                                "quantity"
                            ),
                            "unit": (
                                component.get("unit")
                                or "g"
                            ),
                            "quantity_g": quantity_g,
                            "calories": round(
                                float(
                                    ingredient.get(
                                        "calories_per_100g"
                                    )
                                    or 0
                                )
                                * factor,
                                2,
                            ),
                            "protein": round(
                                float(
                                    ingredient.get(
                                        "protein_per_100g"
                                    )
                                    or 0
                                )
                                * factor,
                                2,
                            ),
                            "carbs": round(
                                float(
                                    ingredient.get(
                                        "carbs_per_100g"
                                    )
                                    or 0
                                )
                                * factor,
                                2,
                            ),
                            "fat": round(
                                float(
                                    ingredient.get(
                                        "fat_per_100g"
                                    )
                                    or 0
                                )
                                * factor,
                                2,
                            ),
                        }
                    )

                if structured:
                    structured_origin = "recipe"

        return {
            "item": {
                **item,
                "structured_ingredients": structured,
                "structured_origin": structured_origin,
                "source_recipe_id": (
                    source_recipe.get("id")
                    if source_recipe is not None
                    else None
                ),
            }
        }

    except HTTPException:
        raise

    except RepositoryError as exc:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=str(exc),
        ) from exc


@router.get("/{meal_date}")
def get_meals_for_date(
    meal_date: date,
    current_user: CurrentUser = Depends(get_current_user),
    repo: MealsRepository = Depends(get_meals_repository),
):
    try:
        meals = repo.list_for_date_compatible(
            user_id=current_user.id,
            log_date=meal_date,
        )

        return {
            "date": str(meal_date),
            "count": len(meals),
            "items": meals,
        }

    except RepositoryError as exc:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=str(exc),
        ) from exc


@router.post("", status_code=status.HTTP_201_CREATED)
def create_meal(
    meal: MealCreate,
    current_user: CurrentUser = Depends(get_current_user),
    repo: MealsRepository = Depends(get_meals_repository),
    ingredients_repo: IngredientsRepository = Depends(
        get_ingredients_repository
    ),
    meal_ingredients_repo: MealIngredientsRepository = Depends(
        get_meal_ingredients_repository
    ),
):
    payload = meal.model_dump(
        mode="json",
        exclude_none=True,
    )

    structured = payload.pop(
        "structured_ingredients",
        None,
    )

    # Database calories column is INTEGER.
    # Pydantic may serialize Decimal values as strings such as "210.0".
    for field in (
        "calories",
        "protein",
        "carbs",
        "fat",
    ):
        if (
            field in payload
            and payload[field] is not None
        ):
            payload[field] = int(
                round(float(payload[field]))
            )

    try:
        if structured is not None:
            result = StructuredMealService(
                meals_repo=repo,
                ingredients_repo=ingredients_repo,
                meal_ingredients_repo=meal_ingredients_repo,
            ).create(
                user_id=current_user.id,
                meal_payload=payload,
                structured_ingredients=structured,
            )

            return {
                "created": True,
                "structured": True,
                "item": result["meal"],
                "meal_ingredients": result[
                    "meal_ingredients"
                ],
            }

        payload["user_id"] = current_user.id

        # Legacy meals table stores nutrition as integers.
        # Pydantic exposes numeric MealCreate fields as floats,
        # so normalize them before sending the payload to Supabase.
        for key in (
            "calories",
            "protein",
            "carbs",
            "fat",
        ):
            if key in payload:
                payload[key] = int(
                    round(float(payload[key] or 0))
                )

        item = repo.create(payload)

        return {
            "created": True,
            "structured": False,
            "item": item if item is not None else payload,
        }

    except StructuredMealError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail=str(exc),
        ) from exc

    except RepositoryError as exc:
        print(
            "CREATE MEAL REPOSITORY ERROR:",
            repr(exc),
            flush=True,
        )
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=str(exc),
        ) from exc


@router.patch("/{meal_id}")
def update_meal(
    meal_id: str,
    changes: MealUpdate,
    current_user: CurrentUser = Depends(get_current_user),
    repo: MealsRepository = Depends(get_meals_repository),
    ingredients_repo: IngredientsRepository = Depends(
        get_ingredients_repository
    ),
    meal_ingredients_repo: MealIngredientsRepository = Depends(
        get_meal_ingredients_repository
    ),
):
    """
    Update a legacy meal or rebuild a structured meal.

    When structured_ingredients are supplied, nutrition is
    recalculated and meal_ingredients snapshots are replaced.
    """
    payload = changes.model_dump(
        mode="json",
        exclude_unset=True,
    )

    if not payload:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No fields supplied",
        )

    structured = payload.pop(
        "structured_ingredients",
        None,
    )

    # Keep PATCH consistent with POST: the database stores all
    # nutrition columns as integers, while clients may send floats
    # after scaling grams or portions.
    for field in (
        "calories",
        "protein",
        "carbs",
        "fat",
    ):
        if (
            field in payload
            and payload[field] is not None
        ):
            payload[field] = int(
                round(float(payload[field]))
            )

    try:
        if structured is not None:
            result = StructuredMealService(
                meals_repo=repo,
                ingredients_repo=ingredients_repo,
                meal_ingredients_repo=meal_ingredients_repo,
            ).update(
                user_id=current_user.id,
                meal_id=meal_id,
                meal_payload=payload,
                structured_ingredients=structured,
            )

            return {
                "updated": True,
                "structured": True,
                "item": result["meal"],
                "meal_ingredients": result[
                    "meal_ingredients"
                ],
            }

        item = repo.update(
            meal_id=meal_id,
            user_id=current_user.id,
            payload=payload,
        )

        return {
            "updated": True,
            "structured": False,
            "item": item,
        }

    except StructuredMealError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail=str(exc),
        ) from exc

    except RepositoryError as exc:
        print(
            "UPDATE MEAL REPOSITORY ERROR:",
            repr(exc),
            flush=True,
        )
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=str(exc),
        ) from exc


@router.delete(
    "/{meal_id}",
    status_code=status.HTTP_200_OK,
)
def delete_meal(
    meal_id: str,
    current_user: CurrentUser = Depends(get_current_user),
    repo: MealsRepository = Depends(get_meals_repository),
    meal_prep_repo: MealPrepRepository = Depends(
        get_meal_prep_repository
    ),
):
    try:
        meal = repo.get_by_id(
            meal_id=meal_id,
            user_id=current_user.id,
        )

        if meal is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Meal not found",
            )

        is_meal_prep = (
            meal.get("category") == "meal_prep"
        )

        batch_id = None

        if is_meal_prep:
            notes = str(meal.get("notes") or "")
            prefix = "Meal prep batch: "

            if prefix in notes:
                batch_id = (
                    notes.split(prefix, 1)[1]
                    .split(";", 1)[0]
                    .strip()
                )

        restored = False

        if batch_id:
            batch = meal_prep_repo.get_by_id(
                batch_id,
                current_user.id,
            )

            if batch is not None:
                remaining = int(
                    batch.get("portions_remaining") or 0
                )
                prepared = int(
                    batch.get("portions_prepared") or 0
                )

                new_remaining = min(
                    prepared,
                    remaining + 1,
                )

                updated_batch = meal_prep_repo.update(
                    batch_id,
                    current_user.id,
                    {
                        "portions_remaining": new_remaining,
                        "status": "available",
                    },
                )

                if updated_batch is not None:
                    restored = True

        repo.delete(
            meal_id=meal_id,
            user_id=current_user.id,
        )

        return {
            "deleted": True,
            "id": meal_id,
            "inventory_restored": restored,
            "meal_prep_batch_id": batch_id,
        }

    except HTTPException:
        raise

    except RepositoryError as exc:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=str(exc),
        ) from exc
