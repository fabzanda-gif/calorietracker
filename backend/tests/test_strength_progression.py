from backend.services.strength_progression import (
    StrengthProgressionService,
)


def planned(
    *,
    pattern="horizontal_push",
    sets=3,
    reps_min=8,
    reps_max=12,
    rir=2,
):
    return {
        "id": "exercise-1",
        "exercise_key": "bench_press",
        "exercise_name": "Bench Press",
        "movement_pattern": pattern,
        "target_sets": sets,
        "target_reps_min": reps_min,
        "target_reps_max": reps_max,
        "target_rir": rir,
    }


def outcome(value):
    return {
        "exercise_id": "exercise-1",
        "outcome": value,
    }


def logs(
    reps,
    *,
    load=80,
    rir=2,
):
    return [
        {
            "strength_workout_exercise_id":
                "exercise-1",
            "set_index": index,
            "reps": rep,
            "load_kg": load,
            "rir": rir,
        }
        for index, rep in enumerate(
            reps,
            start=1,
        )
    ]


def test_over_target_increases_upper_body_load():
    result = StrengthProgressionService().preview(
        planned_exercise=planned(),
        exercise_outcome=outcome(
            "over_target"
        ),
        set_logs=logs(
            [12, 12, 12],
            load=80,
            rir=3,
        ),
    )

    assert result["action"] == (
        "increase_load"
    )
    assert result["current_load_kg"] == 80
    assert result["proposed_load_kg"] == 82.5


def test_over_target_lower_body_uses_five_kg():
    result = StrengthProgressionService().preview(
        planned_exercise=planned(
            pattern="squat"
        ),
        exercise_outcome=outcome(
            "over_target"
        ),
        set_logs=logs(
            [12, 12, 12],
            load=100,
            rir=3,
        ),
    )

    assert result["proposed_load_kg"] == 105


def test_on_target_maintains_load():
    result = StrengthProgressionService().preview(
        planned_exercise=planned(),
        exercise_outcome=outcome(
            "on_target"
        ),
        set_logs=logs(
            [10, 10, 10],
            load=80,
            rir=2,
        ),
    )

    assert result["action"] == "maintain"
    assert result["proposed_load_kg"] == 80


def test_missing_sets_do_not_force_reduction():
    result = StrengthProgressionService().preview(
        planned_exercise=planned(),
        exercise_outcome=outcome(
            "under_target"
        ),
        set_logs=logs(
            [10, 10],
            load=80,
            rir=2,
        ),
    )

    assert result["action"] == "maintain"
    assert result["proposed_load_kg"] == 80


def test_low_reps_reduce_load():
    result = StrengthProgressionService().preview(
        planned_exercise=planned(),
        exercise_outcome=outcome(
            "under_target"
        ),
        set_logs=logs(
            [8, 7, 7],
            load=80,
            rir=1,
        ),
    )

    assert result["action"] == (
        "reduce_load"
    )
    assert result["proposed_load_kg"] == 75


def test_excessive_effort_can_reduce_load():
    result = StrengthProgressionService().preview(
        planned_exercise=planned(),
        exercise_outcome=outcome(
            "under_target"
        ),
        set_logs=logs(
            [8, 8, 8],
            load=80,
            rir=0,
        ),
    )

    assert result["action"] == (
        "reduce_load"
    )
    assert result["proposed_load_kg"] == 75


def test_zero_external_load_is_maintained():
    result = StrengthProgressionService().preview(
        planned_exercise=planned(
            pattern="core"
        ),
        exercise_outcome=outcome(
            "over_target"
        ),
        set_logs=logs(
            [12, 12, 12],
            load=0,
            rir=3,
        ),
    )

    assert result["action"] == "maintain"
    assert result["proposed_load_kg"] == 0


def test_representative_load_uses_mode():
    set_logs = [
        {
            "load_kg": 80,
        },
        {
            "load_kg": 80,
        },
        {
            "load_kg": 85,
        },
    ]

    value = (
        StrengthProgressionService()
        ._representative_load(
            set_logs
        )
    )

    assert value == 80
