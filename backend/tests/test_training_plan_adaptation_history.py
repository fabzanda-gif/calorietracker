from backend.api.routers.activities import (
    _adaptation_history_payload,
)


def test_adaptation_history_keeps_before_after():
    source = {
        "id": "source-1",
        "training_plan_id": "plan-1",
    }

    outcome = {
        "outcome": "under",
        "recommended_action": "ease_next",
        "load_ratio": 0.72,
    }

    proposal = {
        "title": "Consolida",
        "message": "Riduci il prossimo carico.",
        "target": {
            "id": "target-1",
            "distance_meters": 10000,
            "duration_minutes": 60,
        },
        "changes": {
            "distance_meters": 9000,
            "duration_minutes": 54,
        },
    }

    after = {
        "id": "target-1",
        "distance_meters": 9000,
        "duration_minutes": 54,
    }

    result = _adaptation_history_payload(
        user_id="user-1",
        source=source,
        outcome=outcome,
        proposal=proposal,
        decision="applied",
        after_state=after,
    )

    assert result["training_plan_id"] == "plan-1"
    assert (
        result["target_planned_activity_id"]
        == "target-1"
    )
    assert result["decision"] == "applied"
    assert result["load_ratio"] == 0.72
    assert (
        result["before_state"]["distance_meters"]
        == 10000
    )
    assert (
        result["after_state"]["distance_meters"]
        == 9000
    )


def test_kept_decision_preserves_proposal():
    result = _adaptation_history_payload(
        user_id="user-1",
        source={
            "id": "source",
            "training_plan_id": "plan",
        },
        outcome={
            "outcome": "over",
            "recommended_action": "recover_next",
            "load_ratio": 1.3,
        },
        proposal={
            "title": "Recupera",
            "message": "Riduci.",
            "target": {
                "id": "target",
                "distance_meters": 8000,
            },
            "changes": {
                "distance_meters": 6800,
            },
        },
        decision="kept",
        after_state={
            "id": "target",
            "distance_meters": 8000,
        },
    )

    assert result["decision"] == "kept"
    assert result["proposed_changes"] == {
        "distance_meters": 6800,
    }
    assert (
        result["before_state"]["distance_meters"]
        == result["after_state"][
            "distance_meters"
        ]
    )
