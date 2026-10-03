# Milestone 2.5 evidence archive

This is the evidence behind the M2.5 research documents in `docs/`:
- research-landscape-2026-10.md
- capability-matrix.md
- NORTH_STAR_V2_PROPOSAL.md
- residual-hypotheses.md
- benchmark-reuse-assessment.md
- m2.5-decision-record.md

The files were produced on 2026-10-03 by multi-agent research workflows.
They are kept so that every claim in those documents can be checked.

**Do not edit.** These are research records, not maintained documentation.

## Contents

| path | what |
|---|---|
| `notes/<system>.md` | primary-source notes for the nine mandatory systems (`mage`, `flowstate`, `langgraph`, `pos`, `graphiti`, `countermem`, `itp`, `pmbench`, `memoryarena`), with verbatim snippets (code file:line, search extracts, abstracts) |
| `notes/sweep-<lane>.md` | the ten literature-sweep lanes, with works, URLs and snippets |
| `notes/deep-<n>.md` | deep reads of the highest-threat works found by the sweep |
| `notes/mage_msr_abstract.txt` | MAGE's abstract, verbatim from the Microsoft Research publication page |
| `verify/<system>.md` | independent adversarial verification of each mandatory system's ratings |
| `probes/` | scripts (and outputs, for LangGraph) that the analysts executed against cloned code: LangGraph time travel, ActiveGraph fork, Memvara as-of, Corollary retraction, DeepRewind rollback, PoS belief history, Graphiti filters, MemoryArena memory server |
| `synth/digest_mandatory.md`, `synth/digest_sweep.md` | the digests given to the synthesis stage, with citation-check status per work |
| `synth/deepread.json`, `synth/sweep.json` | raw structured outputs of the deep-read and sweep workflows |
| `synth/synthesis.json` | raw structured outputs of the synthesis workflow: composition attack, steelman, future-side analysis, benchmark assessment, UX table, proposals, judgments, decision, dissent, final reconciliation |
| `capability-matrix-evidence.md` | per-cell justification for the capability matrix |

## Provenance and limits

- Paths such as `/tmp/claude-0/.../scratchpad/lit/...` in these files refer
  to the original session's scratch directory. Cloned third-party
  repositories were **not** archived; re-clone them from the URLs given.
- The **local arXiv corpus** these files mention held 117,831 verbatim
  cs.AI/cs.CL daily listings (Dec 2024 to Sep 2026). It was parsed from a
  GitHub-hosted daily-listing mirror and was not archived. Treat a citation
  marked "verified in corpus" as an id and title match against those
  listings.
- arxiv.org, huggingface.co, alphaxiv.org, semanticscholar.org,
  openreview.net and docs.langchain.com were blocked by the session's egress
  policy. WebSearch was used until its session budget ran out. **No arXiv
  full text was read directly.**
- Parts of these files discuss `smoke_v1`'s three reconsiderations. The
  analysts derived them from public artifacts only (events, decision
  records, run reports); no ground-truth file was read. This directory is
  not contestant-facing: contestant processes can read only their bundle and
  the standard library.
- The raw outputs contain the analysts' errors as well as their
  corrections. The documents in `docs/` give the corrected readings. The
  final synthesis lists every correction it applied, under `final` in
  `synth/synthesis.json`.
