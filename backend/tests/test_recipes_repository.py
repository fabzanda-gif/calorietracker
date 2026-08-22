from types import SimpleNamespace

from backend.repositories.recipes import RecipesRepository


class FakeQuery:
    def __init__(self, owner):
        self.owner = owner

    def _call(self, name, *args, **kwargs):
        self.owner.calls.append((name, args, kwargs))
        return self

    def select(self,*a,**k): return self._call("select",*a,**k)
    def eq(self,*a,**k): return self._call("eq",*a,**k)
    def neq(self,*a,**k): return self._call("neq",*a,**k)
    def or_(self,*a,**k): return self._call("or",*a,**k)
    def order(self,*a,**k): return self._call("order",*a,**k)
    def limit(self,*a,**k): return self._call("limit",*a,**k)
    def insert(self,*a,**k): return self._call("insert",*a,**k)
    def update(self,*a,**k): return self._call("update",*a,**k)
    def delete(self,*a,**k): return self._call("delete",*a,**k)

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
    return [x[0] for x in fake.calls]


def test_list_personal():
    fake = FakeSupabase([{"id": 1, "name": "Pasta"}])
    rows = RecipesRepository(fake).list_personal("u1")
    assert rows[0]["name"] == "Pasta"


def test_list_shared():
    fake = FakeSupabase([{"id": 2, "is_shared": True}])
    rows = RecipesRepository(fake).list_shared()
    assert rows[0]["id"] == 2


def test_list_available_uses_or_filter():
    fake = FakeSupabase([{"id": 3}])
    RecipesRepository(fake).list_available("u1")
    assert "or" in names(fake)


def test_get_personal_by_id_is_user_scoped():
    fake = FakeSupabase([{"id": 4, "user_id": "u1"}])
    row = RecipesRepository(fake).get_personal_by_id(4, "u1")
    assert row["id"] == 4
    assert names(fake).count("eq") == 2


def test_create_response():
    fake = FakeSupabase([{"id": 5}])
    response = RecipesRepository(fake).create_response({"name": "Rice"})
    assert response.data[0]["id"] == 5


def test_update_is_user_scoped():
    fake = FakeSupabase([{"id": 6, "image_url": "x.jpg"}])
    row = RecipesRepository(fake).update(
        6,
        "u1",
        {"image_url": "x.jpg"},
    )
    assert row["image_url"] == "x.jpg"
    assert names(fake).count("eq") == 2


def test_set_shared():
    fake = FakeSupabase([{"id": 7, "is_shared": True}])
    row = RecipesRepository(fake).set_shared(
        7,
        "u1",
        True,
    )
    assert row["is_shared"] is True


def test_delete():
    fake = FakeSupabase([])
    assert RecipesRepository(fake).delete(8, "u1") is True
    assert "delete" in names(fake)
