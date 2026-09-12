from __future__ import annotations

from typing import Any

from .base import BaseRepository, RepositoryError


ADAPTATION_SELECT = (
    "id,user_id,training_plan_id,"
    "source_planned_activity_id,"
    "target_planned_activity_id,"
    "outcome,recommended_action,decision,"
    "load_ratio,title,message,"
    "proposed_changes,before_state,after_state,"
    "created_at"
)


class TrainingPlanAdaptationsRepository(
    BaseRepository
):
    table_name = "training_plan_adaptations"

    def create(
        self,
        payload: dict[str, Any],
    ) -> dict | None:
        try:
            response = (
                self.table
                .insert(payload)
                .execute()
            )

            rows = self._data(response)

            return rows[0] if rows else None

        except Exception as exc:
            raise RepositoryError(
                "Unable to save training plan "
                f"adaptation: {exc}"
            ) from exc

    def list_for_plan(
        self,
        user_id: str,
        training_plan_id: Any,
    ) -> list[dict]:
        try:
            response = (
                self.table
                .select(ADAPTATION_SELECT)
                .eq("user_id", user_id)
                .eq(
                    "training_plan_id",
                    training_plan_id,
                )
                .order(
                    "created_at",
                    desc=True,
                )
                .execute()
            )

            return self._data(response)

        except Exception as exc:
            raise RepositoryError(
                "Unable to load training plan "
                f"adaptations: {exc}"
            ) from exc
