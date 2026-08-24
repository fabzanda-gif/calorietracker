from __future__ import annotations

from typing import Any

from backend.services.decision_feedback_blend import (
    DecisionFeedbackBlendService,
)
from backend.services.decision_learning import (
    DecisionLearningService,
)
from backend.services.decision_outcome_report import (
    DecisionOutcomeReportService,
)
from backend.services.outcome_aware_learning import (
    OutcomeAwareLearningService,
)
from backend.services.outcome_feedback_profile import (
    OutcomeFeedbackProfileService,
)


class DecisionLearningPipelineService:
    """
    End-to-end learning pipeline for ranking personalization.

    Inputs:
    - persisted decision selections;
    - logged meals covering the same period.

    Output:
    - selection-only learning;
    - reconstructed outcome report;
    - outcome-aware weighted learning;
    - outcome feedback profile;
    - final blended profile ready for DecisionFeedbackService.

    This service contains no repository or API concerns.
    """

    def build(
        self,
        *,
        selections: list[dict[str, Any]],
        meals: list[dict[str, Any]],
    ) -> dict:
        selection_profile = DecisionLearningService().build(
            events=selections,
        )

        outcome_report = DecisionOutcomeReportService().build(
            selections=selections,
            meals=meals,
        )

        outcome_learning = OutcomeAwareLearningService().build(
            items=outcome_report["items"],
        )

        outcome_profile = OutcomeFeedbackProfileService().build(
            outcome_learning=outcome_learning,
        )

        blended = DecisionFeedbackBlendService().build(
            selection_profile=selection_profile,
            outcome_profile=outcome_profile,
        )

        return {
            "selection_profile": selection_profile,
            "outcome_report": outcome_report,
            "outcome_learning": outcome_learning,
            "outcome_profile": outcome_profile,
            "blended_profile": blended,
        }
