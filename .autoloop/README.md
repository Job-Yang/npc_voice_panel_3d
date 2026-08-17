# AutoLoop · 铁匠铺自迭代实验

一个**无人值守自迭代系统实验**：让一个 AI Agent 每天凌晨先摄取公开外部输入，再给这个 3D 欢迎页做一轮
迭代——回顾→盘点现状→调查外部来源→消化与筛选→改→验证→push→写手记，全程无人参与。
主人像训模型一样低频监督它：每个 commit 是一个可回退、可分析的样本；`journal/` + `runs/` 是实验数据集。

> 当前是**单仓实验**：引擎、实验数据、作品代码都在这一个仓里（`.autoloop/` 放引擎和数据，仓库根是作品）。
> 等实验出结论、能力成熟，再把 `.autoloop/` 整个文件夹剥离成可复用能力（挂 iLoop / 独立仓 / skill 皆可）。

## 目录
```
.autoloop/
├── EXPERIMENT.md        实验框架：命题/变量/阶段/指标/产物清单（写论文的依据）
├── constitution.md      通用宪法骨架（怎么迭代/记录/验证/红线）
├── profile.md           场景锚：这作品是什么/目标/边界/护栏（Agent 不可改）
├── engine/supervisor.py 监督器：预热、分类自愈、同日恢复、终态上报
├── engine/iterate.sh    单次 attempt 执行器：拉起 Agent、验证并采集指标
├── inputs/<date>.md     每轮公开外部输入卡：来源/观察/吸收/拒绝/转化路径
├── journal/<date>.md    Agent 每天亲手写的手记（+ assets/ 无痕验证效果图）
├── CHANGELOG.md         变更概览 + 每轮 commit hash
├── ASK_HUMAN.md         Agent 求助板
├── HUMAN_FEEDBACK.md    （阶段 B 才建）主人的低频批注，Agent 回顾时优先读 = 人类监督注入点
├── feishu.json           飞书 all-in-one 观察文档配置（非密钥）
└── runs/<ts>/           每轮过程留档：final / trace / metrics / 视觉验证 / 飞书写入回读（入库）
仓库根 index.html + assets/   作品本体（GitHub Pages 只发这些）
```

## 机制（一句话）
`远端 cron → workspace_runner.py → 当日隔离 worktree → supervisor.py → attempt → 分类恢复 → 终态飞书/归档`

- 控制仓只保存人工/历史现场；即使有未提交文件或本地分支分叉，也不会进入当天 Agent 上下文，更不会阻塞执行。
- cron 启动器位于仓库外，每次先从最新 `origin/main` 自刷新 launcher、runner 和通知器；控制仓本地分支
  不更新也不会卡住机制升级。
- 02:45 从最新 `origin/main` 创建当天专属 worktree，再预热认证、GitHub、飞书、沙箱、浏览器依赖和磁盘；
  引擎或 CLI 版本变化时额外执行一次真实模型 smoke。
- 03:00 执行正式 attempt；基础设施故障在 03:15、03:45 继续同一个逻辑轮次，最多 3 次。
- 同一天的所有 attempt 复用同一个隔离 worktree，支持未完成改动断点续跑；共享 `AutoLoopRun:<date>`，
  只计一个实验轮次。已有完整 input/journal 时跳过 Agent，
  只恢复验证、报告和归档，避免重复创作或发布。
- 新一天启动前会扫描旧 worktree 的 `notification_pending/finalization_pending`，先补齐历史通知与归档，
  不因日期切换丢失恢复责任。
- 认证、网络、CLI、视觉环境故障可以重试；输入卡或创意质量契约失败不机械重试。
- 飞书和 Git 过程留档只在成功、不可重试失败或重试耗尽后执行一次，不产生中间失败噪音。
- 异常终态会由当前 Lark 应用的 Bot 私聊当前已授权用户；消息发送后按 `message_id` 回读，
  未验证送达则保持 `finalization_pending`，由下一次 cron 继续补偿。
- 控制仓 Git 异常只记录为隔离事件，不再成为当天失败原因；只有无法获取 `origin/main` 且没有可恢复的
  当日 worktree 时才触发失败通知。
- 预热的 Python 编译与单测缓存固定写入 `~/.cache/autoloop-supervisor/pycache`，
  不在源码目录生成 `__pycache__`，避免监督器先写脏仓库再拦截自身。

- 定时层：远端服务机现成 **cron**（不用 iLoop 的 macOS launchd）；cron 日志写到
  `~/.local/state/autoloop/`，不污染 Git 工作区。
- 跑 Agent 层：复用 iLoop oncall 同款 `trae-cli exec` 无人值守姿势（`--sandbox workspace-write` +
  `approval_policy=never` + `--ephemeral`）。远端 oncall 已在用，凭证/权限现成。
