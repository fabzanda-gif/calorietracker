from __future__ import annotations

from dataclasses import dataclass
from datetime import date, timedelta
from typing import Any


SUPPORTED_GOALS = {
    "hypertrophy",
    "strength",
    "general_fitness",
}

SUPPORTED_LEVELS = {
    "beginner",
    "intermediate",
    "advanced",
}

MOVEMENT_PATTERNS = {
    "squat",
    "hinge",
    "horizontal_push",
    "vertical_push",
    "horizontal_pull",
    "vertical_pull",
    "single_leg",
    "core",
    "isolation",
}


@dataclass(frozen=True)
class StrengthPlanInput:
    start_date: date
    goal: str
    experience_level: str
    sessions_per_week: int
    total_weeks: int = 8


@dataclass(frozen=True)
class ExerciseTemplate:
    key: str
    name: str
    movement_pattern: str
    role: str


FULL_BODY_A = (
    ExerciseTemplate(
        "back_squat",
        "Back Squat",
        "squat",
        "primary",
    ),
    ExerciseTemplate(
        "bench_press",
        "Bench Press",
        "horizontal_push",
        "primary",
    ),
    ExerciseTemplate(
        "seated_row",
        "Seated Row",
        "horizontal_pull",
        "secondary",
    ),
    ExerciseTemplate(
        "romanian_deadlift",
        "Romanian Deadlift",
        "hinge",
        "secondary",
    ),
    ExerciseTemplate(
        "lateral_raise",
        "Alzate laterali",
        "isolation",
        "accessory",
    ),
    ExerciseTemplate(
        "plank",
        "Plank",
        "core",
        "accessory",
    ),
)

FULL_BODY_B = (
    ExerciseTemplate(
        "leg_press",
        "Leg Press",
        "squat",
        "primary",
    ),
    ExerciseTemplate(
        "overhead_press",
        "Overhead Press",
        "vertical_push",
        "primary",
    ),
    ExerciseTemplate(
        "lat_pulldown",
        "Lat Pulldown",
        "vertical_pull",
        "secondary",
    ),
    ExerciseTemplate(
        "hip_thrust",
        "Hip Thrust",
        "hinge",
        "secondary",
    ),
    ExerciseTemplate(
        "incline_dumbbell_press",
        "Distensioni manubri inclinata",
        "horizontal_push",
        "secondary",
    ),
    ExerciseTemplate(
        "biceps_curl",
        "Curl bicipiti",
        "isolation",
        "accessory",
    ),
)

FULL_BODY_C = (
    ExerciseTemplate(
        "bulgarian_split_squat",
        "Bulgarian Split Squat",
        "single_leg",
        "primary",
    ),
    ExerciseTemplate(
        "incline_dumbbell_press",
        "Distensioni manubri inclinata",
        "horizontal_push",
        "primary",
    ),
    ExerciseTemplate(
        "cable_row",
        "Cable Row",
        "horizontal_pull",
        "secondary",
    ),
    ExerciseTemplate(
        "leg_curl",
        "Leg Curl",
        "hinge",
        "secondary",
    ),
    ExerciseTemplate(
        "lat_pulldown",
        "Lat Pulldown",
        "vertical_pull",
        "secondary",
    ),
    ExerciseTemplate(
        "triceps_pushdown",
        "Pushdown tricipiti",
        "isolation",
        "accessory",
    ),
)

UPPER_A = (
    ExerciseTemplate(
        "bench_press",
        "Bench Press",
        "horizontal_push",
        "primary",
    ),
    ExerciseTemplate(
        "seated_row",
        "Seated Row",
        "horizontal_pull",
        "primary",
    ),
    ExerciseTemplate(
        "overhead_press",
        "Overhead Press",
        "vertical_push",
        "secondary",
    ),
    ExerciseTemplate(
        "lat_pulldown",
        "Lat Pulldown",
        "vertical_pull",
        "secondary",
    ),
    ExerciseTemplate(
        "lateral_raise",
        "Alzate laterali",
        "isolation",
        "accessory",
    ),
    ExerciseTemplate(
        "biceps_curl",
        "Curl bicipiti",
        "isolation",
        "accessory",
    ),
)

