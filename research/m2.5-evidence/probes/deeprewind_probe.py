"""Probe: does DeepRewind's consistency monitor fire on organic (LLM-reconciled) contradictions?"""
import sys, tempfile, types
sys.path.insert(0, "/tmp/claude-0/-home-user-temporal-agent/45e7646f-fce6-5edf-8cae-b85e30b6afde/scratchpad/lit/repos/deeprewind/src")
# Import modules directly by file to avoid package __init__ side effects.
import importlib.util
def load(name, path):
    spec = importlib.util.spec_from_file_location(name, path); m = importlib.util.module_from_spec(spec)
    sys.modules[name] = m; spec.loader.exec_module(m); return m
base = "/tmp/claude-0/-home-user-temporal-agent/45e7646f-fce6-5edf-8cae-b85e30b6afde/scratchpad/lit/repos/deeprewind/src/open_deep_research/"
pkg = types.ModuleType("open_deep_research"); pkg.__path__ = [base]; sys.modules["open_deep_research"] = pkg
eg = load("open_deep_research.epistemic_graph", base + "epistemic_graph.py")
sc = load("open_deep_research.world_model_scoring", base + "world_model_scoring.py")
mon = load("open_deep_research.world_model_monitor", base + "world_model_monitor.py")
rb = load("open_deep_research.world_model_rollback", base + "world_model_rollback.py")
cfg = types.SimpleNamespace(wm_default_edge_weight=1.0, wm_default_reliability=0.5, wm_beta0=0.0,
    wm_theta_rho_star=0.7, wm_theta_w_star=0.6, wm_beta_star=0.5, wm_preserve_independent=True,
    wm_regenerate_dependents="mark_stale", wm_cost_retract=1.0, wm_cost_regen=1.0, wm_recovery_budget=10.0)

def build(tmp):
    g = eg.EpistemicGraph("probe", tmp)
    s = g.add_source("real web page", url="http://x")          # organic source: no reliability set
    e = g.add_evidence("compressed finding A", sources=[s])
    c = g.add_claim("Claim A", metadata={"iteration": 1})
    g.supports(e, c, research_topic="A")
    h = g.add_hypothesis("Hyp A", metadata={"iteration": 1}); g.depends_on(c, h, iteration=1)
    k = g.add_commitment("Committed to findings for: A", target=c, metadata={"iteration": 1})
    g.depends_on(k, h, iteration=1)
    rec = {"commitment_id": k, "claim_id": c, "theta": {"rho_star": 0.7, "w_star": 0.6}, "step": 1,
           "beta_at_commit": sc.compute_belief(sc.take_snapshot(g), c, cfg)}
    return g, c, k, rec

with tempfile.TemporaryDirectory() as tmp:
    # Case 1: organic path (deep_researcher.py:1169): new Claim --contradicts/invalidates--> committed Claim
    g, c, k, rec = build(tmp)
    c2 = g.add_claim("Claim B (new finding)", metadata={"iteration": 2})
    g.add_edge("contradicts", c2, c, {"iteration": 2, "rationale": "new findings contradict A"})
    g.add_edge("invalidates", c2, c, {"iteration": 2, "rationale": "A is wrong"})
    print("case1 organic Claim->Claim contradicts+invalidates: belief", round(sc.compute_belief(sc.take_snapshot(g), c, cfg),3),
          "fired:", len(mon.monitor(g, {k: rec}, cfg)))
    # Case 2: organic-style Evidence->Claim contradicts from an unrated real source (reliability default 0.5)
    g, c, k, rec = build(tmp)
    s2 = g.add_source("another web page"); e2 = g.add_evidence("counter finding", sources=[s2])
    g.contradicts(e2, c, iteration=2)
    print("case2 Evidence->Claim contradicts, default-reliability source: belief", round(sc.compute_belief(sc.take_snapshot(g), c, cfg),3),
          "fired:", len(mon.monitor(g, {k: rec}, cfg)))
    # Case 3: synthetic switch path (experiments/hooks.py:197): reliability 0.95, weight 0.95
    g, c, k, rec = build(tmp)
    s3 = g.add_source("Synthetic switch contradiction", metadata={"reliability": 0.95})
    e3 = g.add_evidence("New high-confidence contradiction", sources=[s3])
    g.contradicts(e3, c, weight=0.95, synthetic=True)
    fired = mon.monitor(g, {k: rec}, cfg)
    print("case3 synthetic switch injection: belief", round(sc.compute_belief(sc.take_snapshot(g), c, cfg),3), "fired:", len(fired))
    if fired:
        plan = rb.reduced_repair(g, fired[0], cfg); print("  repair plan:", plan)
