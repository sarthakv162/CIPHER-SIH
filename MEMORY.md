# MEMORY.md — Rupantar project memory

> **Read this file at the start of every session, before touching any code.**
> **Update it at the end of every session, before you stop.**
> Keep it under 300 lines. When a section grows past its cap, compress the oldest entries into one summary line.
> This file is append-and-compress, not append-forever. Stale detail is worse than no detail.

---

## 1. Project state

| Field | Value |
|---|---|
| Current phase | **4 — Renderers (not started)** |
| Last session | 2026-09-06 — perf session (7-artefact 765 s → `-ngl 99` + `--parallel 1` fix) |
| Last commit | `perf: fix -ngl 0 CPU-only + pin --parallel 1` |
| `make check` status | **green** (ruff + format + mypy 33 files + 106 unit + 9 inv / 3 inv skeleton; slow lane `pytest -m slow` → 3 pass, ~14 min on loaded box) |
| Active hardware profile | `laptop-16gb` |
| Models present on disk | **brain** only — `models/brain/Qwen3-4B-Instruct-2507-Q4_K_M.gguf` (2.5 GB, sha `3605803b…`); vlm/asr/tts absent |
| Python | 3.11.15, uv-managed, `.venv/`, pinned in `.python-version` |

---

## 2. Phase ledger

Mark each phase `TODO` / `IN PROGRESS` / `DONE (date)`. Add one line on what actually shipped.

| Phase | Status | Notes |
|---|---|---|
| 0 — Scaffold and contracts | **DONE (2026-09-06)** | Package, frozen `core/schemas.py` + `core/artefacts.py` (7 artefacts, all validators), async `core/store.py`, minimal `core/config.py`, `core/errors.py`, Typer CLI stubs (4 commands), 8 inv skip-skeletons, fixtures (2 articles, image, 30s clip, 7 artefact JSONs). `make check` green. |
| 1 — Model Manager | **DONE (2026-09-06)** | `models/` package: `runtime_base.py` (ABC + SIGTERM→SIGKILL `terminate_process`, `wait_healthy`, `read_rss_bytes` via `ps`), `_ports.py`, `runtime_stub.py` (child `python -m` stdlib `http.server`, zero model files), `registry.py` (skips file/SHA for `runtime == "stub"`; real missing file → `ModelFileMissingError` naming `scripts/fetch_models.sh`), `_support.py` (Lease/Event/state), `manager.py` (async `acquire()` CM + `obtain/release`, refcount, single `asyncio.Condition` serialises load/evict/reap, `max_heavy_resident` eviction waits for real process exit, LRU + idle-TTL reaper, external-death respawn, `status()`), `runtime_llama.py` (untested vs real binary, `@pytest.mark.slow`). Events → new `events` table in `store.py`. `models status` CLI (not the API route — see Deviations). INV-1/2/7/8 tests real and green. |
| 2 — Text generation path | **DONE (2026-09-06)** | `models/client.py` (async **httpx** `/v1/chat/completions`, GBNF `grammar` passthrough, SSE `stream()`, retry-once on conn reset, `ModelClientError` on 4xx/5xx). `agents/base.py` (`ArtefactAgent`; `SHARED_PREAMBLE`+dossier in the **system** turn, agent/param text in the **user** turn — prefix-cache design; `string.Template` params; `response_format: json_schema` built once in `__post_init__`; validate → retry-once appending the error as new turns → `AgentError`). *[`agents/grammar.py` was built here then deleted 2026-09-06 — see §5/§9.]* `agents/loader.py` (dotted `module:Class` schema import). `orchestrator/runner.py` `run_single` (minimal 1-`TextBlock` dossier, `acquire`→client→agent→write `data/outputs/<job_id>/<type>.json`; `AgentError` → FAILED job, never raises out; no manifest — Phase 4). `configs/agents/executive_summary.yaml`. Real `cli transform --text FILE --output … [--profile] [--stream/--no-stream] [--out-dir]`. INV-6 real. `runtime_stub.py` now OpenAI-compatible (canned via `RUPANTAR_STUB_COMPLETION`). Real path measured: exec summary in ~53 s on laptop-16gb (DoD < 90 s). |
| 3 — All artefact agents | **DONE (2026-09-06)** | 6 more `configs/agents/*.yaml` (advisory/linkedin_post/x_thread/presentation/infographic_spec/video_package, all `model_key: brain`). `orchestrator/planner.py` (`plan()` → 1 Job/output-type, mints `transform_id`, records `video_package`→`executive_summary` `depends_on` when both requested). `orchestrator/scheduler.py` (`schedule()` pure: modality rank `vlm 0 < asr 1 < brain 2 < unknown 3-alpha`, stable in group, topological pass lets `depends_on` override). `orchestrator/runner.py` split `prepare()` (plan+persist PENDING+dossier) / `execute()` (load+schedule+run) / `run_batch` = both; `run_single` wraps it; one `manager.acquire()` per maximal consecutive same-`model_key` run. `runtime_stub.py` gained directory mode (returns `<dir>/<response_format.json_schema.name>.json`). `cli transform` batches. `api/` package: `app.py` `create_app()` (lifespan owns one `ModelManager`+`Store`+agents, no prewarm), routes `POST/GET /transforms`, `GET /transforms/{id}/artefacts`, `GET /jobs/{id}`, `GET/POST /models*`, `GET /health`; `POST /transforms` → 202 + background `asyncio.create_task(execute(...))`. INV-1 dynamic check real. **Real 7-artefact run: 765 s wall (loaded box), exactly 1 brain load, all 7 schema-valid.** |
| 4 — Renderers | TODO | Next. `render/{markdown,docx_render,pptx_render,pdf_render,svg_render,subtitle}.py` + `audit/provenance.py`. INV-3 (lazy heavy imports — python-docx/pptx/reportlab/jinja **inside** functions) and INV-5 (`.manifest.json` sibling per artefact write) go real here. `runner._write_artefact` currently writes bare JSON with no manifest — that changes. |
| 5 — Parivartan converters | TODO | Adds fixtures: messy CSV, Sigma rule, CEF log. |
| 6 — Multimodal ingestion | TODO | Adds fixture: advisory PDF. en-only ASR/TTS → `language_limitation` manifest warning. |
| 7 — Video assembly | TODO | |
| 8 — Air-gap, audit, selfcheck | TODO | selfcheck asserts `sys.version_info[:2] == (3, 11)`. |
| 9 — Frontend | DEFERRED | Do not start without a PLAN.md update |

