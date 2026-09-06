#!/usr/bin/env bash
# Scripted, non-interactive, offline demo (PLAN.md section 8). Needs all four models on disk
# and llama-server / ffmpeg / piper on PATH. Runs entirely without network.
set -euo pipefail

cd "$(dirname "$0")/.."

PY="python"
[[ -x .venv/bin/python ]] && PY=".venv/bin/python"
RUN=("$PY" -m rupantar.cli)

ART="tests/fixtures/articles/ai_policy_brief.md"
IMG="tests/fixtures/media/sample_image.png"
VID="tests/fixtures/media/sample_clip.mp4"
IOCS="tests/fixtures/parivartan/iocs.csv"
OUT="data/outputs/demo"
rm -rf "$OUT"

hr() { printf '\n=== %s ===\n' "$1"; }

hr "1/6  selfcheck (green table, egress zero)"
"${RUN[@]}" selfcheck

hr "2/6  five artefacts from one article -> one brain load, five manifests"
"${RUN[@]}" transform --text "$ART" \
  --output executive_summary,advisory,linkedin_post,x_thread,presentation \
  --out-dir "$OUT/article"

hr "3/6  image source -> vlm load -> evict -> brain load"
"${RUN[@]}" transform --source "$IMG" --source "$ART" \
  --output executive_summary --out-dir "$OUT/image"

hr "4/6  30-second video -> video_package (.mp4 with narration + subtitles)"
"${RUN[@]}" transform --source "$VID" --output video_package --out-dir "$OUT/video"

hr "5/6  convert IOC CSV -> STIX 2.1 bundle"
"${RUN[@]}" convert "$IOCS" --from ioc-csv --to stix21 --out "$OUT/iocs.stix21.json"

hr "6/6  model residency table"
"${RUN[@]}" models status

hr "done"
echo "artefacts + manifests under: $OUT"
find "$OUT" -name '*.manifest.json' | sort
