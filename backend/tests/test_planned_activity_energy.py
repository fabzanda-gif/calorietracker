from backend.services.planned_activity_energy import summarize_planned_activity_energy


def test_planned_run_uses_weight_and_distance():
    result = summarize_planned_activity_energy(
        [{
            "id": "run-1",
            "status": "planned",
            "title": "5 km facili",
            "activity_type": "Corsa",
            "distance_meters": 5000,
            "duration_minutes": 30,
        }],
        weight_kg=80,
    )

    assert result["estimated_kcal"] == 400
    assert result["activity_level"] == "moderate"


def test_skipped_sessions_do_not_change_the_budget():
    result = summarize_planned_activity_energy(
        [{
            "status": "skipped",
            "activity_type": "Corsa",
            "distance_meters": 5000,
        }],
        weight_kg=80,
    )
    assert result["estimated_kcal"] == 0
