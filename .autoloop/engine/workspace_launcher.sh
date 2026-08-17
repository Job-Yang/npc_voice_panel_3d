#!/usr/bin/env bash
set -euo pipefail

CONTROL_REPO="${1:?usage: workspace_launcher.sh <control-repo> <command>}"
COMMAND="${2:?missing command}"
REMOTE="${AUTOLOOP_REMOTE:-origin}"
BRANCH="${AUTOLOOP_BRANCH:-main}"

if command -v sha256sum >/dev/null 2>&1; then
  REPO_KEY="$(printf '%s' "${CONTROL_REPO}" | sha256sum | awk '{print substr($1,1,16)}')"
else
  REPO_KEY="$(printf '%s' "${CONTROL_REPO}" | shasum -a 256 | awk '{print substr($1,1,16)}')"
fi
RUNTIME_DIR="${HOME}/.local/share/autoloop/launchers/${REPO_KEY}"
mkdir -p "${RUNTIME_DIR}"

# Fetch is best effort: an existing daily workspace remains resumable during outages.
git -C "${CONTROL_REPO}" fetch "${REMOTE}" "${BRANCH}" >/dev/null 2>&1 || true
REMOTE_REF="${REMOTE}/${BRANCH}"

if [ "${AUTOLOOP_LAUNCHER_REEXEC:-0}" != "1" ] &&
  git -C "${CONTROL_REPO}" cat-file -e "${REMOTE_REF}:.autoloop/engine/workspace_launcher.sh" 2>/dev/null; then
  git -C "${CONTROL_REPO}" show \
    "${REMOTE_REF}:.autoloop/engine/workspace_launcher.sh" \
    > "${RUNTIME_DIR}/workspace_launcher.next.sh"
  chmod +x "${RUNTIME_DIR}/workspace_launcher.next.sh"
  exec env AUTOLOOP_LAUNCHER_REEXEC=1 \
    "${RUNTIME_DIR}/workspace_launcher.next.sh" "${CONTROL_REPO}" "${COMMAND}"
fi

for file in workspace_runner.py notify_feishu_failure.py; do
  if git -C "${CONTROL_REPO}" cat-file -e \
    "${REMOTE_REF}:.autoloop/engine/${file}" 2>/dev/null; then
    git -C "${CONTROL_REPO}" show \
      "${REMOTE_REF}:.autoloop/engine/${file}" \
      > "${RUNTIME_DIR}/${file}.next"
    mv "${RUNTIME_DIR}/${file}.next" "${RUNTIME_DIR}/${file}"
  fi
done

test -s "${RUNTIME_DIR}/workspace_runner.py"
exec env \
  AUTOLOOP_CONTROL_REPO="${CONTROL_REPO}" \
  AUTOLOOP_NOTIFIER="${RUNTIME_DIR}/notify_feishu_failure.py" \
  python3 "${RUNTIME_DIR}/workspace_runner.py" "${COMMAND}"
