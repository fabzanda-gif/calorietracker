from __future__ import annotations

from typing import Any

from .base import BaseRepository, RepositoryError


MEAL_COLUMNS = (
    "id,user_id,date,meal_type,name,base_name,quantity,is_per_100g,"
    "base_calories,base_protein,base_carbs,base_fat,"
    "calories,protein,carbs,fat,notes,category,is_reusable,"
    "ingredients_json,recipe_servings,is_shared,image_url"
)

LEGACY_MEAL_COLUMNS = (
    "id,user_id,date,meal_type,name,calories,protein,carbs,fat"
)


class MealsRepository(BaseRepository):
    table_name = "meals"

    def list_for_date_compatible(
        self,
        user_id: str,
        log_date: Any,
    ) -> list[dict]:
        try:
            response = (
                self.table
                .select(MEAL_COLUMNS)
                .eq("user_id", user_id)
                .eq("date", str(log_date))
                .execute()
            )
            return self._data(response)
        except Exception:
            try:
                response = (
                    self.table
                    .select(LEGACY_MEAL_COLUMNS)
                    .eq("user_id", user_id)
                    .eq("date", str(log_date))
                    .execute()
                )
                return self._data(response)
            except Exception as exc:
                raise RepositoryError(
                    f"Unable to load meals for {log_date}: {exc}"
                ) from exc

    # Alias retained for future FastAPI readability.
    def list_for_date(self, user_id: str, log_date: Any) -> list[dict]:
        return self.list_for_date_compatible(user_id, log_date)

    def list_history_compatible(
        self,
        user_id: str,
    ) -> tuple[list[dict], bool]:
        try:
            rows = (
                self.table
                .select(MEAL_COLUMNS)
                .eq("user_id", user_id)
                .order("date", desc=True)
                .execute()
            )
            return self._data(rows), True
        except Exception:
            try:
                rows = (
                    self.table
                    .select(LEGACY_MEAL_COLUMNS)
                    .eq("user_id", user_id)
                    .order("date", desc=True)
                    .execute()
                )
                return self._data(rows), False
            except Exception as exc:
                raise RepositoryError(
                    f"Unable to load meal history: {exc}"
                ) from exc

    def list_by_meal_type_compatible(
        self,
        user_id: str,
        meal_type: str,
    ) -> list[dict]:
        enhanced = (
            "id,date,meal_type,name,base_name,calories,notes,category,is_reusable"
        )
        legacy = (
            "id,date,meal_type,name,base_name,calories,notes"
        )
        try:
            response = (
                self.table
                .select(enhanced)
                .eq("user_id", user_id)
                .eq("meal_type", meal_type)
                .execute()
            )
            return self._data(response)
        except Exception:
            try:
                response = (
                    self.table
                    .select(legacy)
                    .eq("user_id", user_id)
                    .eq("meal_type", meal_type)
                    .execute()
                )
                return self._data(response)
            except Exception as exc:
                raise RepositoryError(
                    f"Unable to load meal type {meal_type}: {exc}"
                ) from exc

    def list_with_ingredients(self, user_id: str) -> list[dict]:
        try:
            response = (
                self.table
                .select(MEAL_COLUMNS)
                .eq("user_id", user_id)
                .not_.is_("ingredients_json", "null")
                .order("date", desc=True)
                .execute()
            )
            return self._data(response)
        except Exception as exc:
            raise RepositoryError(
                f"Unable to load ingredient meals: {exc}"
            ) from exc

    def list_date_range(
        self,
        user_id: str,
        start_date: Any,
        end_date: Any,
        columns: str = MEAL_COLUMNS,
    ) -> list[dict]:
        cache_key = (
            "list_date_range",
            str(user_id),
            str(start_date),
            str(end_date),
            str(columns),
        )

        cached = self._cached(cache_key)
        if cached is not None:
            return cached

        try:
            response = (
                self.table
                .select(columns)
                .eq("user_id", user_id)
                .gte("date", str(start_date))
                .lte("date", str(end_date))
                .execute()
            )
            return self._store_cache(
                cache_key,
                self._data(response),
            )
        except Exception as exc:
            raise RepositoryError(
                f"Unable to load meals in date range: {exc}"
            ) from exc

    def get_by_id(
        self,
        meal_id: Any,
        user_id: str,
    ) -> dict | None:
        try:
            response = (
                self.table
                .select(MEAL_COLUMNS)
                .eq("id", meal_id)
                .eq("user_id", user_id)
                .limit(1)
                .execute()
            )
            rows = self._data(response)
            return rows[0] if rows else None
        except Exception as exc:
            raise RepositoryError(
                f"Unable to load meal: {exc}"
            ) from exc

    def create(self, payload: dict) -> dict | None:
        try:
            response = self.table.insert(payload).execute()
            rows = self._data(response)
            return rows[0] if rows else None
        except Exception as exc:
            raise RepositoryError(
                f"Unable to create meal: {exc}"
            ) from exc

    def create_compatible(self, payload: dict):
        """
        Preserve the current SanoSync rollout compatibility:
        try the enhanced schema first, then fall back to legacy core fields.
        """
        payload = dict(payload)

        for key in ("calories", "protein", "carbs", "fat"):
            if key not in payload or payload[key] is None:
                continue

            try:
                payload[key] = int(round(float(payload[key])))
            except (TypeError, ValueError):
                payload[key] = 0

        try:
            return self.table.insert(payload).execute()
        except Exception as enhanced_exc:
            legacy_payload = {
                key: payload[key]
                for key in (
                    "user_id",
                    "date",
                    "meal_type",
                    "name",
                    "calories",
                    "protein",
                    "carbs",
                    "fat",
                )
            }
            try:
                return self.table.insert(legacy_payload).execute()
            except Exception as legacy_exc:
                raise RepositoryError(
                    "Unable to create meal with enhanced or legacy schema. "
                    f"Enhanced: {enhanced_exc}; Legacy: {legacy_exc}"
                ) from legacy_exc

    def update(
        self,
        meal_id: Any,
        user_id: str,
        payload: dict,
    ) -> dict | None:
        try:
            response = (
                self.table
                .update(payload)
                .eq("id", meal_id)
                .eq("user_id", user_id)
                .execute()
            )
            rows = self._data(response)
            return rows[0] if rows else None
        except Exception as exc:
            raise RepositoryError(
                f"Unable to update meal: {exc}"
            ) from exc

    def delete(
        self,
        meal_id: Any,
        user_id: str,
    ) -> bool:
        try:
            (
                self.table
                .delete()
                .eq("id", meal_id)
                .eq("user_id", user_id)
                .execute()
            )
            return True
        except Exception as exc:
            raise RepositoryError(
                f"Unable to delete meal: {exc}"
            ) from exc

    def breakfast_exists(
        self,
        user_id: str,
        log_date: Any,
    ) -> bool:
        try:
            response = (
                self.table
                .select("id")
                .eq("user_id", user_id)
                .eq("date", str(log_date))
                .eq("meal_type", "Colazione")
                .limit(1)
                .execute()
            )
            return bool(self._data(response))
        except Exception as exc:
            raise RepositoryError(
                f"Unable to check breakfast: {exc}"
            ) from exc
