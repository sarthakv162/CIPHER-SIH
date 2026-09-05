# MEMORY.md — Rupantar project memory

> **Read this file at the start of every session, before touching any code.**
> **Update it at the end of every session, before you stop.**
> Keep it under 300 lines. When a section grows past its cap, compress the oldest entries into one summary line.
> This file is append-and-compress, not append-forever. Stale detail is worse than no detail.

---

## 1. Project state

| Field | Value |
|---|---|
| Current phase | **1 — Model Manager (not started)** |
| Last session | 2026-09-06 — Phase 0 shipped |
| Last commit | `phase-0: scaffold and contracts` |
| `make check` status | **green** (ruff + format + mypy + 57 unit + 8 inv-skipped) |
| Active hardware profile | `laptop-16gb` |
| Models present on disk | none |
| Python | 3.11.15, uv-managed, `.venv/`, pinned in `.python-version` |

---

## 2. Phase ledger

Mark each phase `TODO` / `IN PROGRESS` / `DONE (date)`. Add one line on what actually shipped.

| Phase | Status | Notes |
|---|---|---|
| 0 — Scaffold and contracts | **DONE (2026-09-06)** | Package, frozen `core/schemas.py` + `core/artefacts.py` (7 artefacts, all validators), async `core/store.py`, minimal `core/config.py`, `core/errors.py`, Typer CLI stubs (4 commands), 8 inv skip-skeletons, fixtures (2 articles, image, 30s clip, 7 artefact JSONs). `make check` green. |
| 1 — Model Manager | TODO | Next. `registry.py` must skip file/SHA checks when `runtime == "stub"`. |
| 2 — Text generation path | TODO | |
| 3 — All artefact agents | TODO | |
| 4 — Renderers | TODO | |
| 5 — Parivartan converters | TODO | Adds fixtures: messy CSV, Sigma rule, CEF log. |
| 6 — Multimodal ingestion | TODO | Adds fixture: advisory PDF. en-only ASR/TTS → `language_limitation` manifest warning. |
| 7 — Video assembly | TODO | |
| 8 — Air-gap, audit, selfcheck | TODO | selfcheck asserts `sys.version_info[:2] == (3, 11)`. |
| 9 — Frontend | DEFERRED | Do not start without a PLAN.md update |

---

## 3. Invariant status

| ID | Invariant | Test | Status |
|---|---|---|---|
| INV-1 | No in-process model loads | `tests/inv/test_no_inprocess_models.py` | skip-skeleton (phase 1); grep clean |
| INV-2 | ≤1 heavy model resident | `tests/inv/test_single_resident.py` | skip-skeleton (phase 1) |
| INV-3 | Lazy heavy imports | `tests/inv/test_lazy_imports.py` | skip-skeleton (phase 4) |
| INV-4 | No non-loopback egress | `tests/inv/test_no_egress.py` | skip-skeleton (phase 8); grep clean |
| INV-5 | Provenance manifest per artefact | `tests/inv/test_provenance.py` | skip-skeleton (phase 4) |
| INV-6 | Schema-validated model output | `tests/inv/test_validated_outputs.py` | skip-skeleton (phase 2) |
| INV-7 | Single model-start entry point | `tests/inv/test_single_entry_point.py` | skip-skeleton (phase 1); grep clean |
| INV-8 | Unload = process kill | `tests/inv/test_unload_kills_process.py` | skip-skeleton (phase 1); grep clean |

All eight are `pytest.skip("implemented in phase N")` and run (green as skipped) in `make check`.

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
- **Two entities:** `Transform` = one operator request (batch); `Job` = one artefact. `Job.transform_id` links them. Routes: `POST /transforms`, `GET /transforms/{id}`, `GET /transforms/{id}/artefacts`, `GET /jobs/{id}`.
- **`core/artefacts.py` and `core/schemas.py` are FROZEN** as of end-of-Phase-0. `docs/SCHEMAS.md` is their locked spec. Changing either requires a Deviations entry.
- Python **3.11 exactly** — vendored wheels (ctranslate2, pyarrow, onnxruntime) target 3.11; other versions are a build failure.
- Artefact list items carry **no `index` field** — array order is the order; renderers use `enumerate()`.
- Enums are plain `enum.Enum` (not `StrEnum`/`str,Enum`) — see Deviations.

---

## 5. Deviations from PLAN.md

Anything you did differently from the plan, and why. One line each. Empty is fine.

- **Enums are plain `enum.Enum`, not `str, Enum` / `StrEnum`.** `StrEnum` trips ruff `UP042`; `str, Enum` + `SlideLayout.title` shadows `str.title` under mypy. Pydantic still serialises `.value` in JSON mode; `store.py` uses explicit `.value`. Revisit if Phase 2 GBNF generation needs string-enum identity.
- **Added `tests/unit/test_config.py`** (not in the Phase 0 file list). Leaving `core/config.py` untested contradicted the test-alongside-code rule.
- **Artefact example fixtures were generated by serialising hand-authored model instances** (scratchpad `gen_fixtures.py`, not in repo), not typed as raw JSON by hand. Content is hand-written; only serialisation is mechanical. If `core/artefacts.py` were ever unfrozen and changed, regenerate the 7 fixtures.
- `Advisory` round-trip requires `model_dump(mode="json", by_alias=True)` to emit the `type` key (ruling G alias). The other six artefacts are alias-free.

---

## 6. Blockers

Things that are broken or unfinished and need attention. Include the file and the symptom.

