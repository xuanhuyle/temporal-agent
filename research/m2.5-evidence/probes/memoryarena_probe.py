import sys, importlib.util
sys.path.insert(0, "ma_stub")
def load(name, path):
    spec = importlib.util.spec_from_file_location(name, path); m = importlib.util.module_from_spec(spec); spec.loader.exec_module(m); return m
base = "repos/ZexueHe_MemoryArena/memory/memory_systems/"
lc_mod = load("lc", base + "long_context.py")
lc = lc_mod.LongContextMemorySystem(max_tokens=60)
lc.add_chunk("EVENT-1 decision: chose library A")
lc.add_chunk("EVENT-2 new info: library A deprecated")
print("LONG_CONTEXT wrap ->", repr(lc.wrap_user_prompt("what did we choose?")))
rag_mod = load("rag", base + "rag.py")
r = rag_mod.RAGMemorySystem(retrieval_method="bm25", top_k=1)
for c in ["Step 1: bought camera body Canon EOS R", "Step 2: bought tripod", "Step 3: weather is sunny"]:
    r.add_chunk(c)
print("BM25 wrap ->", repr(r.wrap_user_prompt("which camera body lens mount")))
print("RAG has no delete/update/as-of API:", [a for a in dir(r) if not a.startswith('__')])
