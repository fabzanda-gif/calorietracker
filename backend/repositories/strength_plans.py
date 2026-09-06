from __future__ import annotations

from typing import Any

from .base import BaseRepository, RepositoryError


STRENGTH_PLAN_SELECT = (
    "id,user_id,goal,experience_level,"
    "program_style,sessions_per_week,"
    "start_date,total_weeks,status,"
    "created_at,updated_at"
)


class StrengthPlansRepository(BaseRepository):
    table_name = "strength_plans"

    def list_for_user(
        self,
        user_id: str,
    ) -> list[dict]:
        try:
            response = (
                self.table
                .select(STRENGTH_PLAN_SELECT)
                .eq("user_id", user_id)
                .order(
                    "created_at",
                    desc=True,
                )
                .execute()
            )

            return self._data(response)

        except Exception as exc:
            raise RepositoryError(
                "Unable to load strength plans: "
                f"{exc}"
            ) from exc

    def get(
        self,
        plan_id: Any,
        user_id: str,
    ) -> dict | None:
        try:
            response = (
                self.table
                .select(STRENGTH_PLAN_SELECT)
                .eq("id", plan_id)
                .eq("user_id", user_id)
                .limit(1)
                .execute()
            )

            rows = self._data(response)

            return rows[0] if rows else None

        except Exception as exc:
            raise RepositoryError(
                "Unable to load strength plan: "
                f"{exc}"
            ) from exc

    def update_status(
        self,
        *,
        plan_id: Any,
        user_id: str,
        status: str,
    ) -> dict | None:
        try:
            response = (
                self.table
                .update({"status": status})
                .eq("id", plan_id)
                .eq("user_id", user_id)
                .execute()
            )

            rows = self._data(response)

            return rows[0] if rows else None

        except Exception as exc:
            raise RepositoryError(
                "Unable to update strength plan: "
                f"{exc}"
            ) from exc

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
                "Unable to create strength plan: "
                f"{exc}"
            ) from exc


    def delete(
        self,
        plan_id: Any,
        user_id: str,
    ) -> bool:
        try:
            (
                self.table
                .delete()
                .eq("id", plan_id)
                .eq("user_id", user_id)
                .execute()
            )

            return True

        except Exception as exc:
            raise RepositoryError(
                "Unable to delete strength plan: "
                f"{exc}"
            ) from exc