LOWER_A = (
    ExerciseTemplate(
        "back_squat",
        "Back Squat",
        "squat",
        "primary",
    ),
    ExerciseTemplate(
        "romanian_deadlift",
        "Romanian Deadlift",
        "hinge",
        "primary",
    ),
    ExerciseTemplate(
        "leg_press",
        "Leg Press",
        "squat",
        "secondary",
    ),
    ExerciseTemplate(
        "leg_curl",
        "Leg Curl",
        "hinge",
        "secondary",
    ),
    ExerciseTemplate(
        "standing_calf_raise",
        "Calf Raise",
        "isolation",
        "accessory",
    ),
    ExerciseTemplate(
        "plank",
        "Plank",
        "core",
        "accessory",
    ),
)

UPPER_B = (
    ExerciseTemplate(
        "incline_dumbbell_press",
        "Distensioni manubri inclinata",
        "horizontal_push",
        "primary",
    ),
    ExerciseTemplate(
        "lat_pulldown",
        "Lat Pulldown",
        "vertical_pull",
        "primary",
    ),
    ExerciseTemplate(
        "dumbbell_shoulder_press",
        "Shoulder Press manubri",
        "vertical_push",
        "secondary",
    ),
    ExerciseTemplate(
        "cable_row",
        "Cable Row",
        "horizontal_pull",
        "secondary",
    ),
    ExerciseTemplate(
        "triceps_pushdown",
        "Pushdown tricipiti",
        "isolation",
        "accessory",
    ),
    ExerciseTemplate(
        "biceps_curl",
        "Curl bicipiti",
        "isolation",
        "accessory",
    ),
)

LOWER_B = (
    ExerciseTemplate(
        "deadlift",
        "Deadlift",
        "hinge",
        "primary",
    ),
    ExerciseTemplate(
        "bulgarian_split_squat",
        "Bulgarian Split Squat",
        "single_leg",
        "primary",
    ),
    ExerciseTemplate(
        "leg_press",
        "Leg Press",
        "squat",
        "secondary",
    ),
    ExerciseTemplate(
        "leg_curl",
        "Leg Curl",
        "hinge",
        "secondary",
    ),
    ExerciseTemplate(
        "standing_calf_raise",
        "Calf Raise",
        "isolation",
        "accessory",
    ),
    ExerciseTemplate(
        "dead_bug",
        "Dead Bug",
        "core",
        "accessory",
    ),
)


