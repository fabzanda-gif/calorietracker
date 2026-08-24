from __future__ import annotations

from typing import Any


class DecisionFeedbackService:
    '''
    Convert learned decision preferences into conservative ranking boosts.

    The feedback is intentionally weak:
    - it must not override calorie compatibility;
    - it must not override food-waste priority;
    - it must not turn sparse history into a strong preference.

    Supported learned dimensions:
    - preferred mode;
    - preferred lens;
    - preferred candidate source.

    v0.1 applies only source preference directly to candidates and exposes
    lens/mode preference as metadata for the caller.
    '''

    MAX_SOURCE_BOOST = 0.08

    def enrich_candidates(
        self,
        *,
        candidates: list[dict[str, Any]],
        learned_profile: dict[str, Any],
        mode: str,
    ) -> dict:
        profile = learned_profile.get("profile") or {}

        mode_pref = profile.get("mode") or {}
        lens_pref = profile.get("lens") or {}
        source_pref = profile.get("source") or {}

        preferred_source = self._learned_value(
            source_pref
        )
        preferred_mode = self._learned_value(
            mode_pref
        )
        preferred_lens = self._learned_value(
            lens_pref
        )

        source_boost = self._source_boost(
            source_pref
        )

        enriched = []

        for candidate in candidates:
            item = dict(candidate)

            boost = (
                source_boost
                if (
                    preferred_source
                    and item.get("source") == preferred_source
                )
                else 0.0
            )

            item["decision_feedback_boost"] = round(
                boost,
                4,
            )
            item["decision_feedback_reason"] = (
                "preferred_source"
                if boost > 0
                else None
            )

            enriched.append(item)

        return {
            "mode": mode,
            "preferred_mode": preferred_mode,
            "preferred_lens": preferred_lens,
            "preferred_source": preferred_source,
            "candidates": enriched,
        }

    def score_boost(
        self,
        *,
        candidate: dict[str, Any],
        lens: str,
        mode: str,
        preferred_lens: str | None,
        preferred_mode: str | None,
    ) -> float:
        boost = float(
            candidate.get(
                "decision_feedback_boost",
                0.0,
            )
            or 0.0
        )

        if (
            preferred_lens
            and lens == preferred_lens
        ):
            boost += 0.03

        if (
            preferred_mode
            and mode == preferred_mode
        ):
            boost += 0.02

        return round(
            min(0.13, boost),
            4,
        )

    @classmethod
    def _source_boost(
        cls,
        profile: dict[str, Any],
    ) -> float:
        if profile.get("state") != "learned":
            return 0.0

        try:
            share = float(profile.get("share") or 0)
        except (TypeError, ValueError):
            return 0.0

        return round(
            min(
                cls.MAX_SOURCE_BOOST,
                cls.MAX_SOURCE_BOOST * share,
            ),
            4,
        )

    @staticmethod
    def _learned_value(
        profile: dict[str, Any],
    ) -> str | None:
        if profile.get("state") != "learned":
            return None

        value = profile.get("preferred")

        return (
            str(value)
            if value not in (None, "")
            else None
        )
