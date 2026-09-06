# Rupantar

Offline, air-gapped AI content transformation engine for NTRO / SIH. Source content in,
communication artefacts out. Target hardware: a 16 GB laptop with the network physically off.

Subsystems: `rupantar` (platform) and `parivartan` (format converter).

## Status

Phases 0–4 done: contracts, model manager, text generation, all seven artefact agents,
the API, and the renderers. See `MEMORY.md` for current state.

## Development

```bash
uv pip install -e ".[dev]"
make check        # ruff + mypy + unit + invariant tests
python -m rupantar.cli --help
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
and the GPU sits idle. Phase 8 `selfcheck` verifies offload is actually active.

See `PLAN.md` for the phase plan and `docs/SCHEMAS.md` for the frozen contracts.
Full online-prep -> air-gap -> run instructions arrive in Phase 8.
