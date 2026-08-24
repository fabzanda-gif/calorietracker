from backend.services.decision_learning_pipeline import (
    DecisionLearningPipelineService,
)


REQUIRED_TOP_LEVEL_KEYS = {
    "selection_profile",
    "outcome_report",
    "outcome_learning",
    "outcome_profile",
    "blended_profile",
}


def test_learning_pipeline_public_shape_is_stable():
    result = DecisionLearningPipelineService().build(
        selections=[],
        meals=[],
    )

    assert set(result) == REQUIRED_TOP_LEVEL_KEYS


def test_blended_profile_exposes_three_dimensions():
    result = DecisionLearningPipelineService().build(
        selections=[],
        meals=[],
    )

    profile = result["blended_profile"]["profile"]

    assert set(profile) == {
        "mode",
        "lens",
        "source",
    }

    for dimension in profile.values():
        assert "preferred" in dimension
        assert "share" in dimension
        assert "state" in dimension
        assert "learning_source" in dimension