---

## 3. Invariant status

| ID | Invariant | Test | Status |
|---|---|---|---|
| INV-1 | No in-process model loads | `tests/inv/test_no_inprocess_models.py` | **PASS** — (1) AST scan: no module-scope import of torch/transformers/llama_cpp/ctranslate2/faster_whisper/onnxruntime under `src/`. (2) **dynamic (Phase 3):** a full 7-artefact transform driven through the API `TestClient` leaves all those modules out of `sys.modules`. |
| INV-2 | ≤1 heavy model resident | `tests/inv/test_single_resident.py` | **PASS** — event-stream replay over brain→vlm→brain swaps (stub runtime) proves never two heavy READY; + live `os.kill(pid,0)` probes prove old process dead before new alive. |
| INV-3 | Lazy heavy imports | `tests/inv/test_lazy_imports.py` | skip-skeleton (phase 4) |
| INV-4 | No non-loopback egress | `tests/inv/test_no_egress.py` | skip-skeleton (phase 8); grep clean |
| INV-5 | Provenance manifest per artefact | `tests/inv/test_provenance.py` | skip-skeleton (phase 4) |
| INV-6 | Schema-validated model output | `tests/inv/test_validated_outputs.py` | **PASS** — valid stub completion → `ExecutiveSummary` instance; invalid JSON → `AgentError`, never returned unvalidated. `ArtefactAgent.run` gates every return on `schema.model_validate`. |
| INV-7 | Single model-start entry point | `tests/inv/test_single_entry_point.py` | **PASS** — regex scan: `subprocess`/`Popen`/`os.spawn`/`create_subprocess_*`/`multiprocessing` only in `models/runtime_*.py`; `ModelManager.acquire`/`obtain` present. |
| INV-8 | Unload = process kill | `tests/inv/test_unload_kills_process.py` | **PASS** — acquire stub, `os.kill(pid,0)` ok, evict, poll to `ProcessLookupError`; `EVICT_DONE` event carries the dead pid. |

