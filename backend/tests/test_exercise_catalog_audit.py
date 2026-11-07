from types import SimpleNamespace

from backend.repositories.exercise_library import ExerciseLibraryRepository


class FakeQuery:
    def __init__(self, table, pages):
        self.table = table
        self.pages = pages
        self.start = 0
        self.end = 0

    def select(self, columns):
        return self

    def eq(self, name, value):
        return self

    def order(self, name):
        return self

    def limit(self, count):
        return self

    def range(self, start, end):
        self.start, self.end = start, end
        return self

    def execute(self):
        if self.table == "exercise_relationships":
            return SimpleNamespace(data=[])
        return SimpleNamespace(data=self.pages[self.start:self.end + 1])


class FakeClient:
    def __init__(self, exercises):
        self.exercises = exercises
        self.requested = []

    def table(self, name):
        self.requested.append(name)
        return FakeQuery(name, self.exercises)


def test_catalog_audit_counts_across_pagination_without_writes():
    exercises = [
        {
            "id": f"exercise-{index}",
            "body_part": "back" if index % 2 else "chest",
            "movement_pattern": "horizontal_pull" if index < 10 else None,
            "training_role": "primary" if index < 10 else None,
            "fatigue_cost": "medium" if index < 10 else None,
            "approved_for_generation": index < 10,
        }
        for index in range(517)
    ]
    fake = FakeClient(exercises)
    result = ExerciseLibraryRepository(fake).catalog_status()
    assert result["total_active"] == 517
    assert result["approved_for_generation"] == 10
    assert result["pending_curation"] == 507
    assert result["missing_movement_pattern"] == 507
    assert result["missing_training_role"] == 507
    assert result["missing_fatigue_cost"] == 507
    assert result["has_substitution_relationships"] is False
    assert result["by_body_part"] == {"back": 258, "chest": 259}
    assert fake.requested == [
        "exercises",
        "exercises",
        "exercise_relationships",
    ]
