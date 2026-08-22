from types import SimpleNamespace
from backend.repositories.daily_logs import DailyLogsRepository

class FakeQuery:
    def __init__(self,owner): self.owner=owner
    def _c(self,name,*args,**kwargs):
        self.owner.calls.append((name,args,kwargs)); return self
    def select(self,*a,**k): return self._c("select",*a,**k)
    def eq(self,*a,**k): return self._c("eq",*a,**k)
    def gte(self,*a,**k): return self._c("gte",*a,**k)
    def lte(self,*a,**k): return self._c("lte",*a,**k)
    def order(self,*a,**k): return self._c("order",*a,**k)
    def limit(self,*a,**k): return self._c("limit",*a,**k)
    def upsert(self,*a,**k): return self._c("upsert",*a,**k)
    def update(self,*a,**k): return self._c("update",*a,**k)
    @property
    def not_(self): return self
    def is_(self,*a,**k): return self._c("not.is",*a,**k)
    def execute(self):
        if self.owner.errors:
            e=self.owner.errors.pop(0)
            if e is not None: raise e
        data=self.owner.results.pop(0) if self.owner.results else []
        return SimpleNamespace(data=data)

class FakeSupabase:
    def __init__(self,*results,errors=None):
        self.results=list(results); self.errors=list(errors or []); self.calls=[]
    def table(self,name):
        self.calls.append(("table",(name,),{})); return FakeQuery(self)

def names(fake): return [c[0] for c in fake.calls]

def test_get_for_date():
    fake=FakeSupabase([{"id":1,"steps":7000}])
    assert DailyLogsRepository(fake).get_for_date("u1","2026-08-22")["steps"]==7000

def test_legacy_fallback():
    fake=FakeSupabase([{"id":1,"steps":5000}],errors=[RuntimeError("schema"),None])
    row=DailyLogsRepository(fake).get_for_date_compatible("u1","2026-08-22")
    assert row["steps"]==5000
    assert names(fake).count("select")==2

def test_steps_partial_upsert_shape():
    fake=FakeSupabase([{"id":1,"steps":9000}])
    DailyLogsRepository(fake).upsert_for_date("u1","2026-08-22",{"steps":9000})
    payload=[c for c in fake.calls if c[0]=="upsert"][0][1][0]
    assert payload=={"user_id":"u1","date":"2026-08-22","steps":9000}

def test_planning_partial_upsert():
    fake=FakeSupabase([{"id":2,"day_type":"Ufficio","activity_plan":"Attiva"}])
    row=DailyLogsRepository(fake).upsert_for_date(
        "u1","2026-08-22",{"day_type":"Ufficio","activity_plan":"Attiva"}
    )
    assert row["day_type"]=="Ufficio"

def test_weight_history():
    fake=FakeSupabase([{"date":"2026-08-22","weight":80.1}])
    rows=DailyLogsRepository(fake).list_weight_history("u1")
    assert rows[0]["weight"]==80.1
    assert "not.is" in names(fake)

def test_weight_range():
    fake=FakeSupabase([{"date":"2026-08-22","weight":80.1}])
    rows=DailyLogsRepository(fake).list_weight_range("u1","2026-08-01","2026-08-22")
    assert rows[0]["weight"]==80.1
    assert "gte" in names(fake) and "lte" in names(fake)

def test_date_range():
    fake=FakeSupabase([{"date":"2026-08-22","steps":7000}])
    assert DailyLogsRepository(fake).list_date_range(
        "u1","2026-08-01","2026-08-22","date,steps"
    )[0]["steps"]==7000

def test_update_by_id_is_user_scoped():
    fake=FakeSupabase([{"id":3,"steps":6000}])
    DailyLogsRepository(fake).update_by_id(3,"u1",{"steps":6000})
    assert names(fake).count("eq")==2
