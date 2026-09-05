# MEMORY.md — Rupantar project memory

> **Read this file at the start of every session, before touching any code.**
> **Update it at the end of every session, before you stop.**
> Keep it under 300 lines. When a section grows past its cap, compress the oldest entries into one summary line.
> This file is append-and-compress, not append-forever. Stale detail is worse than no detail.

---

## 1. Project state

| Field | Value |
|---|---|
| Current phase | **2 — Text generation path (not started)** |
| Last session | 2026-09-06 — Phase 1 shipped |
| Last commit | `phase-1: model manager` |
| `make check` status | **green** (ruff + format + mypy 18 files + 84 unit / 1 slow-skip + 6 inv / 4 skeleton) |
| Active hardware profile | `laptop-16gb` |
| Models present on disk | none |
| Python | 3.11.15, uv-managed, `.venv/`, pinned in `.python-version` |

---

## 2. Phase ledger

Mark each phase `TODO` / `IN PROGRESS` / `DONE (date)`. Add one line on what actually shipped.

| Phase | Status | Notes |
|---|---|---|
| 0 — Scaffold and contracts | **DONE (2026-09-06)** | Package, frozen `core/schemas.py` + `core/artefacts.py` (7 artefacts, all validators), async `core/store.py`, minimal `core/config.py`, `core/errors.py`, Typer CLI stubs (4 commands), 8 inv skip-skeletons, fixtures (2 articles, image, 30s clip, 7 artefact JSONs). `make check` green. |
| 1 — Model Manager | **DONE (2026-09-06)** | `models/` package: `runtime_base.py` (ABC + SIGTERM→SIGKILL `terminate_process`, `wait_healthy`, `read_rss_bytes` via `ps`), `_ports.py`, `runtime_stub.py` (child `python -m` stdlib `http.server`, zero model files), `registry.py` (skips file/SHA for `runtime == "stub"`; real missing file → `ModelFileMissingError` naming `scripts/fetch_models.sh`), `_support.py` (Lease/Event/state), `manager.py` (async `acquire()` CM + `obtain/release`, refcount, single `asyncio.Condition` serialises load/evict/reap, `max_heavy_resident` eviction waits for real process exit, LRU + idle-TTL reaper, external-death respawn, `status()`), `runtime_llama.py` (untested vs real binary, `@pytest.mark.slow`). Events → new `events` table in `store.py`. `models status` CLI (not the API route — see Deviations). INV-1/2/7/8 tests real and green. |
| 2 — Text generation path | TODO | Next. `models/client.py` async OpenAI-compat client vs `lease.endpoint`; needs an HTTP client — **none in requirements yet** (Phase 1 used stdlib `urllib` only). Decide httpx vs stdlib and record it. |
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
| INV-1 | No in-process model loads | `tests/inv/test_no_inprocess_models.py` | **PASS** — AST scan: no module-scope import of torch/transformers/llama_cpp/ctranslate2/faster_whisper/onnxruntime under `src/`. Dynamic (API-process) check deferred until `api/` exists. |
| INV-2 | ≤1 heavy model resident | `tests/inv/test_single_resident.py` | **PASS** — event-stream replay over brain→vlm→brain swaps (stub runtime) proves never two heavy READY; + live `os.kill(pid,0)` probes prove old process dead before new alive. |
| INV-3 | Lazy heavy imports | `tests/inv/test_lazy_imports.py` | skip-skeleton (phase 4) |
| INV-4 | No non-loopback egress | `tests/inv/test_no_egress.py` | skip-skeleton (phase 8); grep clean |
| INV-5 | Provenance manifest per artefact | `tests/inv/test_provenance.py` | skip-skeleton (phase 4) |
| INV-6 | Schema-validated model output | `tests/inv/test_validated_outputs.py` | skip-skeleton (phase 2) |
| INV-7 | Single model-start entry point | `tests/inv/test_single_entry_point.py` | **PASS** — regex scan: `subprocess`/`Popen`/`os.spawn`/`create_subprocess_*`/`multiprocessing` only in `models/runtime_*.py`; `ModelManager.acquire`/`obtain` present. |
| INV-8 | Unload = process kill | `tests/inv/test_unload_kills_process.py` | **PASS** — acquire stub, `os.kill(pid,0)` ok, evict, poll to `ProcessLookupError`; `EVICT_DONE` event carries the dead pid. |

INV-1/2/7/8 are real assertions run in `make check`. INV-3/4/5/6 are still `pytest.skip("implemented in phase N")` skeletons (green as skipped).

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
- **Phase 1: `api/routes/models.py` not built.** The Phase 1 build list names it (`GET /models`, `GET /models/status`, `POST /models/{key}/unload`), but there is no `api/` package and FastAPI is not a Phase 1 dependency. Implemented `models status` in `cli/main.py` instead. The route module lands with the rest of `api/` (Phase 3). A fresh CLI process always shows `NOT_LOADED` — the manager lives in the server/runner process, not the CLI.
- **Phase 1: events go to a new `events` table in `core/store.py`** (`id/ts/kind/model_key/pid/detail_json` + `idx_events_kind`, async `append_event`/`list_events`). `store.py` is not frozen. The `ModelManager` event sink is injectable (defaults to in-memory; Store-backed sink available) and events are also kept in-process as `manager.events`.
- **Phase 1: `manager.py` split** — support types/helpers (`Lease`, `Event`, `ModelState`, `store_event_sink`, `default_runtime_factory`) live in `models/_support.py` to keep `manager.py` under 400 lines (337 now). Re-exported from `manager` via `__all__`.
- **Phase 1: manager serialises all load/evict/reap through one `asyncio.Condition`.** A load holds the lock across `runtime.start()`. Intentional — single heavy residency means concurrent heavy loads are never wanted. `status()` is lock-free.
- **Phase 1: new additive `core/errors.py` classes** — `ModelError`, `UnknownModelError`, `ModelFileMissingError` (carries `key`/`path`), `RuntimeStartError`, `NoFreePortError`, `AcquireTimeoutError`. `errors.py` is not a frozen contract.
- **Phase 1: INV-1 test implemented as a static import scan now** (not the phase it was pencilled for). The dynamic "API process never loads a model" check waits for `api/`.

