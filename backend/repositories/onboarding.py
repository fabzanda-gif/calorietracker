from __future__ import annotations

from typing import Any

from .base import BaseRepository, RepositoryError


class OnboardingRepository(BaseRepository):
    """Persistence for modular onboarding and module-specific profiles."""

    table_name = "user_preferences"

    def _get_one(
        self,
        table_name: str,
        user_id: str,
        select: str = "*",
    ) -> dict | None:
        try:
            response = (
                self.supabase
                .table(table_name)
                .select(select)
                .eq("user_id", user_id)
                .limit(1)
                .execute()
            )
            rows = self._data(response)
            return rows[0] if rows else None
        except Exception as exc:
            raise RepositoryError(
                f"Unable to load {table_name}: {exc}"
            ) from exc

    def get_preferences(
        self,
        user_id: str,
    ) -> dict | None:
        return self._get_one(
            "user_preferences",
            user_id,
        )

    def get_nutrition_profile(
        self,
        user_id: str,
    ) -> dict | None:
        return self._get_one(
            "nutrition_profiles",
            user_id,
        )

    def get_training_profile(
        self,
        user_id: str,
    ) -> dict | None:
        return self._get_one(
            "training_profiles",
            user_id,
        )

    def list_preferred_days(
        self,
        user_id: str,
    ) -> list[int]:
        try:
            response = (
                self.supabase
                .table("training_preferred_days")
                .select("weekday")
                .eq("user_id", user_id)
                .order("weekday")
                .execute()
            )
            return [
                int(row["weekday"])
                for row in self._data(response)
            ]
        except Exception as exc:
            raise RepositoryError(
                "Unable to load training preferred days: "
                f"{exc}"
            ) from exc

    def list_muscle_priorities(
        self,
        user_id: str,
    ) -> list[str]:
        try:
            response = (
                self.supabase
                .table("training_muscle_priorities")
                .select("muscle_key")
                .eq("user_id", user_id)
                .order("muscle_key")
                .execute()
            )
            return [
                str(row["muscle_key"])
                for row in self._data(response)
            ]
        except Exception as exc:
            raise RepositoryError(
                "Unable to load training muscle priorities: "
                f"{exc}"
            ) from exc

    def _upsert(
        self,
        table_name: str,
        payload: dict[str, Any],
    ) -> dict | None:
        try:
            response = (
                self.supabase
                .table(table_name)
                .upsert(
                    payload,
                    on_conflict="user_id",
                )
                .execute()
            )
            rows = self._data(response)
            return rows[0] if rows else None
        except Exception as exc:
            raise RepositoryError(
                f"Unable to save {table_name}: {exc}"
            ) from exc

    def upsert_preferences(
        self,
        payload: dict[str, Any],
    ) -> dict | None:
        return self._upsert(
            "user_preferences",
            payload,
        )

    def upsert_nutrition_profile(
        self,
        payload: dict[str, Any],
    ) -> dict | None:
        return self._upsert(
            "nutrition_profiles",
            payload,
        )

    def upsert_training_profile(
        self,
        payload: dict[str, Any],
    ) -> dict | None:
        return self._upsert(
            "training_profiles",
            payload,
        )

    def replace_preferred_days(
        self,
        user_id: str,
        weekdays: list[int],
    ) -> None:
        try:
            (
                self.supabase
                .table("training_preferred_days")
                .delete()
                .eq("user_id", user_id)
                .execute()
            )

            if weekdays:
                (
                    self.supabase
                    .table("training_preferred_days")
                    .insert([
                        {
                            "user_id": user_id,
                            "weekday": weekday,
                        }
                        for weekday in weekdays
                    ])
                    .execute()
                )
        except Exception as exc:
            raise RepositoryError(
                "Unable to save training preferred days: "
                f"{exc}"
            ) from exc

    def replace_muscle_priorities(
        self,
        user_id: str,
        muscle_keys: list[str],
    ) -> None:
        try:
            (
                self.supabase
                .table("training_muscle_priorities")
                .delete()
                .eq("user_id", user_id)
                .execute()
            )

            if muscle_keys:
                (
                    self.supabase
                    .table("training_muscle_priorities")
                    .insert([
                        {
                            "user_id": user_id,
                            "muscle_key": key,
                        }
                        for key in muscle_keys
                    ])
                    .execute()
                )
        except Exception as exc:
            raise RepositoryError(
                "Unable to save training muscle priorities: "
                f"{exc}"
            ) from exc
