from pathlib import Path


path = Path("backend/api/routers/days.py")
text = path.read_text(encoding="utf-8")

# Add pipeline import.
anchor = (
    "from backend.services.decision_learning import "
    "DecisionLearningService\n"
)
pipeline_import = (
    "from backend.services.decision_learning_pipeline import "
    "DecisionLearningPipelineService\n"
)

if pipeline_import not in text:
    if anchor not in text:
        raise SystemExit(
            "Could not find DecisionLearningService import anchor"
        )
    text = text.replace(
        anchor,
        anchor + pipeline_import,
        1,
    )

# Replace manual learning pipeline block with consolidated service.
start_marker = (
    "        selection_preferences = "
    "DecisionLearningService().build(\n"
)
end_marker = (
    "        feedback = DecisionFeedbackService().enrich_candidates(\n"
)

start = text.find(start_marker)
end = text.find(end_marker)

if start == -1:
    raise SystemExit(
        "Could not find manual learning pipeline start block"
    )

if end == -1 or end <= start:
    raise SystemExit(
        "Could not find feedback block after learning pipeline"
    )

replacement = (
    "        outcome_meals = []\n\n"
    "        if selection_events:\n"
    "            selection_dates = [\n"
    "                str(event.get(\"date\"))\n"
    "                for event in selection_events\n"
    "                if event.get(\"date\")\n"
    "            ]\n\n"
    "            if selection_dates:\n"
    "                try:\n"
    "                    outcome_meals = meals_repo.list_date_range(\n"
    "                        current_user.id,\n"
    "                        min(selection_dates),\n"
    "                        max(selection_dates),\n"
    "                    )\n"
    "                except RepositoryError:\n"
    "                    outcome_meals = []\n\n"
    "        learning_pipeline = DecisionLearningPipelineService().build(\n"
    "            selections=selection_events,\n"
    "            meals=outcome_meals,\n"
    "        )\n"
    "        blended_preferences = learning_pipeline[\"blended_profile\"]\n\n"
)

text = (
    text[:start]
    + replacement
    + text[end:]
)

# Remove now-unused manual pipeline imports, but keep DecisionFeedbackService.
unused_imports = [
    (
        "from backend.services.decision_feedback_blend import "
        "DecisionFeedbackBlendService\n"
    ),
    (
        "from backend.services.decision_learning import "
        "DecisionLearningService\n"
    ),
    (
        "from backend.services.decision_outcome_report import "
        "DecisionOutcomeReportService\n"
    ),
    (
        "from backend.services.outcome_aware_learning import "
        "OutcomeAwareLearningService\n"
    ),
    (
        "from backend.services.outcome_feedback_profile import "
        "OutcomeFeedbackProfileService\n"
    ),
]

for import_line in unused_imports:
    text = text.replace(
        import_line,
        "",
    )

# Make sure the pipeline import survived removal of adjacent imports.
if pipeline_import not in text:
    feedback_anchor = (
        "from backend.services.decision_feedback import "
        "DecisionFeedbackService\n"
    )
    if feedback_anchor not in text:
        raise SystemExit(
            "Could not restore pipeline import"
        )
    text = text.replace(
        feedback_anchor,
        feedback_anchor + pipeline_import,
        1,
    )

path.write_text(
    text,
    encoding="utf-8",
)

print("Updated:", path)
