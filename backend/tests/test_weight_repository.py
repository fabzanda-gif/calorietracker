from types import SimpleNamespace

from backend.repositories.weight import WeightRepository


class FakeQuery:
    def __init__(self, owner, result=None):
        self.owner = owner
        self.result = result or []

    def _call(self, name, *args, **kwargs):
        self.owner.calls.append((name, args, kwargs))
        return self

    def select(self, *a, **k): return self._call("select", *a, **k)
    def eq(self, *a, **k): return self._call("eq", *a, **k)
    def order(self, *a, **k): return self._call("order", *a, **k)
    def limit(self, *a, **k): return self._call("limit", *a, **k)
    def update(self, *a, **k): return self._call("update", *a, **k)
    def upsert(self, *a, **k): return self._call("upsert", *a, **k)

    @property
    def not_(self):
        return self

    def is_(self, *a, **k):
        return self._call("not.is", *a, **k)

    def execute(self):
        self.owner.calls.append(("execute", (), {}))
        return SimpleNamespace(data=self.result)


class FakeSupabase:
    def __init__(self, result=None):
        self.result = result or []
        self.calls = []

    def table(self, name):
        self.calls.append(("table", (name,), {}))
        return FakeQuery(self, self.result)


def names(fake):
    return [c[0] for c in fake.calls]


def test_history():
    fake = FakeSupabase([{"id": 1, "date": "2026-08-22", "weight": 78.8}])
    rows = WeightRepository(fake).history("u1")
    assert rows[0]["weight"] == 78.8
    assert "not.is" in names(fake)


def test_save_upserts_by_user_and_date():
    fake = FakeSupabase([{"id": 1, "weight": 78.8}])
    WeightRepository(fake).save("u1", "2026-08-22", 78.8)
    assert "upsert" in names(fake)


def test_update_weight_changes_only_weight():
    fake = FakeSupabase([{"id": 1, "weight": 79.0}])
    WeightRepository(fake).update_weight(1, "u1", 79.0)

    update_calls = [c for c in fake.calls if c[0] == "update"]
    assert update_calls[0][1][0] == {"weight": 79.0}


def test_delete_weight_never_deletes_daily_row():
    fake = FakeSupabase([{"id": 1, "weight": None}])
    WeightRepository(fake).delete_weight(1, "u1")

    assert "update" in names(fake)
    assert "delete" not in names(fake)


def test_move_weight_clears_old_weight_then_upserts_new_date():
    fake = FakeSupabase([{"id": 2, "date": "2026-08-23", "weight": 78.5}])
    WeightRepository(fake).move_weight(
        row_id=1,
        user_id="u1",
        new_date="2026-08-23",
        weight=78.5,
    )

    op_names = names(fake)
    assert op_names.count("update") == 1
    assert op_names.count("upsert") == 1
    assert "delete" not in op_names

    update_call = [c for c in fake.calls if c[0] == "update"][0]
    assert update_call[1][0] == {"weight": None}
