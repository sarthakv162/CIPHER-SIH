# CLAUDE.md — Rupantar

## Session start ritual — do this before anything else

1. Read `MEMORY.md` in full.
2. Read the section of `PLAN.md` for the current phase named in `MEMORY.md`.
3. State in one short paragraph: current phase, what the last session finished, what you are about to do.
4. Then start work.

Do not read the whole codebase to "get oriented". `MEMORY.md` plus the current phase is enough context. Use the `Explore` capability or `Grep` for specific files when you need them.

## Session end ritual — do this before you stop

1. Run the current phase's verify command from `PLAN.md`.
2. Update `MEMORY.md`: project state table, phase ledger, invariant status, any deviations, blockers, new environment facts, and a new session log block.
3. Commit with `phase-N: <summary>`.

If the session is ending because of context limits, the `MEMORY.md` update is the highest-priority remaining action. Do it before anything else.

## What this project is

An offline, air-gapped AI content transformation engine for NTRO / SIH. Source content in, communication artefacts out. Target hardware is a 16 GB laptop. See `PLAN.md`.

## The one rule that matters most

**Exactly one heavy model is resident in memory at a time, and models live in child processes so that unloading is a process kill, not a garbage-collection hope.**

Any code that loads a model with `transformers`, `torch`, `AutoModel`, or similar inside the API process is wrong, even if it works on your machine. `ModelManager.acquire()` is the only path that starts a model.

## Working agreement

- One phase at a time. Do not start phase N+1 until phase N's verify command passes.
- Before coding a phase, restate its Definition of Done and list the files you will create.
- Use the `builder` subagent for phase implementation, `verifier` for health checks, and `arch-guard` before every commit.
- No file over 400 lines. No function over 60 lines.
- Type hints on every public function. One-line docstrings. No comments restating the code.
- New dependency → add to `requirements.txt` AND record it in `MEMORY.md`.
- Python 3.11 exactly. Managed with `uv` (`uv python install 3.11`), pinned in `.python-version`. Do not run or test under any other version — vendored wheels for the air-gapped laptop are built for 3.11.
- `core/artefacts.py` and `core/schemas.py` are frozen after Phase 0; `docs/SCHEMAS.md` is their locked spec. Read it before touching either. Changing a frozen contract requires a `MEMORY.md` deviation entry.
- Stuck after three attempts → `xfail` the test with a reason, log a blocker in `MEMORY.md`, move on. Do not burn a session on one bug.
- Never invent a workaround for a plan requirement. Record the deviation.

## Do not build

Knowledge graph, Neo4j, vector RAG, embeddings, re-rankers, ChromaDB, video RAG, digital twin, fine-tuning, frontend polish. If a task seems to need one, write it under Open Questions in `MEMORY.md` instead.

## Commands

```bash
make check        # ruff check + ruff format --check + mypy src + pytest tests/unit + pytest tests/inv
make check-all    # + integration tests with stub runtime
make check-real   # + slow tests that need real model files
python -m rupantar.cli selfcheck        # full system health report
python -m rupantar.cli models status    # resident models and memory
```

`make check` has exactly one definition, shared verbatim by `PLAN.md` §7 and the Phase 0 verify line.

## Offline discipline

This project must run with the network physically off. Never add code that downloads at runtime. Model and wheel acquisition happens only in `scripts/fetch_models.sh` and `scripts/vendor_wheels.sh`, which are run once while online and never called by application code.
