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

# 先证明线上发布的 HTML 就是当前 commit，再渲染同一份本地代码，避免大 GLB 从 GitHub Pages
# 下载过慢拖垮视觉验证。两类证据缺一不可：发布一致性 + 真实画面。
ONLINE_HTML="${RESULT_JSON%.json}-online.html"
PUBLISHED_URL="${URL}${URL//*\?*/&}autoloop_ts=$(date +%s)"
if [[ "${URL}" != *"?"* ]]; then
  PUBLISHED_URL="${URL}?autoloop_ts=$(date +%s)"
fi
curl --fail --location --silent --show-error --max-time 30 \
  -H "Cache-Control: no-cache" -H "Pragma: no-cache" \
  "${PUBLISHED_URL}" -o "${ONLINE_HTML}"
CURL_RC=$?
if [ "${CURL_RC}" -ne 0 ]; then
  printf '{"status":"failed","reason":"online html fetch failed","curl_rc":%s,"url":"%s"}\n' \
    "${CURL_RC}" "${PUBLISHED_URL}" > "${RESULT_JSON}"
  exit "${CURL_RC}"
fi

LOCAL_SHA256="$(sha256sum "${REPO_DIR}/index.html" | awk '{print $1}')"
ONLINE_SHA256="$(sha256sum "${ONLINE_HTML}" | awk '{print $1}')"
ONLINE_HTML_MATCH=false
[ "${LOCAL_SHA256}" = "${ONLINE_SHA256}" ] && ONLINE_HTML_MATCH=true

LOCAL_PORT="${AUTOLOOP_VERIFY_PORT:-18123}"
timeout 90s python3 -m http.server "${LOCAL_PORT}" --directory "${REPO_DIR}" \
  > "${RESULT_JSON%.json}-server.log" 2>&1 &
for _ in 1 2 3 4 5 6 7 8 9 10; do
  curl --silent --fail "http://127.0.0.1:${LOCAL_PORT}/" >/dev/null 2>&1 && break
  sleep 1
done

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
PUBLISHED_URL="${PUBLISHED_URL}" \
ONLINE_HTML_MATCH="${ONLINE_HTML_MATCH}" \
LOCAL_SHA256="${LOCAL_SHA256}" \
ONLINE_SHA256="${ONLINE_SHA256}" \
timeout 60s node "${ENGINE_DIR}/verify_web.js" \
  "http://127.0.0.1:${LOCAL_PORT}/" "${SCREENSHOT}" "${RESULT_JSON}"
VERIFY_RC=$?

if [ "${VERIFY_RC}" -eq 124 ]; then
  printf '{\n  "status": "timeout",\n  "timeout_seconds": 60,\n  "url": "%s"\n}\n' "${URL}" > "${RESULT_JSON}"
fi

cd "${REPO_DIR}" || true
exit "${VERIFY_RC}"
