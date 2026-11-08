from types import SimpleNamespace

import pytest
from fastapi import HTTPException

from backend.api.dependencies import CurrentUser
from backend.api.routers import profile


class ExportDatabase:
    def __init__(self, tables, cap=137):
        self.tables = tables
        self.cap = cap
        self.requests = []

    def table(self, name):
        return ExportQuery(self, name)


class ExportQuery:
    def __init__(self, database, table):
        self.database, self.table = database, table
        self.filters, self.orders = [], []
        self.columns, self.bounds = "*", (0, 0)

    def select(self, columns):
        self.columns = columns
        return self

    def eq(self, column, value):
        self.filters.append((column, [value]))
        return self

    def in_(self, column, values):
        self.filters.append((column, values))
        return self

    def order(self, column):
        self.orders.append(column)
        return self

    def range(self, start, end):
        self.bounds = (start, end)
        return self

    def limit(self, count):
        self.bounds = (0, count - 1)
        return self

    def execute(self):
        self.database.requests.append(self)
        rows = self.database.tables.get(self.table, [])
        for column, values in self.filters:
            rows = [row for row in rows if row.get(column) in values]
        if self.orders:
            rows = sorted(rows, key=lambda row: tuple(row[c] for c in self.orders))
        start, end = self.bounds
        rows = rows[start:min(end + 1, start + self.database.cap)]
        if self.columns != "*":
            rows = [{key: row.get(key) for key in self.columns.split(",")} for row in rows]
        return SimpleNamespace(data=rows)


def user(read_only=False):
    return CurrentUser(id="owner", access_token="token", read_only=read_only)


def test_export_includes_full_history_and_children_without_other_users_or_secrets(monkeypatch):
    tables = {
        "meals": [{"id": n, "user_id": "owner"} for n in range(1103)],
        "meal_ingredients": [{"id": n, "meal_id": n} for n in range(1103)],
        "recipe_library": [{"id": "recipe", "user_id": "owner"}],
        "recipe_ingredients": [{"id": n, "recipe_id": "recipe"} for n in range(601)],
    }
    for name in ("strength_workout_logs", "strength_set_logs", "special_periods",
                 "training_coach_adjustments", "training_coach_preferences",
                 "training_exercise_preferences", "google_calendar_events"):
        tables[name] = [{"id": 1, "user_id": "owner", "exercise_id": "exercise"}]
    tables["push_subscriptions"] = [{
        "id": 1, "user_id": "owner", "enabled": True,
        "endpoint": "secret-endpoint", "p256dh": "secret-key", "auth": "secret-auth",
    }]
    tables["google_calendar_connections"] = [{
        "user_id": "owner", "calendar_id": "calendar", "access_token": "secret-token",
    }]
    tables["oura_connections"] = [{"user_id": "owner", "refresh_token": "secret-refresh"}]
    tables["meals"].append({"id": 9999, "user_id": "other"})
    tables["meal_ingredients"].append({"id": 9999, "meal_id": 9999})
    tables["recipe_ingredients"].append({"id": 9999, "recipe_id": "other"})
    database = ExportDatabase(tables)
    monkeypatch.setattr(profile, "get_admin_supabase_client", lambda: database)

    result = profile.export_profile_data(user())
    data = result["data"]
    assert len(data["meals"]) == 1103
    assert len(data["meal_ingredients"]) == 1103
    assert len(data["recipe_ingredients"]) == 601
    for table in tables.keys() - {"google_calendar_connections", "oura_connections"}:
        assert data[table]
    assert "secret-" not in str(result)
    for request in database.requests:
        assert request.filters
        if request.table in {"meal_ingredients", "recipe_ingredients"}:
            assert len(request.filters[0][1]) <= 100
        else:
            assert ("user_id", ["owner"]) in request.filters


def test_export_composite_keys_have_deterministic_pagination():
    database = ExportDatabase({"training_preferred_days": [
        {"user_id": "owner", "weekday": n} for n in reversed(range(7))
    ]}, cap=2)
    rows = profile._export_rows(database, "training_preferred_days", user_id="owner")
    assert [row["weekday"] for row in rows] == list(range(7))
    assert all(q.orders == ["user_id", "weekday"] for q in database.requests)


def test_export_demo_cannot_open_admin_client(monkeypatch):
    def forbidden():
        pytest.fail("Demo must not access the export database")
    monkeypatch.setattr(profile, "get_admin_supabase_client", forbidden)
    with pytest.raises(HTTPException) as exc:
        profile.export_profile_data(user(read_only=True))
    assert exc.value.status_code == 403


def test_export_failure_does_not_return_a_partial_success(monkeypatch):
    class BrokenDatabase(ExportDatabase):
        def table(self, name):
            if name == "strength_set_logs":
                raise RuntimeError("database unavailable")
            return super().table(name)
    monkeypatch.setattr(profile, "get_admin_supabase_client", lambda: BrokenDatabase({}))
    with pytest.raises(HTTPException) as exc:
        profile.export_profile_data(user())
    assert exc.value.status_code == 502
