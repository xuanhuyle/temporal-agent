import warnings; warnings.simplefilter("ignore")
from datetime import datetime, timezone
from memvara import Memvara, NullLLM
UTC=timezone.utc
def d(m,dd): return datetime(2026,m,dd,tzinfo=UTC)
mem = Memvara(llm=NullLLM(), user="alice")
mem.remember("user","works_at","Acme",valid_from=d(1,4),recorded_at=d(1,4))
# On (real wall clock: now) we learn she left Acme on Mar 1 -> forget(close="ended", at=Mar 1)
mem.forget("user","works_at", at=d(3,1), close="ended", reason="left Acme")
t=d(3,15)
a=mem.ask("where does the user work?", at=t)
r=a.readings[0]
print("ask stated at 3/15 (store actually believed Acme on 3/15, ending learned later):", [c.object for c in r.stated])
print("get_all(as_of=3/15):", [c.object for c in mem.get_all(as_of=t)])
print("get_all(known_at=3/15, valid_at=3/15):", [c.object for c in mem.get_all(known_at=t, valid_at=t)])
print(a.text)
# Successor erased case
mem2 = Memvara(llm=NullLLM(), user="bob")
mem2.remember("user","lives_in","Rome",valid_from=d(1,4),recorded_at=d(1,4))
rc = mem2.remember("user","lives_in","Berlin",valid_from=d(3,1),recorded_at=d(3,22))
bid = rc.added[0].id
mem2.erase(bid)
r2 = mem2.ask("where does the user live?", at=t).readings
print("after erasing successor, stated at 3/15:", [[c.object for c in x.stated] for x in r2])