INV-1/2/6/7/8 are real assertions run in `make check`. INV-3/4/5 are still `pytest.skip("implemented in phase N")` skeletons (green as skipped).

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
- Enums are plain `enum.Enum` (not `StrEnum`/`str,Enum`) — see Deviations. Phase-0 Deviation-1 (GBNF string identity) is **moot**: hand-rolled GBNF was dropped 2026-09-06 (see below); `model_json_schema()` emits correct string enums for llama-server's own converter.
- **Schema enforcement = llama-server native `response_format: json_schema`** (decided 2026-09-06 after benchmarking — GBNF / json_object / json_schema / unconstrained all the same speed). Built once per agent in `ArtefactAgent.__post_init__` from `schema.model_json_schema()`. `agents/grammar.py` deleted. Pydantic count/length `field_validator`s are still only enforced by `model_validate` + retry-once in `base.py`.
- HTTP client is **httpx** (async). Chosen Phase 2; FastAPI pulls it in at Phase 3 anyway. Imported at module top only in `models/client.py`, like `aiosqlite` in `store.py` — not an INV-3 concern. `LlamaClient.complete/stream` pass through both `grammar` (unused now) and `response_format`.
- **Agent prompt layout:** identical `SHARED_PREAMBLE` + source dossier go in the **system** turn; all agent- and param-specific text goes last, in the **user** turn. This keeps the long dossier as a byte-identical prefix so llama-server prefix caching spares agents 2–7 the re-eval. Retry turns are appended, never spliced into the first user message.

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
- **Phase 2: Deviation-1 (plain `enum.Enum` → GBNF) resolved with no contract change.** `model_json_schema()` emits `{"enum": [...], "type": "string"}` for a string-valued plain Enum and `{"const": "...", "type": "string"}` for a `Literal`. `agents/grammar.py` checks `enum`/`const` before `type` and emits an alternation of exact double-quoted JSON literals, so identity holds regardless.
- **Phase 2: agent validation-retry appends new `assistant`+`user` turns** instead of editing the first user message — keeps the dossier prefix byte-identical for llama-server prefix caching.
- **Phase 2: `runtime_stub.py` extended to speak `/v1/chat/completions`** (OpenAI envelope; canned content from `RUPANTAR_STUB_COMPLETION` = literal or `@file`, else echoes the last user message; SSE frames on `stream`). Not frozen. `tests/unit/test_runtime_stub.py` updated to the new POST shape.
- **Phase 2: real llama-server boot test moved** from `tests/unit/test_runtime_llama.py` (where it was an unconditional `pytest.skip` lie) to `tests/integration/test_runtime_llama_real.py` (`@pytest.mark.slow` + `skipif` on binary/GGUF). Keeps `make check` model-free; it now boots a real server, health-checks, SIGTERMs, asserts the pid is gone.
- **Phase 2: `transform`/`run_single` use `Registry.from_config(verify=False)`** to skip the 2.5 GB startup SHA-256; `llama-server` still fails loudly if the GGUF is missing.
- ~~Phase 2: `--n-gpu-layers` left at 0 for `laptop-16gb` (thought a no-op)~~ **WRONG — reverted 2026-09-06 perf session.** `-ngl 0` forces CPU-only (~2× slower). `models.yaml` laptop-16gb brain+vlm now `-ngl 99 --parallel 1`; all profiles pin `--parallel 1`. See §7 / §8 / §9.
- **Post-Phase-2 (2026-09-06): hand-rolled `agents/grammar.py` + `tests/unit/test_grammar.py` deleted**, replaced by `response_format: json_schema`. Benchmark showed no speed difference between GBNF, json_object, json_schema, and no constraint (see §9). `docs/SCHEMAS.md` line about "GBNF grammar generated from its JSON Schema" edited to name `response_format: json_schema` instead — a mechanism note in the locked doc, no field/model/bound changed. `PLAN.md` Phase 2 build list updated.
- **Phase 3: `orchestrator/runner.py` split `prepare()` / `execute()` / `run_batch`.** PLAN's Phase 2 named only `runner.py` (single-job); the API needs a two-phase entry (persist PENDING → return 202 → run in background). `prepare()` validates the source path *before* persisting anything (old `run_single` persisted the job first). `run_single`/`run_batch` behaviour unchanged.
- **Phase 3: `planner.plan()` mints the `transform_id` itself** (no `transform_id` param); `execute()` rebuilds dossier text from the stored `TransformRequest` (there is no transform→dossier id link in `store.py` — PLAN allowed either).
- **Phase 3: `POST /transforms` runs the batch in a background `asyncio.create_task`** (task held in `app.state.tasks`, done-callback logs `.exception()`), returns 202 + `transform_id`. `GET /transforms/{id}` polls. Synchronous would block for minutes on a real run. `api/routes/*` response models (`TransformAccepted` etc.) are local to the route module — `schemas.py` stays frozen.
- **Phase 3: `api/app.py` does NOT prewarm** despite `policy.yaml:prewarm_on_startup: brain` — auto-spawning llama-server on startup breaks `TestClient`. Carries a `# TODO(phase-8)`.
- **Phase 3: `fastapi` pinned `>=0.115,<0.128`** — starlette ≥1.6 (pulled by fastapi ≥0.128) deprecates `httpx` for `TestClient` in favour of `httpx2`. Pin lands fastapi 0.127.1 / starlette 0.50.0, clean with httpx 0.28.
- **Phase 3: `runtime_stub.py` directory mode.** `RUPANTAR_STUB_COMPLETION` naming a dir → stub returns `<dir>/<response_format.json_schema.name>.json`. Lets one stub serve all 7 artefact fixtures in a batch. Not frozen.

