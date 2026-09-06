# MEMORY.md — Rupantar project memory

> **Read this file at the start of every session, before touching any code.**
> **Update it at the end of every session, before you stop.**
> Keep it under 300 lines. When a section grows past its cap, compress the oldest entries into one summary line.
> This file is append-and-compress, not append-forever. Stale detail is worse than no detail.

---

## 1. Project state

| Field | Value |
|---|---|
| Current phase | **8 — Air-gap, audit, selfcheck (IN PROGRESS)** |
| Last session | 2026-09-06 — piper 1.8 invocation fix + narrated video confirmed; starting Phase 8 |
| Last commit | `phase-7: video assembly + evidence model` |
| `make check` status | **green** (ruff + format + mypy 58 files + 190 unit + 12 inv / 1 inv skeleton; slow lane `pytest -m slow` → 4 pass, ~5 min) |
| Active hardware profile | **auto-detected** — `apple-metal` on this M4 Air. `RUPANTAR_PROFILE` overrides. |
| Models present on disk | **brain + vlm + asr + tts** (all four). vlm: `Qwen2.5-VL-3B-Instruct-Q4_K_M.gguf` (1.93 GB) + `mmproj-F16.gguf` (1.34 GB). asr: `models/asr/faster-whisper-small.en-int8/` (CT2 dir, `model.bin` 483 MB, sha `62b2a45b…`). tts: `models/tts/en_US-lessac-medium.onnx` (63 MB, sha `5efe09e6…`) + `.onnx.json`. |
| Python | 3.11.15, uv-managed, `.venv/`, pinned in `.python-version` |

---

## 2. Phase ledger

Mark each phase `TODO` / `IN PROGRESS` / `DONE (date)`. Add one line on what actually shipped.

| Phase | Status | Notes |
|---|---|---|
| 0 — Scaffold and contracts | **DONE (2026-09-06)** | Package + frozen `core/schemas.py` + `core/artefacts.py` (7 artefacts, all validators) + async `core/store.py` + `config.py`/`errors.py` + Typer stubs + 8 inv skeletons + fixtures. |
| 1 — Model Manager | **DONE (2026-09-06)** | `models/` — `runtime_base` (ABC, SIGTERM→SIGKILL), `runtime_stub` (child stdlib http.server), `registry` (stub skips file/SHA), `manager` (`acquire()` CM, refcount, one `asyncio.Condition`, LRU+TTL reaper, single-heavy eviction, external-death respawn), `runtime_llama`. `events` table. INV-1/2/7/8 real. |
| 2 — Text generation path | **DONE (2026-09-06)** | `models/client.py` (async httpx, SSE `stream()`, `response_format` + `grammar` passthrough, retry-once). `agents/base.py` `ArtefactAgent` (dossier-first prompt for prefix cache; `response_format: json_schema` built in `__post_init__`; validate → retry-once → `AgentError`). `agents/loader.py`. `orchestrator/runner.py` `run_single`. `executive_summary.yaml`. `runtime_stub` OpenAI-compatible. INV-6 real. *(`agents/grammar.py` built then deleted — see §5/§9.)* |
| 3 — All artefact agents | **DONE (2026-09-06)** | 6 more `configs/agents/*.yaml` (advisory/linkedin_post/x_thread/presentation/infographic_spec/video_package, all `model_key: brain`). `orchestrator/planner.py` (`plan()` → 1 Job/output-type, mints `transform_id`, records `video_package`→`executive_summary` `depends_on` when both requested). `orchestrator/scheduler.py` (`schedule()` pure: modality rank `vlm 0 < asr 1 < brain 2 < unknown 3-alpha`, stable in group, topological pass lets `depends_on` override). `orchestrator/runner.py` split `prepare()` (plan+persist PENDING+dossier) / `execute()` (load+schedule+run) / `run_batch` = both; `run_single` wraps it; one `manager.acquire()` per maximal consecutive same-`model_key` run. `runtime_stub.py` gained directory mode (returns `<dir>/<response_format.json_schema.name>.json`). `cli transform` batches. `api/` package: `app.py` `create_app()` (lifespan owns one `ModelManager`+`Store`+agents, no prewarm), routes `POST/GET /transforms`, `GET /transforms/{id}/artefacts`, `GET /jobs/{id}`, `GET/POST /models*`, `GET /health`; `POST /transforms` → 202 + background `asyncio.create_task(execute(...))`. INV-1 dynamic check real. **Real 7-artefact run: 765 s wall (loaded box), exactly 1 brain load, all 7 schema-valid.** |
| 4 — Renderers | **DONE (2026-09-06)** | `render/` — `base.py` (`FORMATS` map + `render(artefact, out_dir) -> list[Path]` dispatch on `(type, fmt)`, `RenderError` on unknown pair), `markdown.py` (all 7 types, pure f-strings), `docx_render.py` (advisory + exec_summary; classification banner, headings, footer), `pptx_render.py` (title + slide-per-`Slide` + speaker notes), `pdf_render.py` (advisory, **fpdf2**, `wrapmode=CHAR` for hex IOCs), `svg_render.py` (infographic, inline Jinja2 template), `subtitle.py` (`.srt` from video_package scenes). All heavy imports **inside** functions (INV-3). `audit/provenance.py` — `Manifest` model (14 fields) + `write_manifest()` → `<file>.manifest.json` sibling. `runner._run_job` now: validate → write `.json` → `render()` → `_emit_manifests()` for every file. `manager.model_meta(key)` + `ModelEntry.declared_sha256` (from yaml) feed the manifest; `ArtefactAgent.prompt_version` (yaml `prompt_version: "1"`). Format map: exec→md,docx · advisory→md,docx,pdf · linkedin/x_thread→md · presentation→md,pptx · infographic→md,svg · video→md,srt. INV-3 + INV-5 now real. |
| 5 — Parivartan converters | **DONE (2026-09-06)** | `parivartan/` — `registry.py` (`ConversionReport{src_format,dst_format,rows,warnings,output_path,duration_seconds,ok}`, `@register` bespoke dict, `list_conversions()`, `convert()` dispatch: missing input → report not raise · bespoke `(src,dst)` → registered fn · else general reader×writer · else `ConversionError`). `general.py` + `_readers.py` + `_writers.py` — **8×8 tabular matrix** (csv/tsv/json/jsonl/xlsx/xml/yaml/parquet) over `list[dict]`, first-seen-union column order, BOM/quoting/short-row-pad/long-row-`_extra_N`/blank-skip all handled, every reader `try/except` → `([], [warning])`. `cyber.py` — **ioc-csv ↔ stix21** (hand-built STIX 2.1 bundle JSON, no `stix2` lib — it pulls `requests`; stable `indicator--uuid5(value)` ids, fixed timestamp; `_pattern_for` per `IocType`), **sigma → sigma-json** (normalised keys, multi-doc → array), **cef → jsonl** (optional syslog prefix, escaped `\|`/`\=`, non-CEF line → `{_raw,_parse_error}` kept). `cli convert` (ext inference, `--from/--to/--out/--opt`). `api/routes/convert.py` — `GET /conversions`, `POST /convert`. INV-3 scan now covers `parivartan/`. Fixtures: `messy.csv`, `sigma_rule.yml`, `cef.log` + `clean.csv`/`iocs.csv` (round-trip test inputs). |
| 6 — Multimodal ingestion | **DONE (2026-09-06)** | `models/runtime_whisper.py` — `WhisperRuntime(Runtime)` + a stdlib-`http.server` worker (`python -m rupantar.models.runtime_whisper`); worker does `from faster_whisper import WhisperModel` **inside `_serve`**, `local_files_only=True`, serves `GET /health` + `POST /transcribe {audio_path}` → `{text, segments}`. `_support.default_runtime_factory` +`whisper` branch. `runtime_stub` +`POST /transcribe` (canned via `RUPANTAR_STUB_TRANSCRIPT`). `ingest/` — `text.py` (pdf/docx/html·selectolax/md/txt, all lazy imports, bad input → `("", [warning])` never raises), `image.py` (`caption_image` → base64 data-URL + `/v1/chat/completions` + json_schema `ImageInsight` + retry-once), `audio.py` (`transcribe` → POST worker), `video.py` (**scene-change keyframes** `select='gt(scene,0.3)'`, falls back to N evenly-spaced with a warning; `extract_audio` → 16 kHz mono wav), `dossier.py` `assemble_dossier` (**phase 1 text → phase 2 `acquire(vlm)` caption images+keyframes, release+evict → phase 3 `acquire(asr)` transcribe, release+evict** → `SourceDossier`; `language != "en"` + audio → `metadata["language_limitation"]`). `runner.execute()` calls it before the brain loop. INV-1 (whisper worker), INV-3 (`ingest/` scanned), INV-7 (ffmpeg exemption) all green. **Real vlm path verified (lead): caption → valid `ImageInsight`, 3.5 GB RSS, clean swap. Real asr + full swap/RSS test skips — asr model absent.** |
| 7 — Video assembly | **DONE (2026-09-06)** | `render/video_render.py` `render_video(artefact, path) -> list[Path]` (returns every file it writes → each manifested). Always: `storyboard.json` (scene timeline + `render_warnings`), `panel_NN.png` (1280×720, one/scene, Pillow — `import PIL` inside fn). If `piper` + tts onnx: `narration.wav`. If `ffmpeg`: `video_package.mp4` (panels @ scene durations, + narration audio, + subtitles — tries burn-in `subtitles` filter, falls back to a selectable `mov_text` track, falls back to none). Any tool failure → a `render_warnings` string + a `video_package.warnings.txt`; **never raises**. `render/base.py`: `_Renderer` may now return `list[Path]`; `FORMATS["video_package"] += ("video",)`. `render/subtitle.py` + `markdown.py` still produce `video_package.srt` + `.md` (the script). INV-3 (`PIL`), INV-7 (`render/video_render.py` `subprocess` exemption). **Plus the A/B/C evidence-model additions — see §5.** |
| 8 — Air-gap, audit, selfcheck | **NEXT** | selfcheck asserts `sys.version_info[:2] == (3, 11)`; +§4b HW/profile/offload consistency (see PLAN); egress monitor (`audit/egress.py`, INV-4 goes real); `scripts/{vendor_wheels,fetch_models,demo}.sh`; README online→air-gap→run. |
| 9 — Frontend | DEFERRED | Do not start without a PLAN.md update |

