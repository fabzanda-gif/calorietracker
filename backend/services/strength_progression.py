from __future__ import annotations

from collections import Counter
from typing import Any


class StrengthProgressionService:
    def preview(
        self,
        *,
        planned_exercise: dict,
        exercise_outcome: dict,
        set_logs: list[dict],
    ) -> dict[str, Any]:
        outcome = exercise_outcome["outcome"]

        current_load = self._representative_load(
            set_logs
        )

        pattern = planned_exercise.get(
            "movement_pattern"
        )

        increment = self._increment_for_pattern(
            pattern
        )

        action = "maintain"
        proposed_load = current_load

        if current_load <= 0:
            message = (
                "Nessun carico esterno valido da "
                "progressionare: mantieni la "
                "prescrizione."
            )

        elif outcome == "over_target":
            action = "increase_load"

            proposed_load = self._round_load(
                current_load + increment
            )

            message = (
                "Top del range raggiunto con "
                "margine: aumenta il carico alla "
                "prossima esposizione."
            )

        elif (
            outcome == "under_target"
            and self._should_reduce(
                planned_exercise=
                    planned_exercise,
                set_logs=set_logs,
            )
        ):
            action = "reduce_load"

            proposed_load = self._round_load(
                max(
                    0,
                    current_load * 0.95,
                )
            )

            if proposed_load >= current_load:
                proposed_load = self._round_load(
                    max(
                        0,
                        current_load - increment,
                    )
                )

            message = (
                "La prestazione indica che il "
                "carico è probabilmente troppo "
                "alto: riduzione prudente del 5%."
            )

        elif outcome == "under_target":
            message = (
                "Outcome sotto target, ma non ci "
                "sono prove sufficienti che il "
                "carico sia eccessivo: mantieni."
            )

        else:
            message = (
                "Prestazione in target: mantieni "
                "il carico e prova a consolidare "
                "il range."
            )

        return {
            "exercise_id": str(
                planned_exercise["id"]
            ),
            "exercise_key":
                planned_exercise.get(
                    "exercise_key"
                ),
            "exercise_name":
                planned_exercise.get(
                    "exercise_name"
                ),
            "movement_pattern": pattern,
            "outcome": outcome,
            "action": action,
            "current_load_kg":
                current_load,
            "proposed_load_kg":
                proposed_load,
            "load_change_kg": self._round_load(
                proposed_load - current_load
            ),
            "message": message,
        }

    @staticmethod
    def _representative_load(
        set_logs: list[dict],
    ) -> float:
        loads = [
            float(item.get("load_kg", 0))
            for item in set_logs
            if float(
                item.get("load_kg", 0)
            ) >= 0
        ]

        if not loads:
            return 0.0

        positive = [
            value
            for value in loads
            if value > 0
        ]

        if not positive:
            return 0.0

        counts = Counter(positive)

        highest_frequency = max(
            counts.values()
        )

        candidates = [
            value
            for value, count in counts.items()
            if count == highest_frequency
        ]

        return round(
            max(candidates),
            2,
        )

    @staticmethod
    def _increment_for_pattern(
        movement_pattern: str | None,
    ) -> float:
        if movement_pattern in {
            "squat",
            "hinge",
            "single_leg",
        }:
            return 5.0

        return 2.5

    @staticmethod
    def _round_load(
        value: float,
    ) -> float:
        return round(
            round(value / 2.5) * 2.5,
            2,
        )

    @staticmethod
    def _should_reduce(
        *,
        planned_exercise: dict,
        set_logs: list[dict],
    ) -> bool:
        target_sets = int(
            planned_exercise["target_sets"]
        )

        if len(set_logs) < target_sets:
            return False

        relevant = set_logs[:target_sets]

        reps_min = int(
            planned_exercise[
                "target_reps_min"
            ]
        )

        if any(
            int(item["reps"]) < reps_min
            for item in relevant
        ):
            return True

        target_rir_raw = (
            planned_exercise.get(
                "target_rir"
            )
        )

        if target_rir_raw is None:
            return False

        target_rir = float(
            target_rir_raw
        )

        known_rirs = [
            float(item["rir"])
            for item in relevant
            if item.get("rir") is not None
        ]

        return bool(
            known_rirs
            and any(
                value < target_rir - 1
                for value in known_rirs
            )
        )
