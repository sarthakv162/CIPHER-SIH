#!/usr/bin/env bash
# Fetch every model file Rupantar needs. Run ONCE while online, before air-gapping.
# Downloads into models/<key>/ with the flat filenames configs/models.yaml expects,
# then deletes the HuggingFace .cache dirs. Verify with: python -m rupantar.cli selfcheck
set -euo pipefail

cd "$(dirname "$0")/.."
MODELS_DIR="models"

if command -v hf >/dev/null 2>&1; then
  HF=(hf download)
elif command -v huggingface-cli >/dev/null 2>&1; then
  HF=(huggingface-cli download)
else
  echo "error: neither 'hf' nor 'huggingface-cli' is on PATH." >&2
  echo "       pip install 'huggingface_hub[cli]' (online), then re-run this script." >&2
  exit 1
fi

fetch() {
  # fetch <repo_id> <dest_dir> <file> [file...]
  local repo="$1" dest="$2"
  shift 2
  mkdir -p "$dest"
  "${HF[@]}" "$repo" "$@" --local-dir "$dest"
}

flatten() {
  # move a nested downloaded file to the flat path models.yaml expects
  local src="$1" dst="$2"
  if [[ -f "$src" && "$src" != "$dst" ]]; then
    mv -f "$src" "$dst"
  fi
}

echo "==> brain: unsloth/Qwen3-4B-Instruct-2507-GGUF"
fetch unsloth/Qwen3-4B-Instruct-2507-GGUF "$MODELS_DIR/brain" \
  Qwen3-4B-Instruct-2507-Q4_K_M.gguf

echo "==> vlm: unsloth/Qwen2.5-VL-3B-Instruct-GGUF"
fetch unsloth/Qwen2.5-VL-3B-Instruct-GGUF "$MODELS_DIR/vlm" \
  Qwen2.5-VL-3B-Instruct-Q4_K_M.gguf mmproj-F16.gguf

echo "==> asr: Systran/faster-whisper-small.en (whole repo)"
fetch Systran/faster-whisper-small.en "$MODELS_DIR/asr/faster-whisper-small.en-int8"

echo "==> tts: rhasspy/piper-voices (en_US-lessac-medium)"
fetch rhasspy/piper-voices "$MODELS_DIR/tts" \
  en/en_US/lessac/medium/en_US-lessac-medium.onnx \
  en/en_US/lessac/medium/en_US-lessac-medium.onnx.json
flatten "$MODELS_DIR/tts/en/en_US/lessac/medium/en_US-lessac-medium.onnx" \
        "$MODELS_DIR/tts/en_US-lessac-medium.onnx"
flatten "$MODELS_DIR/tts/en/en_US/lessac/medium/en_US-lessac-medium.onnx.json" \
        "$MODELS_DIR/tts/en_US-lessac-medium.onnx.json"

echo "==> cleaning HuggingFace .cache dirs and empty nested dirs"
find "$MODELS_DIR" -type d -name ".cache" -prune -exec rm -rf {} +
rm -rf "$MODELS_DIR/tts/en"

echo
echo "resulting tree:"
find "$MODELS_DIR" -type f | sort
echo
echo "next: run 'python -m rupantar.cli selfcheck' to verify sizes and SHA-256 sums."
