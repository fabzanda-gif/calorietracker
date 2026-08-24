from pathlib import Path


def patch_dependencies():
    path = Path("backend/api/dependencies.py")
    text = path.read_text(encoding="utf-8")

    import_anchor = (
        "from backend.repositories.daily_logs "
        "import DailyLogsRepository\n"
    )
    import_line = (
        "from backend.repositories.decision_selections "
        "import DecisionSelectionsRepository\n"
    )

    if import_line not in text:
        if import_anchor not in text:
            raise SystemExit("dependencies.py import anchor not found")
        text = text.replace(
            import_anchor,
            import_anchor + import_line,
            1,
        )

    if "def get_decision_selections_repository(" not in text:
        function = (
            "\n\ndef get_decision_selections_repository(\n"
            "    supabase: Client = Depends(get_authenticated_supabase),\n"
            ") -> DecisionSelectionsRepository:\n"
            "    return DecisionSelectionsRepository(supabase)\n"
        )
        text = text.rstrip() + function + "\n"

    path.write_text(text, encoding="utf-8")
    print("Updated:", path)


def patch_main():
    path = Path("backend/api/main.py")
    text = path.read_text(encoding="utf-8")

    import_anchor = (
        "from backend.api.routers.daily_logs "
        "import router as daily_logs_router\n"
    )
    import_line = (
        "from backend.api.routers.decision_selections "
        "import router as decision_selections_router\n"
    )

    if import_line not in text:
        if import_anchor not in text:
            raise SystemExit("main.py import anchor not found")
        text = text.replace(
            import_anchor,
            import_anchor + import_line,
            1,
        )

    include_line = "app.include_router(decision_selections_router)\n"
    if include_line not in text:
        text = text.rstrip() + "\n" + include_line

    path.write_text(text, encoding="utf-8")
    print("Updated:", path)


patch_dependencies()
patch_main()
