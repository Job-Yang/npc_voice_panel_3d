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
REPORT_SCHEMA="$(node -e 'const fs=require("fs"); console.log(JSON.parse(fs.readFileSync(process.argv[1],"utf8")).report_schema)' "${CONFIG}")"
export LARKSUITE_CLI_NO_UPDATE_NOTIFIER=1
export LARKSUITE_CLI_NO_SKILLS_NOTIFIER=1

REPORT_MODE="failure"
[ -f "${JOURNAL}" ] && REPORT_MODE="success"
if "${LARK_CLI}" docs +fetch --as user --doc "${DOC_ID}" \
  --detail with-ids --format json > "${RUN_DIR}/feishu_marker_check.json" 2>&1 &&
  node -e 'const fs=require("fs"); const d=JSON.parse(fs.readFileSync(process.argv[1],"utf8")); process.exit((d.data?.document?.content||"").includes(process.argv[2])?0:1)' \
    "${RUN_DIR}/feishu_marker_check.json" "${MARKER}"; then
  if python3 "${ENGINE_DIR}/validate_feishu_report.py" \
    "${RUN_DIR}/feishu_marker_check.json" "${MARKER}" "${REPORT_SCHEMA}" "${REPORT_MODE}" \
    > "${RUN_DIR}/feishu_structure_validation.log" 2>&1; then
    printf '{"status":"success","result":"already_reported_and_verified","marker":"%s"}\n' "${MARKER}" > "${RUN_DIR}/feishu_report.json"
    exit 0
  fi
  printf '{"status":"failed","reason":"existing report violates schema","marker":"%s"}\n' "${MARKER}" > "${RUN_DIR}/feishu_report.json"
  exit 1
fi

git -C "${REPO_DIR}" fetch origin main >/dev/null 2>&1 || true
JOURNAL_COMMIT="$(grep -Eo 'Commit:[[:space:]]*`?[0-9a-f]{7,40}' "${JOURNAL}" 2>/dev/null | tail -1 | grep -Eo '[0-9a-f]{7,40}' || true)"
if [ -n "${JOURNAL_COMMIT}" ] && git -C "${REPO_DIR}" cat-file -e "${JOURNAL_COMMIT}^{commit}" 2>/dev/null; then
  COMMIT_HASH="$(git -C "${REPO_DIR}" rev-parse --short "${JOURNAL_COMMIT}")"
  COMMIT_SUBJECT="$(git -C "${REPO_DIR}" log -1 --format='%s' "${JOURNAL_COMMIT}")"
else
  COMMIT_HASH="$(git -C "${REPO_DIR}" rev-parse --short origin/main 2>/dev/null || git -C "${REPO_DIR}" rev-parse --short HEAD)"
  COMMIT_SUBJECT="$(git -C "${REPO_DIR}" log -1 --format='%s' origin/main 2>/dev/null || git -C "${REPO_DIR}" log -1 --format='%s')"
fi
ROUND="$(find "${AUTOLOOP_DIR}/journal" -maxdepth 1 -type f -name '20??-??-??.md' | wc -l | tr -d ' ')"
APPEND_FILE="${RUN_DIR}/feishu_append.xml"
META_FILE="${RUN_DIR}/feishu_round_meta.json"

if [ -f "${JOURNAL}" ]; then
  node - "${META_FILE}" "${ROUND}" "${DATE}" "${COMMIT_SUBJECT}" "${COMMIT_HASH}" "${STAMP}" "${MARKER}" "${REPORT_SCHEMA}" <<'NODE'
const fs = require("fs");
const [path, round, date, subject, commit, stamp, marker, reportSchema] = process.argv.slice(2);
const base = "https://github.com/Job-Yang/npc_voice_panel_3d";
fs.writeFileSync(path, `${JSON.stringify({
  round,
  date,
  subject,
  commit,
  marker,
  report_schema: reportSchema,
  commit_url: `${base}/commit/${commit}`,
  input_url: `${base}/blob/main/.autoloop/inputs/${date}.md`,
  journal_url: `${base}/blob/main/.autoloop/journal/${date}.md`,
  run_url: `${base}/tree/main/.autoloop/runs/${stamp}`,
}, null, 2)}\n`);
NODE
  node "${ENGINE_DIR}/render_feishu_round.js" \
    "${INPUT_CARD}" "${JOURNAL}" "${APPEND_FILE}" "${META_FILE}"
