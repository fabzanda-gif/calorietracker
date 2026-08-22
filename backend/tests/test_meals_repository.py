from types import SimpleNamespace

from backend.repositories.meals import MealsRepository


class FakeQuery:
    def __init__(self, owner):
        self.owner = owner

    def _call(self, name, *args, **kwargs):
        self.owner.calls.append((name, args, kwargs))
        return self

    def select(self,*a,**k): return self._call("select",*a,**k)
    def eq(self,*a,**k): return self._call("eq",*a,**k)
    def gte(self,*a,**k): return self._call("gte",*a,**k)
    def lte(self,*a,**k): return self._call("lte",*a,**k)
    def order(self,*a,**k): return self._call("order",*a,**k)
    def limit(self,*a,**k): return self._call("limit",*a,**k)
    def insert(self,*a,**k): return self._call("insert",*a,**k)
    def update(self,*a,**k): return self._call("update",*a,**k)
    def delete(self,*a,**k): return self._call("delete",*a,**k)

    @property
    def not_(self):
        return self

    def is_(self,*a,**k):
        return self._call("not.is",*a,**k)

    def execute(self):
        if self.owner.errors:
            exc = self.owner.errors.pop(0)
            if exc is not None:
                raise exc
        data = (
            self.owner.results.pop(0)
            if self.owner.results
            else []
        )
        return SimpleNamespace(data=data)


class FakeSupabase:
    def __init__(self, *results, errors=None):
        self.results = list(results)
        self.errors = list(errors or [])
        self.calls = []

    def table(self, name):
        self.calls.append(("table", (name,), {}))
        return FakeQuery(self)


def names(fake):
    return [x[0] for x in fake.calls]


def test_list_for_date():
    fake = FakeSupabase([{"id": 1, "name": "Breakfast"}])
    rows = MealsRepository(fake).list_for_date_compatible(
        "u1",
        "2026-08-22",
    )
    assert rows[0]["id"] == 1
    assert names(fake).count("eq") == 2


def test_history_returns_schema_flag():
    fake = FakeSupabase([{"id": 1}])
    rows, enhanced = MealsRepository(fake).list_history_compatible("u1")
    assert enhanced is True
    assert rows[0]["id"] == 1


def test_create_compatible_uses_enhanced_schema_first():
    fake = FakeSupabase([{"id": 2}])
    result = MealsRepository(fake).create_compatible(
        {
            "user_id": "u1",
            "date": "2026-08-22",
            "meal_type": "Colazione",
            "name": "Breakfast",
            "calories": 400,
            "protein": 30,
            "carbs": 40,
            "fat": 10,
            "base_name": "Breakfast",
        }
    )
    assert result.data[0]["id"] == 2
    assert names(fake).count("insert") == 1


def test_create_compatible_falls_back_to_legacy():
    fake = FakeSupabase(
        [{"id": 3}],
        errors=[RuntimeError("missing new column"), None],
    )
    result = MealsRepository(fake).create_compatible(
        {
            "user_id": "u1",
            "date": "2026-08-22",
            "meal_type": "Colazione",
            "name": "Breakfast",
            "calories": 400,
            "protein": 30,
            "carbs": 40,
            "fat": 10,
            "base_name": "Breakfast",
        }
    )
    assert result.data[0]["id"] == 3
    assert names(fake).count("insert") == 2


def test_update_is_user_scoped():
    fake = FakeSupabase([{"id": 5, "calories": 450}])
    row = MealsRepository(fake).update(
        meal_id=5,
        user_id="u1",
        payload={"calories": 450},
    )
    assert row["calories"] == 450
    assert names(fake).count("eq") == 2


def test_delete_is_user_scoped():
    fake = FakeSupabase([])
    assert MealsRepository(fake).delete(5, "u1") is True
    assert "delete" in names(fake)
    assert names(fake).count("eq") == 2


def test_date_range():
    fake = FakeSupabase([{"date": "2026-08-22", "calories": 1000}])
    rows = MealsRepository(fake).list_date_range(
        "u1",
        "2026-08-01",
        "2026-08-22",
        "date,calories",
    )
    assert rows[0]["calories"] == 1000
    assert "gte" in names(fake)
    assert "lte" in names(fake)
