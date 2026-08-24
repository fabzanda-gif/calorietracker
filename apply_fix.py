from pathlib import Path

path = Path("backend/tests/conftest.py")

block = '''
import pytest

from backend.api.dependencies import (
    get_decision_selections_repository,
)
from backend.api.main import app


class _DefaultFakeDecisionSelectionsRepository:
    def list_for_user(self, user_id, *, limit=100):
        return []


@pytest.fixture(autouse=True)
def _default_decision_selections_override():
    """
    Legacy API tests predate the decision-learning dependency added in 5C.8F.

    Give them an empty decision history by default so they remain isolated
    from real Supabase. Tests that specifically exercise decision feedback
    can override get_decision_selections_repository locally as usual.
    """
    previous = app.dependency_overrides.get(
        get_decision_selections_repository
    )

    app.dependency_overrides.setdefault(
        get_decision_selections_repository,
        lambda: _DefaultFakeDecisionSelectionsRepository(),
    )

    yield

    if previous is None:
        app.dependency_overrides.pop(
            get_decision_selections_repository,
            None,
        )
    else:
        app.dependency_overrides[
            get_decision_selections_repository
        ] = previous
'''

marker = "def _default_decision_selections_override():"

if path.exists():
    text = path.read_text(encoding="utf-8")
    if marker in text:
        print("Already fixed:", path)
    else:
        if text and not text.endswith("\n"):
            text += "\n"
        path.write_text(
            text + "\n" + block.lstrip(),
            encoding="utf-8",
        )
        print("Updated:", path)
else:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(block.lstrip(), encoding="utf-8")
    print("Created:", path)
