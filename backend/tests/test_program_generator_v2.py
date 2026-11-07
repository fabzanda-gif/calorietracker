from __future__ import annotations

from datetime import date

import pytest
from fastapi import HTTPException

from backend.api.dependencies import CurrentUser
from backend.api.main import app
from backend.api.routers import program_v2
from backend.services.program_generator_v2 import (
    ProgramGeneratorV2,
    ProgramV2Input,
    MANDATORY_PATTERNS,
)


def exercise(pattern, key, equipment="dumbbell", *, approved=True):
    return {
        "id": f"id-{key}",
        "slug": key,
        "legacy_key": key,
        "name": key,
        "active": True,
        "approved_for_generation": approved,
        "movement_pattern": pattern,
        "training_role": "secondary",
        "target_muscle": "pectorals" if pattern == "horizontal_push" else "lats",
        "body_part": "chest" if pattern == "horizontal_push" else "back",
        "strength_score": 3,
        "hypertrophy_score": 4,
        "general_fitness_score": 4,
        "equipment": [{"key": equipment, "role": "required"}],
    }


def catalog():
    return [
        exercise("squat", "squat"),
        exercise("hinge", "rdl"),
        exercise("horizontal_push", "bench"),
        exercise("horizontal_pull", "row"),
        exercise("vertical_push", "press"),
        exercise("vertical_pull", "pulldown"),
        exercise("core", "plank"),
        exercise("isolation", "curl"),
        exercise("squat", "press-leg"),
        exercise("hinge", "hip-thrust"),
    ]


def config(**kwargs):
    values = dict(
        start_date=date(2026, 11, 9),
        goal="hypertrophy",
        sessions_per_week=3,
        total_weeks=4,
        experience_level="beginner",
        session_duration_minutes=60,
        preferred_days=(1, 3, 5),
        allowed_equipment=("dumbbell",),
    )
    values.update(kwargs)
    return ProgramV2Input(**values)


def test_v2_ready_plan_contains_only_approved_library_uuids():
    result = ProgramGeneratorV2().preview(
        config=config(), catalog=catalog(),
        athlete_state={"data_status": "available"},
    )
    assert result["ready_for_activation"] is True
    assert result["workout_count"] == 12
    assert result["missing_movement_patterns"] == []
    assert [w["scheduled_date"] for w in result["workouts"][:3]] == [
        "2026-11-09", "2026-11-11", "2026-11-13"
    ]
    assert all(
        item["approved_for_generation"]
        and item["exercise_id"].startswith("id-")
        for workout in result["workouts"]
        for item in workout["exercises"]
    )


def test_v2_real_current_catalog_coverage_gap_fails_closed():
    no_hinge = [item for item in catalog() if item["movement_pattern"] != "hinge"]
    no_hinge.append(exercise("hinge", "unapproved-rdl", approved=False))
    preview = ProgramGeneratorV2().preview(
        config=config(), catalog=no_hinge,
        athlete_state={"data_status": "limited"},
    )
    assert preview["ready_for_activation"] is False
    assert "hinge" in preview["missing_movement_patterns"]
    assert "unapproved-rdl" not in str(preview["workouts"])


def test_v2_respects_exclusions_and_approved_equipment():
    result = ProgramGeneratorV2().preview(
        config=config(),
        catalog=catalog(),
        excluded_ids={"id-rdl"},
    )
    assert all(
        x["exercise_id"] != "id-rdl"
        for w in result["workouts"] for x in w["exercises"]
    )
    assert result["ready_for_activation"] is True

    missing = ProgramGeneratorV2().preview(
        config=config(allowed_equipment=("cable",)),
        catalog=catalog(),
    )
    assert missing["ready_for_activation"] is False
    assert set(missing["missing_movement_patterns"]) == set(MANDATORY_PATTERNS)


def test_missing_equipment_metadata_cannot_bypass_equipment_filter():
    items = catalog()
    items[0]["equipment"] = []
    result = ProgramGeneratorV2().preview(
        config=config(), catalog=items,
    )
    assert result["ready_for_activation"] is False
    assert "squat" in result["missing_movement_patterns"] or (
        len(result["workouts"][0]["exercises"]) < 5
    )