---

## 6. Blockers

Things that are broken or unfinished and need attention. Include the file and the symptom.

- **RESOLVED (Phase 2):** `runtime_llama.py` real path is now verified — `tests/integration/test_runtime_llama_real.py` (slow) boots a real `llama-server` on the brain GGUF, health-checks, SIGTERMs, and asserts the pid is gone. Real end-to-end text path also exercised by `tests/integration/test_text_path_real.py`.
- `configs/models.yaml` `laptop-16gb`: **brain is present**; `vlm`, `asr`, `tts` files are still absent, so `Registry.from_config(verify=True)` on the full profile still raises `ModelFileMissingError` (on `vlm`). `models status`, `transform`, and `run_single` use `verify=False`. Fetch vlm/asr/tts before Phase 6.
- `make check-all` runs `pytest tests/integration` with **no `-m "not slow"` filter**, so on a machine with the brain GGUF it executes **3** real-model tests (`test_text_path_real`, `test_multi_artefact_real`, `test_runtime_llama_real`) — ~15–16 min on the loaded dev box (the 7-artefact one alone is ~13 min). `make check` (the phase gate) stays fast and model-free. See Open Questions.
- `requirements-lock.txt` is still an empty placeholder. `httpx`, `fastapi`, `uvicorn`, `starlette` + transitives must be captured by `scripts/vendor_wheels.sh` before air-gapping.

---

## 7. Open questions for the human

Decisions you could not make on your own. Do not guess — list them here and continue with the safest default.

