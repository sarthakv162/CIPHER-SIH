# PLAN.md — Rupantar: Offline Content Transformation Engine

> **Project:** NTRO / SIH — AI-powered content transformation engine
> **Codename:** `rupantar` (platform) · `parivartan` (format-converter subsystem)
> **Target hardware:** 16 GB RAM laptop, air-gapped. Optional 24 GB Titan profile.
> **This document is the contract.** Claude Code must follow it phase by phase and must not skip ahead.

---

## 0. Mission and non-goals

### Mission
Take a source of information (text, document, image, audio, video, or free-form prompt) and produce one or more requested communication artefacts (LinkedIn post, X thread, advisory, executive summary, presentation, infographic spec, video package), fully offline, on a 16 GB laptop, with **exactly one heavy model resident in memory at a time**.

### Non-goals for this build (explicitly deferred — do NOT implement)
- Knowledge graph / Neo4j
- Vector RAG, embeddings (BGE-M3), re-rankers, ChromaDB
- Video RAG
- Digital twin
- Fine-tuning
- Polished frontend / UX work (Phase 9, later; API + CLI first)

If a task seems to need any of the above, **stop and write it in `MEMORY.md` under Open Questions** instead of building it.

---

## 1. Hard invariants

These are architectural laws. Each has a test file. Breaking one is a build failure.

| ID | Invariant | Test |
|----|-----------|------|
| INV-1 | No ML model is ever loaded inside the API process. All models run as supervised child processes. | `tests/inv/test_no_inprocess_models.py` |
| INV-2 | At most `policy.max_heavy_resident` (default 1) heavy models are resident at any moment. | `tests/inv/test_single_resident.py` |
| INV-3 | Every converter and every renderer imports its heavy dependency **inside** the function, never at module top level. | `tests/inv/test_lazy_imports.py` |
| INV-4 | No outbound network connection to a non-loopback address at runtime. | `tests/inv/test_no_egress.py` |
| INV-5 | Every artefact file written to disk has a sibling `.manifest.json` provenance record. | `tests/inv/test_provenance.py` |
| INV-6 | Every model output passes a Pydantic schema validator before reaching a renderer. | `tests/inv/test_validated_outputs.py` |
| INV-7 | `ModelManager.acquire()` is the only code path that starts a model process. | `tests/inv/test_single_entry_point.py` |
| INV-8 | Unload is process termination, never Python garbage collection. | `tests/inv/test_unload_kills_process.py` |

---

## 2. Tech stack (fixed — do not substitute)

| Concern | Choice | Why |
|---|---|---|
| Language | Python 3.11 exactly (`uv python install 3.11`, pinned in `.python-version`) | Renderer + converter ecosystem; 3.11 wheels for ctranslate2 / pyarrow / onnxruntime are the ones vendored for the air-gapped laptop |
| API | FastAPI + uvicorn (single worker) | Async, OpenAPI docs for free |
| LLM/VLM runtime | `llama.cpp` `llama-server` subprocess, GGUF Q4_K_M | mmap load, guaranteed unload by SIGTERM, CPU-viable |
| ASR | `faster-whisper` in a worker subprocess | int8, small footprint |
| TTS | `piper` CLI | ~60 MB, no residency needed |
| Media | `ffmpeg` CLI | keyframes, audio extract, video assembly |
| Job state | SQLite (`aiosqlite`) | No Redis, no daemon, air-gap friendly |
| Queue | in-process `asyncio` priority queue | One model at a time means no distributed queue is needed |
| Schemas | Pydantic v2 | Validation + JSON Schema → GBNF grammar |
| Config | YAML + Pydantic Settings | `configs/models.yaml`, `configs/policy.yaml` |
| CLI | Typer | Headless demo path, no frontend dependency |
| Tests | pytest + pytest-asyncio | |
| Lint | ruff + mypy (non-strict) | |

**Never add a dependency not listed in `requirements.txt` without recording it in `MEMORY.md`.**

---

## 3. Repository layout

