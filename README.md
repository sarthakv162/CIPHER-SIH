# Rupantar

Offline, air-gapped AI content transformation engine for NTRO / SIH. Source content in
(text, document, image, audio, video, or a free-form prompt), communication artefacts out
(executive summary, advisory, LinkedIn post, X thread, presentation, infographic spec, video
package). Runs on a 16 GB laptop with the network physically off, with **exactly one heavy
model resident in memory at a time**.

Subsystems: `rupantar` (platform) and `parivartan` (format converter).

## Status

Phases 0–8 done: frozen contracts, model manager (one heavy model, child processes, SIGTERM
unload), text generation, all seven artefact agents, the API, renderers, Parivartan
converters, multimodal ingestion, video assembly, and the air-gap / audit / `selfcheck`
layer. Phase 9 (frontend) is deferred. See `MEMORY.md` for the live state and `PLAN.md` for
the plan.

---

## 1. Online prep (do this once, with the network on)

```bash
# 1. Python 3.11 exactly — the vendored wheels target 3.11.
uv python install 3.11
uv venv --python 3.11 && source .venv/bin/activate

# 2. Vendor the whole dependency closure as wheels + write requirements-lock.txt.
#    Run this on the SAME OS/arch as the air-gapped laptop.
PYTHON=$(uv python find 3.11) scripts/vendor_wheels.sh

# 3. Fetch the four model files (~7 GB) into models/.
scripts/fetch_models.sh

# 4. Install the project and verify everything.
uv pip install -e ".[dev]"
python -m rupantar.cli selfcheck        # expect an all-green table
```

`selfcheck` hashes every model file against `configs/models.yaml`, boots the brain once to
confirm GPU offload is actually active, load/unloads it to prove memory is reclaimed, and
scans this process tree for any non-loopback connection.

## 2. Cut the network

Physically disconnect. Nothing below touches the network — `selfcheck` check 8 and the
`INV-4` test prove it, and every process sets `HF_HUB_OFFLINE=1` / `TRANSFORMERS_OFFLINE=1`
at startup.

## 3. Run (offline)

```bash
# Install from the vendored wheels — no index, no network.
pip install --no-index --find-links vendor/wheels -r requirements-lock.txt
pip install --no-index --no-deps -e .

python -m rupantar.cli selfcheck                 # still green with the network off
scripts/demo.sh                                  # the full scripted demo (PLAN.md section 8)

# one transform
python -m rupantar.cli transform --text article.md \
  --output executive_summary,advisory,linkedin_post

# a multimodal transform
python -m rupantar.cli transform --source clip.mp4 --output video_package

# strict air-gap: abort a job if a non-loopback connection appears
python -m rupantar.cli transform --text article.md --output advisory --strict-airgap

# the API (single worker)
uvicorn rupantar.api.app:create_app --factory --host 127.0.0.1 --port 8000
#   GET /health         GET /health/egress
#   POST /transforms    GET /transforms/{id}    GET /transforms/{id}/artefacts
#   GET  /models         POST /convert
```

Every artefact written to disk gets a sibling `<name>.manifest.json` with the source SHA-256,
model file SHA + quant, prompt version, generation params, and timestamps.

## 4. Development

```bash
make check        # ruff check + ruff format --check + mypy src + pytest tests/unit + pytest tests/inv
make check-all    # + integration tests with the stub runtime
make check-real   # + slow tests that need real model files
python -m rupantar.cli selfcheck        # full system health report
python -m rupantar.cli models status    # resident models and memory
```

## Hardware profiles

The hardware profile is selected automatically at startup and logged at INFO:

| detected                          | profile       | llama.cpp needs |
|-----------------------------------|---------------|-----------------|
| macOS on Apple Silicon            | `apple-metal` | a Metal build (`brew install llama.cpp` gives this) |
| `nvidia-smi` on PATH              | `nvidia-cuda` | a **CUDA build** — a plain build ignores the GPU |
| anything else                     | `cpu-only`    | any build (slow: `-ngl 0`, ~2× slower than GPU) |

`RUPANTAR_PROFILE=<name>` forces a profile (`titan-24gb` for the 24 GB-GPU tier, `test-stub`
for tests). If detection is unsure it falls back to `cpu-only` and says so loudly in the log.

**The llama.cpp binary must be built for the right backend.** `brew install llama.cpp` on macOS
is Metal-enabled. On Linux with an NVIDIA GPU you need a CUDA-compiled `llama-server` (build with
`-DGGML_CUDA=ON`, or use a CUDA release binary) — otherwise `--n-gpu-layers 99` is a silent no-op
and the GPU sits idle. `selfcheck` check 4b boots the brain with `-v`, reads the
`offloaded N/M layers to GPU` line, and **fails loudly** when a GPU profile offloads 0 layers.

See `PLAN.md` for the phase plan and `docs/SCHEMAS.md` for the frozen contracts.
