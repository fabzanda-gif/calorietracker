from pathlib import Path


def patch_dependencies():
    path = Path("backend/api/dependencies.py")
    text = path.read_text(encoding="utf-8")

    if "def get_optional_decision_selections_repository(" not in text:
        anchor = (
            "def get_decision_selections_repository(\n"
            "    supabase: Client = Depends(get_authenticated_supabase),\n"
            ") -> DecisionSelectionsRepository:\n"
            "    return DecisionSelectionsRepository(supabase)\n"
        )

        replacement = anchor + (
            "\n\n"
            "def get_optional_decision_selections_repository(\n"
            "    current_user: CurrentUser = Depends(get_current_user),\n"
            ") -> DecisionSelectionsRepository | None:\n"
            "    \"\"\"\n"
            "    Best-effort dependency for non-critical ranking personalization.\n\n"
            "    The core /options endpoint must remain usable even when decision-learning\n"
            "    persistence is not configured or temporarily unavailable. Strict\n"
            "    persistence endpoints continue using get_decision_selections_repository.\n"
            "    \"\"\"\n"
            "    try:\n"
            "        supabase = get_authenticated_supabase(current_user)\n"
            "    except RuntimeError:\n"
            "        return None\n\n"
            "    return DecisionSelectionsRepository(supabase)\n"
        )

        if anchor not in text:
            raise SystemExit(
                "Could not find get_decision_selections_repository in "
                "backend/api/dependencies.py"
            )

        text = text.replace(anchor, replacement, 1)

    path.write_text(text, encoding="utf-8")
    print("Updated:", path)


def patch_days():
    path = Path("backend/api/routers/days.py")
    text = path.read_text(encoding="utf-8")

    if "    get_optional_decision_selections_repository,\n" not in text:
        text = text.replace(
            "    get_decision_selections_repository,\n",
            "    get_optional_decision_selections_repository,\n",
            1,
        )

    old_signature = (
        "    decision_selections_repo: DecisionSelectionsRepository = Depends(\n"
        "        get_decision_selections_repository\n"
        "    ),\n"
    )
    new_signature = (
        "    decision_selections_repo: DecisionSelectionsRepository | None = Depends(\n"
        "        get_optional_decision_selections_repository\n"
        "    ),\n"
    )

    if old_signature in text:
        text = text.replace(
            old_signature,
            new_signature,
            1,
        )

    old_learning = (
        "        selection_events = decision_selections_repo.list_for_user(\n"
        "            current_user.id,\n"
        "            limit=100,\n"
        "        )\n"
        "        learned_preferences = DecisionLearningService().build(\n"
        "            events=selection_events,\n"
        "        )\n"
    )

    new_learning = (
        "        selection_events = []\n\n"
        "        if decision_selections_repo is not None:\n"
        "            try:\n"
        "                selection_events = (\n"
        "                    decision_selections_repo.list_for_user(\n"
        "                        current_user.id,\n"
        "                        limit=100,\n"
        "                    )\n"
        "                )\n"
        "            except RepositoryError:\n"
        "                selection_events = []\n\n"
        "        learned_preferences = DecisionLearningService().build(\n"
        "            events=selection_events,\n"
        "        )\n"
    )

    if old_learning not in text:
        raise SystemExit(
            "Could not find selection learning block in days.py"
        )

    text = text.replace(
        old_learning,
        new_learning,
        1,
    )

    path.write_text(text, encoding="utf-8")
    print("Updated:", path)


patch_dependencies()
patch_days()
