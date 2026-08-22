from types import SimpleNamespace
from backend.repositories.activities import ActivitiesRepository

class FakeQuery:
    def __init__(self, owner):
        self.owner = owner
    def _c(self, name, *args, **kwargs):
        self.owner.calls.append((name, args, kwargs))
        return self
    def select(self,*a,**k): return self._c("select",*a,**k)
    def eq(self,*a,**k): return self._c("eq",*a,**k)
    def limit(self,*a,**k): return self._c("limit",*a,**k)
    def insert(self,*a,**k): return self._c("insert",*a,**k)
    def update(self,*a,**k): return self._c("update",*a,**k)
    def delete(self,*a,**k): return self._c("delete",*a,**k)
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

def names(fake): return [x[0] for x in fake.calls]

def test_list_for_date():
    fake = FakeSupabase([{"id":1,"activity_name":"Padel","burned_calories":500}])
    rows = ActivitiesRepository(fake).list_for_date("u1","2026-08-22")
    assert rows[0]["activity_name"] == "Padel"

def test_upsert_updates_existing_named_activity():
    fake = FakeSupabase(
        [{"id":10,"activity_name":"Passi (Stima)"}],
        [{"id":10,"burned_calories":100}],
    )
    row = ActivitiesRepository(fake).upsert_named_for_date(
        "u1","2026-08-22","Passi (Stima)",100
    )
    assert row["burned_calories"] == 100
    assert "update" in names(fake)
    assert "insert" not in names(fake)

def test_upsert_creates_when_missing():
    fake = FakeSupabase([], [{"id":11,"burned_calories":100}])
    row = ActivitiesRepository(fake).upsert_named_for_date(
        "u1","2026-08-22","Passi (Stima)",100
    )
    assert row["id"] == 11
    assert "insert" in names(fake)

def test_set_named_calories():
    fake = FakeSupabase(
        [{"id":12,"activity_name":"Passi (Stima)"}],
        [{"id":12,"burned_calories":0}],
    )
    ActivitiesRepository(fake).set_named_calories(
        "u1","2026-08-22","Passi (Stima)",0
    )
    assert "update" in names(fake)

def test_delete():
    fake = FakeSupabase([])
    assert ActivitiesRepository(fake).delete(1,"u1") is True
    assert "delete" in names(fake)