def test_v2_prefers_user_selection_without_unapproved_exercises():
    candidates = catalog()
    candidates.append(exercise("horizontal_push", "favorite-bench"))
    result = ProgramGeneratorV2().preview(
        config=config(), catalog=candidates,
        preferred_ids={"id-favorite-bench"},
    )
    assert result["workouts"][0]["exercises"][1]["exercise_id"] == "id-favorite-bench"


def test_v2_fixed_days_must_match_training_frequency():
    with pytest.raises(ValueError, match="match sessions"):
        ProgramGeneratorV2().preview(
            config=config(preferred_days=(1, 3)),
            catalog=catalog(),
        )


def test_v2_unavailable_attire_and_history_are_not_automatic_load_adjustments():
    result = ProgramGeneratorV2().preview(
        config=config(allowed_equipment=()),
        catalog=catalog(),
    )
    assert result["ready_for_activation"] is False
    assert result["athlete_data_status"] == "unavailable"
    assert all(
        x["prescribed_load_kg"] is None
        for w in result["workouts"] for x in w["exercises"]
    )


def test_v2_creation_rejects_incomplete_preview_without_any_writes(monkeypatch):
    monkeypatch.setattr(program_v2, "_preview_v2", lambda *args: {
        "ready_for_activation": False,
        "warnings": ["Missing hinge"],
        "missing_movement_patterns": ["hinge"],
    })
    class ShouldNotWrite:
        def __getattr__(self, name):
            raise AssertionError(f"Unexpected write: {name}")

    with pytest.raises(HTTPException) as exc:
        program_v2.create_program_v2(
            request=program_v2.ProgramV2Request(
                start_date=date(2026, 11, 9),
                goal="hypertrophy",
                allowed_equipment=["dumbbell"],
            ),
            current_user=CurrentUser(id="user-1", access_token="token"),
            supabase=ShouldNotWrite(),
            library_repo=ShouldNotWrite(),
            plans_repo=ShouldNotWrite(),
            workouts_repo=ShouldNotWrite(),
            exercises_repo=ShouldNotWrite(),
        )
    assert exc.value.status_code == 409
    assert "/strength/plans/v2/preview" in app.openapi()["paths"]
    assert "/strength/plans/v2" in app.openapi()["paths"]


def test_v2_demo_account_cannot_activate_program():
    with pytest.raises(HTTPException) as exc:
        program_v2.create_program_v2(
            request=program_v2.ProgramV2Request(
                start_date=date(2026, 11, 9), goal="strength",
            ),
            current_user=CurrentUser(
                id="demo", access_token="token", read_only=True,
            ),
        )
    assert exc.value.status_code == 403


def test_replacing_active_plan_pauses_old_and_preserves_history(monkeypatch):
    """Never call delete: it cascades through logs and their saved sets."""
    monkeypatch.setattr(
        program_v2, "_preview_v2",
        lambda *args: {"ready_for_activation": True},
    )
    monkeypatch.setattr(
        program_v2, "_persist_strength_plan",
        lambda **kwargs: {
            "plan": {"id": "new-plan"},
            "workout_count": 8,
            "exercise_count": 32,
        },
    )

    class Plans:
        def __init__(self):
            self.paused = []

        def list_for_user(self, user_id):
            assert user_id == "user-1"
            return [{"id": "old-plan", "status": "active"}]

        def update_status(self, *, plan_id, user_id, status):
            self.paused.append((plan_id, user_id, status))
            return {"id": plan_id, "status": status}

        def delete(self, *args, **kwargs):
            raise AssertionError("Deleting old plan would cascade workout history")

    plans = Plans()
    result = program_v2.create_program_v2(
        request=program_v2.ProgramV2Request(
            start_date=date(2026, 11, 9),
            goal="hypertrophy",
            allowed_equipment=["dumbbell"],
            replace_active=True,
        ),
        current_user=CurrentUser(id="user-1", access_token="token"),
        supabase=object(),
        library_repo=object(),
        plans_repo=plans,
        workouts_repo=object(),
        exercises_repo=object(),
    )
    assert result["created"] is True
    assert result["replaced_plan_ids"] == ["old-plan"]
    assert plans.paused == [("old-plan", "user-1", "paused")]