class StrengthPlanService:
    def build(
        self,
        plan: StrengthPlanInput,
    ) -> dict[str, Any]:
        self._validate(plan)

        program_style = (
            "full_body"
            if plan.sessions_per_week in {2, 3}
            else "upper_lower"
        )

        templates = self._templates(
            plan.sessions_per_week
        )

        offsets = self._week_offsets(
            plan.sessions_per_week
        )

        workouts: list[dict[str, Any]] = []

        for week in range(
            1,
            plan.total_weeks + 1,
        ):
            week_start = (
                plan.start_date
                + timedelta(weeks=week - 1)
            )

            for workout_index, (
                offset,
                template,
            ) in enumerate(
                zip(offsets, templates),
                start=1,
            ):
                title, focus, exercises = template

                workouts.append(
                    {
                        "scheduled_date": str(
                            week_start
                            + timedelta(days=offset)
                        ),
                        "training_week": week,
                        "workout_index":
                            workout_index,
                        "title": title,
                        "focus": focus,
                        "status": "planned",
                        "estimated_duration_minutes":
                            self._duration_minutes(
                                exercises
                            ),
                        "exercises": [
                            self._exercise_payload(
                                exercise=exercise,
                                position=position,
                                goal=plan.goal,
                                level=(
                                    plan.experience_level
                                ),
                            )
                            for position, exercise
                            in enumerate(
                                exercises,
                                start=1,
                            )
                        ],
                    }
                )

        return {
            "goal": plan.goal,
            "experience_level":
                plan.experience_level,
            "program_style": program_style,
            "sessions_per_week":
                plan.sessions_per_week,
            "start_date": str(plan.start_date),
            "total_weeks": plan.total_weeks,
            "workout_count": len(workouts),
            "workouts": workouts,
        }

    @staticmethod
    def _validate(
        plan: StrengthPlanInput,
    ) -> None:
        if plan.goal not in SUPPORTED_GOALS:
            raise ValueError(
                "Unsupported strength goal"
            )

        if (
            plan.experience_level
            not in SUPPORTED_LEVELS
        ):
            raise ValueError(
                "Unsupported experience level"
            )

        if plan.sessions_per_week not in {
            2,
            3,
            4,
        }:
            raise ValueError(
                "Strength V1 supports "
                "2, 3 or 4 sessions per week"
            )

        if not 4 <= plan.total_weeks <= 24:
            raise ValueError(
                "total_weeks must be "
                "between 4 and 24"
            )

    @staticmethod
    def _week_offsets(
        sessions_per_week: int,
    ) -> tuple[int, ...]:
        if sessions_per_week == 2:
            return (0, 3)

        if sessions_per_week == 3:
            return (0, 2, 4)

        return (0, 1, 3, 4)

    @staticmethod
    def _templates(
        sessions_per_week: int,
    ) -> tuple[
        tuple[
            str,
            str,
            tuple[ExerciseTemplate, ...],
        ],
        ...,
    ]:
        if sessions_per_week == 2:
            return (
                (
                    "Full Body A",
                    "full_body",
                    FULL_BODY_A,
                ),
                (
                    "Full Body B",
                    "full_body",
                    FULL_BODY_B,
                ),
            )

        if sessions_per_week == 3:
            return (
                (
                    "Full Body A",
                    "full_body",
                    FULL_BODY_A,
                ),
                (
                    "Full Body B",
                    "full_body",
                    FULL_BODY_B,
                ),
                (
                    "Full Body C",
                    "full_body",
                    FULL_BODY_C,
                ),
            )

        return (
            (
                "Upper A",
                "upper",
                UPPER_A,
            ),
            (
                "Lower A",
                "lower",
                LOWER_A,
            ),
            (
                "Upper B",
                "upper",
                UPPER_B,
            ),
            (
                "Lower B",
                "lower",
                LOWER_B,
            ),
        )

    def _exercise_payload(
        self,
        *,
        exercise: ExerciseTemplate,
        position: int,
        goal: str,
        level: str,
    ) -> dict[str, Any]:
        (
            sets,
            reps_min,
            reps_max,
            rir,
            rest_seconds,
        ) = self._prescription(
            goal=goal,
            level=level,
            role=exercise.role,
        )

        return {
            "position": position,
            "exercise_key": exercise.key,
            "exercise_name": exercise.name,
            "movement_pattern":
                exercise.movement_pattern,
            "target_sets": sets,
            "target_reps_min": reps_min,
            "target_reps_max": reps_max,
            "target_rir": rir,
            "rest_seconds": rest_seconds,
            "prescribed_load_kg": None,
        }

    @staticmethod
    def _prescription(
        *,
        goal: str,
        level: str,
        role: str,
    ) -> tuple[int, int, int, float, int]:
        if goal == "strength":
            if role == "primary":
                prescription = (
                    3,
                    4,
                    6,
                    2.0,
                    180,
                )
            elif role == "secondary":
                prescription = (
                    3,
                    6,
                    8,
                    2.0,
                    120,
                )
            else:
                prescription = (
                    2,
                    8,
                    12,
                    2.0,
                    75,
                )

        elif goal == "hypertrophy":
            if role == "primary":
                prescription = (
                    3,
                    6,
                    10,
                    2.0,
                    150,
                )
            elif role == "secondary":
                prescription = (
                    3,
                    8,
                    12,
                    2.0,
                    105,
                )
            else:
                prescription = (
                    2,
                    10,
                    15,
                    2.0,
                    60,
                )

        else:
            if role == "primary":
                prescription = (
                    3,
                    8,
                    10,
                    3.0,
                    120,
                )
            elif role == "secondary":
                prescription = (
                    2,
                    8,
                    12,
                    3.0,
                    90,
                )
            else:
                prescription = (
                    2,
                    10,
                    15,
                    3.0,
                    60,
                )

        sets, low, high, rir, rest = (
            prescription
        )

        if level == "beginner":
            rir = max(rir, 3.0)

            if role != "primary":
                sets = min(sets, 2)

        elif level == "advanced":
            rir = max(
                1.0,
                rir - 1.0,
            )

        return (
            sets,
            low,
            high,
            rir,
            rest,
        )

    @staticmethod
    def _duration_minutes(
        exercises: tuple[
            ExerciseTemplate,
            ...
        ],
    ) -> int:
        return 45 + max(
            0,
            len(exercises) - 5,
        ) * 5
