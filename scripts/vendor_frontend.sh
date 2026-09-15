#!/usr/bin/env bash
# Build the operator console and prove the output is air-gap safe.
#
# The demo machine never runs `npm ci` and never starts a node process: it serves the
# committed `frontend/dist/` from the FastAPI app on one port. This script produces that
# dist/ on a machine that has node, and then gates it — a bundle that would reach for a
# remote asset at runtime fails the build here rather than failing INV-4 on the day.
#
# Run this online (or with node_modules already present), then commit frontend/dist/.
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
FRONTEND="${REPO_ROOT}/frontend"
DIST="${FRONTEND}/dist"

command -v npm >/dev/null || { echo "npm not found -- needed to build the console" >&2; exit 1; }

echo "==> Building the console"
cd "${FRONTEND}"
[ -d node_modules ] || npm ci
npm run build

[ -f "${DIST}/index.html" ] || { echo "build produced no ${DIST}/index.html" >&2; exit 1; }

# --- air-gap gate -----------------------------------------------------------------
# Two separate checks, because a bare URL grep cannot tell a fetch from a string.
#
# 1. Fetch vectors: every CSS url(), and every src/href in index.html, must be
#    same-origin. These are the constructs a browser actually dereferences.
# 2. Remote URL literals: anything else is compared against a documented allowlist of
#    strings that are provably never fetched (XML namespace URIs, library error-message
#    links, the font licence, react-router's internal `new URL()` base). A URL outside
#    that list is a genuine finding and fails the build. Each entry below was checked
#    in the built bundle and is advice text or a namespace URI, never dereferenced:
#    ungap/url-search-params is inside react-router's IE11 polyfill warning string.
#    Radix Dialog's docs URL is console-error advice for a missing accessible title
#    (react-dialog/dist/index.mjs, TitleWarning). It is never fetched or rendered.

echo "==> Checking fetch vectors are same-origin"
fail=0

while IFS= read -r ref; do
  case "${ref}" in
    url\(/*|url\(\"/*|url\(\'/*|url\(data:*|url\(\"data:*|url\(#*) ;;
    *) echo "  REMOTE CSS ASSET: ${ref}" >&2; fail=1 ;;
  esac
done < <(grep -rhoE 'url\([^)]*\)' "${DIST}" --include='*.css' || true)

while IFS= read -r ref; do
  case "${ref}" in
    *=\"/*|*=\"./*|*=\"data:*|*=\"#*) ;;
    *) echo "  REMOTE HTML ASSET: ${ref}" >&2; fail=1 ;;
  esac
done < <(grep -ohE '(src|href)="[^"]*"' "${DIST}/index.html" || true)

echo "==> Checking for unexpected remote URLs"
ALLOWED='://(localhost|127\.0\.0\.1)|www\.w3\.org|scripts\.sil\.org/OFL|github\.com/rsms/inter|github\.com/ungap/url-search-params|reactjs\.org/docs/error-decoder|reactrouter\.com/|tailwindcss\.com|radix-ui\.com/primitives/docs/components/'

while IFS= read -r url; do
  echo "  UNEXPECTED REMOTE URL: ${url}" >&2
  fail=1
done < <(grep -rhoE 'https?://[a-zA-Z0-9._:/-]+' "${DIST}" 2>/dev/null \
          | sort -u | grep -vE "${ALLOWED}" || true)

if [ "${fail}" -ne 0 ]; then
  echo >&2
  echo "Air-gap check FAILED. The console must not reference a remote asset (INV-4)." >&2
  echo "Vendor the asset into frontend/public/ and rebuild, or extend the allowlist above" >&2
  echo "only if the URL is provably a string literal that is never dereferenced." >&2
  exit 1
fi

echo
echo "Air-gap check passed. Bundle:"
du -sh "${DIST}" | awk '{print "  dist total: " $1}'
find "${DIST}/assets" -name '*.js' -o -name '*.css' | while read -r f; do
  printf '  %8s  %s\n' "$(du -h "${f}" | cut -f1)" "${f#"${DIST}/"}"
done

echo
echo "Commit frontend/dist/ so the air-gapped machine serves it without building."
