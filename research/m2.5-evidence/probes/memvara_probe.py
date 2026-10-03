import warnings; warnings.simplefilter("ignore")
from datetime import datetime, timezone
from memvara import Memvara, NullLLM
UTC=timezone.utc
def d(m,dd): return datetime(2026,m,dd,tzinfo=UTC)
mem = Memvara(llm=NullLLM(), user="alice")
mem.remember("user","lives_in","Rome",valid_from=d(1,4),recorded_at=d(1,4))
mem.remember("user","lives_in","Berlin",valid_from=d(3,1),recorded_at=d(3,22))
t=d(3,15)
print("valid_at(t):", [c.object for c in mem.get_all(valid_at=t)])
print("known_at(t):", [c.object for c in mem.get_all(known_at=t)])
print("as_of(t):   ", [c.object for c in mem.get_all(as_of=t)])
a = mem.ask("where does the user live?", at=t)
r=a.readings[0]
print("ask now/then/stated:", [c.object for c in r.now],[c.object for c in r.then],[c.object for c in r.stated], "diverged", r.diverged)
print(a.text)
print("history:", [(c.object,c.state,c.valid_from.date(),c.valid_to and c.valid_to.date(), c.recorded_at.date()) for c in mem.history("user","lives_in")])
# search with as_of: hindsight leak?
print("search as_of(t):", [r.claim.object for r in mem.search("where does the user live", as_of=t, query_rewrite=False)])
# since diff
print("since(3/10):", mem.since(d(3,10)))
# Rome row mutated in place?
rome=[c for c in mem.history("user","lives_in") if c.object=="Rome"][0]
print("Rome valid_to stamped in place:", rome.valid_to, "meta:", rome.meta.get("closure") or {k:v for k,v in rome.meta.items()})
