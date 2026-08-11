#!/usr/bin/env bash
set -uo pipefail

ENGINE_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
AUTOLOOP_DIR="$(cd "${ENGINE_DIR}/.." && pwd)"
REPO_DIR="$(cd "${AUTOLOOP_DIR}/.." && pwd)"
OUTPUT="${1:?usage: preflight.sh <output-json>}"

export PATH="${HOME}/.local/bin:${HOME}/.npm-global/bin:${PATH}"
TRAE_CLI="${AUTOLOOP_TRAE_CLI:-${HOME}/.local/bin/trae-cli}"
LARK_CLI="${AUTOLOOP_LARK_CLI:-${HOME}/.npm-global/bin/lark-cli}"
DOC_ID="$(node -e 'const fs=require("fs"); console.log(JSON.parse(fs.readFileSync(process.argv[1],"utf8")).document_id)' \
  "${AUTOLOOP_DIR}/feishu.json" 2>/dev/null || true)"

mkdir -p "$(dirname "${OUTPUT}")"
WORK_DIR="$(dirname "${OUTPUT}")"
FAILED=0

check() {
  local name="$1"
  shift
  if "$@" > "${WORK_DIR}/preflight-${name}.log" 2>&1; then
    printf '%s=passed\n' "${name}" >> "${WORK_DIR}/preflight-status.txt"
  else
    printf '%s=failed\n' "${name}" >> "${WORK_DIR}/preflight-status.txt"
    FAILED=1
  fi
}

: > "${WORK_DIR}/preflight-status.txt"
check bwrap sh -c 'command -v bwrap >/dev/null && bwrap --version >/dev/null'
check trae_login timeout 20s "${TRAE_CLI}" login status
check trae_sandbox timeout 20s "${TRAE_CLI}" sandbox linux -- true
check github timeout 20s git -C "${REPO_DIR}" ls-remote origin refs/heads/main
check feishu timeout 20s "${LARK_CLI}" docs +fetch --as user --doc "${DOC_ID}" \
  --scope keyword --keyword AutoLoop --format json
check disk sh -c 'test "$(df -P "$1" | awk "NR==2 {gsub(/%/,\"\",\$5); print \$5}")" -lt 95' sh "${REPO_DIR}"

node - "${WORK_DIR}/preflight-status.txt" "${OUTPUT}" "${FAILED}" <<'NODE'
const fs = require("fs");
const [statusPath, outputPath, failed] = process.argv.slice(2);
const checks = Object.fromEntries(
  fs.readFileSync(statusPath, "utf8").trim().split("\n").filter(Boolean).map((line) => line.split("=")),
);
fs.writeFileSync(outputPath, `${JSON.stringify({
  status: failed === "0" ? "passed" : "failed",
  checked_at: new Date().toISOString(),
  checks,
}, null, 2)}\n`);
NODE

exit "${FAILED}"
