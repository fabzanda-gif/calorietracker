from __future__ import annotations

from dataclasses import dataclass
from datetime import date, timedelta
from typing import Any

from backend.services.strength_plan import StrengthPlanService


# Minimum pattern coverage for a balanced general-purpose strength program.
# Never silently replace a missing hinge with an unrelated squat/curl.
MANDATORY_PATTERNS = (
    "squat",
    "hinge",
    "horizontal_push",
    "horizontal_pull",
    "vertical_push",
    "vertical_pull",
)
TEMPLATE_SLOTS = {
    2: (
        ("Full Body A", "full_body", ("squat", "horizontal_push", "horizontal_pull", "hinge", "core")),
        ("Full Body B", "full_body", ("hinge", "vertical_push", "vertical_pull", "squat", "isolation")),
    ),
    3: (
        ("Full Body A", "full_body", ("squat", "horizontal_push", "horizontal_pull", "hinge", "core")),
        ("Full Body B", "full_body", ("hinge", "vertical_push", "vertical_pull", "squat", "isolation")),
        ("Full Body C", "full_body", ("squat", "vertical_pull", "horizontal_push", "hinge", "core")),
    ),
    4: (
        ("Upper A", "upper", ("horizontal_push", "horizontal_pull", "vertical_push", "vertical_pull", "isolation")),
        ("Lower A", "lower", ("squat", "hinge", "squat", "core")),
        ("Upper B", "upper", ("vertical_push", "vertical_pull", "horizontal_push", "horizontal_pull", "isolation")),
        ("Lower B", "lower", ("hinge", "squat", "hinge", "core")),
    ),
}
MUSCLE_ALIASES = {
    "chest": ("chest", "pectorals"),
    "back": ("back", "lats"),
    "shoulders": ("shoulders", "deltoids", "delts"),
    "quadriceps": ("quadriceps", "quads", "upper legs"),
    "hamstrings": ("hamstrings", "upper legs"),
    "glutes": ("glutes", "hips"),
    "core": ("core", "waist", "abdominals"),
    "triceps": ("triceps", "upper arms"),
    "biceps": ("biceps", "upper arms"),
}


@dataclass(frozen=True)
class ProgramV2Input:
    start_date: date
    goal: str
    sessions_per_week: int
    total_weeks: int
    experience_level: str
    session_duration_minutes: int
    preferred_days: tuple[int, ...] = ()
    priority_muscles: tuple[str, ...] = ()
    allowed_equipment: tuple[str, ...] = ()


