#!/usr/bin/env bash
set -uo pipefail

ENGINE_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_DIR="$(cd "${ENGINE_DIR}/../.." && pwd)"
CACHE_ROOT="${AUTOLOOP_BROWSER_CACHE:-${HOME}/.cache/autoloop-browser}"
PLAYWRIGHT_ROOT="${CACHE_ROOT}/playwright"
BROWSER_ROOT="${CACHE_ROOT}/browsers"
LIB_ROOT="${CACHE_ROOT}/runtime-libs"
PACKAGE_ROOT="${CACHE_ROOT}/packages"

URL="${1:?usage: verify_web.sh <url> <screenshot-path> <result-json>}"
SCREENSHOT="${2:?missing screenshot path}"
RESULT_JSON="${3:?missing result json path}"

mkdir -p "${PLAYWRIGHT_ROOT}" "${BROWSER_ROOT}" "${LIB_ROOT}" "${PACKAGE_ROOT}"
mkdir -p "$(dirname "${SCREENSHOT}")" "$(dirname "${RESULT_JSON}")"

if [ ! -f "${PLAYWRIGHT_ROOT}/node_modules/playwright/package.json" ]; then
  npm install --prefix "${PLAYWRIGHT_ROOT}" playwright@1.54.2
fi

if ! find "${BROWSER_ROOT}" -type f -name chrome -print -quit 2>/dev/null | grep -q .; then
  PLAYWRIGHT_BROWSERS_PATH="${BROWSER_ROOT}" \
    "${PLAYWRIGHT_ROOT}/node_modules/.bin/playwright" install chromium
fi

if [ ! -f "${LIB_ROOT}/usr/lib/x86_64-linux-gnu/libgbm.so.1" ] ||
   [ ! -f "${LIB_ROOT}/usr/lib/x86_64-linux-gnu/libwayland-server.so.0" ]; then
  (
    cd "${PACKAGE_ROOT}" || exit 1
    apt-get download libgbm1 libwayland-server0
    for package in ./*.deb; do
      [ -f "${package}" ] && dpkg-deb -x "${package}" "${LIB_ROOT}"
    done
  )
fi

PLAYWRIGHT_MODULE="${PLAYWRIGHT_ROOT}/node_modules/playwright" \
PLAYWRIGHT_BROWSERS_PATH="${BROWSER_ROOT}" \
LD_LIBRARY_PATH="${LIB_ROOT}/usr/lib/x86_64-linux-gnu${LD_LIBRARY_PATH:+:${LD_LIBRARY_PATH}}" \
timeout 60s node "${ENGINE_DIR}/verify_web.js" \
  "${URL}" "${SCREENSHOT}" "${RESULT_JSON}"
VERIFY_RC=$?

if [ "${VERIFY_RC}" -eq 124 ]; then
  printf '{\n  "status": "timeout",\n  "timeout_seconds": 60,\n  "url": "%s"\n}\n' "${URL}" > "${RESULT_JSON}"
fi

cd "${REPO_DIR}" || true
exit "${VERIFY_RC}"
