# 自迭代画像 · 铁匠铺欢迎页（场景锚 · profile）

> 本文件是「老杨的铁匠铺」欢迎页这个**实验对象**的自我说明，也是 AutoLoop 每轮宪法的后半段。
> **大方向不可变**——Agent 可在场景内自由发挥，但绝不能把它迭代成一个不相干的东西。

## 这是什么（一句话本质，不可漂移）
「老杨（老羊）的铁匠铺」个人主页的 **3D 欢迎页**。它**永远是一个"欢迎页 / 个人主页门面"**——
有铁匠铺氛围、能体现主人是谁（一个爱用 AI 给自己升级科技的 iOS 工程师、做 iLoop）的可交互展示页。
可以越来越精致、好玩、可探索，但**不是游戏、不是工具、不是别的产品形态**。
隐喻：铁匠铺 = 把混乱的问题锻造成能跑的工具。

## 使用方式 / 怎么跑起来
- **零构建单文件**：几乎所有逻辑在根目录 `index.html`（约 2000 行，清晰中文注释分区）；3D 模型/语音在 `assets/`。
- three.js r0.160 走 CDN importmap，无 npm / 无编译 / 无 CI。
- 本地预览（GLB/wav 需经 http，别用 file://）：`python3 -m http.server 8123`，开 `http://127.0.0.1:8123/`。

## 线上地址（无痕验证用）
https://job-yang.github.io/npc_voice_panel_3d/
- 部署：从 `main` 根目录直发 GitHub Pages，`git push origin main` 即上线（生效约 1–3 分钟）。

## 场景大方向 & 自由度边界
- **鼓励（在"铁匠铺欢迎页"场景内大胆尝试）**：加新 NPC / 可点物件 / 彩蛋 / 场景细节与氛围、
  丰富文案与导览、加 BGM 曲目、增强交互与可探索性、让画面更有生命力。方向可野，只要还是"这家铺子的门面"。
- **红线（本质定位，不可变）**：始终是老杨的**个人主页欢迎页**；铁匠铺主题不可替换；核心要能让访客
  "认识老杨 + 感受手艺人气质 + 找到 iLoop 等项目入口"。不可迭代成与个人主页无关的独立游戏/应用。

## 安全区（放心改，改错也不崩）—— index.html 声明式配置层
- 文案池：`yqLines` / `WELCOME_LINES` / `YQ_EASTER_LINES` / `GUIDE_CARDS` / `OBJECT_CONFIG.line`
- 新增 NPC：`NPC_CONFIG` 加项（需配套 GLB + `voiceFiles`，摆位参数要视觉验证）
- 新增可点物件：`OBJECT_CONFIG` + `makeProp`，或 `createHotspot` 挂隐形热区
- 新增彩蛋：参照 `triggerYQEasterEgg` / `triggerILoopEasterEgg` 的键盘序列框架
- 新增 BGM 曲目：`TRACKS` 加一套和弦

## 中风险（可改，但必须视觉/听觉验证）
`SCENE_PRESETS` 灯光与场景模式、相机默认参数（`DEFAULT_CAMERA_*`）、`makeProp` 几何摆位

## 高风险（要改先想清楚，改完必须验证，宁可不改）
- 渲染循环 `animate()`（性能敏感：火焰逐顶点形变、隔帧优化、阴影冻结）
- `loadNPC` 归一化/贴地/骨骼修正（依赖模型内部结构，改错易致 NPC 悬空/入地/姿势诡异）
- BGM 合成引擎调度时序（Web Audio scheduler，改错破音/卡顿）
- **不要撤销刻意的性能取舍**：`setPixelRatio` 封顶 1.75、`shadowMap.autoUpdate=false`、隔帧顶点更新

## 验证方式
- **本地**：`python3 -m http.server 8123` 打开，确认渲染正常、改动生效、控制台无 error。
- **线上无痕**：push 后等 Pages 生效，用禁缓存/cache-busting（URL 加 `?t=<时间戳>`）或无痕等效方式打开
  线上地址，确认**线上真实效果**（不只信本地），截图存 `.autoloop/journal/assets/<date>.png`。
- 「没弄坏」底线：页面能打开、能拖拽旋转、NPC/物件在位、无 JS 报错。
