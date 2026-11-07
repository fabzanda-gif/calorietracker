from __future__ import annotations

from collections import Counter, defaultdict
from datetime import date, timedelta
from statistics import mean


class AthleteStateService:
    """Descriptive trends from verified completed workouts, not medical readiness."""

    HARD_FEELINGS = {"hard", "too_hard"}

    def build(
        self, *, history: dict, as_of: date, profile: dict | None = None
    ) -> dict:
        logs = [
            item for item in history.get("logs", [])
            if item.get("status") == "completed"
            and self._day(item.get("performed_date")) is not None
            and as_of - timedelta(days=55)
            <= self._day(item.get("performed_date")) <= as_of
        ]
        log_by_id = {str(item["id"]): item for item in logs}
        exercises = {str(x["id"]): x for x in history.get("exercises", [])}
        workouts = {str(x["id"]): x for x in history.get("workouts", [])}
        sets = [
            item for item in history.get("sets", [])
            if str(item.get("strength_workout_log_id")) in log_by_id
        ]
        sets_by_log = defaultdict(list)
        for item in sets:
            sets_by_log[str(item["strength_workout_log_id"])].append(item)

        def window(days: int) -> dict:
            first = as_of - timedelta(days=days - 1)
            selected = [
                item for item in logs
                if self._day(item["performed_date"]) >= first
            ]
            selected_ids = {str(x["id"]) for x in selected}
            selected_sets = [
                x for x in sets
                if str(x["strength_workout_log_id"]) in selected_ids
            ]
            return {
                "completed_sessions": len(selected),
                "training_days": len({x["performed_date"] for x in selected}),
                "total_sets": len(selected_sets),
                "volume_load_kg": round(sum(
                    self._positive(x.get("load_kg")) *
                    self._positive(x.get("reps"))
                    for x in selected_sets
                ), 1),
                "reported_hard_sets": sum(
                    str(x.get("feeling") or "").lower() in self.HARD_FEELINGS
                    for x in selected_sets
                ),
                "feelings_reported": sum(bool(x.get("feeling")) for x in selected_sets),
                "total_duration_minutes": round(sum(
                    self._positive(x.get("duration_minutes")) for x in selected
                ), 1),
            }

        recent = window(7)
        previous_start = as_of - timedelta(days=13)
        previous_end = as_of - timedelta(days=7)
        previous_logs = [
            x for x in logs
            if previous_start <= self._day(x["performed_date"]) <= previous_end
        ]
        previous_ids = {str(x["id"]) for x in previous_logs}
        previous_sets = [
            x for x in sets
            if str(x["strength_workout_log_id"]) in previous_ids
        ]
        previous = {
            "completed_sessions": len(previous_logs),
            "total_sets": len(previous_sets),
            "volume_load_kg": round(sum(
                self._positive(x.get("load_kg")) *
                self._positive(x.get("reps")) for x in previous_sets
            ), 1),
        }

        weekly = []
        for offset in range(7, -1, -1):
            end = as_of - timedelta(days=offset * 7)
            start = end - timedelta(days=6)
            matching = [
                x for x in logs
                if start <= self._day(x["performed_date"]) <= end
            ]
            weekly.append({
                "start": start.isoformat(),
                "end": end.isoformat(),
                "sessions": len(matching),
                "sets": sum(
                    len(sets_by_log[str(x["id"])]) for x in matching
                ),
            })

        per_exercise: dict[str, dict] = {}
        for log in logs:
            log_date = self._day(log["performed_date"])
            for set_item in sets_by_log[str(log["id"])]:
                planned = exercises.get(
                    str(set_item.get("strength_workout_exercise_id"))
                )
                if planned is None:
                    continue
                key = str(
                    planned.get("exercise_id") or planned.get("exercise_key")
                    or planned["id"]
                )
                record = per_exercise.setdefault(key, {
                    "exercise_id": key,
                    "name": planned.get("exercise_name") or "Esercizio",
                    "movement_pattern": planned.get("movement_pattern"),
                    "sessions": set(),
                    "sets": 0,
                    "best_load_kg": 0.0,
                    "best_volume_set_kg": 0.0,
                    "last_performed_date": None,
                })
                record["sets"] += 1
                record["sessions"].add(str(log["id"]))
                load = self._positive(set_item.get("load_kg"))
                record["best_load_kg"] = max(record["best_load_kg"], load)
                record["best_volume_set_kg"] = max(
                    record["best_volume_set_kg"],
                    load * self._positive(set_item.get("reps"))
                )
                if record["last_performed_date"] is None or (
                    log_date.isoformat() > record["last_performed_date"]
                ):
                    record["last_performed_date"] = log_date.isoformat()

        top_exercises = []
        for item in per_exercise.values():
            top_exercises.append({
                **item,
                "sessions": len(item["sessions"]),
                "best_volume_set_kg": round(item["best_volume_set_kg"], 1),
            })
        top_exercises.sort(
            key=lambda x: (-x["sessions"], -x["sets"], x["name"])
        )

        goal = (profile or {}).get("sessions_per_week")
        target = int(goal) if isinstance(goal, int) and 1 <= goal <= 7 else None
        recent_28 = window(28)
        counted_weeks = sum(
            1 for item in weekly[-4:] if item["sessions"] > 0
        )
        consistency = (
            round(min(1.0, recent_28["completed_sessions"] / (target * 4)), 2)
            if target else None
        )
        last_day = max(
            (self._day(x["performed_date"]) for x in logs),
            default=None,
        )
        quality = {
            "weeks_with_training_last_4": counted_weeks,
            "sessions_with_sets": sum(bool(sets_by_log[str(x["id"])]) for x in logs),
            "sessions_without_sets": sum(not sets_by_log[str(x["id"])] for x in logs),
            "history_truncated": bool(history.get("truncated")),
        }
        # A trend description is not a fatigue diagnosis or prescription.
        return {
            "as_of": as_of.isoformat(),
            "window_days": 56,
            "source": "completed_strength_workouts",
            "scope": "strength_only",
            "data_status": "limited" if len(logs) < 3 or quality["history_truncated"] else "available",
            "last_completed_date": last_day.isoformat() if last_day else None,
            "days_since_last_completed": (as_of - last_day).days if last_day else None,
            "recent_7_days": recent,
            "previous_7_days": previous,
            "last_28_days": recent_28,
            "last_56_days": window(56),
            "weekly": weekly,
            "target_sessions_per_week": target,
            "consistency_ratio_last_4_weeks": consistency,
            "most_logged_exercises": top_exercises[:12],
            "quality": quality,
            "note": (
                "Statistiche descrittive basate solo su sedute completate e "
                "serie salvate. Non misurano recupero fisiologico, "
                "rischio di infortunio o prontezza clinica."
            ),
        }

    @staticmethod
    def _day(value) -> date | None:
        try:
            return date.fromisoformat(str(value)[:10])
        except (ValueError, TypeError):
            return None

    @staticmethod
    def _positive(value) -> float:
        try:
            return max(0.0, float(value or 0))
        except (TypeError, ValueError):
            return 0.0
