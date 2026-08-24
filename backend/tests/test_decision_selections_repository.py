from types import SimpleNamespace

from backend.repositories.decision_selections import (
    DecisionSelectionsRepository,
)


class FakeQuery:
    def __init__(self, owner):
        self.owner = owner

    def _call(self, name, *args, **kwargs):
        self.owner.calls.append((name, args, kwargs))
        return self

    def insert(self, *a, **k):
        return self._call("insert", *a, **k)

    def select(self, *a, **k):
        return self._call("select", *a, **k)

    def eq(self, *a, **k):
        return self._call("eq", *a, **k)

    def gte(self, *a, **k):
        return self._call("gte", *a, **k)

    def lte(self, *a, **k):
        return self._call("lte", *a, **k)

    def order(self, *a, **k):
        return self._call("order", *a, **k)

    def limit(self, *a, **k):
        return self._call("limit", *a, **k)

    def execute(self):
        data = self.owner.results.pop(0) if self.owner.results else []
        return SimpleNamespace(data=data)


class FakeSupabase:
    def __init__(self, *results):
        self.results = list(results)
        self.calls = []

    def table(self, name):
        self.calls.append(("table", (name,), {}))
        return FakeQuery(self)


def names(fake):
    return [call[0] for call in fake.calls]


def test_create_selection_event():
    fake = FakeSupabase([{"id": "selection-1", "user_id": "u1"}])
    repo = DecisionSelectionsRepository(fake)

    result = repo.create(
        {
            "user_id": "u1",
            "date": "2026-09-01",
            "meal_slot": "dinner",
            "meal_type": "Cena",
            "mode": "order",
            "lens": "taste",
            "option_index": 2,
            "selected_at": "2026-09-01T18:00:00Z",
            "candidate": {"name": "Poke"},
            "decision_context": {},
        }
    )

    assert result["id"] == "selection-1"
    assert "insert" in names(fake)


def test_history_is_user_scoped():
    fake = FakeSupabase([{"id": "selection-1", "user_id": "u1"}])
    DecisionSelectionsRepository(fake).list_for_user("u1")

    eq_calls = [call for call in fake.calls if call[0] == "eq"]

    assert ("user_id", "u1") in [call[1] for call in eq_calls]


def test_date_range_is_user_scoped():
    fake = FakeSupabase([{"id": "selection-1", "user_id": "u1"}])

    DecisionSelectionsRepository(fake).list_date_range(
        "u1",
        "2026-09-01",
        "2026-09-07",
    )

    assert "gte" in names(fake)
    assert "lte" in names(fake)
    assert "eq" in names(fake)
