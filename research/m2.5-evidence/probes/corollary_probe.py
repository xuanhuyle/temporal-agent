import json, tempfile, os
from datetime import datetime, timedelta, timezone
from corollary import BeliefBase, rule, TrustLedger

class Clock:
    def __init__(self): self.now = datetime(2026,1,1,tzinfo=timezone.utc)
    def __call__(self): return self.now
clock = Clock()

@rule(name="choose")
def choose(dep_ok):
    return "use-libfoo" if dep_ok else "use-libbar"

kb = BeliefBase(clock=clock, rules=[choose])
kb.assert_("libfoo:safe", True, source="tool:scanner")
kb.derive("decision", "choose", "libfoo:safe")
kb.changes()
t1 = clock.now
proof_t1 = kb.proof("decision")
print("t1 decision:", kb.value("decision"), kb.status("decision"))

# Later event: a CVE is published. Not a retraction of a premise: a NEW fact on a different key.
clock.now += timedelta(days=10)
kb.assert_("cve:libfoo", "CVE-2026-0001", source="tool:advisories")
print("after unrelated-key CVE fact, decision:", kb.value("decision"), kb.status("decision"), "(no cascade: no dependency/unless declared)")

# Explicit correction of the premise
clock.now += timedelta(days=1)
kb.retract("libfoo:safe", reason="CVE published", fault="none")
kb.assert_("libfoo:safe", False, source="tool:scanner")
prop = kb.propagate()
for c in prop: print("  ", c)
t2 = clock.now
print("t2 decision:", kb.value("decision"))
print("revisions(decision):", [(b.ref, b.value, kb.status(b.ref).name, b.created_at.date().isoformat()) for b in kb.revisions("decision")])
print("why_out decision@1:", kb.why_out("decision@1"))
print("proof diff t1->t2:", proof_t1.diff(kb.proof("decision")))
print("history:")
print(kb.transcript())
# Is there any as-of API?
print("as-of methods:", [m for m in dir(kb) if any(s in m.lower() for s in ("as_of","asof","at","snapshot","state_at","checkout","fork","branch"))])

# restore mutates the retracted flag of the old revision
kb.restore("libfoo:safe@1")
print("after restore libfoo:safe@1 ->", kb.status("libfoo:safe@1").name, "conflicts:", [c.description for c in kb.conflicts()])

# Ledger: does reliability(at=past) exclude later outcomes?
led = TrustLedger(memory_half_life=timedelta(days=30))
past = datetime(2026,1,1,tzinfo=timezone.utc)
led.record("tool:x", False, at=datetime(2026,6,1,tzinfo=timezone.utc))
print("ledger reliability at 2026-01-01 (outcome recorded 2026-06-01):", led.reliability("tool:x", 0.95, at=past), "prior=0.95")

# Persistence
with tempfile.TemporaryDirectory() as d:
    p = os.path.join(d, "kb.json"); kb.save(p)
    data = json.load(open(p))
    print("snapshot keys:", list(data.keys()))
    kb2 = BeliefBase.load(p, rules=[choose], clock=clock)
    print("reloaded revisions:", [(b.ref, kb2.status(b.ref).name) for b in kb2.revisions("decision")], "history len", len(kb2.history))
