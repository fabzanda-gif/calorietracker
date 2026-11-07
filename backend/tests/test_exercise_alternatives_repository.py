from types import SimpleNamespace

from backend.repositories.exercise_library import ExerciseLibraryRepository


class Query:
    def __init__(self, table, records):
        self.table = table
        self.records = records
        self.filters = []
        self.ids = None

    def select(self, columns):
        return self

    def eq(self, field, value):
        self.filters.append((field, value))
        return self

    def in_(self, field, values):
        self.filters.append((field, set(values)))
        return self

    def order(self, field):
        return self

    def limit(self, count):
        return self

    def execute(self):
        rows = self.records.get(self.table, [])
        for field, value in self.filters:
            if isinstance(value, set):
                rows = [r for r in rows if r.get(field) in value]
            else:
                rows = [r for r in rows if r.get(field) == value]
        return SimpleNamespace(data=rows)


class Client:
    def __init__(self, records):
        self.records = records

    def table(self, name):
        return Query(name, self.records)


def test_alternative_repository_prioritizes_links_and_hides_inactive():
    records = {
        "exercise_relationships": [
            {"source_exercise_id": "source",
             "target_exercise_id": "active",
             "relationship": "close_substitute",
             "similarity_score": 0.91,
             "rationale": "Comparable pattern"},
            {"source_exercise_id": "source",
             "target_exercise_id": "inactive",
             "relationship": "substitute",
             "similarity_score": 0.80,
             "rationale": "Should be excluded"},
            {"source_exercise_id": "source",
             "target_exercise_id": "second",
             "relationship": "regression",
             "similarity_score": None,
             "rationale": "Simpler option"},
        ],
        "exercises": [
            {"id": "active", "active": True, "name_default": "First"},
            {"id": "inactive", "active": False, "name_default": "Hidden"},
            {"id": "second", "active": True, "name_default": "Second"},
        ],
        "equipment": [{"id": "dumbbell-eq", "key": "dumbbell"}],
        "exercise_equipment": [
            {"exercise_id": "active", "equipment_id": "dumbbell-eq"}
        ],
    }
    repo = ExerciseLibraryRepository(Client(records))
    repo.get_exercise = lambda identifier, language="it": (
        {"id": "source"} if identifier == "source" else None
    )
    repo._hydrate = lambda rows, **kwargs: [
        {**row, "name": row["name_default"]} for row in rows
    ]
    suggestions = repo.list_alternatives("source")
    assert [s["exercise"]["id"] for s in suggestions] == [
        "active", "second"
    ]
    assert all(s["requires_confirmation"] for s in suggestions)
    assert repo.list_alternatives("source", equipment_key="dumbbell")[
        0
    ]["exercise"]["id"] == "active"
    assert len(repo.list_alternatives("source", equipment_key="dumbbell")) == 1
    assert repo.list_alternatives("missing") is None