```
rupantar/
├── CLAUDE.md                     # session instructions (read first, every session)
├── MEMORY.md                     # rolling project memory — read at start, update at end
├── PLAN.md                       # this file
├── README.md
├── .python-version               # 3.11, enforced by selfcheck
├── requirements.txt
├── requirements-lock.txt         # pip freeze, for air-gapped wheel vendoring
├── docs/
│   └── SCHEMAS.md                # frozen contracts — the artefact + request models
├── .claude/
│   └── agents/
│       ├── builder.md            # task-scoped implementer subagent
│       ├── verifier.md           # end-to-end health checker subagent
│       └── arch-guard.md         # invariant enforcement subagent
├── configs/
│   ├── models.yaml               # model registry, per hardware profile
│   ├── policy.yaml               # residency, TTL, ports, limits
│   └── agents/                   # one YAML per artefact agent (prompt + params)
│       ├── executive_summary.yaml
│       ├── advisory.yaml
│       ├── linkedin_post.yaml
│       ├── x_thread.yaml
│       ├── presentation.yaml
│       ├── infographic_spec.yaml
│       └── video_package.yaml
├── src/rupantar/
│   ├── __init__.py
│   ├── core/
│   │   ├── config.py             # settings loading, profile resolution
│   │   ├── schemas.py            # SourceDossier, Job, ArtefactDraft base
│   │   ├── artefacts.py          # one Pydantic model per artefact type
│   │   ├── store.py              # SQLite job + dossier persistence
│   │   └── errors.py
│   ├── models/
│   │   ├── registry.py           # parse models.yaml, verify files on disk
│   │   ├── manager.py            # ModelManager: acquire/release/evict  ← CRITICAL PATH
│   │   ├── runtime_base.py       # Runtime ABC: start/stop/health/endpoint
│   │   ├── runtime_llama.py      # llama-server subprocess
│   │   ├── runtime_whisper.py    # faster-whisper worker subprocess
│   │   ├── runtime_stub.py       # fake runtime for tests, no model files
│   │   └── client.py             # OpenAI-compatible HTTP client to llama-server
│   ├── ingest/
│   │   ├── dossier.py            # SourceDossier assembly
│   │   ├── text.py               # txt/md/html/pdf/docx extraction
│   │   ├── image.py              # VLM captioning + OCR
│   │   ├── audio.py              # whisper transcription
│   │   └── video.py              # ffmpeg keyframes + audio track
│   ├── agents/
│   │   ├── base.py               # ArtefactAgent: prompt + schema + grammar + validate
│   │   ├── loader.py             # build agents from configs/agents/*.yaml
│   │   └── grammar.py            # Pydantic JSON Schema → GBNF
│   ├── orchestrator/
│   │   ├── planner.py            # request → job list
│   │   ├── scheduler.py          # modality-grouped ordering  ← key improvement
│   │   └── runner.py             # executes jobs, owns leases
│   ├── render/
│   │   ├── base.py
│   │   ├── markdown.py
│   │   ├── docx_render.py        # advisory, exec summary
│   │   ├── pptx_render.py        # presentation
│   │   ├── pdf_render.py         # advisory PDF
│   │   ├── svg_render.py         # infographic
│   │   ├── subtitle.py           # .srt
│   │   └── video_render.py       # piper + ffmpeg → .mp4
│   ├── parivartan/
│   │   ├── registry.py           # (src, dst) → converter, lazy imports
│   │   ├── general.py            # csv/tsv/json/jsonl/xlsx/xml/yaml/parquet
│   │   └── cyber.py              # stix2.1, misp, sigma, cef/syslog, nessus
│   ├── audit/
│   │   ├── provenance.py         # manifest writer
│   │   ├── egress.py             # loopback-only enforcement + monitor
│   │   └── selfcheck.py          # full system health report  ← the checker
│   ├── api/
│   │   ├── app.py
│   │   └── routes/{jobs,models,convert,health}.py
│   └── cli/
│       └── main.py               # typer: transform, convert, selfcheck, models
├── tests/
│   ├── inv/                      # invariant tests (INV-1..8)
│   ├── unit/
│   ├── integration/
│   └── fixtures/
├── models/                       # GGUF + whisper + piper files (gitignored)
├── data/
│   ├── samples/                  # demo source articles, images, a short video
│   └── outputs/                  # generated artefacts + manifests
└── scripts/
    ├── fetch_models.sh           # run ONCE while online, before air-gapping
    ├── vendor_wheels.sh          # pip download for offline install
    └── demo.sh                   # scripted 2-minute demo
```

---

## 4. Core data flow

