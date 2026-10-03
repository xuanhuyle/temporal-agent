import warnings; warnings.simplefilter("ignore")
from datetime import datetime, timezone
from memvara import Memvara, NullLLM
UTC=timezone.utc
def d(m,dd): return datetime(2026,m,dd,tzinfo=UTC)
mem = Memvara(llm=NullLLM(), user="alice")
mem.remember("user","works_at","Acme",valid_from=d(1,4),recorded_at=d(1,4))
mem.forget("user","works_at", at=d(3,1), close="ended", reason="left Acme")
print([(c.object,c.state,c.valid_to,c.invalidated_at,c.meta.get("closure")) for c in mem.history("user","works_at")])
