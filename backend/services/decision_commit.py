from __future__ import annotations

from typing import Any

from backend.repositories.base import RepositoryError
from backend.repositories.decision_selections import (
    DecisionSelectionsRepository,
)
from backend.repositories.meals import MealsRepository
from backend.services.decision_selection import (
    DecisionSelectionService,
)


class DecisionCommitError(RuntimeError):
    pass


class DecisionCommitService:
    """
    Persist a decision selection and its realized meal in one application-level
    operation.

    This is not a database transaction, because the two repositories are
    independent. If meal creation fails after selection persistence, the
    selection is removed on a best-effort basis.
    """

    MEAL_SLOT_TO_TYPE = {
        "breakfast": "Colazione",
        "lunch": "Pranzo",
        "dinner": "Cena",
    }

    def __init__(
        self,
        selections_repo: DecisionSelectionsRepository,
        meals_repo: MealsRepository,
    ):
        self.selections_repo = selections_repo
        self.meals_repo = meals_repo

    def commit(
        self,
        *,
        user_id: str,
        day_date: Any,
        meal_slot: str,
        mode: str,
        lens: str,
        option_index: int,
        candidate: dict[str, Any],
        available_kcal: float | None = None,
        protein_remaining_g: float | None = None,
    ) -> dict:
        meal_type = self.MEAL_SLOT_TO_TYPE.get(meal_slot)

        if meal_type is None:
            raise DecisionCommitError(
                "Unknown meal slot"
            )

        candidate_name = str(
            candidate.get("name") or ""
        ).strip()

        if not candidate_name:
            raise DecisionCommitError(
                "Candidate name is required"
            )

        existing = self._existing_meal(
            user_id=user_id,
            day_date=day_date,
            meal_type=meal_type,
            candidate_name=candidate_name,
        )

        if existing is not None:
            return {
                "committed": True,
                "already_committed": True,
                "selection": None,
                "meal": existing,
            }

        event = DecisionSelectionService().build_event(
            user_id=user_id,
            day_date=day_date,
            meal_slot=meal_slot,
            meal_type=meal_type,
            mode=mode,
            lens=lens,
            candidate=candidate,
            option_index=option_index,
            available_kcal=available_kcal,
            protein_remaining_g=protein_remaining_g,
        )

        selection = self.selections_repo.create(
            event
        )

        selection_id = (
            selection.get("id")
            if selection is not None
            else None
        )

        meal_payload = {
            "user_id": user_id,
            "date": str(day_date),
            "meal_type": meal_type,
            "name": candidate_name,
            "base_name": candidate_name,
            "calories": self._integer_number(
                candidate.get("calories")
            ),
            "protein": self._integer_number(
                candidate.get("protein_g")
                if candidate.get("protein_g") is not None
                else candidate.get("protein")
            ),
            "carbs": self._integer_number(
                candidate.get("carbs_g")
                if candidate.get("carbs_g") is not None
                else candidate.get("carbs")
            ),
            "fat": self._integer_number(
                candidate.get("fat_g")
                if candidate.get("fat_g") is not None
                else candidate.get("fat")
            ),
            "category": (
                str(candidate.get("source"))
                if candidate.get("source")
                else None
            ),
            "notes": "SanoSync decision",
        }

        meal_payload = {
            key: value
            for key, value in meal_payload.items()
            if value is not None
        }

        try:
            response = self.meals_repo.create_compatible(
                meal_payload
            )
            rows = getattr(
                response,
                "data",
                None,
            ) or []

            meal = (
                rows[0]
                if rows
                else meal_payload
            )

            return {
                "committed": True,
                "already_committed": False,
                "selection": (
                    selection
                    if selection is not None
                    else event
                ),
                "meal": meal,
            }

        except Exception as exc:
            if selection_id is not None:
                try:
                    self.selections_repo.delete(
                        selection_id,
                        user_id,
                    )
                except RepositoryError:
                    pass

            if isinstance(
                exc,
                RepositoryError,
            ):
                raise

            raise DecisionCommitError(
                f"Unable to create meal: {exc}"
            ) from exc

    def _existing_meal(
        self,
        *,
        user_id: str,
        day_date: Any,
        meal_type: str,
        candidate_name: str,
    ) -> dict | None:
        meals = (
            self.meals_repo.list_for_date_compatible(
                user_id,
                day_date,
            )
        )

        normalized_name = self._normalize(
            candidate_name
        )

        for meal in meals:
            if (
                str(
                    meal.get("meal_type")
                    or ""
                )
                != meal_type
            ):
                continue

            meal_name = (
                meal.get("base_name")
                or meal.get("name")
            )

            if (
                self._normalize(meal_name)
                == normalized_name
            ):
                return meal

        return None

    @staticmethod
    def _normalize(value: Any) -> str:
        return " ".join(
            str(value or "")
            .strip()
            .lower()
            .split()
        )

    @staticmethod
    def _integer_number(
        value: Any,
    ) -> int:
        try:
            return int(round(float(value or 0)))
        except (
            TypeError,
            ValueError,
        ):
            return 0

    @staticmethod
    def _number(
        value: Any,
    ) -> float:
        try:
            return float(value or 0)
        except (
            TypeError,
            ValueError,
        ):
            return 0.0
