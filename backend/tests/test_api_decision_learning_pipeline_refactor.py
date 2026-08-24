import inspect

from backend.api.routers import days
from backend.services.decision_learning_pipeline import (
    DecisionLearningPipelineService,
)


def test_days_router_uses_consolidated_learning_pipeline():
    source = inspect.getsource(
        days.get_ranked_meal_options
    )

    assert "DecisionLearningPipelineService().build(" in source


def test_router_no_longer_composes_manual_learning_services():
    source = inspect.getsource(
        days.get_ranked_meal_options
    )

    assert "DecisionLearningService().build(" not in source
    assert "DecisionOutcomeReportService().build(" not in source
    assert "OutcomeAwareLearningService().build(" not in source
    assert "OutcomeFeedbackProfileService().build(" not in source
    assert "DecisionFeedbackBlendService().build(" not in source


def test_pipeline_service_is_importable_from_router_module():
    assert (
        days.DecisionLearningPipelineService
        is DecisionLearningPipelineService
    )
