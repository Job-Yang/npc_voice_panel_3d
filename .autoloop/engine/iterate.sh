#!/usr/bin/env bash
# =============================================================================
# AutoLoop 引擎 · 单仓实验版 · 跑一轮
# -----------------------------------------------------------------------------
# 部署在远端服务机，由 cron 每天凌晨调用一次。它自己不做创作决策——真正的
# "回顾→盘点→找灵感→改→本地验证→push→线上无痕验证→写手记" 全交给 trae-cli exec
# 拉起的一个无人值守 Agent 完成（宪法 = constitution.md + profile.md）。
#
# 单仓：作品代码在仓库根，实验数据在 .autoloop/，共享一条 commit 历史，一起 push。
# 引擎只负责：同步→拉起 Agent→采集本轮客观指标→把过程留档(runs/)提交入库。
#
# 用法（cron）：
#   0 3 * * *  /abs/npc_voice_panel_3d/.autoloop/engine/iterate.sh >> /abs/npc_voice_panel_3d/.autoloop/runs/cron.log 2>&1
# =============================================================================
set -uo pipefail

ENGINE_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
AUTOLOOP_DIR="$(cd "${ENGINE_DIR}/.." && pwd)"       # .autoloop/
REPO_DIR="$(cd "${AUTOLOOP_DIR}/.." && pwd)"          # 仓库根
# cron 的默认 PATH 不含用户级工具。TRAE CLI 的 workspace-write 沙箱会从 PATH
# 查找 ~/.local/bin/bwrap；缺失时模型能启动，但所有本地工具调用都会失败。
export PATH="${HOME}/.local/bin:${HOME}/.npm-global/bin:${PATH}"

MODEL="${AUTOLOOP_MODEL:-gpt-5.5}"
BRANCH="${AUTOLOOP_BRANCH:-main}"
# trae-cli 定位：cron 环境的 PATH 极简，不含 ~/.local/bin，故自动兜底探测常见绝对路径。
TRAE_CLI="${AUTOLOOP_TRAE_CLI:-}"
if [ -z "${TRAE_CLI}" ]; then
  if command -v trae-cli >/dev/null 2>&1; then TRAE_CLI="$(command -v trae-cli)";
  else for c in "${HOME}/.local/bin/trae-cli" /usr/local/bin/trae-cli /opt/homebrew/bin/trae-cli; do
    [ -x "$c" ] && { TRAE_CLI="$c"; break; }; done; fi
  TRAE_CLI="${TRAE_CLI:-trae-cli}"
fi
TASK_TIMEOUT="${AUTOLOOP_TIMEOUT:-3600}"
ONLINE_URL="${AUTOLOOP_ONLINE_URL:-https://job-yang.github.io/npc_voice_panel_3d/}"

cd "${REPO_DIR}" || { echo "[autoloop] 无法进入仓库 ${REPO_DIR}"; exit 1; }
TODAY="$(date +%Y-%m-%d)"; STAMP="$(date +%Y-%m-%d_%H%M%S)"
RUN_DIR="${AUTOLOOP_DIR}/runs/${STAMP}"; mkdir -p "${RUN_DIR}"
log() { echo "[autoloop][$(date '+%H:%M:%S')] $*"; }