---

## 6. Blockers

Things that are broken or unfinished and need attention. Include the file and the symptom.

- `make check-all` currently errors: no `tests/integration/` directory yet (arrives Phase 2/3). `make check` does not touch it, so this is not blocking Phase 0/1.
- `runtime_llama.py` is unverified against a real binary — `llama-server` is not installed. argv construction has a fast test; the real boot/health/stop path has only `@pytest.mark.slow` tests that skip (`shutil.which("llama-server") is None`). Install `llama-server` + a GGUF before trusting the real path (Phase 2 real-model DoD, Phase 8 selfcheck).
- `configs/models.yaml` `active_profile: laptop-16gb` points at model paths that do not exist. `Registry.from_config(config, verify=True)` on the default profile raises `ModelFileMissingError`. `models status` avoids this (constructs stub-safe); Phase 2+ callers and selfcheck must select `test-stub` or pass `verify=False` deliberately until models are fetched.

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
| `asyncio.Condition()` outside a running loop | constructs fine on 3.11 (used in sync CLI path) | 2026-09-06 |
| Stub runtime child | `python -m rupantar.models.runtime_stub --port N`, stdlib `http.server`, real PID, SIGKILL grace 3s | 2026-09-06 |
| Phase 1 test suite | no stray `runtime_stub`/`llama-server` procs after run; ports 8100–8199 clean | 2026-09-06 |
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

### 2026-09-06 — Phase 1 — Model Manager shipped, INV-1/2/7/8 real and green
Did:
- Built `src/rupantar/models/`: `runtime_base.py` (Runtime ABC, `terminate_process` SIGTERM→grace→SIGKILL, `wait_healthy`, `read_rss_bytes`), `_ports.py` (bind-test allocator), `runtime_stub.py` (child stdlib `http.server`, `python -m` entrypoint — zero model files), `registry.py` (`ModelEntry` + `Registry.from_config`; skips file/SHA when `runtime == "stub"`; real missing → `ModelFileMissingError` naming `scripts/fetch_models.sh`), `_support.py` (Lease/Event/ModelState/sinks), `manager.py` (async `acquire()` CM + `obtain/release`, refcount, one `asyncio.Condition` serialising load/evict/reap, `max_heavy_resident` eviction that waits for real process exit via `wait_process_gone`, LRU + idle-TTL reaper, external-death respawn, `status()`), `runtime_llama.py` (SIGKILL grace 10s; real-binary tests `@pytest.mark.slow`).
- `core/errors.py`: +`ModelError`/`UnknownModelError`/`ModelFileMissingError`/`RuntimeStartError`/`NoFreePortError`/`AcquireTimeoutError` (additive).
- `core/store.py`: +`events` table + `append_event`/`list_events`.
- `cli/main.py`: `models status` prints the residency table (deviation: not the planned `api/routes/models.py`).
- Made INV-2 (`test_single_resident`), INV-7 (`test_single_entry_point`), INV-8 (`test_unload_kills_process`) real. Also implemented INV-1 (`test_no_inprocess_models`) as a module-scope import scan (was a lying skip skeleton).
- Ran builder → verifier (PASS w/ warnings) → arch-guard (CLEAN).
Verified:
- `make check` → ruff ✓, format ✓ (38 files), mypy ✓ (18 files), `pytest tests/unit` → 84 passed / 1 slow-skip, `pytest tests/inv` → 6 passed / 4 skeleton
- Phase 1 verify `pytest tests/inv/test_single_resident.py tests/inv/test_unload_kills_process.py -q` → 2 passed
- `pytest -m slow` → 1 skipped (llama-server absent), 0 errors
- zero `.gguf`/`.onnx` on disk; no stray child procs; `models status` → 4-row table; `--help` → 4 commands
- `core/schemas.py` + `core/artefacts.py` untouched
Changed in this file:
- §1 phase→2, commit, check counts. §2 Phase 1 → DONE with build summary; §2 Phase 2 note (HTTP client gap). §3 INV-1/2/7/8 → PASS with method. §5 +7 deviations. §6 +2 blockers (llama unverified, laptop-16gb paths absent). §8 +3 env facts. §9 this block.
Next session should start with:
- Phase 2 — Text generation path. First decision: HTTP client for `models/client.py` (httpx vs stdlib `urllib`+`asyncio.to_thread`) — Phase 1 added no HTTP dep. Record the choice in §10 + `requirements.txt` if httpx. Use `test-stub` profile / stub runtime for all non-slow tests.

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
- **Phase 1 added no dependency** — Model Manager is stdlib only (`asyncio`, `subprocess`, `http.server`, `urllib`, `socket`, `signal`, `os`). Phase 2's `models/client.py` is the first place an HTTP client may be needed.