```
Operator request  ──►  TransformRequest
   │  {sources: [SourceInput...], output_types: [ArtefactType...], params: {audience, tone, language, detail, objective, style}}
   │  One request == one Transform (the batch). See docs/SCHEMAS.md for every field.
   ▼
Planner            → list[Job]        (one Job per requested artefact)
   ▼
Scheduler          → jobs reordered, grouped by required model_key
   ▼
Runner
   ├─ acquire(vlm)     → caption all images  → unload
   ├─ acquire(asr)     → transcribe audio    → unload
   ├─ SourceDossier assembled (pure text from here on)
   ├─ acquire(brain)   → run ALL text agents → unload
   └─ renderers + piper/ffmpeg (no model residency)
   ▼
ArtefactFile + .manifest.json  →  data/outputs/<job_id>/
```

**One swap per modality per request. Never per artefact.** This is the headline architectural claim.

---

## 5. Model registry (`configs/models.yaml`)

Sizes are approximate; `registry.py` must read actual file size and SHA-256 at startup and record them.

Profiles (auto-selected by `core/config.py`; `RUPANTAR_PROFILE` overrides): `apple-metal`,
`nvidia-cuda`, `cpu-only` — all the 4B/3B "16 GB laptop" tier, differing only in llama.cpp args
(`-ngl`, `--threads`, `--ctx-size`) — plus `titan-24gb` (bigger models, explicit override only)
and `test-stub`.

| key | class | apple-metal / nvidia-cuda / cpu-only | titan-24gb |
|---|---|---|---|
| `brain` | heavy | Qwen3-4B-Instruct Q4_K_M (~2.5 GB) | Qwen2.5-14B-Instruct Q4_K_M (~9 GB) |
| `vlm` | heavy | Qwen2.5-VL-3B-Instruct Q4_K_M + mmproj (~3 GB) | Qwen2.5-VL-7B Q4_K_M |
| `asr` | light | faster-whisper `small.en` int8 (~0.5 GB) | `medium.en` int8 |
| `tts` | transient | piper `en_US-lessac-medium` (~60 MB) | same |

`policy.yaml`:
```yaml
max_heavy_resident: 1
idle_ttl_seconds: 120
acquire_timeout_seconds: 180
port_range: [8100, 8199]
context_length: 8192
health_poll_interval: 0.5
health_timeout_seconds: 120
prewarm_on_startup: brain
```

---

## 6. Build phases

Each phase: implement → run its verify command → have the `verifier` subagent confirm → update `MEMORY.md` → only then move on.

---

### Phase 0 — Scaffold and contracts *(no models)*

**Build**
- Repo layout above, `pyproject.toml` + `requirements.txt` (src layout, `pip install -e .`), `.python-version` (3.11), ruff + mypy config (mypy with the `pydantic.mypy` plugin), `Makefile`
- `core/errors.py`: typed exception hierarchy (`RupantarError` and subclasses)
- `core/config.py`: **minimal** — locate `configs/`, load `models.yaml` + `policy.yaml`, resolve the active profile, expose the SQLite path. Grows in Phase 1. *(Post-Phase-3: profile is now auto-detected from the platform — Apple Silicon → `apple-metal`, `nvidia-smi` on PATH → `nvidia-cuda`, else `cpu-only`; `RUPANTAR_PROFILE` overrides; the choice is logged at INFO.)*
- `core/schemas.py`: `SourceInput`, `TransformRequest`, `ArtefactType`, `JobStatus`, `Job`, `GenerationParams`, `SourceDossier` (see `docs/SCHEMAS.md`)
- `core/artefacts.py`: Pydantic model for **all seven** artefact types with every list min/max and char limit enforced in `field_validator`s (see `docs/SCHEMAS.md`)
- `core/store.py`: SQLite schema + **async** CRUD (`aiosqlite`, JSON columns) for dossiers and jobs
- `cli/main.py` + `cli/__main__.py`: Typer skeleton — `transform`, `convert`, `selfcheck` commands plus a `models` sub-app, all stubs
- `tests/inv/`: all eight invariant test files as `pytest.skip("implemented in phase N")` skeletons
- `tests/fixtures/`: 2 sample articles, 1 image, 1 ~30-second video, 7 hand-written artefact example JSONs. `scripts/make_fixtures.sh` regenerates the image + video with `ffmpeg` (run once). Parivartan fixtures (CSV, Sigma, CEF) arrive in Phase 5; the advisory PDF in Phase 6.