worktree_matches_origin() {
  git diff --quiet "origin/${BRANCH}" -- . 2>/dev/null || return 1
  git diff --cached --quiet "origin/${BRANCH}" -- . 2>/dev/null || return 1
  while IFS= read -r path; do
    case "${path}" in
      .autoloop/runs/*|.autoloop/journal/assets/*-online.png) continue ;;
    esac
    git cat-file -e "origin/${BRANCH}:${path}" 2>/dev/null || return 1
    cmp -s "${path}" <(git show "origin/${BRANCH}:${path}") || return 1
  done < <(git ls-files --others --exclude-standard)
  return 0
}

log "=== 铁匠铺自迭代 · ${STAMP} 开工 ===  仓库=${REPO_DIR} 分支=${BRANCH} 模型=${MODEL}"

# ---- 1. 同步（保守快进，冲突跳过本轮）----
git fetch origin "${BRANCH}" 2>&1 | tee -a "${RUN_DIR}/git.log"
# 防御：上一轮 TRAE 沙箱可能用平行 GIT_DIR 提交，导致本地工作区残留"未提交"文件
# （其内容其实已 push 到远端）。这些残留会挡住 ff-only。若本地相对 origin 无实质差异，
# 说明残留都已在远端，安全清理后再快进；只有真正的内容分叉才跳过本轮。
if [ -n "$(git status --porcelain)" ]; then
  if worktree_matches_origin; then
    log "检测到工作区残留（内容已在远端），自动清理以恢复干净状态。"
    git checkout -- . 2>/dev/null || true
    # 排除 runs/：本轮 RUN_DIR 已在同步前建好，且历史 runs 已随远端快进拉回，勿误删。
    git clean -fd -e ".autoloop/runs" . 2>&1 | tee -a "${RUN_DIR}/git.log" || true
  else
    log "!! 工作区有未同步到远端的本地改动，为安全起见跳过本轮。"; echo dirty > "${RUN_DIR}/SKIPPED"; exit 0
  fi
fi
if ! git merge --ff-only "origin/${BRANCH}" 2>&1 | tee -a "${RUN_DIR}/git.log"; then
  log "!! 无法快进（分叉），本轮跳过，绝不强制覆盖。"; echo skipped > "${RUN_DIR}/SKIPPED"; exit 0
fi
HEAD_BEFORE="$(git rev-parse HEAD)"

# ---- 2. 校验依赖 ----
command -v "${TRAE_CLI}" >/dev/null 2>&1 || [ -x "${TRAE_CLI}" ] || { log "!! 找不到 trae-cli（${TRAE_CLI}）"; echo err > "${RUN_DIR}/ERROR"; exit 1; }
[ -f "${AUTOLOOP_DIR}/constitution.md" ] && [ -f "${AUTOLOOP_DIR}/profile.md" ] || { log "!! 缺 constitution.md 或 profile.md"; echo err > "${RUN_DIR}/ERROR"; exit 1; }

# ---- 3. 拼装完整宪法 = 通用骨架 + 本仓画像 ----
PROMPT="今天是 ${TODAY}。下面是你的自迭代宪法（通用骨架 + 本仓画像）。请严格按它完成今天这一轮
（回顾→现状盘点→摄取公开外部输入→消化筛选→改→本地验证→push→线上无痕验证→写手记→更新CHANGELOG）。
你运行在远端、无人值守、stdin 已关闭，不要空等交互。
仓库根=${REPO_DIR}（作品代码在此，实验数据写 .autoloop/）。分支=${BRANCH}。线上地址=${ONLINE_URL}
本轮RUN_DIR=${RUN_DIR}（视觉验证 JSON、final、trace 等本轮证据写这里）。

========== 通用骨架 constitution.md ==========
$(cat "${AUTOLOOP_DIR}/constitution.md")

========== 本仓画像 profile.md（场景锚，不可改变其本质定位）==========
$(cat "${AUTOLOOP_DIR}/profile.md")"

FINAL_TXT="${RUN_DIR}/final.txt"; TRACE_JSONL="${RUN_DIR}/trae.jsonl"

# ---- 4. 无人值守拉起 Agent（姿势对齐 iLoop oncall 网关）----
log "拉起 Agent（超时上限 ${TASK_TIMEOUT}s）……"
"${TRAE_CLI}" exec \
  --permission-mode custom --sandbox workspace-write --disable hooks \
  -c 'approval_policy="never"' -m "${MODEL}" -C "${REPO_DIR}" \
  "${PROMPT}" --json --ephemeral -o "${FINAL_TXT}" \
  > "${TRACE_JSONL}" 2>&1 &
AGENT_PID=$!
( sleep "${TASK_TIMEOUT}"; kill -0 "${AGENT_PID}" 2>/dev/null && { echo "[autoloop] 超时终止"; kill "${AGENT_PID}" 2>/dev/null; } ) & WATCHDOG=$!
wait "${AGENT_PID}"; AGENT_RC=$?; kill "${WATCHDOG}" 2>/dev/null

# ---- 5. 外部输入门禁（缺输入卡或不可追溯来源时，该轮实验标记失败）----
INPUT_CARD="${AUTOLOOP_DIR}/inputs/${TODAY}.md"
INPUT_RC=0
INPUT_MODE="missing"
INPUT_SOURCE_COUNT=0
if [ -s "${INPUT_CARD}" ]; then
  INPUT_SOURCE_COUNT="$(grep -Eo 'https?://[^ )>]+' "${INPUT_CARD}" 2>/dev/null | sort -u | wc -l | tr -d ' ')"
  if grep -q 'self_generated_after_search' "${INPUT_CARD}"; then
    INPUT_MODE="self_generated_after_search"
    [ "${INPUT_SOURCE_COUNT}" -ge 3 ] || INPUT_RC=2
  else
    INPUT_MODE="public_external"
    [ "${INPUT_SOURCE_COUNT}" -ge 2 ] || INPUT_RC=2
  fi
else
  INPUT_RC=2
fi
cat > "${RUN_DIR}/input_validation.json" <<EOF
{
  "status": "$([ "${INPUT_RC}" -eq 0 ] && echo passed || echo failed)",
  "input_card": ".autoloop/inputs/${TODAY}.md",
  "input_mode": "${INPUT_MODE}",
  "public_source_count": ${INPUT_SOURCE_COUNT}
}
EOF
if [ "${INPUT_RC}" -ne 0 ]; then
  log "!! 外部输入门禁失败：缺输入卡或公开来源数量不足。"
fi

# ---- 6. 引擎兜底线上视觉验证（Agent 未产出时补跑，60 秒硬超时）----
ONLINE_SCREENSHOT="${AUTOLOOP_DIR}/journal/assets/${TODAY}-online.png"
VISUAL_RESULT="${RUN_DIR}/visual_verification.json"
VISUAL_RC=0
if [ ! -s "${ONLINE_SCREENSHOT}" ] || [ ! -s "${VISUAL_RESULT}" ]; then
  log "执行线上 3D 页面真实截图验证（60 秒硬超时）……"
  bash "${ENGINE_DIR}/verify_web.sh" "${ONLINE_URL}" "${ONLINE_SCREENSHOT}" "${VISUAL_RESULT}" \
    >> "${RUN_DIR}/visual_verification.log" 2>&1 || VISUAL_RC=$?
fi

# TRAE workspace-write 可能用平行 GIT_DIR 完成 commit/push，默认 .git 仍停在旧 HEAD。
# 若工作区内容与远端一致，清理平行 GIT_DIR 的视图残留并快进默认仓；保留本轮 runs 与引擎截图。
git fetch origin "${BRANCH}" >> "${RUN_DIR}/git.log" 2>&1 || true
if [ -n "$(git status --porcelain)" ] && worktree_matches_origin; then
  git checkout -- . 2>/dev/null || true
  git clean -fd \
    -e ".autoloop/runs" \
    -e ".autoloop/journal/assets/${TODAY}-online.png" \
    . >> "${RUN_DIR}/git.log" 2>&1 || true
fi
git merge --ff-only "origin/${BRANCH}" >> "${RUN_DIR}/git.log" 2>&1 || true

HEAD_AFTER="$(git rev-parse HEAD)"
git log -1 --oneline > "${RUN_DIR}/head_after.txt" 2>&1 || true

# ---- 7. 采集本轮客观指标（实验定量数据）----
COMMITTED=false; DIFF_STAT="0 0 0"
if [ "${HEAD_BEFORE}" != "${HEAD_AFTER}" ]; then
  COMMITTED=true
  DIFF_STAT="$(git diff --shortstat "${HEAD_BEFORE}" "${HEAD_AFTER}" 2>/dev/null || echo '')"
fi
cat > "${RUN_DIR}/metrics.json" <<EOF
{
  "date": "${TODAY}", "stamp": "${STAMP}", "agent_rc": ${AGENT_RC},
  "input_validation_rc": ${INPUT_RC},
  "input_mode": "${INPUT_MODE}",
  "input_source_count": ${INPUT_SOURCE_COUNT},
  "visual_verification_rc": ${VISUAL_RC},
  "committed": ${COMMITTED},
  "head_before": "${HEAD_BEFORE}", "head_after": "${HEAD_AFTER}",
  "commit_oneline": "$(git log -1 --format='%h %s' "${HEAD_AFTER}" 2>/dev/null | sed 's/"/\\"/g')",
  "diff_shortstat": "$(echo "${DIFF_STAT}" | tr -s ' ' | sed 's/"/\\"/g')"
}
EOF

if [ "${AGENT_RC}" -eq 0 ] && [ -s "${FINAL_TXT}" ]; then
  log "本轮完成 ✅  结论存 ${FINAL_TXT}"
  ${COMMITTED} && log "本轮 commit：$(git log -1 --oneline)" || log "本轮未产生 commit（可能只盘点未落地）。"
else
  log "!! 本轮异常 rc=${AGENT_RC}，trace 见 ${TRACE_JSONL}"; echo "rc=${AGENT_RC}" > "${RUN_DIR}/ERROR"
fi

# ---- 8. 同步飞书上帝视角文档（失败留证据，不阻断作品迭代）----
log "同步飞书 AutoLoop 实验日志……"
bash "${ENGINE_DIR}/report_feishu.sh" "${RUN_DIR}" "${TODAY}" \
  >> "${RUN_DIR}/feishu_report.log" 2>&1 || log "!! 飞书同步失败，证据已写入本轮 runs。"

# ---- 9. 把过程留档、视觉证据提交入库（实验数据必须每轮保存并推送）----
log "提交本轮过程留档、视觉证据与飞书回读……"
git add "${AUTOLOOP_DIR}/runs/${STAMP}" 2>/dev/null || true
[ -s "${ONLINE_SCREENSHOT}" ] && git add "${ONLINE_SCREENSHOT}" 2>/dev/null || true
if ! git diff --cached --quiet 2>/dev/null; then
  git -c core.hooksPath=/dev/null commit -m "chore(autoloop): 过程留档 ${STAMP}" 2>&1 | tee -a "${RUN_DIR}/git.log" || true
  git fetch origin "${BRANCH}" >/dev/null 2>&1 || true
  git merge --ff-only "origin/${BRANCH}" >/dev/null 2>&1 || true
  git push origin "${BRANCH}" 2>&1 | tee -a "${RUN_DIR}/git.log" || log "!! 过程留档 push 失败，数据已在本地 ${RUN_DIR}"
fi

log "=== 收工 · HEAD=$(git rev-parse --short HEAD) ==="
ROUND_RC="${AGENT_RC}"
[ "${INPUT_RC}" -ne 0 ] && ROUND_RC="${INPUT_RC}"
exit "${ROUND_RC}"
