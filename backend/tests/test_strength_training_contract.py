from backend.repositories.strength_plans import (
    STRENGTH_PLAN_SELECT,
    StrengthPlansRepository,
)
from backend.repositories.strength_workouts import (
    STRENGTH_EXERCISE_SELECT,
    STRENGTH_WORKOUT_SELECT,
    StrengthWorkoutExercisesRepository,
    StrengthWorkoutsRepository,
)


def test_strength_repository_table_names():
    assert (
        StrengthPlansRepository.table_name
        == "strength_plans"
    )

    assert (
        StrengthWorkoutsRepository.table_name
        == "strength_workouts"
    )

    assert (
        StrengthWorkoutExercisesRepository.table_name
        == "strength_workout_exercises"
    )


def test_strength_plan_contract_fields():
    fields = set(
        STRENGTH_PLAN_SELECT.split(",")
    )

    assert {
        "id",
        "user_id",
        "goal",
        "experience_level",
        "program_style",
        "sessions_per_week",
        "start_date",
        "total_weeks",
        "status",
    }.issubset(fields)


def test_strength_workout_contract_fields():
    fields = set(
        STRENGTH_WORKOUT_SELECT.split(",")
    )

    assert {
        "strength_plan_id",
        "scheduled_date",
        "training_week",
        "workout_index",
        "focus",
        "status",
    }.issubset(fields)


def test_strength_exercise_contract_fields():
    fields = set(
        STRENGTH_EXERCISE_SELECT.split(",")
    )

    assert {
        "strength_workout_id",
        "position",
        "exercise_key",
        "exercise_name",
        "movement_pattern",
        "target_sets",
        "target_reps_min",
        "target_reps_max",
        "target_rir",
    }.issubset(fields)