- `make check-all` currently errors: no `tests/integration/` directory yet (arrives Phase 2/3). `make check` does not touch it, so this is not blocking Phase 0/1.

---

## 7. Open questions for the human

Decisions you could not make on your own. Do not guess — list them here and continue with the safest default.

- Exact GGUF builds and quantisation for `brain` and `vlm` on the demo laptop, **and the laptop's OS/arch** (needed for `requirements-lock.txt` / wheel vendoring — the dev machine is macOS arm64, the demo laptop may not be). Needs a one-time online fetch + benchmark.
- Which three cyber formats matter most to the evaluators for Parivartan. Current default: IOC CSV ↔ STIX 2.1, Sigma YAML → JSON, CEF/syslog → JSONL.
- Whether the recorded demo video uses the `laptop-16gb` or `titan-24gb` profile.
- `GenerationParams.language`: field kept, brain honours it best-effort; ASR/TTS are en-only and emit a `language_limitation` manifest warning (Phase 6). Tested values `en`, `hi`; others accepted as best-effort. Confirm `hi` is actually a demo requirement.

---

## 8. Environment facts learned

Measured, not assumed. Update whenever you measure something new.

| Fact | Value | Measured on |
|---|---|---|
| Dev machine | macOS 15.3 (Darwin 25.3), Apple Silicon, 16 GB RAM — matches target profile | 2026-09-06 |
| Python | 3.11.15 (uv-managed), `.venv/` | 2026-09-06 |
| `uv` version | 0.11.29 | 2026-09-06 |
| `ffmpeg` version | 8.1.2 (`/opt/homebrew/bin/ffmpeg`) | 2026-09-06 |
| `llama-server` on PATH | **absent** — install before Phase 1 real-model work | 2026-09-06 |
| `piper` on PATH | **absent** — needed Phase 7 | 2026-09-06 |
| `git` version | 2.51.2 | 2026-09-06 |
| Free RAM | ~1 GB free+inactive under load (not a clean idle measure) | 2026-09-06 |
| brain cold/warm load time | unknown | — |
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

### 2026-09-06 — Phase 0 — scaffold and contracts shipped, `make check` green
Did:
- Applied the user's rulings A–O to the docs: rewrote `docs/SCHEMAS.md` (moved from root; added `SourceInput`/`TransformRequest`/`Job`/`JobStatus`/`ArtefactType`; removed `index` fields; `priority`+`ioc_type` enums; `artefact_type` → `Literal`; `confidence_notes` default `""`; language best-effort note). Updated `PLAN.md` (§2 Python 3.11-exact, §3 layout, §4 Transform vs Job, Phase 0 build list, Phase 1 stub-skip note, Phase 3 routes, Phase 8 version assert, §7 single `make check` def + fixture accumulation, rule 10 → `main`). Aligned `CLAUDE.md` `make check` wording + added 3.11 / frozen-contract bullets.
- Repo housekeeping: `master` → `main`; `SCHEMAS.md` → `docs/`, agent `.md` → `.claude/agents/`, `models.yaml` → `configs/` (fixed 9 invalid `1_000_000` YAML literals); removed committed `.DS_Store`; `uv python install 3.11` + `.venv` + `.python-version`.
- Built Phase 0 via a builder subagent: `pyproject.toml` (src layout, ruff/mypy+pydantic-plugin/pytest config), `requirements.txt` + lock stub, `Makefile`, `.gitignore`, `README`, `configs/policy.yaml`; `src/rupantar/` — `__init__`, `py.typed`, `core/{errors,config,schemas,artefacts,store}.py`, `cli/{__main__,main}.py`; `tests/` — conftest, 6 unit modules (57 tests), 8 inv skip-skeletons, fixtures (2 articles, PNG, 30s MP4, 7 artefact JSONs); `scripts/{make_fixtures(real),fetch_models,vendor_wheels,demo}.sh`.
Verified:
- `make check` → ruff ✓, `ruff format --check` ✓ (26 files), `mypy src` ✓ (10 files), `pytest tests/unit` → 57 passed, `pytest tests/inv` → 8 skipped
- `python -m rupantar.cli --help` → lists exactly transform, convert, selfcheck, models
- All 7 artefact models round-trip their fixture; re-parse stable
- INV-1/4/7/8 greps over `src/` → clean (no torch/transformers/subprocess/gc-unload/network libs)
- Largest src file `core/artefacts.py` = 356 lines (< 400); no function > ~25 lines
Changed in this file:
- Rewrote §1–§9 for Phase 0 completion; added frozen-contract + Python-3.11 + Transform/Job decisions; recorded 4 deviations; added env facts (Python, ffmpeg 8.1.2, llama-server/piper absent).
Next session should start with:
- Phase 1 — Model Manager. Restate its Definition of Done, list files. Note: `registry.py` skips existence/SHA checks when `runtime == "stub"`; `test-stub` profile in `configs/models.yaml` has no `path` keys. Consider installing `llama-server` for the real-model checks, or stay on `runtime_stub`.

---

## 10. Dependencies

Recorded per CLAUDE.md. Also in `requirements.txt` / `pyproject.toml`.

- **runtime** — `pydantic>=2.7`, `pydantic-settings>=2.2`, `PyYAML>=6.0`, `typer>=0.12`, `aiosqlite>=0.20`
- **dev** (`[dev]` extra) — `ruff`, `mypy`, `pytest`, `pytest-asyncio`, `types-PyYAML`
