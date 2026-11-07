from __future__ import annotations


class RecipeRecommendationService:
    @staticmethod
    def _normalize_name(value: object) -> str:
        return " ".join(
            str(value or "")
            .strip()
            .casefold()
            .split()
        )

    def select(
        self,
        *,
        recipes: list[dict],
        history: list[dict],
        user_id: str,
    ) -> list[dict]:
        cooked_names = {
            self._normalize_name(
                meal.get("base_name")
                or meal.get("name")
            )
            for meal in history
            if (
                meal.get("base_name")
                or meal.get("name")
            )
        }

        personal: list[dict] = []
        shared_cooked: list[dict] = []

        for recipe in recipes:
            recipe_name = self._normalize_name(
                recipe.get("name")
            )

            if (
                str(recipe.get("user_id"))
                == str(user_id)
            ):
                item = dict(recipe)
                item["_recommendation_scope"] = (
                    "personal"
                )
                personal.append(item)
                continue

            if (
                bool(recipe.get("is_shared"))
                and recipe_name
                and recipe_name in cooked_names
            ):
                item = dict(recipe)
                item["_recommendation_scope"] = (
                    "shared_cooked"
                )
                shared_cooked.append(item)

        return [
            *personal,
            *shared_cooked,
        ]