- Exact GGUF builds and quantisation for `brain` and `vlm` on the demo laptop, **and the laptop's OS/arch** (needed for `requirements-lock.txt` / wheel vendoring — the dev machine is macOS arm64, the demo laptop may not be). Needs a one-time online fetch + benchmark.
- Which three cyber formats matter most to the evaluators for Parivartan. Current default: IOC CSV ↔ STIX 2.1, Sigma YAML → JSON, CEF/syslog → JSONL.
- Whether the recorded demo video uses the `laptop-16gb` or `titan-24gb` profile.
- `GenerationParams.language`: field kept, brain honours it best-effort; ASR/TTS are en-only and emit a `language_limitation` manifest warning (Phase 6). Tested values `en`, `hi`; others accepted as best-effort. Confirm `hi` is actually a demo requirement.
- Should `make check-all` deselect `-m slow`? It currently runs the real-model integration tests when models are on disk. Fixing it touches the `Makefile` **and** `PLAN.md` §7 (the single shared `make check` / `check-all` definition) and `CLAUDE.md`. Left as-is for now; `make check` itself is unaffected.
- ~~Schema-enforcement mechanism~~ **RESOLVED 2026-09-06.** Human chose native `response_format: json_schema`; `agents/grammar.py` deleted. See §4 / §5 / §9. Speed was a wash across all options; the call was made on maintenance + guarantee strength for the 6 remaining Phase 3 schemas.
- **Untested for Phase 3:** unconstrained/constrained *validation failure rate* was only measured for `ExecutiveSummary` (0/32). Advisory / Presentation / VideoPackage are structurally harder (nested models, enums, int fields). If the retry-once path fires often on those, revisit temperature or prompt, not the constraint mechanism.
- ~~7-artefact run is 765 s~~ **RESOLVED 2026-09-06 (perf session).** Root cause: `models.yaml` `--n-gpu-layers 0` (CPU-only) + that test running on a heavily-loaded dev box. Pipeline itself is efficient (0.7 s dead time, prefix cache works, 18 s total prompt-eval). Fixed `-ngl 0 → 99` + `--parallel 1`. Projected with the fix: loaded box ~320 s / demo-4 ~167 s; a quiet demo machine at ~25–35 tok/s → 7 in ~140–180 s, demo-4 in ~70–90 s. **The real demo hardware, measured quiet, is the remaining unknown** — if demo-4 is still >90 s there, tighten the `advisory`/`presentation`/`video_package` prompts for brevity (they currently emit 668/815/903 tok; caps are 2400/2600/2600 so lowering caps alone won't help — the prompt must ask for concision). `--threads` (6 of 6P+4E cores) also untested on quiet HW.

---

## 8. Environment facts learned

Measured, not assumed. Update whenever you measure something new.

| Fact | Value | Measured on |
|---|---|---|
| Dev machine | macOS 15.3 (Darwin 25.3), Apple Silicon, 16 GB RAM — matches target profile | 2026-09-06 |
| Python | 3.11.15 (uv-managed), `.venv/` | 2026-09-06 |
| `uv` version | 0.11.29 | 2026-09-06 |
| `ffmpeg` version | 8.1.2 (`/opt/homebrew/bin/ffmpeg`) | 2026-09-06 |
| `llama-server` on PATH | **present** — v0.4.0 build 10809 (AppleClang, Darwin arm64, Metal), `/opt/homebrew/bin/llama-server` | 2026-09-06 |
| `piper` on PATH | **absent** — needed Phase 7 | 2026-09-06 |
| `git` version | 2.51.2 | 2026-09-06 |
| `asyncio.Condition()` outside a running loop | constructs fine on 3.11 (used in sync CLI path) | 2026-09-06 |
| Stub runtime child | `python -m rupantar.models.runtime_stub --port N`, stdlib `http.server`, real PID, SIGKILL grace 3s | 2026-09-06 |
| Phase 1 test suite | no stray `runtime_stub`/`llama-server` procs after run; ports 8100–8199 clean | 2026-09-06 |
| Free RAM | ~1 GB free+inactive under load (not a clean idle measure) | 2026-09-06 |
| brain GGUF | `models/brain/Qwen3-4B-Instruct-2507-Q4_K_M.gguf`, 2 497 281 120 B, sha256 `3605803b982cb64aead44f6c1b2ae36e3acdb41d8e46c8a94c6533bc4c67e597` | 2026-09-06 |
| brain llama-server boot → healthy | ~7.5 s first, ~4.0 s warm (GGUF page-cache hot; no true cold-disk figure — `purge` needs sudo) | 2026-09-06 |
| brain prompt eval | ~40 tok/s (752-tok dossier prompt); with `cache_prompt` a repeat prompt is ~0 | 2026-09-06 |
| brain generation — **constraint mechanism is NOT the cost** | GBNF, `response_format:json_object`, `response_format:json_schema`, and *no constraint* all measured **within noise of each other** (see grammar-investigation block in §9). Interleaved: 6.9 / 6.9 / 6.9 tok/s. First (staggered) run: 6.6 / 7.7 / 7.8 / 7.2. GBNF is at most ~10 % slower; json_schema == unconstrained. | 2026-09-06 |
| brain generation, absolute tok/s | **swings 2–3× with machine load** — 17 tok/s (single gen, quieter moment) down to ~7 tok/s (sustained, dev box running node/vite servers + a 54 %-CPU `python@3.14`). `llama-bench` (synthetic, tiny prompt) ~37 tok/s. **Re-measure on the real demo hardware, quiet.** | 2026-09-06 |
| artefact JSON validity, real brain | `ExecutiveSummary`: 0 failures in 32 runs incl. unconstrained. **All 7 artefact types validated first try** in the Phase 3 real run (Advisory/Presentation/VideoPackage included), `response_format:json_schema`, temp 0.3–0.45. | 2026-09-06 |
| One `executive_summary` end-to-end (CLI, laptop-16gb) | ~53 s wall morning; ~70–103 s under later dev-box load. DoD is < 90 s — re-measure quiet. | 2026-09-06 |
| **All 7 artefacts, one request, real brain** | **765 s wall** (`test_multi_artefact_real`, heavily loaded box), **exactly 1 brain `LOAD_START`**, 0 evict/reload, all 7 schema-valid. ~9 K generated tokens total. On quiet demo HW expect materially less; still the number to beat for the demo. | 2026-09-06 |
| `fastapi` / `starlette` / `uvicorn` | 0.127.1 / 0.50.0 / 0.52.4 (pin `fastapi>=0.115,<0.128` — see §5) | 2026-09-06 |
| `--n-gpu-layers` on Apple Silicon — **`-ngl 0` was a real mistake** | `-ngl 0` forces CPU-only: **~7 tok/s gen, ~21 tok/s prompt-eval, 6.6 s boot**. `-ngl 99` (or the flag unset) → Metal: **~13 tok/s gen, ~125 tok/s prompt-eval, 1.5–2 s boot**. ~1.9× / ~6× / ~3×. The earlier "36.6 vs 36.8, no difference" compared `-ngl 99` vs *unset* (both Metal) — `-ngl 0` was never tested. `models.yaml` fixed to `-ngl 99` for laptop-16gb brain+vlm (2026-09-06). | 2026-09-06 |
| `--parallel N` default | `-1` = auto → **4 slots**, each capped at `ctx/4` = 2048 tok (would overflow a real multimodal dossier). Running the 7 agents concurrently across 4 slots gave only ~20 % wall improvement (290 s vs 363 s) at 3× worse per-artefact latency (4–8 vs 13 tok/s) and cache loss on ~3 agents. `models.yaml` now pins `--parallel 1`: one slot, full 8192 ctx, perfect prefix reuse, low latency. | 2026-09-06 |
| 7-artefact run, per-agent (Metal, `--parallel 1`, `ai_policy_brief.md`, loaded box ~13 tok/s) | prompt/gen tokens: exec 752/506, advisory 345/668, linkedin 214/467, x_thread 196/328, presentation 242/815, infographic 282/442, video 273/903. cache hit ≈ 556 tok for agents 2–7. **Total gen ≈ 306 s, prompt-eval ≈ 18 s, dead time 0.7 s, wall ≈ 324 s.** ~4130 generated tokens total; demo-4 subset ≈ 2000 tok / ~167 s. | 2026-09-06 |
| llama-server prefix caching | per-slot; `cache_prompt: true` reuses the longest common token prefix across requests to the same slot. Agents put the identical dossier first so agents 2–7 skip re-evaluating it. | 2026-09-06 |
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

### 2026-09-06 — Perf session — the 765 s 7-artefact run (pre-Phase-4)
Instrumented a full 7-agent run (raw httpx, full llama-server `timings`), tested concurrency and `--n-gpu-layers`.
Findings:
- **`--n-gpu-layers 0` in `models.yaml` was forcing CPU-only.** `-ngl 0` ≈ 7 tok/s; `-ngl 99`/unset (Metal) ≈ 13 tok/s + 6× faster prompt-eval + 3× faster boot. The Phase 3 765 s run went through `ModelManager` → those args → CPU. The old "no difference" note compared `-ngl 99` vs unset, never `-ngl 0`.
- **Pipeline is not scaling badly.** Instrumented (Metal): total gen 306 s, prompt-eval 18 s, dead time 0.7 s, wall 324 s. Prefix cache works (agents 2–7 hit ~556 cached tok). 765 vs 324 was ~all machine load (7 vs 13 tok/s on a contended box).
- **Concurrency across the 4 auto-slots doesn't help here** — CPU-bound at 6 threads, ~20 % wall gain for 3× worse per-artefact latency + cache loss. `--parallel 1` is better (full ctx, perfect cache).
- 4-variant enforcement table (GBNF/json_object/json_schema/none): all ~7 tok/s, 8/8 valid, **0 unconstrained failures** — no fences, no retries. (ExecutiveSummary only.)
Did: `models.yaml` — laptop-16gb brain+vlm `-ngl 0/none → -ngl 99 --parallel 1`; titan brain+vlm `+--parallel 1`. Updated `brain.notes`. `make check` still green (config-only change). Benchmark scripts in scratchpad (not committed).
Recommendation to human: land the config fix; **measure a clean 7-artefact + demo-4 run on the actual demo laptop, quiet**, before deciding on prompt-brevity edits. Targets (7 < 240 s, demo-4 < 90 s) are plausible on quiet HW with the fix alone.
Next: Phase 4 (renderers) — unless the human wants prompt-brevity work first.

### 2026-09-06 — Phase 3 — artefact agents + orchestration + `api/` shipped
Did (two builder subagents + lead coordination):
- **Part 1:** 6 agent configs (advisory/linkedin_post/x_thread/presentation/infographic_spec/video_package); `orchestrator/planner.py` + `orchestrator/scheduler.py`; `runner.py` → `prepare`/`execute`/`run_batch` split with one `manager.acquire()` per consecutive same-`model_key` run; `runtime_stub.py` directory mode; `cli transform` batches.
- **Part 2:** `src/rupantar/api/` — `app.py` `create_app()` + lifespan (one `ModelManager`+`Store`+agents, no prewarm), routes `transforms`/`jobs`/`models`/`health`; `POST /transforms` → 202 + background task. INV-1 dynamic check added to `tests/inv/test_no_inprocess_models.py`.
- Lead: added `fastapi>=0.115,<0.128` + `uvicorn>=0.30` (pinned below starlette 1.6 for clean `TestClient`); ran verifier (PASS w/ warnings) + arch-guard (CLEAN).
Verified:
- `make check` → ruff ✓, format ✓ (65 files), mypy ✓ (33 files), `pytest tests/unit` → 106 passed, `pytest tests/inv` → 9 passed / 3 skeleton
- Phase 3 verify `pytest tests/integration/test_multi_artefact.py -q` → 2 passed
- `pytest tests/integration` → 11 passed (~16 min, runs the 3 slow real-model tests too)
- `pytest -m slow` → 3 passed; **`test_multi_artefact_real`: 765 s wall, 1 brain `LOAD_START`, all 7 schema-valid**
- `create_app()` on the real profile → no model spawned, no runtime modules imported
- no stray `llama-server`/`runtime_stub` procs
Changed in this file:
- §1 phase→4, commit, counts. §2 Phase 3 → DONE + Phase 4 note. §3 INV-1 → +dynamic check. §5 +7 Phase-3 deviations. §8 +3 rows (7-artefact wall, all-schemas-valid, fastapi versions). §9 this block. §10 +fastapi/uvicorn.
Next session should start with:
- Phase 4 — Renderers. `render/{markdown,docx_render,pptx_render,pdf_render,svg_render,subtitle}.py` + `audit/provenance.py`. INV-3 (heavy imports INSIDE functions) + INV-5 (`.manifest.json` sibling per write) go real. `runner._write_artefact` must start emitting manifests. New deps: python-docx, python-pptx, reportlab (or fpdf2), jinja2 — record each.

### 2026-09-06 — Investigation — GBNF sampling cost (pre-Phase-3)
Premise to test: "GBNF is costing >half our throughput (37→17 tok/s), ×7 in Phase 3."
Method: `executive_summary` agent, `ai_policy_brief.md`, one warm llama-server, raw httpx for full `timings`. Two runs: (1) 4 modes × 8 seeds staggered; (2) cold single-shot + 4 interleaved rounds × 3 modes. Each output run through `ExecutiveSummary.model_validate`. Scripts in scratchpad (not committed).
Findings:
- **The premise is wrong.** GBNF / `response_format:json_object` / `response_format:json_schema` / no-constraint all generate at the same tok/s. Interleaved: 6.9/6.9/6.9. Staggered: 6.6/7.7/7.8/7.2 (GBNF ran first/coolest and was still slowest → its ~10 % gap is real but tiny). `json_schema` output was **token-identical** to unconstrained for every seed — the constraint never fires.
- The 37→17→7 drop is **context size + sustained load + a busy dev box** (node/vite servers, a 54 %-CPU `python@3.14`), not grammar. Absolute tok/s here is unreliable; must be re-measured on quiet demo hardware.
- **0 validation failures in 32 runs**, unconstrained included, for `ExecutiveSummary`. Retry-once path would rarely fire for this schema.
- Generated GBNF for `ExecutiveSummary` inspected: 11 rules, 1079 chars, canonical JSON `string` rule, no unbounded-alternation traps. Our GBNF does **not** encode the Pydantic count validators (`key_points` 3–6 etc.) — neither would `json_schema` as generated from the frozen models (bounds live in `field_validator`s, not `Field(...)`).
- Noted but not changed: `agents/base.py` calls `gbnf_for(self.schema)` once per `run()` (per artefact), not cached on the agent. Cheap (~1 ms) but should be memoised whichever mechanism wins.
Decision (human, same day): **switch to native `response_format: json_schema`.** Done in a follow-up commit — `agents/grammar.py` + `test_grammar.py` deleted; `ArtefactAgent.__post_init__` builds the `json_schema` constraint once from `schema.model_json_schema()`; `LlamaClient.complete/stream` gained a `response_format` param (kept `grammar` too). `make check` green (103 unit + 8 inv / 3 skeleton). Real-brain `test_text_path_real.py` passes on the json_schema path (~115 s, loaded box). `PLAN.md` Phase 2 + `docs/SCHEMAS.md` mechanism line updated.
Also did: fixed the stale `sample_article.txt` → `--text tests/fixtures/articles/ai_policy_brief.md` in `PLAN.md` §8 demo path.
Next: start Phase 3 (6 more agent configs + planner + scheduler + api/).

### 2026-09-06 — Phase 2 — Text generation path shipped, INV-6 real, real brain measured
Did:
- Recorded the two benchmark notes from the human (`--n-gpu-layers` no-op on Apple Silicon; llama-server prefix caching → dossier-first prompt design).
- Repointed `configs/models.yaml` `laptop-16gb.brain` at the real GGUF (`Qwen3-4B-Instruct-2507-Q4_K_M.gguf`), added `sha256:` + real `approx_bytes`; updated `tests/unit/test_registry.py` for the new filename.
- Chose **httpx** as the HTTP client; added to `requirements.txt` + `pyproject.toml`; installed in `.venv` (0.28.1).
- Builder subagent built Phase 2: `models/client.py`, `agents/{grammar,base,loader}.py`, `orchestrator/runner.py`, `configs/agents/executive_summary.yaml`, real `cli transform`, OpenAI-compatible `runtime_stub.py`, `core/errors.py` +`ModelClientError`/`AgentError`, INV-6 made a real assertion.
- Moved the real llama-server boot test out of `tests/unit/` (was a lying unconditional skip) into `tests/integration/test_runtime_llama_real.py` (slow) — now a genuine boot→health→SIGTERM→pid-gone assertion. Keeps `make check` model-free.
- Ran builder → verifier (PASS w/ warnings) → arch-guard (CLEAN). Ran a real-brain benchmark + timed CLI run.
Verified:
- `make check` → ruff ✓, format ✓ (53 files), mypy ✓ (25 files), `pytest tests/unit tests/inv` → 107 passed / 3 inv skeleton, model-free, 15.9 s
- Phase 2 verify `pytest tests/integration/test_text_path.py -q` → 2 passed (stub, zero model files)
- `pytest -m slow -q` → 2 passed / 112 deselected, 52 s (real llama boot + real exec summary); no stray `llama-server`/`runtime_stub` procs
- `transform --text tests/fixtures/articles/ai_policy_brief.md --output executive_summary` → 52.7 s wall, valid `ExecutiveSummary` JSON written to `data/outputs/<job_id>/`
Changed in this file:
- §1 phase→3, commit, check counts, brain on disk. §2 Phase 2 → DONE + Phase 3 note. §3 INV-6 → PASS. §4 +httpx / prompt-layout / Deviation-1-resolved decisions. §5 +7 Phase-2 deviations. §6 rewrote (llama real path resolved; brain present / vlm-asr-tts absent; check-all slow note; lock file). §7 +2 open questions. §8 llama-server present + 8 measured rows. §9 this block. §10 httpx.
Next session should start with:
- Phase 3 — All artefact agents. `client.py`/`grammar.py`/`base.py`/`loader.py` already general; add the 6 remaining `configs/agents/*.yaml` + prompts, `orchestrator/{planner,scheduler}.py`, and the `api/` package (FastAPI + uvicorn land here). Assert: one 7-output request → exactly one `brain` load, zero reloads. Watch GBNF gen speed (~17 tok/s) for the multi-artefact wall time.

### 2026-09-06 — Phases 0 & 1 (compressed)
- **Phase 0** — scaffold + frozen contracts (`core/{schemas,artefacts,store,config,errors}.py`, Typer stubs, 8 inv skeletons, fixtures). Applied docs rulings A–O; repo housekeeping (`master`→`main`, dirs, `.venv` 3.11). `make check` green, 57 unit.
- **Phase 1** — `models/` package: `runtime_base` (Runtime ABC, SIGTERM→SIGKILL), `runtime_stub` (child stdlib http.server), `registry` (stub skips file/SHA), `manager` (`acquire()` CM, refcount, one `asyncio.Condition`, LRU+TTL reaper, single-heavy eviction, external-death respawn), `runtime_llama`. `core/errors.py` +6 model errors. `core/store.py` +`events` table. `models status` CLI (not the API route — deviation). INV-1/2/7/8 made real. builder→verifier→arch-guard. 84 unit / 6 inv.

---

## 10. Dependencies

Recorded per CLAUDE.md. Also in `requirements.txt` / `pyproject.toml`.

- **runtime** — `pydantic>=2.7`, `pydantic-settings>=2.2`, `PyYAML>=6.0`, `typer>=0.12`, `aiosqlite>=0.20`, `httpx>=0.27`, `fastapi>=0.115,<0.128`, `uvicorn>=0.30`
- **dev** (`[dev]` extra) — `ruff`, `mypy`, `pytest`, `pytest-asyncio`, `types-PyYAML`
- **Phase 1 added no dependency** — Model Manager is stdlib only.
- **Phase 2 added `httpx>=0.27`** (resolved 0.28.1; transitively `anyio`, `certifi`, `h11`, `httpcore`, `idna`, `sniffio`). Used only in `models/client.py`, imported at module top like `aiosqlite`.
- **Phase 3 added `fastapi>=0.115,<0.128`** (0.127.1; pulls `starlette` 0.50.0) **and `uvicorn>=0.30`** (0.52.4; pulls `click`). Upper pin: starlette ≥1.6 deprecates `httpx` for `TestClient`. Used only in `src/rupantar/api/`. Neither `httpx`, `fastapi`, `uvicorn`, `starlette` nor their transitives are yet in `requirements-lock.txt` — must be captured by `scripts/vendor_wheels.sh` before air-gapping (blocker §6).
