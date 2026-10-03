from corollary import BeliefBase
kb = BeliefBase()
kb.assert_("libfoo:safe", True, source="tool:scanner")
kb.derive("decision", lambda s: "use-libfoo", "libfoo:safe", unless=["cve:libfoo"])
kb.changes()
kb.assert_("cve:libfoo", "CVE-1", source="tool:advisories")
print("with unless declared up front:", kb.status("decision").name, kb.why_out("decision@1"))
