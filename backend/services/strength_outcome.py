from __future__ import annotations

from collections import defaultdict
from typing import Any


UNDER_TARGET = "under_target"
ON_TARGET = "on_target"
OVER_TARGET = "over_target"


class StrengthOutcomeService:
    def evaluate(
        self,
        *,
        planned_exercises: list[dict],
        set_logs: list[dict],
    ) -> dict[str, Any]:
        if not planned_exercises:
            raise ValueError(
                "Strength workout has no "
                "planned exercises"
            )

        sets_by_exercise = defaultdict(list)

        for item in set_logs:
            exercise_id = str(
                item[
                    "strength_workout_exercise_id"
                ]
            )

            sets_by_exercise[
                exercise_id
            ].append(item)

        for items in sets_by_exercise.values():
            items.sort(
                key=lambda item: int(
                    item.get("set_index", 0)
                )
            )

        exercise_outcomes = []

        ordered_exercises = sorted(
            planned_exercises,
            key=lambda item: int(
                item.get("position", 0)
            ),
        )

        for exercise in ordered_exercises:
            exercise_id = str(
                exercise["id"]
            )

            actual_sets = sets_by_exercise.get(
                exercise_id,
                [],
            )

            exercise_outcomes.append(
                self._evaluate_exercise(
                    planned=exercise,
                    actual_sets=actual_sets,
                )
            )

        under_count = sum(
            item["outcome"] == UNDER_TARGET
            for item in exercise_outcomes
        )

        on_count = sum(
            item["outcome"] == ON_TARGET
            for item in exercise_outcomes
        )

        over_count = sum(
            item["outcome"] == OVER_TARGET
            for item in exercise_outcomes
        )

        logged_exercise_count = sum(
            item["completed_sets"] > 0
            for item in exercise_outcomes
        )

        total = len(exercise_outcomes)

        if under_count > 0:
            workout_outcome = UNDER_TARGET
            message = (
                "Almeno un esercizio è sotto "
                "la prescrizione prevista."
            )

        elif (
            logged_exercise_count == total
            and over_count * 2 >= total
        ):
            workout_outcome = OVER_TARGET
            message = (
                "Seduta sopra target: almeno "
                "metà degli esercizi è stata "
                "completata con margine."
            )

        else:
            workout_outcome = ON_TARGET
            message = (
                "Seduta in linea con la "
                "prescrizione prevista."
            )

        return {
            "outcome": workout_outcome,
            "message": message,
            "planned_exercise_count": total,
            "logged_exercise_count":
                logged_exercise_count,
            "under_target_count": under_count,
            "on_target_count": on_count,
            "over_target_count": over_count,
            "exercises": exercise_outcomes,
        }

    def _evaluate_exercise(
        self,
        *,
        planned: dict,
        actual_sets: list[dict],
    ) -> dict[str, Any]:
        target_sets = int(
            planned["target_sets"]
        )

        reps_min = int(
            planned["target_reps_min"]
        )

        reps_max = int(
            planned["target_reps_max"]
        )

        target_rir_raw = planned.get(
            "target_rir"
        )

        target_rir = (
            float(target_rir_raw)
            if target_rir_raw is not None
            else None
        )

        completed_sets = len(actual_sets)

        relevant_sets = actual_sets[
            :target_sets
        ]

        reps = [
            int(item["reps"])
            for item in relevant_sets
        ]

        known_rirs = [
            float(item["rir"])
            for item in relevant_sets
            if item.get("rir") is not None
        ]

        volume_load = round(
            sum(
                float(item.get("load_kg", 0))
                * int(item["reps"])
                for item in actual_sets
            ),
            2,
        )

        average_reps = (
            round(
                sum(reps) / len(reps),
                2,
            )
            if reps
            else None
        )

        average_rir = (
            round(
                sum(known_rirs)
                / len(known_rirs),
                2,
            )
            if known_rirs
            else None
        )

        reasons = []

        if completed_sets < target_sets:
            outcome = UNDER_TARGET
            reasons.append(
                "Serie completate inferiori "
                "al target."
            )

        elif any(
            value < reps_min
            for value in reps
        ):
            outcome = UNDER_TARGET
            reasons.append(
                "Almeno una serie è sotto "
                "il minimo di ripetizioni."
            )

        elif (
            target_rir is not None
            and known_rirs
            and any(
                value < target_rir - 1
                for value in known_rirs
            )
        ):
            outcome = UNDER_TARGET
            reasons.append(
                "Lo sforzo è stato molto "
                "più alto del target RIR."
            )

        elif self._is_over_target(
            target_sets=target_sets,
            reps_max=reps_max,
            target_rir=target_rir,
            relevant_sets=relevant_sets,
        ):
            outcome = OVER_TARGET
            reasons.append(
                "Top del rep range raggiunto "
                "con margine superiore al target."
            )

        else:
            outcome = ON_TARGET
            reasons.append(
                "Volume, ripetizioni e sforzo "
                "sono compatibili con il target."
            )

        return {
            "exercise_id": str(
                planned["id"]
            ),
            "exercise_key": planned.get(
                "exercise_key"
            ),
            "exercise_name": planned.get(
                "exercise_name"
            ),
            "position": planned.get(
                "position"
            ),
            "outcome": outcome,
            "message": reasons[0],
            "target_sets": target_sets,
            "completed_sets": completed_sets,
            "target_reps_min": reps_min,
            "target_reps_max": reps_max,
            "target_rir": target_rir,
            "average_reps": average_reps,
            "average_rir": average_rir,
            "volume_load": volume_load,
        }

    @staticmethod
    def _is_over_target(
        *,
        target_sets: int,
        reps_max: int,
        target_rir: float | None,
        relevant_sets: list[dict],
    ) -> bool:
        if len(relevant_sets) < target_sets:
            return False

        if target_rir is None:
            return False

        if not all(
            int(item["reps"]) >= reps_max
            for item in relevant_sets
        ):
            return False

        if not all(
            item.get("rir") is not None
            for item in relevant_sets
        ):
            return False

        return all(
            float(item["rir"])
            >= target_rir + 1
            for item in relevant_sets
        )
