from __future__ import annotations

from datetime import date
from typing import Any


class AdaptiveTrainingCoachService:
    LOWER_PATTERNS = {
        "squat",
        "hinge",
        "single_leg",
        "legs",
        "calf",
    }

    QUALITY_RUNNING_KINDS = {
        "tempo",
        "interval",
        "intervals",
        "long",
    }

    SEVERITY_ORDER = {
        "low": 1,
        "moderate": 2,
        "high": 3,
    }

    def build(
        self,
        *,
        recent_events: list[dict[str, Any]],
        upcoming_strength: list[dict[str, Any]],
        strength_exercises: dict[
            str,
            list[dict[str, Any]],
        ],
        upcoming_running: list[dict[str, Any]],
    ) -> list[dict[str, Any]]:
        candidates: list[dict[str, Any]] = []

        for event in recent_events:
            candidates.extend(
                self._strength_conflicts(
                    event=event,
                    workouts=upcoming_strength,
                    exercises_by_workout=
                        strength_exercises,
                )
            )
            candidates.extend(
                self._running_conflicts(
                    event=event,
                    sessions=upcoming_running,
                )
            )

        return self._deduplicate(candidates)

    def _strength_conflicts(
        self,
        *,
        event: dict[str, Any],
        workouts: list[dict[str, Any]],
        exercises_by_workout:
            dict[str, list[dict[str, Any]]],
    ) -> list[dict[str, Any]]:
        if event.get("scope") not in {
            "lower",
            "full_body",
        }:
            return []

        if event.get("intensity") not in {
            "moderate",
            "high",
        }:
            return []

        result = []

        for workout in workouts:
            if workout.get("status") != "planned":
                continue

            target_scope = self._workout_scope(
                workout
            )

            if target_scope not in {
                "lower",
                "full_body",
            }:
                continue

            gap = self._days_between(
                event.get("date"),
                workout.get("scheduled_date"),
            )

            if gap is None or gap < 0 or gap > 2:
                continue

            severity = self._conflict_severity(
                intensity=str(
                    event.get("intensity")
                ),
                gap_days=gap,
            )

            if severity == "low":
                continue

            exercises = exercises_by_workout.get(
                str(workout.get("id")),
                [],
            )

            if severity == "high":
                load_change = self._load_guard(
                    workout=workout,
                    exercises=exercises,
                )
                if load_change:
                    result.append(
                        self._proposal(
                            event=event,
                            target_kind=
                                "strength_workout",
                            target=workout,
                            action="reduce_load",
                            severity=severity,
                            scope=target_scope,
                            title=(
                                "Carico protetto dopo "
                                "l'allenamento recente"
                            ),
                            message=(
                                self._source_message(
                                    event
                                )
                                + " è abbastanza vicino a "
                                "questa seduta gambe. "
                                "Ridurrò del 5% solo i carichi "
                                "già prescritti, senza "
                                "cambiare la struttura."
                            ),
                            proposed_changes=
                                load_change,
                            auto_apply=True,
                        )
                    )

            volume_change = self._volume_guard(
                workout=workout,
                exercises=exercises,
            )

            if volume_change:
                reduction = (
                    "una serie"
                    if severity == "high"
                    else "il volume"
                )
                result.append(
                    self._proposal(
                        event=event,
                        target_kind=
                            "strength_workout",
                        target=workout,
                        action="reduce_volume",
                        severity=severity,
                        scope=target_scope,
                        title=(
                            "Proteggi il recupero delle gambe"
                        ),
                        message=(
                            self._source_message(event)
                            + " può sovrapporsi alla prossima "
                            "seduta lower/full body. "
                            "Propongo di ridurre "
                            + reduction
                            + " sugli esercizi più tassanti."
                        ),
                        proposed_changes=
                            volume_change,
                        auto_apply=False,
                    )
                )

        return result

    def _running_conflicts(
        self,
        *,
        event: dict[str, Any],
        sessions: list[dict[str, Any]],
    ) -> list[dict[str, Any]]:
        if event.get("modality") != "strength":
            return []

        if event.get("scope") not in {
            "lower",
            "full_body",
        }:
            return []

        if event.get("intensity") not in {
            "moderate",
            "high",
        }:
            return []

        result = []

        for session in sessions:
            if session.get("status") != "planned":
                continue

            kind = str(
                session.get("session_kind")
                or ""
            ).strip().casefold()

            intensity = str(
                session.get("intensity")
                or ""
            ).strip().casefold()

            if (
                kind == "race"
                or intensity == "race"
            ):
                continue

            if (
                kind
                not in self.QUALITY_RUNNING_KINDS
                and intensity != "hard"
            ):
                continue

            gap = self._days_between(
                event.get("date"),
                session.get("scheduled_date"),
            )

            if gap is None or gap < 0 or gap > 2:
                continue

            severity = self._conflict_severity(
                intensity=str(
                    event.get("intensity")
                ),
                gap_days=gap,
            )

            if severity == "low":
                continue

            reduction = (
                0.15
                if severity == "high"
                else 0.10
            )

            changes = self._running_guard(
                session=session,
                reduction=reduction,
            )

            if not changes:
                continue

            result.append(
                self._proposal(
                    event=event,
                    target_kind="planned_activity",
                    target=session,
                    action="reduce_running_load",
                    severity=severity,
                    scope="cardio",
                    title=(
                        "Corsa protetta dopo la palestra"
                    ),
                    message=(
                        self._source_message(event)
                        + " ha già caricato le gambe. "
                        "Propongo di alleggerire la prossima "
                        "corsa di qualità del "
                        + str(int(reduction * 100))
                        + "%."
                    ),
                    proposed_changes=changes,
                    auto_apply=False,
                )
            )

        return result

    def _load_guard(
        self,
        *,
        workout: dict[str, Any],
        exercises: list[dict[str, Any]],
    ) -> dict[str, Any]:
        updates = []

        for exercise in exercises:
            if not self._exercise_is_lower(
                exercise,
                workout,
            ):
                continue

            raw_load = exercise.get(
                "prescribed_load_kg"
            )

            try:
                current = float(raw_load)
            except (TypeError, ValueError):
                continue

            if current <= 0:
                continue

            proposed = self._round_load(
                current * 0.95
            )

            if proposed >= current:
                continue

            updates.append(
                {
                    "exercise_id":
                        exercise.get("id"),
                    "exercise_name":
                        exercise.get(
                            "exercise_name"
                        ),
                    "before_load_kg": current,
                    "prescribed_load_kg":
                        proposed,
                }
            )

        return {
            "exercise_updates": updates,
            "load_multiplier": 0.95,
        } if updates else {}

    def _volume_guard(
        self,
        *,
        workout: dict[str, Any],
        exercises: list[dict[str, Any]],
    ) -> dict[str, Any]:
        updates = []

        for exercise in exercises:
            if not self._exercise_is_lower(
                exercise,
                workout,
            ):
                continue

            try:
                current = int(
                    exercise.get(
                        "target_sets"
                    )
                    or 0
                )
            except (TypeError, ValueError):
                continue

            if current <= 1:
                continue

            updates.append(
                {
                    "exercise_id":
                        exercise.get("id"),
                    "exercise_name":
                        exercise.get(
                            "exercise_name"
                        ),
                    "before_target_sets":
                        current,
                    "target_sets":
                        current - 1,
                }
            )

        return {
            "exercise_updates": updates,
        } if updates else {}

    @staticmethod
    def _running_guard(
        *,
        session: dict[str, Any],
        reduction: float,
    ) -> dict[str, Any]:
        changes: dict[str, Any] = {}

        distance = AdaptiveTrainingCoachService._number(
            session.get("distance_meters")
        )
        duration = AdaptiveTrainingCoachService._number(
            session.get("duration_minutes")
        )

        if distance > 0:
            changes["distance_meters"] = round(
                distance * (1.0 - reduction),
                0,
            )

        if duration > 0:
            changes["duration_minutes"] = max(
                1,
                round(
                    duration * (1.0 - reduction)
                ),
            )

        if str(
            session.get("intensity")
            or ""
        ).strip().casefold() == "hard":
            changes["intensity"] = "moderate"

        return changes

    def _exercise_is_lower(
        self,
        exercise: dict[str, Any],
        workout: dict[str, Any],
    ) -> bool:
        focus = str(
            workout.get("focus")
            or ""
        ).strip().casefold()

        if focus in {"lower", "legs"}:
            return True

        pattern = str(
            exercise.get("movement_pattern")
            or ""
        ).strip().casefold()

        if pattern in self.LOWER_PATTERNS:
            return True

        name = str(
            exercise.get("exercise_name")
            or ""
        ).casefold()

        return any(
            token in name
            for token in (
                "squat",
                "deadlift",
                "leg ",
                "leg-",
                "lunge",
                "split squat",
                "calf",
                "hip thrust",
                "romanian",
            )
        )

    @staticmethod
    def _workout_scope(
        workout: dict[str, Any],
    ) -> str:
        focus = str(
            workout.get("focus")
            or ""
        ).strip().casefold()

        if focus in {"lower", "legs"}:
            return "lower"

        if focus in {
            "upper",
            "push",
            "pull",
        }:
            return "upper"

        return "full_body"

    def _conflict_severity(
        self,
        *,
        intensity: str,
        gap_days: int,
    ) -> str:
        if intensity == "high":
            if gap_days <= 1:
                return "high"
            return "moderate"

        if intensity == "moderate":
            if gap_days == 0:
                return "moderate"
            if gap_days == 1:
                return "moderate"

        return "low"

    def _deduplicate(
        self,
        candidates: list[dict[str, Any]],
    ) -> list[dict[str, Any]]:
        chosen: dict[
            tuple[str, str, str],
            dict[str, Any],
        ] = {}

        for item in candidates:
            key = (
                str(item["target_kind"]),
                str(item["target_id"]),
                str(item["action"]),
            )

            existing = chosen.get(key)

            if existing is None:
                chosen[key] = item
                continue

            current_rank = self.SEVERITY_ORDER.get(
                str(item.get("severity")),
                0,
            )
            existing_rank = (
                self.SEVERITY_ORDER.get(
                    str(
                        existing.get("severity")
                    ),
                    0,
                )
            )

            if current_rank > existing_rank:
                chosen[key] = item
                continue

            if (
                current_rank == existing_rank
                and str(item.get("source_date"))
                > str(
                    existing.get(
                        "source_date"
                    )
                )
            ):
                chosen[key] = item

        return sorted(
            chosen.values(),
            key=lambda item: (
                str(item.get("target_date")),
                -self.SEVERITY_ORDER.get(
                    str(item.get("severity")),
                    0,
                ),
                str(item.get("action")),
            ),
        )

    @staticmethod
    def _proposal(
        *,
        event: dict[str, Any],
        target_kind: str,
        target: dict[str, Any],
        action: str,
        severity: str,
        scope: str,
        title: str,
        message: str,
        proposed_changes: dict[str, Any],
        auto_apply: bool,
    ) -> dict[str, Any]:
        return {
            "source_kind": event["source_kind"],
            "source_id": str(event["source_id"]),
            "source_date": str(event["date"]),
            "source_title": event.get("title"),
            "target_kind": target_kind,
            "target_id": str(target["id"]),
            "target_date": str(
                target.get("scheduled_date")
            ),
            "target_title": target.get("title"),
            "action": action,
            "severity": severity,
            "scope": scope,
            "title": title,
            "message": message,
            "proposed_changes":
                proposed_changes,
            "before_state": target,
            "auto_apply": auto_apply,
        }

    @staticmethod
    def _source_message(
        event: dict[str, Any],
    ) -> str:
        title = str(
            event.get("title")
            or "L'allenamento recente"
        )

        if (
            event.get("source_kind")
            == "activity"
        ):
            return (
                title
                + " ha generato un carico "
                + str(event.get("intensity"))
            )

        prefix = (
            "Il workout libero"
            if event.get("workout_kind")
            == "free"
            else "La seduta palestra"
        )

        return (
            prefix
            + " “"
            + title
            + "” ha generato un carico "
            + str(event.get("intensity"))
        )

    @staticmethod
    def _round_load(value: float) -> float:
        return round(
            max(0.0, value) / 2.5
        ) * 2.5

    @staticmethod
    def _number(value: Any) -> float:
        try:
            return max(
                0.0,
                float(value or 0),
            )
        except (TypeError, ValueError):
            return 0.0

    @staticmethod
    def _days_between(
        source: Any,
        target: Any,
    ) -> int | None:
        try:
            source_date = date.fromisoformat(
                str(source)[:10]
            )
            target_date = date.fromisoformat(
                str(target)[:10]
            )
        except ValueError:
            return None

        return (
            target_date - source_date
        ).days