**Definition of done**
- `python -m rupantar.cli --help` lists 4 commands (`transform`, `convert`, `selfcheck`, `models`)
- Every artefact Pydantic model round-trips its hand-written example fixture
- `make check` passes green

**Verify:** `make check` → `ruff check` + `ruff format --check` + `mypy src` + `pytest tests/unit` + `pytest tests/inv`

> Freeze `core/artefacts.py` **and `core/schemas.py`** at the end of this phase, and treat `docs/SCHEMAS.md` as their locked spec. Everything downstream depends on them. Changes after this require a `MEMORY.md` deviation entry explaining why.

---

### Phase 1 — Model Manager *(critical path)*

**Build**
- `models/registry.py` — parse `models.yaml`, resolve active profile, verify each model file exists, record size + SHA-256. Missing file → clear actionable error naming `scripts/fetch_models.sh`. **Skip file-existence and SHA-256 checks for any entry whose `runtime` is `stub`.**
- `models/runtime_base.py` — ABC: `start()`, `stop()`, `is_healthy()`, `endpoint`, `class_` (`heavy|light|transient`), `pid`, `rss_bytes`.
- `models/runtime_llama.py` — spawn `llama-server -m <gguf> --port <p> --ctx-size N --host 127.0.0.1`, poll `/health`, `stop()` sends SIGTERM then SIGKILL after 10 s grace.
- `models/runtime_stub.py` — an HTTP echo server; lets the whole system be tested with **zero model files**.
- `models/manager.py`:
  - `async acquire(key) -> Lease` (async context manager), `release()`
  - reference counting; a model with refcount > 0 is never evicted
  - LRU + `idle_ttl_seconds` background reaper
  - enforces `max_heavy_resident`: acquiring a heavy model when one is resident evicts the idle one first, waits for process exit, then starts the new one
  - `status()` → list of `{key, state, pid, port, rss_mb, refcount, loaded_at, last_used}`
  - emits structured events: `LOAD_START`, `LOAD_READY`, `EVICT_START`, `EVICT_DONE` (the UI will subscribe later)
- `api/routes/models.py` — `GET /models`, `GET /models/status`, `POST /models/{key}/unload`

**Definition of done**
- INV-2, INV-7, INV-8 tests pass using `runtime_stub`
- Acquiring `vlm` while `brain` is resident: process table shows brain PID gone **before** the vlm PID appears
- Concurrent `acquire` of the same key from two coroutines starts exactly one process
- Killing a model process externally is detected and the manager recovers on next acquire

**Verify:** `pytest tests/inv/test_single_resident.py tests/inv/test_unload_kills_process.py -q`

---

### Phase 2 — Text generation path

**Build**
- `models/client.py` — async OpenAI-compatible client (`/v1/chat/completions`) against `lease.endpoint`, with `grammar` and `response_format` passthrough, retry-once on connection reset, streaming optional
- ~~`agents/grammar.py` — Pydantic → GBNF~~ **Dropped** (investigation 2026-09-06, `MEMORY.md` §9): a hand-rolled GBNF converter, `response_format: json_object`, `response_format: json_schema`, and *no constraint at all* all generate at the same tok/s, and `ExecutiveSummary` had 0 validation failures unconstrained. `agents/base.py` uses llama-server's native `response_format: json_schema` (built once per agent from `schema.model_json_schema()`); the validate-and-retry-once path covers the Pydantic count/length `field_validator`s that no schema constraint encodes.
- `agents/base.py` — `ArtefactAgent`: renders system+user prompt from template, calls client with a `json_schema` constraint, parses JSON, validates against the Pydantic model, retries once with the validation error appended on failure, then fails the job cleanly.
- `configs/agents/executive_summary.yaml` + its prompt template
- `orchestrator/runner.py` (single-job version)
- `cli`: `rupantar transform --text FILE --output executive_summary`

**Definition of done**
- With stub runtime: agent pipeline runs end to end, validation errors surface as `JobStatus.FAILED` with a readable reason
- With real `brain`: sample article → valid `ExecutiveSummary` JSON in under 90 s on the laptop profile
- INV-6 passes

**Verify:** `pytest tests/integration/test_text_path.py -q`

