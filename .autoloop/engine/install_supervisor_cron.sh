#!/usr/bin/env bash
set -euo pipefail

ENGINE_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_DIR="$(cd "${ENGINE_DIR}/../.." && pwd)"
CRON_LOG="${REPO_DIR}/.autoloop/runs/cron-supervisor.log"
BEGIN="# BEGIN autoloop-blacksmith-supervisor"
END="# END autoloop-blacksmith-supervisor"
CURRENT="$(mktemp)"
UPDATED="$(mktemp)"
trap 'rm -f "${CURRENT}" "${UPDATED}"' EXIT

crontab -l > "${CURRENT}" 2>/dev/null || true
awk -v begin="${BEGIN}" -v end="${END}" '
  $0 == begin { skip = 1; next }
  $0 == end { skip = 0; next }
  /# autoloop-blacksmith$/ { next }
  !skip { print }
' "${CURRENT}" > "${UPDATED}"

cat >> "${UPDATED}" <<EOF
${BEGIN}
45 2 * * * cd ${REPO_DIR} && python3 .autoloop/engine/supervisor.py prewarm >> ${CRON_LOG} 2>&1
0,15,45 3 * * * cd ${REPO_DIR} && python3 .autoloop/engine/supervisor.py run >> ${CRON_LOG} 2>&1
${END}
EOF

crontab "${UPDATED}"
crontab -l
