from datetime import date
from types import SimpleNamespace

from backend.repositories.strength_workouts import StrengthWorkoutsRepository


class FakeQuery:
    def __init__(self, name, client):
        self.name, self.client = name, client
        self.filters = {}
    def select(self, _): return self
    def eq(self, name, value):
        self.filters[name] = value
        return self
    def gte(self, name, value):
        self.filters[name + ":gte"] = value
        return self
    def lte(self, name, value):
        self.filters[name + ":lte"] = value
        return self
    def in_(self, name, values):
        self.filters[name + ":in"] = list(values)
        return self
    def order(self, name): return self
    def execute(self):
        self.client.calls.append((self.name, dict(self.filters)))
        if self.name == "strength_workouts":
            return SimpleNamespace(data=self.client.workouts)
        return SimpleNamespace(data=self.client.plans)


class FakeSupabase:
    def __init__(self):
        self.calls = []
        self.workouts = [
            {"id": "w-active", "strength_plan_id": "active",
             "user_id": "owner", "status": "planned"},
            {"id": "w-paused", "strength_plan_id": "paused",
             "user_id": "owner", "status": "planned"},
            {"id": "w-finished", "strength_plan_id": "completed",
             "user_id": "owner", "status": "planned"},
            {"id": "w-history", "strength_plan_id": "paused",
             "user_id": "owner", "status": "completed"},
            {"id": "w-free", "strength_plan_id": None,
             "user_id": "owner", "status": "planned"},
        ]
        self.plans = [
            {"id": "active", "status": "active"},
            {"id": "paused", "status": "paused"},
            {"id": "completed", "status": "completed"},
        ]
    def table(self, name): return FakeQuery(name, self)


def test_paused_program_workouts_hidden_but_historical_logs_preserved():
    client = FakeSupabase()
    result = StrengthWorkoutsRepository(client).list_date_range(
        "owner", date(2026, 11, 8), date(2026, 11, 15),
    )
    assert {x["id"] for x in result} == {
        "w-active", "w-history", "w-free"
    }
    assert len(client.calls) == 2
    assert all(filters["user_id"] == "owner" for _, filters in client.calls)
    assert sorted(client.calls[1][1]["id:in"]) == [
        "active", "completed", "paused"
    ]


def test_unknown_plan_state_fails_closed_for_planned_workouts():
    client = FakeSupabase()
    client.plans = [{"id": "active", "status": "active"}]
    rows = StrengthWorkoutsRepository(client).list_date_range(
        "owner", date(2026, 11, 8), date(2026, 11, 15),
    )
    assert "w-paused" not in {w["id"] for w in rows}
    assert "w-history" in {w["id"] for w in rows}


def test_free_sessions_do_not_require_second_plan_query():
    client = FakeSupabase()
    client.workouts = [client.workouts[-1]]
    rows = StrengthWorkoutsRepository(client).list_date_range(
        "owner", date(2026, 11, 8), date(2026, 11, 15),
    )
    assert len(rows) == 1 and rows[0]["id"] == "w-free"
    assert len(client.calls) == 1
