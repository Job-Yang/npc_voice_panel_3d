#!/usr/bin/env bash
set -euo pipefail

ENGINE_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_DIR="$(cd "${ENGINE_DIR}/../.." && pwd)"
REPO_KEY="$(printf '%s' "${REPO_DIR}" | shasum -a 256 | awk '{print substr($1,1,16)}')"
RUNTIME_DIR="${HOME}/.local/state/autoloop/${REPO_KEY}"
CRON_LOG="${RUNTIME_DIR}/cron-supervisor.log"
LAUNCHER_DIR="${HOME}/.local/share/autoloop/launchers/${REPO_KEY}"
LAUNCHER="${LAUNCHER_DIR}/workspace_launcher.sh"
BEGIN="# BEGIN autoloop-blacksmith-supervisor"
END="# END autoloop-blacksmith-supervisor"
CURRENT="$(mktemp)"
UPDATED="$(mktemp)"
trap 'rm -f "${CURRENT}" "${UPDATED}"' EXIT
mkdir -p "${RUNTIME_DIR}"
mkdir -p "${LAUNCHER_DIR}"
cp "${ENGINE_DIR}/workspace_launcher.sh" "${LAUNCHER}"
chmod +x "${LAUNCHER}"

crontab -l > "${CURRENT}" 2>/dev/null || true
awk -v begin="${BEGIN}" -v end="${END}" '
  $0 == begin { skip = 1; next }
  $0 == end { skip = 0; next }
  /# autoloop-blacksmith$/ { next }
  !skip { print }
' "${CURRENT}" > "${UPDATED}"

cat >> "${UPDATED}" <<EOF
${BEGIN}
45 2 * * * ${LAUNCHER} ${REPO_DIR} prewarm >> ${CRON_LOG} 2>&1
0,15,45 3 * * * ${LAUNCHER} ${REPO_DIR} run >> ${CRON_LOG} 2>&1
${END}
EOF

crontab "${UPDATED}"
crontab -l
