#!/usr/bin/env bash
# Regenerate the binary test fixtures (image + short video) with ffmpeg.
# Run once, online or offline; ffmpeg must be on PATH. Text and JSON fixtures are hand-written.
set -euo pipefail

here="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
media="${here}/tests/fixtures/media"
mkdir -p "${media}"

if ! command -v ffmpeg >/dev/null 2>&1; then
  echo "ffmpeg not found on PATH" >&2
  exit 1
fi

ffmpeg -y -f lavfi -i "testsrc=size=640x360:rate=1:duration=1" \
  -frames:v 1 -pix_fmt rgb24 "${media}/sample_image.png"

ffmpeg -y -f lavfi -i "testsrc=size=640x360:rate=15:duration=30" \
  -f lavfi -i "sine=frequency=220:duration=30" \
  -shortest -pix_fmt yuv420p -c:v libx264 -preset veryfast -c:a aac \
  "${media}/sample_clip.mp4"

echo "wrote ${media}/sample_image.png and ${media}/sample_clip.mp4"
