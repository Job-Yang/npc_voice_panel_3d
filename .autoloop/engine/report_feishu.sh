#!/usr/bin/env bash
set -uo pipefail

ENGINE_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
AUTOLOOP_DIR="$(cd "${ENGINE_DIR}/.." && pwd)"
REPO_DIR="$(cd "${AUTOLOOP_DIR}/.." && pwd)"

RUN_DIR="${1:?usage: report_feishu.sh <run-dir> <date>}"
DATE="${2:?missing date}"
STAMP="$(basename "${RUN_DIR}")"
JOURNAL="${AUTOLOOP_DIR}/journal/${DATE}.md"
INPUT_CARD="${AUTOLOOP_DIR}/inputs/${DATE}.md"
CONFIG="${AUTOLOOP_DIR}/feishu.json"
MARKER="AutoLoopRun:${STAMP}"

if [ ! -f "${CONFIG}" ]; then
  printf '{"status":"skipped","reason":"missing config"}\n' > "${RUN_DIR}/feishu_report.json"
  exit 0
fi
if [ ! -f "${JOURNAL}" ] && [ ! -f "${RUN_DIR}/final.txt" ]; then
  printf '{"status":"skipped","reason":"missing journal and final"}\n' > "${RUN_DIR}/feishu_report.json"
  exit 0
fi

LARK_CLI="${AUTOLOOP_LARK_CLI:-}"
if [ -z "${LARK_CLI}" ]; then
  for candidate in \
    "$(command -v lark-cli 2>/dev/null)" \
    "${HOME}/.npm-global/bin/lark-cli" \
    "${HOME}/.local/bin/lark-cli"; do
    [ -n "${candidate}" ] && [ -x "${candidate}" ] && { LARK_CLI="${candidate}"; break; }
  done
fi
if [ -z "${LARK_CLI}" ]; then
  printf '{"status":"failed","reason":"lark-cli not found"}\n' > "${RUN_DIR}/feishu_report.json"
  exit 1
fi

DOC_ID="$(node -e 'const fs=require("fs"); console.log(JSON.parse(fs.readFileSync(process.argv[1],"utf8")).document_id)' "${CONFIG}")"
export LARKSUITE_CLI_NO_UPDATE_NOTIFIER=1
export LARKSUITE_CLI_NO_SKILLS_NOTIFIER=1

if "${LARK_CLI}" docs +fetch --as user --doc "${DOC_ID}" \
  --scope keyword --keyword "${MARKER}" --format json > "${RUN_DIR}/feishu_marker_check.json" 2>&1 &&
  node -e 'const fs=require("fs"); const d=JSON.parse(fs.readFileSync(process.argv[1],"utf8")); process.exit((d.data?.document?.content||"").includes(process.argv[2])?0:1)' \
    "${RUN_DIR}/feishu_marker_check.json" "${MARKER}"; then
  printf '{"status":"success","result":"already_reported","marker":"%s"}\n' "${MARKER}" > "${RUN_DIR}/feishu_report.json"
  exit 0
fi

git -C "${REPO_DIR}" fetch origin main >/dev/null 2>&1 || true
COMMIT_HASH="$(git -C "${REPO_DIR}" rev-parse --short origin/main 2>/dev/null || git -C "${REPO_DIR}" rev-parse --short HEAD)"
COMMIT_SUBJECT="$(git -C "${REPO_DIR}" log -1 --format='%s' origin/main 2>/dev/null || git -C "${REPO_DIR}" log -1 --format='%s')"
ROUND="$(find "${AUTOLOOP_DIR}/journal" -maxdepth 1 -type f -name '20??-??-??.md' | wc -l | tr -d ' ')"
APPEND_FILE="${RUN_DIR}/feishu_append.md"

{
  printf '\n---\n\n'
  if [ -f "${JOURNAL}" ]; then
    printf '## 第 %s 轮｜%s｜%s\n\n' "${ROUND}" "${DATE}" "${COMMIT_SUBJECT}"
    printf '**作品 commit：** [`%s`](https://github.com/Job-Yang/npc_voice_panel_3d/commit/%s)\n\n' "${COMMIT_HASH}" "${COMMIT_HASH}"
    if [ -f "${INPUT_CARD}" ]; then
      printf '### 本轮外部输入卡\n\n'
      cat "${INPUT_CARD}"
      printf '\n\n'
    fi
    printf '### 本轮自迭代手记\n\n'
    cat "${JOURNAL}"
  else
    printf '## 运行异常｜%s｜未形成有效实验轮次\n\n' "${DATE}"
    printf '**状态：** 定时任务已触发，但 Agent 未生成 input/journal/作品 commit，因此不计入正式轮次。\n\n'
    printf '**原始证据：** [查看本轮 run](https://github.com/Job-Yang/npc_voice_panel_3d/tree/main/.autoloop/runs/%s)\n\n' "${STAMP}"
    printf '### 失败摘要\n\n'
    sed -n '1,12p' "${RUN_DIR}/final.txt"
    printf '\n\n'
  fi
  printf '\n\n`%s`\n' "${MARKER}"
} > "${APPEND_FILE}"

cd "${REPO_DIR}" || exit 1
REL_APPEND=".autoloop/runs/${STAMP}/feishu_append.md"
if ! "${LARK_CLI}" docs +update --as user --doc "${DOC_ID}" --command append \
  --doc-format markdown --content "@${REL_APPEND}" --format json > "${RUN_DIR}/feishu_update.json" 2>&1; then
  printf '{"status":"failed","reason":"document append failed","marker":"%s"}\n' "${MARKER}" > "${RUN_DIR}/feishu_report.json"
  exit 1
fi

SCREENSHOT=""
for candidate in \
  ".autoloop/journal/assets/${DATE}-online.png" \
  ".autoloop/journal/assets/${DATE}-local.png" \
  ".autoloop/journal/assets/${DATE}-local-diagnostic.png"; do
  [ -f "${candidate}" ] && { SCREENSHOT="${candidate}"; break; }
done
if [ -n "${SCREENSHOT}" ]; then
  "${LARK_CLI}" docs +media-insert --as user --doc "${DOC_ID}" --file "${SCREENSHOT}" \
    --align center --width 720 --caption "第 ${ROUND} 轮页面效果（${DATE}）" \
    --format json > "${RUN_DIR}/feishu_media.json" 2>&1 || true
fi

"${LARK_CLI}" docs +fetch --as user --doc "${DOC_ID}" --scope keyword \
  --keyword "${MARKER}" --format json > "${RUN_DIR}/feishu_readback.json" 2>&1
if node -e 'const fs=require("fs"); const d=JSON.parse(fs.readFileSync(process.argv[1],"utf8")); process.exit((d.data?.document?.content||"").includes(process.argv[2])?0:1)' \
  "${RUN_DIR}/feishu_readback.json" "${MARKER}"; then
  printf '{"status":"success","result":"appended_and_verified","marker":"%s","document_id":"%s"}\n' \
    "${MARKER}" "${DOC_ID}" > "${RUN_DIR}/feishu_report.json"
  exit 0
fi

printf '{"status":"failed","reason":"readback marker missing","marker":"%s"}\n' "${MARKER}" > "${RUN_DIR}/feishu_report.json"
exit 1
