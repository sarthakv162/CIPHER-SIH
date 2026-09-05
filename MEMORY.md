# MEMORY.md — Rupantar project memory

> **Read this file at the start of every session, before touching any code.**
> **Update it at the end of every session, before you stop.**
> Keep it under 300 lines. When a section grows past its cap, compress the oldest entries into one summary line.
> This file is append-and-compress, not append-forever. Stale detail is worse than no detail.

---

## 1. Project state

| Field | Value |
|---|---|
| Current phase | **0 — not started** |
| Last session | — |
| Last commit | — |
| `make check` status | not yet runnable |
| Active hardware profile | `laptop-16gb` |
| Models present on disk | none |

---

## 2. Phase ledger

Mark each phase `TODO` / `IN PROGRESS` / `DONE (date)`. Add one line on what actually shipped.

| Phase | Status | Notes |
|---|---|---|
| 0 — Scaffold and contracts | TODO | |
| 1 — Model Manager | TODO | |
| 2 — Text generation path | TODO | |
| 3 — All artefact agents | TODO | |
| 4 — Renderers | TODO | |
| 5 — Parivartan converters | TODO | |
| 6 — Multimodal ingestion | TODO | |
| 7 — Video assembly | TODO | |
| 8 — Air-gap, audit, selfcheck | TODO | |
| 9 — Frontend | DEFERRED | Do not start without a PLAN.md update |

---

## 3. Invariant status

| ID | Invariant | Test | Status |
|---|---|---|---|
| INV-1 | No in-process model loads | `tests/inv/test_no_inprocess_models.py` | not written |
| INV-2 | ≤1 heavy model resident | `tests/inv/test_single_resident.py` | not written |
| INV-3 | Lazy heavy imports | `tests/inv/test_lazy_imports.py` | not written |
| INV-4 | No non-loopback egress | `tests/inv/test_no_egress.py` | not written |
| INV-5 | Provenance manifest per artefact | `tests/inv/test_provenance.py` | not written |
| INV-6 | Schema-validated model output | `tests/inv/test_validated_outputs.py` | not written |
| INV-7 | Single model-start entry point | `tests/inv/test_single_entry_point.py` | not written |
| INV-8 | Unload = process kill | `tests/inv/test_unload_kills_process.py` | not written |

---

## 4. Frozen decisions

Things that are settled. Do not relitigate these without an explicit instruction from the user.

- Models run as **child processes** (`llama-server`), never in-process with torch/transformers. Unload = SIGTERM. This is the core of the design.
- **One heavy model resident at a time**, enforced by `ModelManager` with refcounting + LRU + idle TTL.
- "Agents" are **prompt template + Pydantic schema + GBNF grammar + validator** over the single loaded brain. Not separate fine-tuned models.
- Scheduler groups jobs by required model so a multi-artefact request causes **one swap per modality**, not per artefact.
- Dropped from scope: knowledge graph, Neo4j, vector RAG, embeddings, re-ranker, ChromaDB, video RAG, digital twin, fine-tuning.
- Frontend deferred to Phase 9. API + Typer CLI are the interface until then.
- Deterministic work (renderers, converters) has **zero model dependency** and must never block on the Model Manager.
- Air-gap is proven, not claimed: offline env vars, loopback-only assertion, egress monitor, selfcheck report.

---

## 5. Deviations from PLAN.md

Anything you did differently from the plan, and why. One line each. Empty is fine.

_(none yet)_

---

## 6. Blockers

Things that are broken or unfinished and need attention. Include the file and the symptom.

_(none yet)_

---

## 7. Open questions for the human

Decisions you could not make on your own. Do not guess — list them here and continue with the safest default.

- Exact GGUF builds and quantisation for `brain` and `vlm` on the demo laptop (needs a one-time online fetch and a benchmark run).
- Which three cyber formats matter most to the evaluators for Parivartan. Current default: IOC CSV ↔ STIX 2.1, Sigma YAML → JSON, CEF/syslog → JSONL.
- Whether the recorded demo video uses the `laptop-16gb` or `titan-24gb` profile.

---

## 8. Environment facts learned

Measured, not assumed. Update whenever you measure something new.

| Fact | Value | Measured on |
|---|---|---|
| `llama-server` on PATH | unknown | — |
| `ffmpeg` version | unknown | — |
| `piper` on PATH | unknown | — |
| Free RAM at idle | unknown | — |
| brain cold load time | unknown | — |
| brain warm load time (page cache) | unknown | — |
| brain tok/s, laptop profile | unknown | — |
| Peak RSS, full multimodal run | unknown | — |

---

## 9. Session log

Newest first. One block per session. Keep the last 8; compress older ones into a single summary line.

### Session template — copy this
```
### YYYY-MM-DD — <phase> — <one-line outcome>
Did:
- 
Verified:
- command → result
Changed in this file:
- 
Next session should start with:
- 
```

_(no sessions yet)_
