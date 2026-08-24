from __future__ import annotations

from collections import Counter
from typing import Any


class DecisionLearningService:
    """
    Learn selection preferences from persisted decision-selection events.

    This service intentionally does NOT calculate an acceptance/conversion
    rate because v0.1 stores selected options, not every option impression.

    It can safely learn:
    - which mode is selected most often;
    - which ranking lens is selected most often;
    - which candidate source is selected most often;
    - how often generic fallbacks are selected.

    Confidence is based on evidence volume + dominance of the leading choice.
    """

    MIN_LEARNED_OBSERVATIONS = 3

    def build(
        self,
        *,
        events: list[dict[str, Any]],
    ) -> dict:
        valid = [
            event
            for event in events
            if self._valid(event)
        ]

        mode = self._dimension(
            valid,
            extractor=lambda event: event.get("mode"),
        )
        lens = self._dimension(
            valid,
            extractor=lambda event: event.get("lens"),
        )
        source = self._dimension(
            valid,
            extractor=lambda event: (
                event.get("candidate") or {}
            ).get("source"),
        )

        generic_count = sum(
            1
            for event in valid
            if bool(
                (event.get("candidate") or {}).get(
                    "generic_fallback"
                )
            )
        )

        generic_share = (
            generic_count / len(valid)
            if valid
            else 0.0
        )

        learned = []
        learning = []

        for kind, profile in (
            ("mode", mode),
            ("lens", lens),
            ("source", source),
        ):
            if profile["preferred"] is None:
                continue

            insight = {
                "kind": kind,
                **profile,
            }

            if profile["state"] == "learned":
                learned.append(insight)
            else:
                learning.append(insight)

        return {
            "selection_count": len(valid),
            "profile": {
                "mode": mode,
                "lens": lens,
                "source": source,
                "generic_fallback": {
                    "selected_count": generic_count,
                    "share": round(generic_share, 4),
                },
            },
            "learned": learned,
            "learning": learning,
        }

    def _dimension(
        self,
        events: list[dict[str, Any]],
        *,
        extractor,
    ) -> dict:
        values = [
            str(value).strip()
            for event in events
            if (
                (value := extractor(event))
                is not None
                and str(value).strip()
            )
        ]

        observations = len(values)

        if observations == 0:
            return {
                "preferred": None,
                "count": 0,
                "share": 0.0,
                "observations": 0,
                "confidence_level": None,
                "state": "unknown",
                "distribution": {},
            }

        counts = Counter(values)
        preferred, count = counts.most_common(1)[0]
        share = count / observations

        confidence_level = self._confidence_level(
            observations=observations,
            share=share,
        )

        state = (
            "learned"
            if observations >= self.MIN_LEARNED_OBSERVATIONS
            and confidence_level in {"medium", "high"}
            else "learning"
        )

        return {
            "preferred": preferred,
            "count": count,
            "share": round(share, 4),
            "observations": observations,
            "confidence_level": confidence_level,
            "state": state,
            "distribution": dict(
                sorted(
                    counts.items(),
                    key=lambda item: (
                        -item[1],
                        item[0],
                    ),
                )
            ),
        }

    @staticmethod
    def _confidence_level(
        *,
        observations: int,
        share: float,
    ) -> str:
        if observations >= 6 and share >= 0.70:
            return "high"

        if observations >= 3 and share >= 0.60:
            return "medium"

        return "low"

    @staticmethod
    def _valid(event: dict[str, Any]) -> bool:
        return bool(
            event.get("mode")
            and event.get("lens")
            and isinstance(
                event.get("candidate"),
                dict,
            )
            and event["candidate"].get("source")
        )
