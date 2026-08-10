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
├── engine/iterate.sh    引擎：cron 调它，拉起 Agent 跑一轮 + 采集指标 + 提交过程留档
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
`远端 cron → .autoloop/engine/iterate.sh → trae-cli exec（塞 constitution+profile）→ 一个完整 Agent 自己走完闭环 → 一起 push`
- 定时层：远端服务机现成 **cron**（不用 iLoop 的 macOS launchd）。
- 跑 Agent 层：复用 iLoop oncall 同款 `trae-cli exec` 无人值守姿势（`--sandbox workspace-write` +
  `approval_policy=never` + `--ephemeral`）。远端 oncall 已在用，凭证/权限现成。
- 单仓：作品改动 + 实验数据共享一条 commit 历史，一起 push。Pages 只发作品本体，`.autoloop/` 不影响上线。
- 飞书观察文档：<https://bytedance.larkoffice.com/docx/Urw8drpGholNETx7CCBchka8ntd>。每轮完成后由
  `engine/report_feishu.sh` 追加“怎么想、怎么做、最终效果”，原始证据仍以仓库为准。
- 输入规则：每轮必须先调查至少 2 个公开可追溯来源，记录“看了什么→学到什么→为何吸收/拒绝→如何转化”。
  仓库与完整 trace 公开，因此严格禁止搜索或引用任何公司内部/飞书内部/内网资料。
- 线上视觉验证：`engine/verify_web.sh` 先校验线上 HTML 与当前 commit 的 SHA-256 一致，再用真实 Chromium
  渲染同一份本地代码并截图；浏览器阶段有 60 秒硬超时。截图及结果 JSON 随本轮入库，不再让 Agent 临时
  拼 Playwright 环境，也不让 GitHub Pages 的大模型下载速度决定整轮是否卡住。

## 部署到远端服务机（一次性）
1. 远端 clone / pull 本仓，确保 `trae-cli` 在 PATH 且已登录（远端 oncall 已在用，凭证应就绪）。
2. `chmod +x .autoloop/engine/iterate.sh`
3. 先手动跑一轮验证链路：`bash .autoloop/engine/iterate.sh`
4. 挂 cron（凌晨模型不排队）：
   ```cron
   0 3 * * *  /abs/npc_voice_panel_3d/.autoloop/engine/iterate.sh >> /abs/npc_voice_panel_3d/.autoloop/runs/cron.log 2>&1
   ```

## 可调环境变量
`AUTOLOOP_MODEL`(默认 gpt-5.5) · `AUTOLOOP_BRANCH`(默认 main) · `AUTOLOOP_TRAE_CLI`(不在 PATH 时给绝对路径) ·
`AUTOLOOP_TIMEOUT`(默认 3600s) · `AUTOLOOP_ONLINE_URL`

## 怎么监督这个实验（人在环上）
- **阶段 A 外部输入驱动的纯观察**：不建 HUMAN_FEEDBACK.md，但每轮必须学习公开外部来源；观察它如何筛选与转化。
- **阶段 B 弱监督**：建 `.autoloop/HUMAN_FEEDBACK.md` 写低频批注（「这个好」「别再改配色」），Agent 下轮"回顾"优先读它。
- 看 AI 每天在想什么 → journal/；概览 → CHANGELOG.md；求助 → ASK_HUMAN.md；某轮细节/指标 → runs/。

## 安全底座
- 只快进合并，冲突跳过本轮，**绝不** reset --hard / push -f。
- 宪法禁止 Agent 改引擎自身与 profile、禁止毁 git 历史、禁止破坏现有 assets、一次只做一件事。
- 翻车了 `git revert` 或回退某 commit 即可，一切可回溯。
