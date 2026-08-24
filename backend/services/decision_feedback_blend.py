from __future__ import annotations

from typing import Any


class DecisionFeedbackBlendService:
    DIMENSIONS = ("mode", "lens", "source")

    def build(
        self,
        *,
        selection_profile: dict[str, Any],
        outcome_profile: dict[str, Any],
    ) -> dict:
        selection = selection_profile.get("profile") or {}
        outcome = outcome_profile.get("profile") or {}

        blended = {}

        for dimension in self.DIMENSIONS:
            outcome_value = outcome.get(dimension) or {}
            selection_value = selection.get(dimension) or {}

            if self._learned(outcome_value):
                blended[dimension] = {
                    **outcome_value,
                    "learning_source": "outcome",
                }
                continue

            if self._learned(selection_value):
                blended[dimension] = {
                    **selection_value,
                    "learning_source": "selection",
                }
                continue

            blended[dimension] = {
                "preferred": None,
                "share": 0.0,
                "state": "unknown",
                "learning_source": None,
            }

        return {
            "profile": blended,
            "outcome_evidence": outcome_profile.get("evidence") or {},
        }

    @staticmethod
    def _learned(profile: dict[str, Any]) -> bool:
        return (
            profile.get("state") == "learned"
            and profile.get("preferred") not in (None, "")
        )
