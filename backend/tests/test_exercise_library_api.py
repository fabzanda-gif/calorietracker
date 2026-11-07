from __future__ import annotations

import pytest
from fastapi import HTTPException

from backend.api.core_main import app as core_app
from backend.api.dependencies import CurrentUser
from backend.api.routers import exercises


class FakeExerciseLibraryRepo:
    def __init__(self):
        self.list_calls = []
        self.items = [
            {
                "id": "exercise-1",
                "slug": "barbell-bench-press",
                "name": "Panca piana con bilanciere",
                "name_default": "Barbell Bench Press",
                "media": [
                    {
                        "media_type": "video",
                        "variant": "male",
                        "url": "https://example.test/bench.mp4",
                    }
                ],
                "muscles": [
                    {
                        "key": "pectorals",
                        "role": "primary",
                        "contribution": 1.0,
                    }
                ],
                "equipment": [
                    {
                        "key": "barbell",
                        "role": "primary",
                    }
                ],
                "aliases": [],
            }
        ]

    def catalog_status(self):
        return {
            "total_active": 317,
            "approved_for_generation": 10,
            "pending_curation": 307,
            "missing_movement_pattern": 307,
            "missing_training_role": 307,
            "missing_fatigue_cost": 307,
            "has_substitution_relationships": False,
            "by_body_part": {"back": 56},
        }

    def list_exercises(self, **kwargs):
        self.list_calls.append(kwargs)
        return list(self.items)

    def get_exercise(
        self,
        identifier,
        *,
        language="it",
    ):
        if identifier == "missing":
            return None
        return {
            **self.items[0],
            "requested_language": language,
        }


def user():
    return CurrentUser(
        id="user-1",
        access_token="token",
    )


def test_list_exercises_returns_media_and_filters():
    repo = FakeExerciseLibraryRepo()

    result = exercises.list_exercises(
        search="bench",
        body_part="chest",
        equipment="barbell",
        difficulty="beginner",
        approved_only=True,
        language="it",
        limit=10,
        offset=0,
        current_user=user(),
        repo=repo,
    )

    assert result["count"] == 1
    assert result["items"][0]["media"][0][
        "media_type"
    ] == "video"

    assert repo.list_calls == [
        {
            "search": "bench",
            "body_part": "chest",
            "equipment_key": "barbell",
            "difficulty": "beginner",
            "approved_only": True,
            "language": "it",
            "limit": 10,
            "offset": 0,
        }
    ]


def test_get_exercise_uses_language():
    repo = FakeExerciseLibraryRepo()

    result = exercises.get_exercise(
        identifier="barbell-bench-press",
        language="it",
        current_user=user(),
        repo=repo,
    )

    assert result["requested_language"] == "it"


def test_get_exercise_returns_404_when_missing():
    with pytest.raises(HTTPException) as exc:
        exercises.get_exercise(
            identifier="missing",
            language="it",
            current_user=user(),
            repo=FakeExerciseLibraryRepo(),
        )

    assert exc.value.status_code == 404


def test_core_backend_exposes_exercise_library():
    paths = set(core_app.openapi()["paths"])

    assert "/exercises" in paths
    assert "/exercises/{identifier}" in paths


def test_catalog_status_reports_quality_without_modifying_entries():
    repo = FakeExerciseLibraryRepo()
    response = exercises.get_catalog_status(
        current_user=user(),
        repo=repo,
    )
    assert response["total_active"] == 317
    assert response["approved_for_generation"] == 10
    assert response["pending_curation"] == 307
    assert response["has_substitution_relationships"] is False
    assert "/exercises/catalog/status" in core_app.openapi()["paths"]
