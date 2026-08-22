from types import SimpleNamespace

from backend.repositories.activities import ActivitiesRepository
from backend.repositories.daily_logs import DailyLogsRepository
from backend.repositories.meals import MealsRepository
from backend.repositories.recipes import RecipesRepository
from backend.repositories.weight import WeightRepository


class FakeQuery:
    def __init__(self, result=None):
        self.result = result or []
        self.calls = []

    def _record(self, name, *args, **kwargs):
        self.calls.append((name, args, kwargs))
        return self

    def select(self, *a, **k): return self._record("select", *a, **k)
    def eq(self, *a, **k): return self._record("eq", *a, **k)
    def neq(self, *a, **k): return self._record("neq", *a, **k)
    def order(self, *a, **k): return self._record("order", *a, **k)
    def limit(self, *a, **k): return self._record("limit", *a, **k)
    def insert(self, *a, **k): return self._record("insert", *a, **k)
    def update(self, *a, **k): return self._record("update", *a, **k)
    def delete(self, *a, **k): return self._record("delete", *a, **k)
    def upsert(self, *a, **k): return self._record("upsert", *a, **k)

    @property
    def not_(self):
        return self

    def is_(self, *a, **k):
        return self._record("not.is", *a, **k)

    def execute(self):
        self.calls.append(("execute", (), {}))
        return SimpleNamespace(data=self.result)


class FakeSupabase:
    def __init__(self, result=None):
        self.result = result or []
        self.last_table = None
        self.last_query = None

    def table(self, name):
        self.last_table = name
        self.last_query = FakeQuery(self.result)
        return self.last_query


def call_names(fake):
    return [x[0] for x in fake.last_query.calls]


def test_meals_list_for_date_filters_user_and_date():
    fake = FakeSupabase([{"id": 1}])
    repo = MealsRepository(fake)

    assert repo.list_for_date("u1", "2026-08-22") == [{"id": 1}]
    assert fake.last_table == "meals"
    assert call_names(fake) == ["select", "eq", "eq", "execute"]


def test_meals_breakfast_exists():
    fake = FakeSupabase([{"id": 99}])
    repo = MealsRepository(fake)
    assert repo.breakfast_exists("u1", "2026-08-22") is True
    assert "limit" in call_names(fake)


def test_meals_create():
    fake = FakeSupabase([{"id": 2, "name": "Pasto"}])
    repo = MealsRepository(fake)
    result = repo.create({"name": "Pasto"})
    assert result["id"] == 2
    assert "insert" in call_names(fake)


def test_daily_log_upsert():
    fake = FakeSupabase([{"id": 1, "steps": 5000}])
    repo = DailyLogsRepository(fake)
    row = repo.upsert_for_date("u1", "2026-08-22", {"steps": 5000})
    assert row["steps"] == 5000
    assert call_names(fake)[0] == "upsert"


def test_activities_for_date():
    fake = FakeSupabase([{"activity_name": "Padel", "burned_calories": 500}])
    repo = ActivitiesRepository(fake)
    rows = repo.list_for_date("u1", "2026-08-22")
    assert rows[0]["activity_name"] == "Padel"


def test_weight_latest():
    fake = FakeSupabase([{"id": 4, "date": "2026-08-22", "weight": 78.8}])
    repo = WeightRepository(fake)
    row = repo.latest("u1")
    assert row["weight"] == 78.8
    assert "not.is" in call_names(fake)
    assert "limit" in call_names(fake)


def test_weight_delete_clears_column_not_daily_row():
    fake = FakeSupabase([{"id": 4, "weight": None}])
    repo = WeightRepository(fake)
    repo.delete_weight(4, "u1")
    names = call_names(fake)
    assert "update" in names
    assert "delete" not in names


def test_recipes_personal():
    fake = FakeSupabase([{"id": 7, "name": "Pasta"}])
    repo = RecipesRepository(fake)
    rows = repo.list_personal("u1")
    assert rows[0]["name"] == "Pasta"
    assert fake.last_table == "recipe_library"


def test_recipes_shared_excludes_current_user_if_requested():
    fake = FakeSupabase([])
    repo = RecipesRepository(fake)
    repo.list_shared("u1")
    assert "neq" in call_names(fake)