---

### Phase 3 — All artefact agents

**Build** the remaining six agent configs + prompt templates + schemas:
`advisory`, `linkedin_post`, `x_thread`, `presentation`, `infographic_spec`, `video_package`.

Each config declares: `model_key`, `system_prompt`, `user_template`, `schema` (class path), `max_tokens`, `temperature`, `param_hints` (how audience/tone/language/detail/objective/style are injected).

Also build:
- `orchestrator/planner.py` — request → job list, dedup, dependency edges (e.g. `video_package` may consume `executive_summary` output if present)
- `orchestrator/scheduler.py` — group by `model_key`, order to minimise swaps, stable within group
- `api/routes/transforms.py` — `POST /transforms`, `GET /transforms/{id}`, `GET /transforms/{id}/artefacts`; `api/routes/jobs.py` — `GET /jobs/{id}` (a Transform is the batch, a Job is one artefact)

**Definition of done**
- One request selecting all seven outputs causes **exactly one** `brain` load and zero re-loads (assert on manager events)
- Each artefact validates against its schema
- Scheduler unit test: mixed image+text request produces order `[vlm jobs..., brain jobs...]`

**Verify:** `pytest tests/integration/test_multi_artefact.py -q`

---

### Phase 4 — Renderers

**Build**
- `render/markdown.py` — every artefact gets a `.md` rendering (universal fallback)
- `render/docx_render.py` — advisory + executive summary as Word, with heading styles, classification banner, footer with manifest ID
- `render/pptx_render.py` — presentation with title slide, content slides, speaker notes in the notes pane
- `render/pdf_render.py` — advisory PDF
- `render/svg_render.py` — infographic from `infographic_spec` using a Jinja SVG template (title, 3–5 stat blocks, key messages, footer)
- `render/subtitle.py` — `.srt` from the video package narration with timing estimated at ~2.6 words/second
- `audit/provenance.py` — every write emits `<file>.manifest.json`: source SHA-256, artefact type, model key + file SHA + quant, prompt template version, generation params, timestamps, operator, app version

**Definition of done**
- All renderers import their heavy library **inside** the function (INV-3)
- Generated `.docx`/`.pptx`/`.pdf` open without repair warnings
- INV-5 passes

**Verify:** `pytest tests/integration/test_renderers.py -q` and manually open the three binary outputs once.

---

### Phase 5 — Parivartan (format converter)

**Build**
- `parivartan/registry.py` — `@register(src, dst, label, notes)` decorator, `list_conversions()`, `convert(path, src, dst, opts) -> ConversionReport{rows, warnings, output_path, duration}`
- `parivartan/general.py` — csv, tsv, json, jsonl, xlsx, xml, yaml, parquet (all pairs that make sense; use a common intermediate `list[dict]`)
- `parivartan/cyber.py` — **ship 3 solid, not 6 shaky**:
  1. IOC CSV ↔ STIX 2.1 bundle
  2. Sigma rule YAML → normalised JSON
  3. CEF / syslog line file → JSONL
- `api/routes/convert.py`, `cli convert`

**Definition of done**
- Round-trip property test: `csv → json → csv` preserves rows and column order
- Every converter's heavy import is lazy (INV-3)
- Malformed input produces a `ConversionReport` with warnings, never a traceback to the user

**Verify:** `pytest tests/unit/test_parivartan.py -q`

---

### Phase 6 — Multimodal ingestion

**Build**
- `ingest/text.py` — pdf (pypdf), docx (python-docx), html (selectolax), md, txt
- `ingest/image.py` — acquire `vlm`, caption + OCR-style description, structured `ImageInsight`
- `ingest/audio.py` — acquire `asr`, transcript + segments
- `ingest/video.py` — ffmpeg: N keyframes (default 6, scene-change based) + audio track → images to VLM, audio to ASR
- `ingest/dossier.py` — merge everything into one `SourceDossier` with a `to_prompt_text()` method

**Definition of done**
- A 30-second sample video produces a dossier with keyframe captions and a transcript
- Manager events show: vlm load → vlm evict → asr load → asr evict → brain load. Never two heavy models at once.
- Peak RSS across the whole run stays under 10 GB on the laptop profile (assert in the test)

**Verify:** `pytest tests/integration/test_multimodal.py -q` (marked `slow`, needs real models)

