from pathlib import Path

path = Path("backend/api/routers/days.py")
text = path.read_text(encoding="utf-8")

anchor = "from backend.services.decision_feedback import DecisionFeedbackService\n"
extra = (
    "from backend.services.decision_feedback_blend import DecisionFeedbackBlendService\n"
    "from backend.services.decision_outcome_report import DecisionOutcomeReportService\n"
    "from backend.services.outcome_aware_learning import OutcomeAwareLearningService\n"
    "from backend.services.outcome_feedback_profile import OutcomeFeedbackProfileService\n"
)

if "DecisionFeedbackBlendService" not in text:
    if anchor not in text:
        raise SystemExit("Decision feedback import anchor not found")
    text = text.replace(anchor, anchor + extra, 1)

old_block = (
    '        learned_preferences = DecisionLearningService().build(\n'
    '            events=selection_events,\n'
    '        )\n'
    '        feedback = DecisionFeedbackService().enrich_candidates(\n'
    '            candidates=mode_result["candidates"],\n'
    '            learned_profile=learned_preferences,\n'
    '            mode=mode_result["mode"],\n'
    '        )\n'
)

new_block = (
    '        selection_preferences = DecisionLearningService().build(\n'
    '            events=selection_events,\n'
    '        )\n\n'
    '        outcome_profile = {"profile": {}, "evidence": {}}\n\n'
    '        if selection_events:\n'
    '            selection_dates = [\n'
    '                str(event.get("date"))\n'
    '                for event in selection_events\n'
    '                if event.get("date")\n'
    '            ]\n\n'
    '            if selection_dates:\n'
    '                start_date = min(selection_dates)\n'
    '                end_date = max(selection_dates)\n\n'
    '                try:\n'
    '                    outcome_meals = meals_repo.list_date_range(\n'
    '                        current_user.id,\n'
    '                        start_date,\n'
    '                        end_date,\n'
    '                    )\n'
    '                    outcome_report = DecisionOutcomeReportService().build(\n'
    '                        selections=selection_events,\n'
    '                        meals=outcome_meals,\n'
    '                    )\n'
    '                    outcome_learning = OutcomeAwareLearningService().build(\n'
    '                        items=outcome_report["items"],\n'
    '                    )\n'
    '                    outcome_profile = OutcomeFeedbackProfileService().build(\n'
    '                        outcome_learning=outcome_learning,\n'
    '                    )\n'
    '                except RepositoryError:\n'
    '                    outcome_profile = {"profile": {}, "evidence": {}}\n\n'
    '        blended_preferences = DecisionFeedbackBlendService().build(\n'
    '            selection_profile=selection_preferences,\n'
    '            outcome_profile=outcome_profile,\n'
    '        )\n\n'
    '        feedback = DecisionFeedbackService().enrich_candidates(\n'
    '            candidates=mode_result["candidates"],\n'
    '            learned_profile=blended_preferences,\n'
    '            mode=mode_result["mode"],\n'
    '        )\n'
)

if old_block not in text:
    raise SystemExit("Could not find selection feedback block in days.py")

text = text.replace(old_block, new_block, 1)

old_response = (
    '            "decision_preferences": {\n'
    '                "preferred_mode": feedback["preferred_mode"],\n'
    '                "preferred_lens": feedback["preferred_lens"],\n'
    '                "preferred_source": feedback["preferred_source"],\n'
    '            },\n'
)

new_response = (
    '            "decision_preferences": {\n'
    '                "preferred_mode": feedback["preferred_mode"],\n'
    '                "preferred_lens": feedback["preferred_lens"],\n'
    '                "preferred_source": feedback["preferred_source"],\n'
    '                "mode_learning_source": blended_preferences["profile"]["mode"]["learning_source"],\n'
    '                "lens_learning_source": blended_preferences["profile"]["lens"]["learning_source"],\n'
    '                "source_learning_source": blended_preferences["profile"]["source"]["learning_source"],\n'
    '                "outcome_evidence": blended_preferences["outcome_evidence"],\n'
    '            },\n'
)

if old_response not in text:
    raise SystemExit("Could not find decision_preferences response block")

text = text.replace(old_response, new_response, 1)

path.write_text(text, encoding="utf-8")
print("Updated:", path)
