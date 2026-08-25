from __future__ import annotations

from typing import Any

from .base import BaseRepository, RepositoryError


RECIPE_COLUMNS = (
    "id,user_id,name,meal_type,category,recipe_servings,"
    "calories,protein,carbs,fat,notes,ingredients_json,"
    "is_shared,image_url,created_at"
)


class RecipesRepository(BaseRepository):
    table_name = "recipe_library"

    def list_personal(self, user_id: str) -> list[dict]:
        try:
            response = (
                self.table
                .select(RECIPE_COLUMNS)
                .eq("user_id", user_id)
                .order("created_at", desc=True)
                .execute()
            )
            return self._data(response)
        except Exception as exc:
            raise RepositoryError(
                f"Unable to load personal recipes: {exc}"
            ) from exc

    def list_shared(
        self,
        exclude_user_id: str | None = None,
    ) -> list[dict]:
        try:
            query = (
                self.table
                .select(RECIPE_COLUMNS)
                .eq("is_shared", True)
            )
            if exclude_user_id:
                query = query.neq(
                    "user_id",
                    exclude_user_id,
                )
            response = query.order(
                "created_at",
                desc=True,
            ).execute()
            return self._data(response)
        except Exception as exc:
            raise RepositoryError(
                f"Unable to load shared recipes: {exc}"
            ) from exc

    def list_available(self, user_id: str) -> list[dict]:
        try:
            response = (
                self.table
                .select(RECIPE_COLUMNS)
                .or_(
                    f"user_id.eq.{user_id},"
                    "is_shared.eq.true"
                )
                .order("created_at", desc=True)
                .execute()
            )
            return self._data(response)
        except Exception as exc:
            raise RepositoryError(
                f"Unable to load available recipes: {exc}"
            ) from exc

    def get_available_by_name(
        self,
        name: str,
        user_id: str,
    ) -> dict | None:
        """
        Find an available recipe by its canonical name.

        Personal recipes win over shared recipes with the
        same name.
        """
        target = " ".join(
            str(name or "").strip().casefold().split()
        )

        if not target:
            return None

        matches = []

        for row in self.list_available(user_id):
            candidate = " ".join(
                str(row.get("name") or "")
                .strip()
                .casefold()
                .split()
            )

            if candidate == target:
                matches.append(row)

        if not matches:
            return None

        matches.sort(
            key=lambda row: (
                str(row.get("user_id")) == str(user_id),
            ),
            reverse=True,
        )

        return matches[0]

    def get_personal_by_id(
        self,
        recipe_id: Any,
        user_id: str,
    ) -> dict | None:
        try:
            response = (
                self.table
                .select(RECIPE_COLUMNS)
                .eq("id", recipe_id)
                .eq("user_id", user_id)
                .limit(1)
                .execute()
            )
            rows = self._data(response)
            return rows[0] if rows else None
        except Exception as exc:
            raise RepositoryError(
                f"Unable to load recipe: {exc}"
            ) from exc

    def create_response(self, payload: dict):
        try:
            return self.table.insert(payload).execute()
        except Exception as exc:
            raise RepositoryError(
                f"Unable to create recipe: {exc}"
            ) from exc

    def create(self, payload: dict) -> dict | None:
        response = self.create_response(payload)
        rows = self._data(response)
        return rows[0] if rows else None

    def update(
        self,
        recipe_id: Any,
        user_id: str,
        payload: dict,
    ) -> dict | None:
        try:
            response = (
                self.table
                .update(payload)
                .eq("id", recipe_id)
                .eq("user_id", user_id)
                .execute()
            )
            rows = self._data(response)
            return rows[0] if rows else None
        except Exception as exc:
            raise RepositoryError(
                f"Unable to update recipe: {exc}"
            ) from exc

    def set_shared(
        self,
        recipe_id: Any,
        user_id: str,
        is_shared: bool,
    ) -> dict | None:
        return self.update(
            recipe_id=recipe_id,
            user_id=user_id,
            payload={"is_shared": bool(is_shared)},
        )

    def delete(
        self,
        recipe_id: Any,
        user_id: str,
    ) -> bool:
        try:
            (
                self.table
                .delete()
                .eq("id", recipe_id)
                .eq("user_id", user_id)
                .execute()
            )
            return True
        except Exception as exc:
            raise RepositoryError(
                f"Unable to delete recipe: {exc}"
            ) from exc