---

### Phase 7 — Video assembly (+ evidence-model additions from Phase 6)

**Build**
- `render/video_render.py` — piper TTS on narration segments → wav; ffmpeg concat storyboard panels (rendered as SVG→PNG) with narration + burned-in subtitles → `.mp4`
- Fallback: if piper or ffmpeg is unavailable, emit script + storyboard + `.srt` only and record a warning in the manifest — **never crash the job**
- **Evidence IDs (deviation from the Phase 0 freeze — see `MEMORY.md`):** every unit in `SourceDossier` (each `TextBlock`, `ImageInsight`, `TranscriptSegment`, `VideoEvent`) carries a stable `evidence_id` (`E1`, `E2`, …) assigned at dossier assembly. `to_prompt_text()` emits `[E1] …`. Each artefact model gains `sources: list[str]` (evidence IDs it draws on); agent prompts instruct the model to populate it. This is the prerequisite for Phase 8.5.
- **Video event timeline:** `ingest/video.py` groups keyframes + transcript segments into `VideoEvent{start, end, transcript, caption, evidence_id}` instead of loose captions; a video-sourced artefact can cite `04:12–05:30`.
- **PDF structure:** `ingest/text.py` uses **PyMuPDF** (`pymupdf`) to keep headings + page numbers — one `TextBlock` per page/section with `page: int`. No Docling / PaddleOCR — the VLM handles OCR.

**Definition of done**
- `video_package` output directory contains: `script.md`, `storyboard.json`, `narration.wav`, `subtitles.srt`, `video.mp4`, `manifest.json`
- The mp4 plays with audio and visible subtitles
- A dossier's blocks have `E1…En`; an artefact populates `sources`; a PDF block carries a `page`

**Verify:** `pytest tests/integration/test_video_package.py -q`

---

### Phase 8.5 — Cross-artefact verification *(runs only after Phase 8 ships)*

**Build** — `audit/verify.py`, run by the orchestrator after every artefact in a transform is generated (before/alongside manifest finalisation):
- **Claim extraction** — one `brain` call per artefact: extract its factual claims as a list.
- **Grounding** — for each claim, check it against the `SourceDossier` evidence (the same `[E1] …` text) → `SUPPORTED` / `UNSUPPORTED`, with the evidence IDs that support it.
- **Cross-artefact consistency** — compare the claim sets across artefacts in the transform → pairs marked `AGREE` / `CONFLICT`.
- Write both results into each artefact's `.manifest.json` (`verification: {claims: [...], conflicts: [...]}`).
- Reuses the single resident `brain` (the artefact-generation lease is still warm) — **one extra brain call per artefact, no new model, no new storage**.

**Definition of done**
- Every manifest in a multi-artefact transform gains a `verification` block.
- A deliberately contradictory pair of artefacts produces a `CONFLICT` entry.
- An unsupported claim is flagged `UNSUPPORTED` with no evidence IDs.

**Verify:** `pytest tests/integration/test_verification.py -q`

---

### Phase 8 — Air-gap, audit, selfcheck

**Build**
- `audit/egress.py`
  - startup: set/assert `HF_HUB_OFFLINE=1`, `TRANSFORMERS_OFFLINE=1`, `NO_PROXY=*`
  - monitor: psutil scan of our process tree's connections; any non-loopback remote → log `EGRESS_VIOLATION` and expose on `GET /health/egress`
  - `--strict-airgap` flag: violation aborts the job
- `audit/selfcheck.py` — the system checker. Produces a table + JSON report + non-zero exit on failure:
  1. Python version (**assert `sys.version_info[:2] == (3, 11)`, fail loudly otherwise**), platform, free RAM, free disk
  2. `ffmpeg`, `llama-server`, `piper` on PATH with versions
  3. Every model file in the active profile: exists, size, SHA-256 matches registry
  4. Ports in range are free
  4b. **Hardware / profile / offload consistency.** Report: detected platform (`platform.system()/machine()`, `nvidia-smi` present?), the chosen profile and how it was chosen (`config.profile_source`: auto-detect vs `RUPANTAR_PROFILE`), and — after a one-token `brain` load — **whether GPU offload is actually active** (query `llama-server /props` / parse startup output for offloaded layer count > 0, or check `n_gpu_layers`). **Fail loudly** when the profile expects GPU (`apple-metal`/`nvidia-cuda`) but offload is 0 — that means a wrong-backend llama.cpp build (CPU-only Homebrew bottle, missing CUDA), the exact class of bug (`--n-gpu-layers 0`) that cost ~2× undetected through Phases 1–3 (see `MEMORY.md` 2026-09-06 perf session). Also warn if `--parallel` is unset, or if `--ctx-size` / `--parallel` gives a slot less context than the largest agent's `max_tokens`.
  5. Model Manager: load `brain`, one-token generation, unload, assert RSS returns to baseline ±200 MB
  6. Each renderer produces a sample file
  7. Each converter round-trips a fixture
  8. Egress: zero non-loopback connections during the whole check
