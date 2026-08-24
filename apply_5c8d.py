from pathlib import Path


path = Path("backend/api/main.py")
text = path.read_text(encoding="utf-8")

import_anchor = (
    "from backend.api.routers.daily_logs "
    "import router as daily_logs_router\n"
)
import_line = (
    "from backend.api.routers.decision_learning "
    "import router as decision_learning_router\n"
)

if import_line not in text:
    if import_anchor not in text:
        raise SystemExit("main.py import anchor not found")

    text = text.replace(
        import_anchor,
        import_anchor + import_line,
        1,
    )

include_line = "app.include_router(decision_learning_router)\n"

if include_line not in text:
    text = text.rstrip() + "\n" + include_line

path.write_text(
    text,
    encoding="utf-8",
)

print("Updated:", path)