- 单仓：作品改动 + 实验数据共享一条 commit 历史，一起 push。Pages 只发作品本体，`.autoloop/` 不影响上线。
- 飞书观察文档：<https://bytedance.larkoffice.com/docx/Urw8drpGholNETx7CCBchka8ntd>。每轮完成后由
  `engine/report_feishu.sh` 追加“怎么想、怎么做、最终效果”，原始证据仍以仓库为准。
- 飞书记录格式由 `.autoloop/FEISHU_REPORT_FORMAT.md` 和 `AutoLoopReportSchema:v1` 固定：
  确定性脚本只生成 H2 轮次标题、六行摘要表、证据链接和截图；回读层级或表格不符合规范时同步直接失败。
- 输入规则：每轮必须先调查至少 2 个公开可追溯来源，记录“看了什么→学到什么→为何吸收/拒绝→如何转化”。
  仓库与完整 trace 公开，因此严格禁止搜索或引用任何公司内部/飞书内部/内网资料。
- 线上视觉验证：`engine/verify_web.sh` 先校验线上 HTML 与当前 commit 的 SHA-256 一致，再用真实 Chromium
  渲染同一份本地代码并截图；浏览器阶段有 60 秒硬超时。截图及结果 JSON 随本轮入库，不再让 Agent 临时
  拼 Playwright 环境，也不让 GitHub Pages 的大模型下载速度决定整轮是否卡住。

## 部署到远端服务机（一次性）
1. 远端 clone / pull 本仓，确保 `trae-cli` 在 PATH 且已登录（远端 oncall 已在用，凭证应就绪）。
2. `chmod +x .autoloop/engine/iterate.sh .autoloop/engine/install_supervisor_cron.sh`
3. 先验证预热：`python3 .autoloop/engine/supervisor.py prewarm`
4. 运行 `bash .autoloop/engine/install_supervisor_cron.sh` 安装并回读 cron。脚本会移除旧的单次 `iterate.sh`
   调度，安装 02:45 预热与 03:00/03:15/03:45 恢复调度。

## 可调环境变量
`AUTOLOOP_MODEL`(默认 gpt-5.5) · `AUTOLOOP_BRANCH`(默认 main) · `AUTOLOOP_TRAE_CLI`(不在 PATH 时给绝对路径) ·
`AUTOLOOP_TIMEOUT`(默认 3600s) · `AUTOLOOP_ONLINE_URL` · `AUTOLOOP_MAX_ATTEMPTS`(默认 3) ·
`AUTOLOOP_ATTEMPT_TIMEOUT`(默认 4500s) · `AUTOLOOP_PRIVATE_STATE_DIR`(默认 `~/.local/state/autoloop`) ·
`AUTOLOOP_WORKSPACE_ROOT`(默认 `~/.local/share/autoloop/workspaces/<repo-key>`)

## Supervisor 状态与口径
- 每日状态：`.autoloop/runs/<date>_supervisor/state.json`。
- attempt 证据：`.autoloop/runs/<date>_attempt_01/` 等。
- `succeeded`：全部门禁、飞书回读和 Git 归档完成。
- `retry_wait`：基础设施故障，等待当日下一次调度恢复。
- `failed_nonretryable`：输入/创意契约失败，保留证据但不重复消耗 Token。
- `failed_exhausted`：3 次基础设施恢复或终态上报仍失败，需要人工处理。

## 怎么监督这个实验（人在环上）
- **阶段 A 外部输入驱动的纯观察**：不建 HUMAN_FEEDBACK.md，但每轮必须学习公开外部来源；观察它如何筛选与转化。
- **阶段 B 弱监督**：建 `.autoloop/HUMAN_FEEDBACK.md` 写低频批注（「这个好」「别再改配色」），Agent 下轮"回顾"优先读它。
- 看 AI 每天在想什么 → journal/；概览 → CHANGELOG.md；求助 → ASK_HUMAN.md；某轮细节/指标 → runs/。

## 安全底座
- 每日执行只基于 `origin/main` 的隔离 worktree；控制仓脏文件和分叉提交原样保留、永不自动提交。
- 发布仍只允许普通 push，竞争更新按失败分类重试，**绝不** reset --hard / push -f。
- 隔离分支发布使用显式 `HEAD:main`，禁止把长期控制仓的本地 `main` 当作发布源。
- 宪法禁止 Agent 改引擎自身与 profile、禁止毁 git 历史、禁止破坏现有 assets、一次只做一件事。
- 翻车了 `git revert` 或回退某 commit 即可，一切可回溯。
