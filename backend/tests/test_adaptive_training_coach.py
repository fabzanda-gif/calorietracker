from backend.services.adaptive_training_coach import (
    AdaptiveTrainingCoachService,
)


def hard_run():
    return {
        "source_kind": "activity",
        "source_id": "10",
        "date": "2026-11-07",
        "title": "Corsa 10 km",
        "modality": "running",
        "scope": "lower",
        "intensity": "high",
        "load_score": 120,
    }


def lower_workout():
    return {
        "id": "workout-1",
        "scheduled_date": "2026-11-08",
        "title": "Lower A",
        "focus": "lower",
        "status": "planned",
    }


def lower_exercises():
    return [
        {
            "id": "exercise-1",
            "exercise_name": "Back Squat",
            "movement_pattern": "squat",
            "target_sets": 4,
            "prescribed_load_kg": 100,
        },
        {
            "id": "exercise-2",
            "exercise_name": "Leg Curl",
            "movement_pattern": "isolation",
            "target_sets": 3,
            "prescribed_load_kg": 50,
        },
    ]


def test_hard_run_guards_next_lower_workout():
    proposals = (
        AdaptiveTrainingCoachService().build(
            recent_events=[hard_run()],
            upcoming_strength=[
                lower_workout()
            ],
            strength_exercises={
                "workout-1":
                    lower_exercises()
            },
            upcoming_running=[],
        )
    )

    by_action = {
        item["action"]: item
        for item in proposals
    }

    assert "reduce_load" in by_action
    assert "reduce_volume" in by_action

    load = by_action["reduce_load"]
    assert load["auto_apply"] is True
    assert (
        load["proposed_changes"]
        ["exercise_updates"][0]
        ["prescribed_load_kg"]
        == 95
    )

    volume = by_action["reduce_volume"]
    assert volume["auto_apply"] is False
    assert (
        volume["proposed_changes"]
        ["exercise_updates"][0]
        ["target_sets"]
        == 3
    )


def test_upper_strength_does_not_change_running():
    event = {
        "source_kind": "strength_workout",
        "source_id": "strength-1",
        "date": "2026-11-07",
        "title": "Upper A",
        "modality": "strength",
        "scope": "upper",
        "intensity": "high",
    }

    proposals = (
        AdaptiveTrainingCoachService().build(
            recent_events=[event],
            upcoming_strength=[],
            strength_exercises={},
            upcoming_running=[
                {
                    "id": "run-1",
                    "scheduled_date":
                        "2026-11-08",
                    "title": "Tempo",
                    "status": "planned",
                    "session_kind": "tempo",
                    "intensity": "hard",
                    "distance_meters": 8000,
                }
            ],
        )
    )

    assert proposals == []


def test_lower_strength_proposes_lighter_quality_run():
    event = {
        "source_kind": "strength_workout",
        "source_id": "strength-1",
        "date": "2026-11-07",
        "title": "Lower A",
        "modality": "strength",
        "scope": "lower",
        "intensity": "high",
    }

    proposals = (
        AdaptiveTrainingCoachService().build(
            recent_events=[event],
            upcoming_strength=[],
            strength_exercises={},
            upcoming_running=[
                {
                    "id": "run-1",
                    "scheduled_date":
                        "2026-11-08",
                    "title": "Tempo 8 km",
                    "status": "planned",
                    "session_kind": "tempo",
                    "intensity": "hard",
                    "distance_meters": 8000,
                    "duration_minutes": 45,
                }
            ],
        )
    )

    assert len(proposals) == 1
    proposal = proposals[0]
    assert (
        proposal["action"]
        == "reduce_running_load"
    )
    assert proposal["auto_apply"] is False
    assert (
        proposal["proposed_changes"]
        ["distance_meters"]
        == 6800
    )
    assert (
        proposal["proposed_changes"]
        ["intensity"]
        == "moderate"
    )


def test_race_is_never_rewritten_by_cross_load():
    event = {
        "source_kind": "strength_workout",
        "source_id": "strength-1",
        "date": "2026-11-07",
        "title": "Lower A",
        "modality": "strength",
        "scope": "lower",
        "intensity": "high",
    }

    proposals = (
        AdaptiveTrainingCoachService().build(
            recent_events=[event],
            upcoming_strength=[],
            strength_exercises={},
            upcoming_running=[
                {
                    "id": "race-1",
                    "scheduled_date":
                        "2026-11-08",
                    "title": "Gara",
                    "status": "planned",
                    "session_kind": "race",
                    "intensity": "race",
                    "distance_meters": 10000,
                }
            ],
        )
    )

    assert proposals == []


def test_strongest_signal_wins_for_same_target_action():
    moderate = {
        **hard_run(),
        "source_id": "9",
        "date": "2026-11-06",
        "intensity": "moderate",
    }

    proposals = (
        AdaptiveTrainingCoachService().build(
            recent_events=[
                moderate,
                hard_run(),
            ],
            upcoming_strength=[
                lower_workout()
            ],
            strength_exercises={
                "workout-1":
                    lower_exercises()
            },
            upcoming_running=[],
        )
    )

    volume = next(
        item
        for item in proposals
        if item["action"]
        == "reduce_volume"
    )

    assert volume["severity"] == "high"
    assert volume["source_id"] == "10"