---

## 3. Invariant status

| ID | Invariant | Test | Status |
|---|---|---|---|
| INV-1 | No in-process model loads | `tests/inv/test_no_inprocess_models.py` | **PASS** — (1) AST scan: no module-scope import of torch/transformers/llama_cpp/ctranslate2/faster_whisper/onnxruntime/numpy/av under `src/` (the whisper worker imports `faster_whisper` inside `_serve`, reached only as `__main__`). (2) dynamic (Phase 3): a 7-artefact transform through the API `TestClient` leaves all those out of `sys.modules`. |
| INV-2 | ≤1 heavy model resident | `tests/inv/test_single_resident.py` | **PASS** — event-stream replay over brain→vlm→brain swaps (stub runtime) proves never two heavy READY; + live `os.kill(pid,0)` probes prove old process dead before new alive. |
| INV-3 | Lazy heavy imports | `tests/inv/test_lazy_imports.py` | **PASS** — AST scan of `render/` + `parivartan/` + `ingest/`: no module-scope `import` of docx/pptx/fpdf/jinja2/openpyxl/pyarrow/pypdf/selectolax/av/numpy/**pymupdf/PIL**. All heavy imports inside their functions. |
| INV-4 | No non-loopback egress | `tests/inv/test_no_egress.py` | skip-skeleton (phase 8); grep clean |
| INV-5 | Provenance manifest per artefact | `tests/inv/test_provenance.py` | **PASS** — `run_batch` (stub) then assert every non-`.manifest.json` file under each job dir has a sibling `<name>.manifest.json` parsing as `Manifest` with non-empty `source_sha256` + `model_key` + matching `artefact_format`. |
| INV-6 | Schema-validated model output | `tests/inv/test_validated_outputs.py` | **PASS** — valid stub completion → `ExecutiveSummary` instance; invalid JSON → `AgentError`, never returned unvalidated. `ArtefactAgent.run` gates every return on `schema.model_validate`. |
| INV-7 | Single model-start entry point | `tests/inv/test_single_entry_point.py` | **PASS** — regex scan: `subprocess`/`Popen`/`os.spawn`/`create_subprocess_*`/`multiprocessing` only in `models/runtime_*.py`; `ModelManager.acquire`/`obtain` present. |
| INV-8 | Unload = process kill | `tests/inv/test_unload_kills_process.py` | **PASS** — acquire stub, `os.kill(pid,0)` ok, evict, poll to `ProcessLookupError`; `EVICT_DONE` event carries the dead pid. |

INV-1/2/3/5/6/7/8 are real assertions run in `make check`. Only **INV-4** (egress) is still a `pytest.skip` skeleton — lands Phase 8.

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
- **Phase 4: `render/subtitle.py` added** beyond PLAN §6's explicit file list — PLAN §320 and the `FORMATS` map both need `.srt` for `video_package`. Pure stdlib.
- **Phase 4: `tests/unit/test_provenance.py` → `test_provenance_writer.py`** — pytest can't have two `test_provenance.py` basenames (no `__init__.py` in the test dirs); the INV-5 one keeps its PLAN-mandated name.
- **Phase 4: `_RunContext` frozen dataclass** bundles the ~10 things `_run_job` now needs (agents, dossier text+sha, request, store, out_root, manager, operator, clock, stream). `execute`/`run_batch`/`run_single` gained kw-only `operator: str = "operator"`; all prior signatures still valid.
- **Phase 4: manifest model identity** — `ModelEntry.declared_sha256` (new, from the yaml `sha256:` key) + `ModelManager.model_meta(key)`. With `verify=False` (runner/API/CLI default) the computed sha is None, so the manifest uses the declared one; stub → `model_sha256: null`, `model_quant: "stub"`.
- **Phase 4: SVG template inlined** in `svg_render.py` (< 60 lines) — no `package-data` entry needed. docx footer "manifest id" = the sibling manifest *filename* (renderers only get `(artefact, path)`; job/transform ids live in the manifest itself).
- **Post-Phase-4 (2026-09-06): auto hardware-profile selection.** `configs/models.yaml` restructured — `laptop-16gb` renamed `apple-metal`; added `nvidia-cuda` (`-ngl 99`, no `--threads` → llama picks physical cores) and `cpu-only` (`-ngl 0`, ctx 4096/2048 — usable fallback); `titan-24gb`/`test-stub` kept; **`active_profile:` key removed**. Model defs are now YAML anchors (`&brain_4b` etc.) merged per profile — PyYAML `safe_load` resolves `<<`. `core/config.py` `detect_profile()`: Darwin+arm64 → apple-metal; `shutil.which("nvidia-smi")` → nvidia-cuda (presence only — Phase 8 selfcheck checks it actually works); else cpu-only (loud `WARNING`). `RUPANTAR_PROFILE` still overrides (via `Env.profile`). `AppConfig.profile_source` records how it was chosen; logged at INFO. CLI `@app.callback` does `logging.basicConfig`; `api/app.py` sets the `rupantar` logger to INFO; `/health` gained `profile_source` + `platform`. Nvidia detection is presence-only (running `nvidia-smi` would trip the INV-7 subprocess scan).
- **Phase 5: `general.py` split into `general.py` + `_readers.py` + `_writers.py`** — 8 readers + 8 writers + the matrix would exceed 400 lines in one file (PLAN allowed the split).
- **Phase 5: STIX 2.1 hand-built, no `stix2` library.** `stix2` pulls `requests` — wrong for an air-gapped project. A STIX bundle is just JSON; `cyber._pattern_for` maps `IocType` → a STIX pattern and `_PATTERN_RE` reverses it. Stable ids via `uuid5(NAMESPACE_URL, value)` + a fixed `2020-01-01` timestamp so round-trip is byte-stable.
- **Phase 5: bespoke registry holds 4 registrations for 3 converters** (ioc-csv↔stix21 is bidirectional). `sigma→sigma-json` and `cef→jsonl` are one-way.
- **Phase 5: +2 fixtures beyond the plan** — `clean.csv` (round-trip property test needs a quirk-free input) and `iocs.csv` (STIX round-trip input). +`tests/integration/test_convert_api.py`. `test_cli.py`'s "convert/selfcheck are stubs" parametrized test split — `selfcheck` keeps the stub assertion.
- **Post-Phase-5 fix (2026-09-06): `presentation.pptx` "file format is invalid" in Keynote** — python-pptx / PowerPoint / LibreOffice / macOS Spotlight all accept the file; only Keynote's strict importer bails. **Root cause (confirmed by diffing against LibreOffice's Keynote-friendly re-save):** python-pptx **never writes `<p:notesMasterIdLst>` into `ppt/presentation.xml`** even though it adds a notes master part + rel + notes slides — a real OOXML reference-integrity defect (notes slides point at a notesMaster the presentation never declares). Also writes the deprecated `<p:sldSz type="screen4x3">` attr. `render/pptx_render.py._repair_ooxml()` now post-save patches only `presentation.xml`: inserts `<p:notesMasterIdLst><p:notesMasterId r:id="<notesMaster rId>"/></p:notesMasterIdLst>` in schema position (after `sldMasterIdLst`), strips `sldSz type`. *(An earlier attempt patched `app.xml` counts + stripped thumbnail/printerSettings — that did NOT fix Keynote; reverted.)* Separately fixed a real bug: `_LAYOUT_INDEX["title"]` was `0` → a *content* slide rendered onto the Title Slide layout, bullets dumped into a subtitle. Now `{title:2, bullets:1, two_column:3, quote:1, closing:2}`. Tests: `test_renderers_binary.py`/`test_renderers.py` now assert per-content-slide title/bullets/notes, that `presentation.xml` declares its notes master + correct element order + no `sldSz type`, open the PDF with `pypdf`, and — when LibreOffice is installed — convert the deck through it as an independent strict-parser check. **Keynote itself not testable in-session — but this is a documented python-pptx↔Keynote bug and the fix is verified structurally + against LibreOffice.**
- **Phase 6: INV-7 test exempts `ingest/video.py` for the bare `subprocess` name only** (it shells out to `ffmpeg`/`ffprobe` — media tools, not model processes). `Popen`/`create_subprocess_*`/`multiprocessing`/`os.spawn*` still forbidden there and everywhere outside `models/runtime_*.py`.
- **Phase 6: assembled `SourceDossier.id == transform_id`** so `store.get_dossier(transform_id)` retrieves it (no transform→dossier link column in `store.py`). `runner.prepare()` saves a placeholder `SourceDossier(id=tid, sha256="")`; `execute()` re-saves the real one after `assemble_dossier`.
- **Phase 6: `ingest/image.py` uses `typing.cast`** to pass multimodal list-content into `LlamaClient.complete` (typed `list[dict[str,str]]`) — widening the client was out of scope. `ingest/video.py` uses `-fps_mode vfr` (ffmpeg 9 deprecated `-vsync`).
- **Phase 6: whisper worker protocol** — `python -m rupantar.models.runtime_whisper --port P --model DIR --compute-type int8 --beam-size 1`; stdlib `http.server`; `GET /health` (200 once model loaded, 503 before); `POST /transcribe {"audio_path": "..."}` → `{"text", "segments":[{start,end,text}]}`. `WhisperModel(DIR, device="cpu", compute_type=..., local_files_only=True)`.
- **Phase 7: FROZEN CONTRACT CHANGE (`core/schemas.py` + `core/artefacts.py` + `docs/SCHEMAS.md`) — evidence model.** Reason: prerequisite for Phase 8.5 cross-artefact verification (a claim can't be checked against evidence that has no stable handle). All additive + optional-with-default, so existing data/fixtures still validate.
  - `TextBlock` +`evidence_id: str = ""`, +`page: int | None = None`, +`heading: str = ""`
  - `ImageInsight` +`evidence_id`; `TranscriptSegment` +`evidence_id`
  - new `VideoEvent{source_name, start, end, transcript, caption, evidence_id}`; `SourceDossier` +`video_events: list[VideoEvent] = []`
  - `ArtefactBase` +`sources: list[str] = []` (evidence IDs the artefact cites) → all 7 artefacts inherit it
  - `SourceDossier.to_prompt_text()` rewritten: each unit prefixed `[En]`, video/audio spans as `m:ss–m:ss`, page/heading shown. Still byte-identical across agents (prefix-cache design intact).
  - `assemble_dossier` assigns `E1..En` in order (text → images → video events → audio segments). The 7 artefact fixtures gained a `sources` array. All 7 agent prompts instruct the model to fill `sources` with the `[En]` IDs it used.
- **Phase 7: `ingest/text.py` — `extract_blocks(path) -> tuple[list[TextBlock], list[str]]`** replaces the single-string return (`extract_text` kept as a compat shim; `text_block` removed). PDF via **PyMuPDF** (`import pymupdf` inside `_from_pdf`) — one `TextBlock` per page with `page` + a detected `heading` (span font size ≥ 1.15× page median, or bold, and ≤ 80 chars). docx splits on `Heading N` styles. `pypdf` no longer imported in `ingest/` (still a dep for the renderer test). `keyframes()` returns `list[(Path, float)]`; new `video.probe_duration()`.
- **Phase 7: video source → `VideoEvent`s only** (no loose keyframe `ImageInsight`s, no separate `Transcript` for the video's own audio). `_build_video_events`: keyframe *i* spans `[t_i, t_{i+1})`, transcript = segments overlapping the span; first event `start` clamped to `0.0` (plan said `t_i`) so leading narration isn't dropped.
- **Phase 7: `render_video` degradation is graceful, not the plan's literal shape.** Burn-in subtitles need a libass ffmpeg; this machine's Homebrew ffmpeg 9.0.1 lacks libass → falls back to a selectable `mov_text` subtitle track (+ the `.srt` sidecar) with a warning. On a full ffmpeg build the burn-in path wins. `render_video` has a `max_scene_seconds: int = 60` cap (kw-only, default) so a hostile `duration_seconds` can't make ffmpeg run away.

---

## 6. Blockers

Things that are broken or unfinished and need attention. Include the file and the symptom.

- **RESOLVED (Phase 2):** `runtime_llama.py` real path is now verified — `tests/integration/test_runtime_llama_real.py` (slow) boots a real `llama-server` on the brain GGUF, health-checks, SIGTERMs, and asserts the pid is gone. Real end-to-end text path also exercised by `tests/integration/test_text_path_real.py`.
- **RESOLVED 2026-09-06:** asr fetched; the full Phase 6 real-model DoD is **verified** — `test_multimodal.py` passes (real whisper worker + `local_files_only` + real transcription + real vlm captions + `vlm→evict→asr→evict` sequence + peak RSS < 10 GB). A full image+video+text→executive_summary run also confirmed the `→ brain` half (§8). `registry.py` now handles the whisper directory model under `verify=True`.
- **RESOLVED 2026-09-06:** `tts` landed. `models/tts/en_US-lessac-medium.onnx` (+ `.onnx.json`) on disk; piper installed as the `piper-tts` 1.8.0 Python package. `render/video_render.py` updated for the 1.8 flags (`-f`, `--data-dir`, `python -m piper` fallback). Narrated `video_package.mp4` confirmed (§8). `test_video_package.py` real narration tests now run and pass; `configs/models.yaml` tts entry gained `model_bin_sha256`.
- `make check-all` runs `pytest tests/integration` with **no `-m "not slow"` filter**, so on a machine with the brain GGUF it executes **3** real-model tests (`test_text_path_real`, `test_multi_artefact_real`, `test_runtime_llama_real`) — ~15–16 min on the loaded dev box (the 7-artefact one alone is ~13 min). `make check` (the phase gate) stays fast and model-free. See Open Questions.
- `requirements-lock.txt` is still an empty placeholder. Everything added Phase 2–6 (`httpx`, `fastapi`, `uvicorn`, `starlette`, `python-docx`, `python-pptx`, `fpdf2`, `jinja2`, `openpyxl`, **`pyarrow`**, `pypdf`, `selectolax`, **`faster-whisper` → `ctranslate2` + `onnxruntime` + `av` + `numpy` + `tokenizers` + `huggingface-hub` + `hf-xet`**, `lxml`, `Pillow` + transitives) must be captured by `scripts/vendor_wheels.sh` for macOS arm64 py3.11 before air-gapping. `ctranslate2` + `onnxruntime` + `av` are the ones that need platform-specific wheels.

---

## 7. Open questions for the human

Decisions you could not make on your own. Do not guess — list them here and continue with the safest default.

- Demo hardware is **confirmed = this dev machine, a fanless MacBook Air M4** (macOS arm64, 16 GB). So `requirements-lock.txt` / wheel vendoring target macOS arm64 py3.11. Still open: whether the demo can instead run on an M4 **Pro/Max** (would fix the latency targets — see the demo-latency item below).
- `vlm` GGUF quant/build still unverified (file not on disk yet — Phase 6).
- Which three cyber formats matter most to the evaluators for Parivartan. Current default: IOC CSV ↔ STIX 2.1, Sigma YAML → JSON, CEF/syslog → JSONL.
- Whether the recorded demo video uses the auto profile (`apple-metal` on the M4 Air) or `RUPANTAR_PROFILE=titan-24gb`.
- `GenerationParams.language`: field kept, brain honours it best-effort; ASR/TTS are en-only and emit a `language_limitation` manifest warning (Phase 6). Tested values `en`, `hi`; others accepted as best-effort. Confirm `hi` is actually a demo requirement.
- Should `make check-all` deselect `-m slow`? It currently runs the real-model integration tests when models are on disk. Fixing it touches the `Makefile` **and** `PLAN.md` §7 (the single shared `make check` / `check-all` definition) and `CLAUDE.md`. Left as-is for now; `make check` itself is unaffected.
- ~~Schema-enforcement mechanism~~ **RESOLVED 2026-09-06.** Human chose native `response_format: json_schema`; `agents/grammar.py` deleted. See §4 / §5 / §9. Speed was a wash across all options; the call was made on maintenance + guarantee strength for the 6 remaining Phase 3 schemas.
- **Untested for Phase 3:** unconstrained/constrained *validation failure rate* was only measured for `ExecutiveSummary` (0/32). Advisory / Presentation / VideoPackage are structurally harder (nested models, enums, int fields). If the retry-once path fires often on those, revisit temperature or prompt, not the constraint mechanism.
- **Template support for pptx/docx/pdf output — DEFERRED to Phase 9 (with the frontend).** `.potx`/`.dotx` template files loaded by `python-pptx`/`python-docx` (`Presentation(template_path)` / `Document(template_path)`); HTML+CSS via WeasyPrint for the PDF path instead of the current fpdf2 hand-layout; a `template` field on `GenerationParams` (or per-request) to select one. Would also let a demo/customer skin match a house style and sidesteps the python-pptx-default-template quirks (§5 Keynote fix). Not started — needs the frontend to expose the selector and a small library of vetted templates.
- ~~Demo latency target~~ **SETTLED 2026-09-06 — option (d).** Accept ~150 s for demo-4 and ~304 s for the full 7, with token streaming so progress is visible. Keep Q4_K_M, `--parallel 1`, `--threads 4`. The ~14.5 tok/s is a memory-bandwidth ceiling on the M4 Air, **not a bug and not open for further tuning**. Fallback if it becomes available: **option (c)** — record the demo on the Titan via the existing `titan-24gb` profile (Qwen2.5-14B, more bandwidth). Not chasing speculative decoding or prompt-trimming.

---

## 8. Environment facts learned

Measured, not assumed. Update whenever you measure something new.

| Fact | Value | Measured on |
|---|---|---|
| Dev machine = demo machine | **MacBook Air M4** (`Mac16,12`), 10 cores (4 P + 6 E), **fanless**, 16 GB, macOS 15.3 (Darwin 25.3). ~120 GB/s memory bandwidth (M4 non-Pro). | 2026-09-06 |
| Python | 3.11.15 (uv-managed), `.venv/` | 2026-09-06 |
| `uv` version | 0.11.29 | 2026-09-06 |
| `ffmpeg` version | 9.0.1 (`/opt/homebrew/bin/ffmpeg`) — see the subtitle burn-in limitation row below. | 2026-09-06 |
| `llama-server` on PATH | **present** — v0.4.0 build 10809 (AppleClang, Darwin arm64, Metal), `/opt/homebrew/bin/llama-server` | 2026-09-06 |
| LibreOffice | installed on the dev machine (`/Applications/LibreOffice.app/.../soffice`) purely as an independent strict OOXML validator for the pptx tests — NOT a project dependency; the test skips when it's absent | 2026-09-06 |
| `piper` — **installed as the Python package `piper-tts` 1.8.0**, NOT a Homebrew binary | `shutil.which("piper")` finds the venv console-script; `render/video_render._piper_base()` falls back to `[sys.executable, "-m", "piper"]` so it works venv-active or not. **Flags changed in 1.8:** output is `-f OUT.wav` (was `--output_file`). Always pass `--data-dir models/tts` so piper never attempts a voice download at runtime (air-gap — same rule as faster-whisper `local_files_only=True`). | 2026-09-06 |
| **Narrated video confirmed** — `video_package.json` fixture through `render_video` | `narration.wav` 1 815 118 B / **41.16 s** (4 scenes, piper `en_US-lessac-medium`); `video_package.mp4` = h264 video + **aac audio** + `mov_text` subtitle track, **90.08 s** (full planned scene time — narration plays from 0:00, tail is silent). Only warning: the soft-subs fallback below. | 2026-09-06 |
| `ffmpeg` subtitle burn-in — **known limitation, NOT being fixed** | Homebrew `ffmpeg` 9.0.1 has no libass → the `subtitles` burn-in filter is unavailable. `render_video` falls back to a selectable `mov_text` track + the `.srt` sidecar and records a `render_warnings` entry. Building ffmpeg from source for one demo is not worth it; document it. A libass build (`brew install homebrew-ffmpeg/ffmpeg/ffmpeg`) enables the burn-in path automatically. | 2026-09-06 |
| `git` version | 2.51.2 | 2026-09-06 |
| `asyncio.Condition()` outside a running loop | constructs fine on 3.11 (used in sync CLI path) | 2026-09-06 |
| Stub runtime child | `python -m rupantar.models.runtime_stub --port N`, stdlib `http.server`, real PID, SIGKILL grace 3s | 2026-09-06 |
| Phase 1 test suite | no stray `runtime_stub`/`llama-server` procs after run; ports 8100–8199 clean | 2026-09-06 |
| Free RAM | ~1 GB free+inactive under load (not a clean idle measure) | 2026-09-06 |
| brain GGUF | `models/brain/Qwen3-4B-Instruct-2507-Q4_K_M.gguf`, 2 497 281 120 B, sha256 `3605803b982cb64aead44f6c1b2ae36e3acdb41d8e46c8a94c6533bc4c67e597` | 2026-09-06 |
| **CLEAN PERF BASELINE** — the rows below are **idle machine, `sudo purge`d page cache**, `-ngl 99 --parallel 1 --ctx-size 8192 --threads 6`. Earlier contended/`-ngl 0` figures were deleted as misleading. | ↓ | 2026-09-06 |
| brain cold boot → healthy | **2.47 s** (from a purged page cache) | 2026-09-06 |
| brain warm boot → healthy | **1.03 s** | 2026-09-06 |
| vlm (Qwen2.5-VL-3B Q4_K_M + mmproj-F16) | boot→healthy ~5.5 s; `ps` RSS ~3.5 GB (Metal — `ps -o rss` likely undercounts GPU-resident weights); one image caption ~10 s → valid `ImageInsight`. | 2026-09-06 |
| asr (faster-whisper small.en int8) | `models/asr/faster-whisper-small.en-int8/`, `model.bin` 483 545 366 B sha256 `62b2a45b05ee59acb4a5341b33ee35e041395d378d418a18acfe4c9e768ee37a`. Worker boot + `local_files_only=True` load + 30 s clip transcription: **136 s** for the bare video-dossier test. (`sample_clip.mp4` is synthetic → whisper returns "You", a non-speech artifact — fine for the fixture.) | 2026-09-06 |
| **Full multimodal run** — image + 30 s video + text → executive_summary (`apple-metal`, real vlm+asr+brain) | **210 s wall**, job SUCCEEDED. Manager events EXACTLY `vlm LOAD→READY→EVICT×2 · asr LOAD→READY→EVICT×2 · brain LOAD→READY` — **the single-heavy-residency claim proven for real**. Dossier: 1 text block, **6 keyframe captions**, 1 transcript. | 2026-09-06 |
| **Peak process-tree RSS, full multimodal run** | **3.39 GB** (`_RssPoller` polling `pgrep -P` + `ps -o rss` every 0.75 s; `test_multimodal.py` asserts < 10 GB). Even doubling for Metal undercount → ~7 GB. The real guarantee is the eviction discipline, not the number. | 2026-09-06 |
| brain generation, real artefacts | **~14.5 tok/s** — median across the 7 agents, ctx 8192, `json_schema` constraint. **This is a genuine hardware ceiling, NOT thermal throttling** — `executive_summary` run 5× back-to-back from a cool start held 14.6→14.5 tok/s over 184 s of sustained load (flat; thermal would decay). Memory-bandwidth-bound: `--threads 4` (M4 Air has 4 P-cores) is perf-identical to `--threads 6`. `llama-bench`'s ~37 tok/s is a tiny-context synthetic. An M4 Pro/Max (273/410 GB/s) would do ~2–3×. | 2026-09-06 |
| brain prompt eval | first agent pays the full ~750-tok dossier eval (folded into its ~40 s wall); agents 2–7 hit ~556 cached tok (byte-identical dossier prefix) and evaluate only 200–350 new. Total prompt-eval across a 7-run ≈ 18 s. | 2026-09-06 |
| **7-artefact run, one request** (`ai_policy_brief.md`, fresh server) | **304 s wall**, 4133 generated tokens, 1 brain `LOAD_START`, 0.7 s dead time. Per-agent gen tok / wall s: exec 503/40.4 · advisory 639/46.8 · linkedin 433/31.2 · x_thread 322/23.6 · presentation 764/55.1 · infographic 434/32.0 · video 1038/74.9. | 2026-09-06 |
| **demo-4 subset** (exec, linkedin, x_thread, advisory), fresh server | **~143–156 s wall** (two idle runs; ~9 % run-to-run variance), ~2000 gen tok — **MISSES the < 90 s target** (needs ~21 tok/s; this machine does ~14.4). | 2026-09-06 |
| IQ4_XS quant vs Q4_K_M (demo-4, idle) | **IQ4_XS is 8 % SLOWER** — 169 s vs 156 s, 13.3 vs 14.5 tok/s; saves 0.3 GB RSS (3.96 vs 4.26). IQ dequant compute outweighs the 9 % smaller file on this Metal build. **Rejected; keep Q4_K_M.** File deleted (re-download from `unsloth/Qwen3-4B-Instruct-2507-GGUF`, sha `cfd15a69…`). | 2026-09-06 |
| Peak RSS, brain resident (Metal, 8192 ctx) | **4.89 GB** across the whole 7+4 run. Comfortably inside 16 GB — the one-heavy-model thesis holds. | 2026-09-06 |
| enforcement mechanism cost (GBNF / json_object / json_schema / none) | all within noise of each other; 0 validation failures incl. unconstrained on `ExecutiveSummary` (32 runs). All 7 artefact types validate first try with `json_schema`. See §9 investigation block. | 2026-09-06 |
| `fastapi` / `starlette` / `uvicorn` | 0.127.1 / 0.50.0 / 0.52.4 (pin `fastapi>=0.115,<0.128` — see §5) | 2026-09-06 |
| `--n-gpu-layers` on Apple Silicon — **`-ngl 0` was a real mistake** | `-ngl 0` forces CPU-only: **~7 tok/s gen, ~21 tok/s prompt-eval, 6.6 s boot**. `-ngl 99` (or the flag unset) → Metal: **~13 tok/s gen, ~125 tok/s prompt-eval, 1.5–2 s boot**. ~1.9× / ~6× / ~3×. The earlier "36.6 vs 36.8, no difference" compared `-ngl 99` vs *unset* (both Metal) — `-ngl 0` was never tested. `apple-metal`/`nvidia-cuda` profiles use `-ngl 99`; only `cpu-only` uses `-ngl 0` (deliberately). | 2026-09-06 |
| `--parallel N` default | `-1` = auto → **4 slots**, each capped at `ctx/4` = 2048 tok (would overflow a real multimodal dossier). Running the 7 agents concurrently across 4 slots gave only ~20 % wall improvement (290 s vs 363 s) at 3× worse per-artefact latency (4–8 vs 13 tok/s) and cache loss on ~3 agents. `models.yaml` now pins `--parallel 1`: one slot, full 8192 ctx, perfect prefix reuse, low latency. | 2026-09-06 |
| llama-server prefix caching | per-slot; `cache_prompt: true` (default on) reuses the longest common token prefix. Agents put the identical dossier first so agents 2–7 skip re-evaluating it — confirmed working (~556 cached tok/agent). | 2026-09-06 |
| Peak RSS, full multimodal run (vlm+asr+brain) | unknown — brain-alone is 4.89 GB | — |

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

### 2026-09-06 — piper 1.8 invocation fix + narrated video confirmed
Did: `render/video_render.py` — `_piper_base()` (`shutil.which("piper")` → else `[sys.executable, "-m", "piper"]`); `_write_narration` gates on the voice `.onnx` file (not the binary), builds `piper -m … -c … --data-dir models/tts -f _nar_NN.wav` (1.8 flags), enriched failure warning with stderr tail. Removed `-shortest` from `_VideoPlan.command()` so panels run full planned time and the `.srt` stays in sync. `configs/models.yaml` tts += `model_bin_sha256` (5efe09e6…), real `approx_bytes`. `test_registry.py::test_missing_real_file_names_fetch_script` rewritten to use a synthetic missing-path config (all four models are now on this disk, so the old "verify apple-metal raises" premise was dead). Updated `test_video_render.py` + `test_video_package.py` (`_HAS_VOICE = _TTS_MODEL.is_file()`; two new muxed-narration / missing-voice tests).
Verified: `make check` green (190 unit + 12 inv / 1 skeleton, mypy 58). Manual render of the `video_package.json` fixture → `narration.wav` 41.16 s, `video_package.mp4` h264 + **aac** + mov_text, 90.08 s. §8 updated.
Next: Phase 8 — air-gap / audit / selfcheck (builder). Do NOT start 8.5.

### 2026-09-06 — Phase 7 — video assembly + evidence model
Did: **lead** — frozen-contract additions (`schemas.py`/`artefacts.py`/`docs/SCHEMAS.md`): evidence IDs on dossier units, `VideoEvent`, `ArtefactBase.sources`, `to_prompt_text()` rewrite (§5 deviation). Added PLAN.md **Phase 8.5** (cross-artefact verification). **builder 1** — `assemble_dossier` assigns `E1..En`; 7 agent prompts cite `sources`; `keyframes()` → `(path, t)`; video source → `VideoEvent`s; `ingest/text.py extract_blocks()` with PyMuPDF page/heading. **builder 2** — `render/video_render.py` (storyboard.json + Pillow panels always; narration.wav if piper; mp4 if ffmpeg; graceful `render_warnings` + `warnings.txt`, never raises); `render/base.py` renderers may return `list[Path]`.
Verified: `make check` green (190 unit + 12 inv / 1 skeleton, mypy 58). `test_video_package.py` 7 passed (mp4 h264 1280×720 built + ffprobe OK; piper-absent degrades gracefully, `warnings.txt` written). integration non-slow 32 passed. `pytest -m slow` 4 passed (252 s) — real multimodal event order + video_events + peak RSS asserted; `test_multi_artefact_real` renders a real-brain video_package (mp4 48 s, no audio, mov_text subs). arch-guard CLEAN.
Env notes: this Homebrew ffmpeg 9.0.1 lacks libass → subtitles muxed as a selectable track, not burned in (needs the full ffmpeg build). piper + tts model still absent.
Next: Phase 8 — air-gap / audit / selfcheck.

### 2026-09-06 — Phase 6 — multimodal ingestion shipped
Did (builder + lead): `models/runtime_whisper.py` (WhisperRuntime + stdlib worker, `faster_whisper` inside `_serve`, `local_files_only=True`), `ingest/{text,image,audio,video,dossier}.py`, `_support` whisper factory branch, `runtime_stub` `/transcribe`, `runner.execute()` → `assemble_dossier` (text → acquire vlm caption → evict → acquire asr transcribe → evict → then brain loop). Scene-change keyframes with even-spread fallback. INV-1/3/7 handled + tests. Lead: updated `models.yaml` vlm (real filenames + SHAs — anchor had a wrong mmproj name); added `tests/unit/test_ingest_image.py` (retry branches — verifier flagged the gap); **ran the real vlm caption path by hand — valid `ImageInsight`, 3.5 GB RSS, clean swap.**
Verified: `make check` green (179 unit + 12 inv / 1 skeleton, mypy 57). `test_multimodal_stub.py` asserts the exact 10-event vlm→evict→asr→evict→brain sequence + `{vlm,brain}` never both READY. `pytest -m slow` → 3 pass, `test_multimodal.py` **skips** (asr absent — the real swap + peak-RSS-<10GB check is the one unproven DoD). arch-guard CLEAN. verifier PASS w/ warnings.
Blocker: `models/asr/` not on disk → real audio path unverified. **[Resolved same day — asr fetched; `test_multimodal.py` passes; full image+video+text→exec-summary run: 210 s, exact vlm→evict→asr→evict→brain sequence, peak RSS 3.39 GB. `models.yaml` asr `model_bin_sha256`; `registry.py` handles the whisper dir under `verify=True`; whisper worker handles SIGTERM cleanly (was leaking a CT2 semaphore on SIGKILL). §8.]**
Next: Phase 7 — video assembly. Needs `piper` + tts model (both absent).

### 2026-09-06 — Fix — `presentation.pptx` rejected by Keynote (2 rounds)
Round 1 (wrong): patched `app.xml` counts + stripped thumbnail/printerSettings → user re-tested, **still failed**. Round 2 (right): installed LibreOffice as an independent strict OOXML parser, diffed its Keynote-friendly re-save against python-pptx → python-pptx **omits `<p:notesMasterIdLst>` from `presentation.xml`** (notes slides reference a notesMaster the presentation never declares — a reference-integrity defect Keynote hard-rejects). `_repair_ooxml()` rewritten to inject that element + strip `<p:sldSz type>`. Also fixed `_LAYOUT_INDEX["title"] = 0` bug. +`pypdf>=5`. Tests assert the notesMaster declaration + element order + LibreOffice conversion. `make check` green (157 unit). Sent the user a regenerated file to confirm in Keynote. See §5.

### 2026-09-06 — Phase 5 — Parivartan converters shipped
Did (builder + lead): `parivartan/` — `registry.py` (`ConversionReport`, `@register`, `list_conversions`, `convert` with the missing-input/bespoke/general/error dispatch), `general.py`+`_readers.py`+`_writers.py` (8×8 tabular matrix over `list[dict]`), `cyber.py` (ioc-csv↔stix21 hand-built, sigma→json, cef→jsonl). `cli convert` + `api/routes/convert.py` (`GET /conversions`, `POST /convert`). `core/errors.py` +`ConversionError`. Fixtures `messy.csv`/`sigma_rule.yml`/`cef.log` (+`clean.csv`/`iocs.csv`). INV-3 scan now covers `parivartan/`.
Verified: `make check` green (mypy 50, 154 unit, 12 inv / 1 skeleton); `test_parivartan*.py` 21 passed; integration (non-slow) 23 passed; `pytest -m slow` 3 passed. csv→json→csv byte-identical round-trip; IOC CSV→stix21→CSV preserves (type,value); `messy.csv→json` → `ok=True` + 2 warnings, no traceback; missing input → clean exit-1, no traceback. verifier + arch-guard [running at commit].
Deviations: §5 (general.py split, no stix2 lib, +2 fixtures).
Next: Phase 6 — Multimodal ingestion. `ingest/{text,image,audio,video,dossier}.py`. **Needs vlm + asr GGUFs fetched** (not on disk — run `scripts/fetch_models.sh` online first). DoD: 30 s video → dossier; manager events vlm→evict→asr→evict→brain (never 2 heavy); peak RSS < 10 GB (assert). New deps: pypdf, selectolax, faster-whisper. `runtime_whisper.py` (referenced by `models.yaml` but not built) lands here.

### 2026-09-06 — Auto hardware-profile selection (post-Phase-4, pre-Phase-5)
Why: the `-ngl 0` bug happened because nobody checked the config matched the machine; the team has mixed HW.
Did: `models.yaml` — 3 auto profiles (`apple-metal` [was `laptop-16gb`], `nvidia-cuda`, `cpu-only`) via YAML anchors + `titan-24gb`/`test-stub`; dropped `active_profile:`. `config.py` `detect_profile()` (platform + `nvidia-smi` presence; cpu-only fallback with loud WARNING); `RUPANTAR_PROFILE` overrides; `AppConfig.profile_source`; INFO log. CLI `@app.callback` basicConfig; `api/app.py` logger→INFO; `/health` +`profile_source`/`platform`. `PLAN.md` §5 + Phase-8 §4b (now "report HW/profile/offload, fail if GPU profile but offload=0"); README HW-profiles section. Renamed `laptop-16gb`→`apple-metal` in 4 test files; rewrote `test_config.py` (detection branches via monkeypatch, override, cpu-only WARNING).
Verified: `make check` green (143 unit + 12 inv / 1 skeleton); CLI logs `hardware profile: apple-metal (Darwin/arm64 …)`; forced `RUPANTAR_PROFILE=cpu-only` + mocked-Linux paths both behave; stub integration 20 passed; `pytest -m slow` [running at commit].
Deviation: nvidia detection is `shutil.which` presence only — running `nvidia-smi` would trip the INV-7 subprocess scan; "does the GPU actually work" is Phase 8 selfcheck.

### 2026-09-06 — Phase 4 — renderers + provenance [compressed]
`render/` — `base.py` (`FORMATS` + `render()` dispatch), `markdown.py` (7 types), `docx_render`/`pptx_render`/`pdf_render` (fpdf2)/`svg_render` (Jinja2)/`subtitle` (.srt); heavy imports inside functions. `audit/provenance.py` — `Manifest` (14 fields) + `write_manifest()` → `<file>.manifest.json`. `runner._run_job`: validate → `.json` → `render()` → manifest per file (`_RunContext`, `operator`). `manager.model_meta()` + `ModelEntry.declared_sha256` + `ArtefactAgent.prompt_version`. INV-3 + INV-5 made real. +python-docx/python-pptx/fpdf2/jinja2. Deviations §5. Real 7-artefact run 305 s, 1 brain load.

### 2026-09-06 — Perf sessions (pre-Phase-4) [compressed — see §7/§8 for the live numbers]
Root cause of the 765 s Phase-3 run: `models.yaml` `--n-gpu-layers 0` (CPU-only) + a contended box. Pipeline itself is efficient (0.7 s dead time, prefix cache works, 18 s prompt-eval). Clean idle measurement on the **fanless MacBook Air M4**: cold boot 2.47 s, 7-artefact 304 s, demo-4 ~150 s, peak RSS 4.89 GB, gen **~14.5 tok/s flat** — a memory-bandwidth ceiling, **not thermal** (5× back-to-back flat), not a config bug. IQ4_XS quant tried, 8 % slower, rejected. Fixes landed: `-ngl 99`, `--parallel 1`, `--threads 4`. Human chose **option (d)** — accept ~150 s with streaming (§7). `PLAN.md` Phase 8 §4b: selfcheck must fail on `-ngl 0` while GPU available. Also: 4-mode enforcement benchmark → all the same speed, 0 unconstrained failures (→ `json_schema`, `grammar.py` deleted).

### 2026-09-06 — Phase 3 — artefact agents + orchestration + `api/` [compressed]
6 agent configs; `orchestrator/planner.py` + `scheduler.py` (modality rank, `depends_on` topo); `runner.py` → `prepare`/`execute`/`run_batch` (one `acquire()` per consecutive same-`model_key` run); `runtime_stub` directory mode; `cli transform` batches. `api/` package — `create_app()`, routes `transforms`/`jobs`/`models`/`health`, `POST /transforms` → 202 + background task. INV-1 dynamic check real. Real 7-artefact run: 1 brain load, all 7 schema-valid. +`fastapi`/`uvicorn`. Deviations in §5.
### 2026-09-06 — Investigation — GBNF sampling cost (pre-Phase-3) [compressed]
Benchmarked GBNF / json_object / json_schema / no-constraint on `executive_summary` (32 real-brain runs). **All the same tok/s**; `json_schema` output token-identical to unconstrained (constraint never fires); **0 validation failures incl. unconstrained**. The 37→17→7 tok/s scare was context+load, not grammar. Human decision → native `response_format: json_schema`, `agents/grammar.py` deleted. Also fixed stale `sample_article.txt` in `PLAN.md` §8. Details in §4/§5.

### 2026-09-06 — Phase 2 — Text generation path [compressed]
Builder built `models/client.py` (httpx), `agents/{base,loader}.py`, `orchestrator/runner.py` `run_single`, `executive_summary.yaml`, real `cli transform`, OpenAI-compat `runtime_stub.py`, `core/errors.py` +`ModelClientError`/`AgentError`. INV-6 real. Pointed `models.yaml` brain at the real GGUF + `sha256:`. Moved the lying `runtime_llama` skip → real slow test in `tests/integration/`. Chose httpx. Real: exec summary ~53 s. Deviations in §5, decisions in §4.

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
- **Phase 3 added `fastapi>=0.115,<0.128`** (0.127.1; pulls `starlette` 0.50.0) **and `uvicorn>=0.30`** (0.52.4; pulls `click`). Upper pin: starlette ≥1.6 deprecates `httpx` for `TestClient`. Used only in `src/rupantar/api/`.
- **Phase 4 added `python-docx>=1.1`, `python-pptx>=1.0`, `fpdf2>=2.8`, `jinja2>=3.1`** (1.2.0 / 1.0.2 / 2.8.8 / 3.1.6; pull `lxml`, `Pillow`, `fonttools`, `xlsxwriter`, `defusedxml`, `markupsafe`). `fpdf2` over `reportlab` for a smaller air-gap footprint. Used only in `src/rupantar/render/`, all imported **inside functions** (INV-3).
- **Phase 5 added `openpyxl>=3.1`, `pyarrow>=17`** (3.1.5 / 25.0.1; `pyarrow` is a ~40 MB wheel — has macOS arm64 py3.11 wheels; `openpyxl` pulls `et-xmlfile`). Used only in `parivartan/_readers.py` + `_writers.py`, **inside functions** (INV-3). No pandas, no `stix2` (would pull `requests`).
- **Post-Phase-5 added `pypdf>=5`** (6.17.0) — the strengthened PDF renderer test opens the output with `PdfReader`. Also the Phase 6 `ingest/text.py` PDF path. Now in the INV-3 `_HEAVY` set → imported inside functions.
- **Phase 6 added `selectolax>=0.3`, `faster-whisper>=1.1`** (0.4.11 / 1.2.1). `faster-whisper` pulls `ctranslate2` 4.8.2, `onnxruntime` 1.29, `av` 18.1, `numpy` 2.4, `tokenizers` 0.23, `huggingface-hub` 1.30, `hf-xet`, `tqdm`. `faster_whisper`/`ctranslate2` only imported inside the whisper worker (`__main__`); `selectolax`/`av`/`numpy` only inside `ingest/*` functions (INV-1 + INV-3 both cover them).
- **Phase 7 added `pymupdf>=1.24`** (1.28.2 — `import pymupdf`, mac arm64 wheel). Used only inside `ingest/text.py._from_pdf` (INV-3 `_HEAVY` += `pymupdf`). `Pillow` (already present via `python-pptx`) is now also used by `render/video_render.py` — INV-3 `_HEAVY` += `PIL`.
- **`piper-tts` 1.8.0** — TTS CLI, invoked as a subprocess (never imported), so not an INV-3/INV-1 concern. Pulls `onnxruntime` (already present via faster-whisper), `piper-phonemize-cross`, `espeak-phonemizer` equivalents. Must be in `vendor_wheels.sh`. `ffmpeg` stays an OS-level CLI, not vendored. | 2026-09-06 |
- **No Phase 2–5 dep is in `requirements-lock.txt` yet** — see blocker §6 for the full list.