else
  FAILURE_TEXT="$(sed -n '1,12p' "${RUN_DIR}/final.txt")"
  node - "${APPEND_FILE}" "${DATE}" "${STAMP}" "${MARKER}" "${FAILURE_TEXT}" <<'NODE'
const fs = require("fs");
const [path, date, stamp, marker, failure] = process.argv.slice(2);
const esc = (s) => s.replaceAll("&", "&amp;").replaceAll("<", "&lt;").replaceAll(">", "&gt;");
fs.writeFileSync(path, [
  "<hr/>",
  `<h2>运行异常｜${esc(date)}｜未形成有效实验轮次</h2>`,
  "<p><b>状态：</b>定时任务已触发，但 Agent 未生成 input/journal/作品 commit，因此不计入正式轮次。</p>",
  `<p><b>失败摘要：</b>${esc(failure.replace(/\\s+/g, " ").slice(0, 600))}</p>`,
  `<p><b>原始证据：</b><a href="https://github.com/Job-Yang/npc_voice_panel_3d/tree/main/.autoloop/runs/${esc(stamp)}">查看本轮 run</a></p>`,
  `<p><code>${esc(marker)}</code></p>`,
].join("\n") + "\n");
NODE
fi

cd "${REPO_DIR}" || exit 1
REL_APPEND=".autoloop/runs/${STAMP}/feishu_append.xml"
if ! "${LARK_CLI}" docs +update --as user --doc "${DOC_ID}" --command append \
  --content "@${REL_APPEND}" --format json > "${RUN_DIR}/feishu_update.json" 2>&1; then
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

# 每轮先追加到文末，再把“7. 阶段结论”整节移动回文末。这样每日轮次始终归属
# “6. 实验记录”，而阶段结论保持为最后一个一级章节。
"${LARK_CLI}" docs +fetch --as user --doc "${DOC_ID}" --detail with-ids \
  --format json > "${RUN_DIR}/feishu_structure.json" 2>&1 || true
STAGE_IDS="$(python3 - "${RUN_DIR}/feishu_structure.json" <<'PY'
import json
import sys
import xml.etree.ElementTree as ET

try:
    data = json.load(open(sys.argv[1]))
    content = data["data"]["document"]["content"]
    root = ET.fromstring("<root>" + content + "</root>")
except Exception:
    print("")
    raise SystemExit

collect = False
ids = []
for child in root:
    text = "".join(child.itertext()).strip()
    if child.tag == "h1" and text == "7. 阶段结论":
        collect = True
    elif collect and child.tag in {"hr", "h1", "h2"}:
        break
    if collect and child.attrib.get("id"):
        ids.append(child.attrib["id"])
print(",".join(ids))
PY
)"
if [ -n "${STAGE_IDS}" ]; then
  if ! "${LARK_CLI}" docs +update --as user --doc "${DOC_ID}" --command block_move_after \
    --block-id -1 --src-block-ids "${STAGE_IDS}" --format json \
    > "${RUN_DIR}/feishu_move_stage.json" 2>&1; then
    printf '{"status":"failed","reason":"move stage conclusion failed","marker":"%s"}\n' "${MARKER}" > "${RUN_DIR}/feishu_report.json"
    exit 1
  fi
else
  printf '{"status":"failed","reason":"stage conclusion section not found","marker":"%s"}\n' "${MARKER}" > "${RUN_DIR}/feishu_report.json"
  exit 1
fi

"${LARK_CLI}" docs +fetch --as user --doc "${DOC_ID}" --detail with-ids \
  --format json > "${RUN_DIR}/feishu_readback.json" 2>&1
if python3 "${ENGINE_DIR}/validate_feishu_report.py" \
  "${RUN_DIR}/feishu_readback.json" "${MARKER}" "${REPORT_SCHEMA}" "${REPORT_MODE}" \
  > "${RUN_DIR}/feishu_structure_validation.log" 2>&1
then
  printf '{"status":"success","result":"appended_and_verified","marker":"%s","document_id":"%s"}\n' \
    "${MARKER}" "${DOC_ID}" > "${RUN_DIR}/feishu_report.json"
  exit 0
fi

printf '{"status":"failed","reason":"readback marker missing","marker":"%s"}\n' "${MARKER}" > "${RUN_DIR}/feishu_report.json"
exit 1
