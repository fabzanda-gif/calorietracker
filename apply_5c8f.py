from pathlib import Path


def patch_dependencies():
    path = Path("backend/api/dependencies.py")
    text = path.read_text(encoding="utf-8")

    # No new dependency function needed if 5C.8B is already applied.
    if "def get_decision_selections_repository(" not in text:
        raise SystemExit(
            "5C.8B dependency is missing. Apply 5C.8B first."
        )

    print("Verified:", path)


def patch_days():
    path = Path("backend/api/routers/days.py")
    text = path.read_text(encoding="utf-8")

    dep_anchor = (
        "    get_daily_logs_repository,\n"
    )
    dep_line = (
        "    get_decision_selections_repository,\n"
    )

    if dep_line not in text:
        if dep_anchor not in text:
            raise SystemExit("days.py dependency anchor not found")
        text = text.replace(
            dep_anchor,
            dep_anchor + dep_line,
            1,
        )

    import_anchor = (
        "from backend.services.decision_mode import (\n"
    )
    extra_imports = (
        "from backend.services.decision_feedback import "
        "DecisionFeedbackService\n"
        "from backend.services.decision_learning import "
        "DecisionLearningService\n"
    )

    if (
        "from backend.services.decision_feedback import "
        "DecisionFeedbackService\n"
    ) not in text:
        if import_anchor not in text:
            raise SystemExit("days.py service import anchor not found")
        text = text.replace(
            import_anchor,
            extra_imports + import_anchor,
            1,
        )

    repo_import_anchor = (
        "from backend.repositories.daily_logs import DailyLogsRepository\n"
    )
    repo_import_line = (
        "from backend.repositories.decision_selections import "
        "DecisionSelectionsRepository\n"
    )

    if repo_import_line not in text:
        if repo_import_anchor not in text:
            raise SystemExit("days.py repo import anchor not found")
        text = text.replace(
            repo_import_anchor,
            repo_import_anchor + repo_import_line,
            1,
        )

    signature_anchor = (
        "    recipes_repo: RecipesRepository = Depends(\n"
        "        get_recipes_repository\n"
        "    ),\n"
        "):\n"
    )
    signature_replacement = (
        "    recipes_repo: RecipesRepository = Depends(\n"
        "        get_recipes_repository\n"
        "    ),\n"
        "    decision_selections_repo: DecisionSelectionsRepository = Depends(\n"
        "        get_decision_selections_repository\n"
        "    ),\n"
        "):\n"
    )

    if (
        "decision_selections_repo: DecisionSelectionsRepository"
        not in text
    ):
        if signature_anchor not in text:
            raise SystemExit("options signature anchor not found")
        text = text.replace(
            signature_anchor,
            signature_replacement,
            1,
        )

    ranking_anchor = (
        "        ranked = DecisionRankingService().rank(\n"
        "            candidates=mode_result[\"candidates\"],\n"
        "            available_kcal=available_kcal,\n"
        "            protein_remaining_g=protein_remaining_g,\n"
        "            mode=mode_result[\"mode\"],\n"
        "        )\n"
    )

    ranking_replacement = (
        "        selection_events = decision_selections_repo.list_for_user(\n"
        "            current_user.id,\n"
        "            limit=100,\n"
        "        )\n"
        "        learned_preferences = DecisionLearningService().build(\n"
        "            events=selection_events,\n"
        "        )\n"
        "        feedback = DecisionFeedbackService().enrich_candidates(\n"
        "            candidates=mode_result[\"candidates\"],\n"
        "            learned_profile=learned_preferences,\n"
        "            mode=mode_result[\"mode\"],\n"
        "        )\n\n"
        "        ranked = DecisionRankingService().rank(\n"
        "            candidates=feedback[\"candidates\"],\n"
        "            available_kcal=available_kcal,\n"
        "            protein_remaining_g=protein_remaining_g,\n"
        "            mode=mode_result[\"mode\"],\n"
        "            preferred_lens=feedback[\"preferred_lens\"],\n"
        "            preferred_mode=feedback[\"preferred_mode\"],\n"
        "        )\n"
    )

    if "selection_events = decision_selections_repo.list_for_user(" not in text:
        if ranking_anchor not in text:
            raise SystemExit("ranking anchor not found")
        text = text.replace(
            ranking_anchor,
            ranking_replacement,
            1,
        )

    response_anchor = (
        '            "empty_reason": mode_result["empty_reason"],\n'
    )
    response_replacement = (
        '            "decision_preferences": {\n'
        '                "preferred_mode": feedback["preferred_mode"],\n'
        '                "preferred_lens": feedback["preferred_lens"],\n'
        '                "preferred_source": feedback["preferred_source"],\n'
        '            },\n'
        '            "empty_reason": mode_result["empty_reason"],\n'
    )

    if '"decision_preferences": {' not in text:
        if response_anchor not in text:
            raise SystemExit("response anchor not found")
        text = text.replace(
            response_anchor,
            response_replacement,
            1,
        )

    path.write_text(text, encoding="utf-8")
    print("Updated:", path)


patch_dependencies()
patch_days()
