# Rupantar

Offline, air-gapped AI content transformation engine for NTRO / SIH. Source content in,
communication artefacts out. Target hardware: a 16 GB laptop with the network physically off.

Subsystems: `rupantar` (platform) and `parivartan` (format converter).

## Status

Phase 0 — scaffold and frozen contracts. No models yet.

## Development

```bash
uv pip install -e ".[dev]"
make check        # ruff + mypy + unit + invariant tests
python -m rupantar.cli --help
```

See `PLAN.md` for the phase plan and `docs/SCHEMAS.md` for the frozen request/artefact contracts.
Full online-prep -> air-gap -> run instructions arrive in Phase 8.
