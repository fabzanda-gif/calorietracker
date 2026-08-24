from __future__ import annotations

from collections import defaultdict
from typing import Any


class OutcomeAwareLearningService:
    """
    Convert reconstructed decision outcomes into conservative learning signals.

    Rules:
    - a selection is already a weak positive signal;
    - an `observed` outcome strengthens that signal;
    - `not_observed`, `ambiguous`, and `unresolved` are neutral;
    - no negative preference is inferred from a missing diary match.

    This service produces additive evidence. It does not replace the existing
    DecisionLearningService yet.
    """

    SELECTION_WEIGHT = 1.0
    OBSERVED_BONUS = 1.0

    def build(
        self,
        *,
        items: list[dict[str, Any]],
    ) -> dict:
        mode_scores: dict[str, float] = defaultdict(float)
        lens_scores: dict[str, float] = defaultdict(float)
        source_scores: dict[str, float] = defaultdict(float)

        observed_count = 0

        for item in items:
            weight = self.SELECTION_WEIGHT
            outcome = item.get("outcome") or {}

            if outcome.get("status") == "observed":
                weight += self.OBSERVED_BONUS
                observed_count += 1

            self._add(
                mode_scores,
                item.get("mode"),
                weight,
            )
            self._add(
                lens_scores,
                item.get("lens"),
                weight,
            )

            candidate = item.get("candidate") or {}
            self._add(
                source_scores,
                candidate.get("source"),
                weight,
            )

        return {
            "item_count": len(items),
            "observed_count": observed_count,
            "mode_scores": self._sorted_scores(
                mode_scores
            ),
            "lens_scores": self._sorted_scores(
                lens_scores
            ),
            "source_scores": self._sorted_scores(
                source_scores
            ),
            "preferred_mode": self._winner(
                mode_scores
            ),
            "preferred_lens": self._winner(
                lens_scores
            ),
            "preferred_source": self._winner(
                source_scores
            ),
        }

    @staticmethod
    def _add(
        scores: dict[str, float],
        value: Any,
        weight: float,
    ) -> None:
        normalized = str(
            value or ""
        ).strip()

        if not normalized:
            return

        scores[normalized] += weight

    @staticmethod
    def _sorted_scores(
        scores: dict[str, float],
    ) -> dict[str, float]:
        return dict(
            sorted(
                scores.items(),
                key=lambda item: (
                    -item[1],
                    item[0],
                ),
            )
        )

    @staticmethod
    def _winner(
        scores: dict[str, float],
    ) -> str | None:
        if not scores:
            return None

        ordered = sorted(
            scores.items(),
            key=lambda item: (
                -item[1],
                item[0],
            ),
        )

        if (
            len(ordered) > 1
            and ordered[0][1] == ordered[1][1]
        ):
            return None

        return ordered[0][0]
