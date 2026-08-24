from __future__ import annotations

from typing import Any


class OutcomeFeedbackProfileService:
    """
    Convert outcome-aware evidence scores into a profile compatible with
    DecisionFeedbackService.

    The adapter is intentionally conservative:
    - at least 3 total weighted points are required;
    - the winner must hold at least 60% of weighted evidence;
    - ties never become learned preferences.

    Output shape mirrors DecisionLearningService's profile dimensions.
    """

    MIN_WEIGHTED_EVIDENCE = 3.0
    MIN_SHARE = 0.60

    def build(
        self,
        *,
        outcome_learning: dict[str, Any],
    ) -> dict:
        return {
            "profile": {
                "mode": self._dimension(
                    outcome_learning.get("mode_scores") or {}
                ),
                "lens": self._dimension(
                    outcome_learning.get("lens_scores") or {}
                ),
                "source": self._dimension(
                    outcome_learning.get("source_scores") or {}
                ),
            },
            "evidence": {
                "item_count": int(
                    outcome_learning.get("item_count") or 0
                ),
                "observed_count": int(
                    outcome_learning.get("observed_count") or 0
                ),
            },
        }

    def _dimension(
        self,
        scores: dict[str, Any],
    ) -> dict:
        normalized = self._normalize_scores(scores)

        total = sum(normalized.values())

        if not normalized or total <= 0:
            return {
                "preferred": None,
                "share": 0.0,
                "state": "unknown",
                "weighted_evidence": 0.0,
                "distribution": {},
            }

        ordered = sorted(
            normalized.items(),
            key=lambda item: (
                -item[1],
                item[0],
            ),
        )

        winner, winner_score = ordered[0]

        tied = (
            len(ordered) > 1
            and winner_score == ordered[1][1]
        )

        share = (
            winner_score / total
            if total > 0
            else 0.0
        )

        learned = (
            not tied
            and total >= self.MIN_WEIGHTED_EVIDENCE
            and share >= self.MIN_SHARE
        )

        return {
            "preferred": winner if learned else None,
            "share": round(share, 4),
            "state": "learned" if learned else "learning",
            "weighted_evidence": round(total, 4),
            "distribution": dict(ordered),
        }

    @staticmethod
    def _normalize_scores(
        scores: dict[str, Any],
    ) -> dict[str, float]:
        result = {}

        for key, value in scores.items():
            name = str(key or "").strip()

            if not name:
                continue

            try:
                score = float(value)
            except (TypeError, ValueError):
                continue

            if score <= 0:
                continue

            result[name] = score

        return result