class ProgramGeneratorV2:
    """Deterministic, auditable, fail-closed program preview."""

    def preview(
        self, *, config: ProgramV2Input,
        catalog: list[dict[str, Any]],
        excluded_ids: set[str] | None = None,
        preferred_ids: set[str] | None = None,
        athlete_state: dict | None = None,
    ) -> dict[str, Any]:
        if config.goal not in {"strength", "hypertrophy", "general_fitness"}:
            raise ValueError("Unsupported strength goal")
        if config.experience_level not in {"beginner", "intermediate", "advanced"}:
            raise ValueError("Unsupported experience level")
        if config.sessions_per_week not in TEMPLATE_SLOTS:
            raise ValueError("V2 supports 2, 3 or 4 sessions per week")
        if not 4 <= config.total_weeks <= 12:
            raise ValueError("V2 supports 4 to 12 weeks")
        if not 20 <= config.session_duration_minutes <= 180:
            raise ValueError("Session duration must be 20 to 180 minutes")
        if any(day not in range(1, 8) for day in config.preferred_days):
            raise ValueError("Invalid preferred weekday")
        if len(set(config.preferred_days)) != len(config.preferred_days):
            raise ValueError("Duplicate preferred weekdays")
        if config.preferred_days and len(config.preferred_days) != config.sessions_per_week:
            raise ValueError("Fixed training days must match sessions per week")

        excluded = excluded_ids or set()
        preferred = preferred_ids or set()
        by_pattern: dict[str, list[dict]] = {}
        for item in catalog:
            if not item.get("active", True) or not item.get("approved_for_generation"):
                continue
            if not item.get("id") or str(item["id"]) in excluded:
                continue
            required_equipment = {
                str(e.get("key")) for e in item.get("equipment", [])
                if e.get("key") and e.get("role") != "optional"
            }
            if config.allowed_equipment and not required_equipment.issubset(
                set(config.allowed_equipment)
            ):
                continue
            pattern = item.get("movement_pattern")
            if not pattern:
                continue
            by_pattern.setdefault(str(pattern), []).append(item)

        def priority(item: dict) -> tuple:
            goal_score = item.get({
                "strength": "strength_score",
                "hypertrophy": "hypertrophy_score",
                "general_fitness": "general_fitness_score",
            }[config.goal]) or 0
            searchable = {
                str(item.get("body_part") or "").casefold(),
                str(item.get("target_muscle") or "").casefold(),
            }
            muscle_match = any(
                bool(searchable.intersection(MUSCLE_ALIASES.get(key, (key,))))
                for key in config.priority_muscles
            )
            return (
                -(str(item["id"]) in preferred),
                -muscle_match,
                -float(goal_score),
                str(item.get("slug") or item["id"]),
            )

        for candidates in by_pattern.values():
            candidates.sort(key=priority)
        missing_patterns = [
            pattern for pattern in MANDATORY_PATTERNS if not by_pattern.get(pattern)
        ]
        days = (
            tuple(sorted(config.preferred_days))
            if config.preferred_days
            else tuple(x + 1 for x in StrengthPlanService._week_offsets(
                config.sessions_per_week
            ))
        )
        # The first seven days begin on the requested start date, so
        # preferred weekday values are real ISO weekday values.
        first_week_monday = config.start_date - timedelta(
            days=config.start_date.isoweekday() - 1
        )
        # Avoid scheduling before the requested start date.
        week_start = first_week_monday
        if any(
            week_start + timedelta(days=day - 1) < config.start_date
            for day in days
        ):
            week_start += timedelta(days=7)
        schedule = []
        incomplete = False
        for week in range(1, config.total_weeks + 1):
            for index, (title, focus, patterns) in enumerate(
                TEMPLATE_SLOTS[config.sessions_per_week], 1
            ):
                used: set[str] = set()
                planned_exercises = []
                for position, pattern in enumerate(patterns, 1):
                    candidate = next(
                        (x for x in by_pattern.get(pattern, [])
                         if str(x["id"]) not in used),
                        None,
                    )
                    if candidate is None:
                        incomplete = True
                        continue
                    used.add(str(candidate["id"]))
                    role = candidate.get("training_role") or (
                        "primary" if position == 1 else "secondary"
                    )
                    sets, low, high, rir, rest = StrengthPlanService._prescription(
                        goal=config.goal,
                        level=config.experience_level,
                        role=role,
                    )
                    planned_exercises.append({
                        "position": position,
                        "exercise_id": str(candidate["id"]),
                        "exercise_key": candidate.get("legacy_key")
                            or candidate.get("slug") or str(candidate["id"]),
                        "exercise_name": candidate.get("name") or candidate.get("name_default"),
                        "movement_pattern": pattern,
                        "target_sets": sets,
                        "target_reps_min": low,
                        "target_reps_max": high,
                        "target_rir": rir,
                        "rest_seconds": rest,
                        "prescribed_load_kg": None,
                        "approved_for_generation": True,
                    })
                day = week_start + timedelta(
                    days=7 * (week - 1) + days[index - 1] - 1
                )
                schedule.append({
                    "scheduled_date": day.isoformat(),
                    "training_week": week,
                    "workout_index": index,
                    "title": title,
                    "focus": focus,
                    "status": "planned",
                    "estimated_duration_minutes": config.session_duration_minutes,
                    "exercises": planned_exercises,
                })

        warnings = []
        if missing_patterns:
            warnings.append(
                "Mancano esercizi approvati per: " +
                ", ".join(missing_patterns) + "."
            )
        if incomplete:
            warnings.append(
                "Alcune sedute hanno movimenti mancanti: il piano non può essere attivato."
            )
        athlete_quality = (athlete_state or {}).get("data_status", "unavailable")
        if athlete_quality != "available":
            warnings.append(
                "Storico atleta incompleto: nessun incremento di carico automatico."
            )
        if not config.allowed_equipment:
            warnings.append(
                "Attrezzatura non specificata: controlla la disponibilità prima di attivare."
            )
        ready = not missing_patterns and not incomplete and bool(config.allowed_equipment)
        return {
            "generator_version": 2,
            "preview": True,
            "ready_for_activation": ready,
            "warnings": warnings,
            "missing_movement_patterns": missing_patterns,
            "approved_catalog_count": sum(len(items) for items in by_pattern.values()),
            "goal": config.goal,
            "experience_level": config.experience_level,
            "sessions_per_week": config.sessions_per_week,
            "session_duration_minutes": config.session_duration_minutes,
            "program_style": "full_body" if config.sessions_per_week < 4 else "upper_lower",
            "start_date": config.start_date.isoformat(),
            "total_weeks": config.total_weeks,
            "workout_count": len(schedule),
            "athlete_data_status": athlete_quality,
            "workouts": schedule,
        }
