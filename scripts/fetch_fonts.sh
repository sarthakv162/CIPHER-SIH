#!/usr/bin/env bash
# Fetch the self-hosted UI webfont. ONLINE PREP ONLY -- never called by application code.
#
# The console vendors Inter as woff2 files committed to the repo, so the air-gapped machine
# never resolves fonts.googleapis.com or any other host at runtime (INV-4). This script only
# needs re-running to change the font or bump its version; the files are already committed.
#
# Weights 400 and 500 only, latin subset -- the design system forbids 600/700.
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
DEST="${REPO_ROOT}/frontend/public/fonts"
PKG="@fontsource/inter@5.3.0"

EXPECTED_400="8909904ab6c872eb994093482a88a28eca2cd95912d7b6fecd72103b0dc07edc"
EXPECTED_500="f3779f1efccc4bdcdf9c0a02ab95bf6bd092ed09c48c08cedc725889edd1d19f"

command -v npm >/dev/null || { echo "npm not found -- needed for the one-time font fetch" >&2; exit 1; }

STAGE="$(mktemp -d)"
trap 'rm -rf "${STAGE}"' EXIT

echo "Fetching ${PKG} into a staging dir (online step)..."
(cd "${STAGE}" && npm init -y >/dev/null 2>&1 && npm install --no-audit --no-fund "${PKG}" >/dev/null)

SRC="${STAGE}/node_modules/@fontsource/inter"
mkdir -p "${DEST}"
cp "${SRC}/files/inter-latin-400-normal.woff2" "${DEST}/"
cp "${SRC}/files/inter-latin-500-normal.woff2" "${DEST}/"
cp "${SRC}/LICENSE" "${DEST}/LICENSE-Inter.txt"

verify() {
  local file="$1" expected="$2" actual
  actual="$(shasum -a 256 "${file}" | awk '{print $1}')"
  if [ "${actual}" != "${expected}" ]; then
    echo "SHA-256 mismatch for ${file}" >&2
    echo "  expected ${expected}" >&2
    echo "  actual   ${actual}" >&2
    echo "The upstream package changed. Review the diff, then update the expected hash here." >&2
    exit 1
  fi
}

verify "${DEST}/inter-latin-400-normal.woff2" "${EXPECTED_400}"
verify "${DEST}/inter-latin-500-normal.woff2" "${EXPECTED_500}"

echo "Vendored Inter 400/500 (latin, woff2) into ${DEST} -- SHA-256 verified."
echo "Inter is SIL OFL 1.1; LICENSE-Inter.txt ships beside the fonts. Commit these files."
