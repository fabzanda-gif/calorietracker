from __future__ import annotations


class NextMealReplanningService:
    """
    Identify the next standard meal slot that has not yet
    been logged.

    V1 considers only breakfast, lunch and dinner.
    Extra meal types do not alter the normal sequence.
    """

    SLOT_SEQUENCE = (
        ("breakfast", "Colazione"),
        ("lunch", "Pranzo"),
        ("dinner", "Cena"),
    )

    def next_slot(
        self,
        *,
        logged_meal_types: list[str],
    ) -> str | None:
        logged = {
            str(meal_type).strip()
            for meal_type in logged_meal_types
            if meal_type
        }

        for slot, meal_type in self.SLOT_SEQUENCE:
            if meal_type not in logged:
                return slot

        return None