- `scripts/vendor_wheels.sh`, `scripts/fetch_models.sh`, `scripts/demo.sh`
- `README.md` with online-prep → air-gap → run instructions

**Definition of done**
- `python -m rupantar.cli selfcheck` prints a green table on a machine with models present, and a precise red row on a machine without
- Full demo runs with Wi-Fi physically off
- INV-4 passes

**Verify:** `python -m rupantar.cli selfcheck --json > /tmp/sc.json && pytest tests/inv -q`

---

### Phase 9 — Frontend *(deferred, do not start unless PLAN.md is updated)*

Dashboard with source input, output-type checkboxes, generation parameter controls, live job progress, **Model Manager memory visualiser**, artefact downloads, converter panel, egress indicator.

---

## 7. Testing strategy

- **Unit** — pure functions, schemas, converters, grammar generation, scheduler ordering. No models. Must run in under 20 s.
- **Invariant** (`tests/inv/`) — the eight laws. Run on every phase completion. Use `runtime_stub` where possible.
- **Integration** — full paths with `runtime_stub` by default; `-m slow` for the real-model runs.
- **Fixtures** — one canonical set under `tests/fixtures/`; `data/samples/` holds **copies** (not symlinks — Windows and `git archive`), refreshed by `make fixtures`. The set accumulates by phase: Phase 0 ships 2 articles, 1 image, 1 ~30-second video, 7 artefact example JSONs; Phase 5 adds a messy CSV, a Sigma rule, a CEF log sample; Phase 6 adds an advisory PDF.

`make check` = `ruff check` + `ruff format --check` + `mypy src` + `pytest tests/unit` + `pytest tests/inv`.
`make check-all` = the above + integration (stub).
`make check-real` = everything including `-m slow`.
This is the one definition of `make check`; the Phase 0 verify line and `CLAUDE.md` must match it verbatim.

---

## 8. Demo path (build toward this)

```
scripts/demo.sh
  1. selfcheck                                → green table, egress zero
  2. transform --text tests/fixtures/articles/ai_policy_brief.md \
       --output executive_summary,advisory,linkedin_post,x_thread,presentation
                                              → one brain load, five artefacts, five manifests
  3. transform sample_with_image/             → visible vlm load → evict → brain load
  4. transform sample_video.mp4 --output video_package
                                              → real .mp4 with narration + subtitles
  5. convert iocs.csv --to stix21             → STIX bundle
  6. models status                            → memory table
```

Every step must be non-interactive and complete without network.

---

## 9. Rules for Claude Code

1. **Read `MEMORY.md` at the start of every session. Update it at the end of every session.** No exceptions.
2. Work **one phase at a time**. Do not begin phase N+1 until phase N's verify command passes and `verifier` reports green.
3. Before writing code for a phase, restate its Definition of Done in your own words and list the files you will create.
4. Prefer many small files over few large ones. No file over 400 lines.
5. Every public function gets a type hint and a one-line docstring. No inline commentary explaining obvious code.
6. When something in this plan turns out to be wrong or impossible, **do not silently work around it**. Record it in `MEMORY.md` under Deviations with the reason, and continue with the closest workable alternative.
7. Never introduce a dependency outside `requirements.txt` without recording it.
8. Never load a model outside `ModelManager.acquire()`.
9. If a test is failing and you cannot fix it in three attempts, mark it `xfail` with a reason, log it in `MEMORY.md` under Blockers, and move on.
10. Commit after each phase on the `main` branch with message `phase-N: <summary>`. No per-phase branches — the per-phase commits are the checkpoints.
