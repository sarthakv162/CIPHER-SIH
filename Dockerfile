# syntax=docker/dockerfile:1.7
#
# Rupantar — one image holding the API, the operator console, and every model runtime binary.
#
#   docker compose build        # online, once
#   make docker-save            # -> vendor/rupantar-images.tar.gz for the air-gapped machine
#   docker compose up -d        # offline; console at http://127.0.0.1:8000/
#
# Model weights are NOT baked in: ./models is mounted read-only at run time (scripts/fetch_models.sh
# fills it). Models still run as child processes of the API (llama-server, the whisper worker,
# piper) inside this one container, so unloading stays a process kill (CLAUDE.md, the one rule).
#
# Inside Linux there is no Metal: the profile auto-detects to `cpu-only`. llama.cpp is built with
# every CPU variant and picks the best one for the host at run time.

ARG PYTHON_IMAGE=python:3.11-slim-trixie
ARG LLAMA_CPP_TAG=b10809
ARG UV_VERSION=0.11.29

# --- llama-server ---------------------------------------------------------------------------
FROM debian:trixie-slim AS llama
ARG LLAMA_CPP_TAG
RUN apt-get update && apt-get install -y --no-install-recommends \
        build-essential cmake git ca-certificates \
    && rm -rf /var/lib/apt/lists/*
RUN git clone --depth 1 --branch "${LLAMA_CPP_TAG}" https://github.com/ggml-org/llama.cpp /src
WORKDIR /src
# LLAMA_CURL=OFF: the binary cannot download a model even if asked (air-gap).
RUN cmake -B build \
        -DCMAKE_BUILD_TYPE=Release \
        -DBUILD_SHARED_LIBS=ON \
        -DGGML_NATIVE=OFF \
        -DGGML_BACKEND_DL=ON \
        -DGGML_CPU_ALL_VARIANTS=ON \
        -DLLAMA_CURL=OFF \
        -DLLAMA_BUILD_TESTS=OFF \
        -DLLAMA_BUILD_EXAMPLES=OFF \
    && cmake --build build --config Release -j"$(nproc)" --target llama-server \
    && mkdir -p /opt/llama \
    && cp -a build/bin/llama-server build/bin/*.so* /opt/llama/ \
    && /opt/llama/llama-server --version

# --- operator console -----------------------------------------------------------------------
FROM node:20-trixie-slim AS console
WORKDIR /repo
COPY frontend/package.json frontend/package-lock.json frontend/
RUN cd frontend && npm ci --no-audit --no-fund
COPY frontend/ frontend/
COPY scripts/vendor_frontend.sh scripts/
# Builds dist/ AND runs the same-origin / remote-URL air-gap gate; a CDN reference fails here.
RUN bash scripts/vendor_frontend.sh

# --- python environment ---------------------------------------------------------------------
FROM ghcr.io/astral-sh/uv:${UV_VERSION} AS uv
FROM ${PYTHON_IMAGE} AS pydeps
COPY --from=uv /uv /usr/local/bin/uv
RUN apt-get update && apt-get install -y --no-install-recommends build-essential \
    && rm -rf /var/lib/apt/lists/*
ENV UV_PROJECT_ENVIRONMENT=/opt/venv \
    UV_PYTHON_DOWNLOADS=never \
    UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy
WORKDIR /app
COPY pyproject.toml uv.lock README.md .python-version ./
RUN --mount=type=cache,target=/root/.cache/uv uv sync --frozen --no-dev --no-install-project
COPY src/ src/
RUN --mount=type=cache,target=/root/.cache/uv uv sync --frozen --no-dev --no-editable

# --- runtime --------------------------------------------------------------------------------
FROM ${PYTHON_IMAGE} AS runtime
ARG UID=1000
RUN apt-get update && apt-get install -y --no-install-recommends \
        ffmpeg fonts-dejavu-core libgomp1 tini \
    && rm -rf /var/lib/apt/lists/* \
    && useradd --create-home --uid "${UID}" rupantar
COPY --from=llama /opt/llama /opt/llama
COPY --from=pydeps /opt/venv /opt/venv
WORKDIR /app
COPY configs/ configs/
COPY scripts/ scripts/
COPY --from=console /repo/frontend/dist frontend/dist
RUN mkdir -p models data/outputs data/uploads data/samples data/qa_sessions \
    && chown -R rupantar:rupantar data
ENV PATH=/opt/venv/bin:/opt/llama:$PATH \
    LD_LIBRARY_PATH=/opt/llama \
    PYTHONUNBUFFERED=1 \
    HF_HUB_OFFLINE=1 \
    TRANSFORMERS_OFFLINE=1 \
    HF_HUB_DISABLE_TELEMETRY=1
USER rupantar
EXPOSE 8000
HEALTHCHECK --interval=15s --timeout=5s --start-period=20s --retries=5 \
    CMD ["python", "-c", "import urllib.request as u; u.urlopen('http://127.0.0.1:8000/health', timeout=4)"]
ENTRYPOINT ["/usr/bin/tini", "--"]
# One worker, always: the ModelManager is per-process and enforces single heavy residency.
CMD ["uvicorn", "rupantar.api.app:create_app", "--factory", "--host", "0.0.0.0", "--port", "8000", "--workers", "1"]

# --- test lane: `make check` inside the image (docker build --target test .) ----------------
FROM runtime AS test
USER root
COPY --from=uv /uv /usr/local/bin/uv
RUN apt-get update && apt-get install -y --no-install-recommends make \
    && rm -rf /var/lib/apt/lists/*
COPY pyproject.toml uv.lock README.md .python-version Makefile ./
COPY src/ src/
COPY tests/ tests/
ENV UV_PROJECT_ENVIRONMENT=/opt/venv UV_PYTHON_DOWNLOADS=never
RUN uv sync --frozen --extra dev && chown -R rupantar:rupantar /app
USER rupantar
CMD ["make", "check", "PYTHON=python"]
