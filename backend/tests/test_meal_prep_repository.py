from types import SimpleNamespace

from backend.repositories.meal_prep import MealPrepRepository


class FakeQuery:
    def __init__(self, owner):
        self.owner = owner

    def _call(self, name, *args, **kwargs):
        self.owner.calls.append((name, args, kwargs))
        return self

    def select(self,*a,**k): return self._call("select",*a,**k)
    def eq(self,*a,**k): return self._call("eq",*a,**k)
    def gt(self,*a,**k): return self._call("gt",*a,**k)
    def order(self,*a,**k): return self._call("order",*a,**k)
    def limit(self,*a,**k): return self._call("limit",*a,**k)
    def insert(self,*a,**k): return self._call("insert",*a,**k)
    def update(self,*a,**k): return self._call("update",*a,**k)

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
    return [item[0] for item in fake.calls]


def test_list_available_filters_status_and_remaining():
    fake = FakeSupabase([{"id": "b1", "status": "available"}])
    rows = MealPrepRepository(fake).list_available("u1")

    assert rows[0]["id"] == "b1"
    assert "gt" in names(fake)
    assert names(fake).count("eq") == 2


def test_get_by_id_is_user_scoped():
    fake = FakeSupabase([{"id": "b1", "user_id": "u1"}])
    row = MealPrepRepository(fake).get_by_id("b1", "u1")

    assert row["id"] == "b1"
    assert names(fake).count("eq") == 2


def test_create():
    fake = FakeSupabase([{"id": "b1"}])
    row = MealPrepRepository(fake).create(
        {"user_id": "u1", "name": "Chili"}
    )

    assert row["id"] == "b1"
    assert "insert" in names(fake)


def test_update_is_user_scoped():
    fake = FakeSupabase([{"id": "b1", "portions_remaining": 3}])
    row = MealPrepRepository(fake).update(
        "b1",
        "u1",
        {"portions_remaining": 3},
    )

    assert row["portions_remaining"] == 3
    assert names(fake).count("eq") == 2
