
---

## 第 2 轮｜2026-08-12｜docs: record guidepost verification

**作品 commit：** [`eb46ec7`](https://github.com/Job-Yang/npc_voice_panel_3d/commit/eb46ec7)

### 本轮外部输入卡

# 2026-08-12 外部输入卡

访问日期：2026-08-12

## 候选 1：3D Interactive Portfolio

- 标题：`arvincatalbas/3D-Interactive-Portfolio`
- URL：https://github.com/arvincatalbas/3D-Interactive-Portfolio
- 看到的机制：项目说明强调点击 3D 房间里的物件后，镜头聚焦到对应对象，同时淡入 2D 信息面板；hover、浮动元素和提示动画让可交互点更容易被发现。
- 与铁匠铺的关系：老杨的铁匠铺已经有 NPC、铁砧、工作台、卷轴等可点物件，适合继续用“空间物件承载信息”的方式介绍本人和项目，而不是把欢迎页改成普通简历。
- 可吸收原则：关键入口最好有场景内实体锚点，并在点击后把访客带到更清晰的内容层。

## 候选 2：Interactive Way-finding Maps

- 标题：`Interactive Way-finding Maps`
- URL：https://www.axiell.com/uk/solutions/product/cultureconnect/interactive-way-finding-maps-culture-connect-case-study/
- 看到的机制：博物馆导览把内容入口拆成三种方式：按编号查找、看地图定位、通过视觉列表识别展品；目的不是炫技，而是降低访客在空间中的认知负担。
- 与铁匠铺的关系：铁匠铺是一个小型 3D 欢迎空间，首次访问者可能先看到氛围，却不一定知道“老杨是谁、项目在哪、iLoop 怎么看”。一个场景内导览牌可以提供“你在这里”的轻量定位。
- 可吸收原则：导览要给访客地标、方向和目的地，不需要解释系统本身。

## 候选 3：National Museum of Natural History Wayfinding Kiosk

- 标题：`National Museum of Natural History Wayfinding Kiosk`
- URL：https://interactiveknowledge.com/our-portfolio/national-museum-natural-history-wayfinding-kiosk
- 看到的机制：地点菜单搭配每个目的地的图像、图标和标题；选中目的地后，地图用路径和地标帮助访客记住怎么走。
- 与铁匠铺的关系：铁匠铺不需要完整地图，但可以借用“地标 + 目的地”的思路，把 NPC、火炉、卷轴、项目入口变成可记忆的路线。
- 可吸收原则：方向提示应该来自场景自己的地标，而不是额外悬浮一大块说明文字。

## 候选 4：The Art of Immersion: How Environment Design Shapes Player Experience

- 标题：`The Art of Immersion: How Environment Design Shapes Player Experience`
- URL：https://vaguely.xyz/posts/the-art-of-immersion-how-environment-design-shapes-player-experience
- 看到的机制：环境叙事通过物件摆放、磨损、灯光和微故事传达“谁在这里、发生过什么”，让探索本身成为理解世界的过程。
- 与铁匠铺的关系：铁匠铺欢迎页需要让访客感到这里是老杨工作的地方，而不是通用 3D 展厅。导览物件也应该像铺子里本来就会有的木牌，而不是现代 UI 牌。
- 可吸收原则：新增导览必须有铁匠铺质感，使用木头、铁件、炉火小标记等语言。

## 消化与选择

今天吸收的核心原则是：首次访问者需要一个低干扰的场景内定位点，告诉他“你在这里、可以去哪里、每个地标对应什么”。这比再新增一个项目说明弹窗更适合当前页面，因为上一轮刚加了 iLoop 证据链卷轴，今天应该补足进入空间后的方向感。

转译方案：新增“铺子导览牌 · 你在这里”。它不是现代地图面板，而是一个木制路牌：三层箭头木板、铆钉、炉火色定位环，放在主视角前场偏左。点击后用老杨的口吻指出四个地标：左边认识老杨，右边看项目，火炉试欢迎语，卷轴看 iLoop 闭环。

未采用候选：没有采用完整 3D portfolio 的镜头缩放大面板模式，也没有采用博物馆 kiosk 的完整地图和路径系统。理由是铁匠铺空间很小，过重的地图 UI 会把欢迎页推向工具化；今天只需要一个小物件改善首次探索。


### 本轮自迭代手记

# 2026-08-12 自迭代手记

## 现状分析

今天接手时，作品已经有比较完整的铁匠铺欢迎页骨架：3D 场景、三个 NPC、铁砧、水桶、工作台、火炉、iLoop 彩蛋，以及上一轮新增的“闭环卷轴 · iLoop 证据链”。CHANGELOG 里最新一轮还停在 2026-08-10，仓库没有 HUMAN_FEEDBACK，工作树只有本轮 `.autoloop/runs/` 未跟踪。

我看到的主要缺口不是内容不足，而是首次访问者的方向感还可以更清楚。访客能点很多东西，但第一次进门时可能不知道“老杨是谁、项目在哪里、iLoop 从哪里看、火炉能做什么”。上一轮刚补了 iLoop 方法论物件，今天不适合继续堆项目说明，应该补一个轻量的空间导览，让欢迎页更像一个可逛的铺子。

## 外部输入与来源

本轮输入卡写在 `.autoloop/inputs/2026-08-12.md`。

我调查了 4 个公开来源：

- `arvincatalbas/3D-Interactive-Portfolio`：https://github.com/arvincatalbas/3D-Interactive-Portfolio，看到 3D 房间用可点击物件聚焦内容、再打开信息面板的机制。
- `Interactive Way-finding Maps`：https://www.axiell.com/uk/solutions/product/cultureconnect/interactive-way-finding-maps-culture-connect-case-study/，看到博物馆导览用编号、地图、视觉列表降低访客找展品的成本。
- `National Museum of Natural History Wayfinding Kiosk`：https://interactiveknowledge.com/our-portfolio/national-museum-natural-history-wayfinding-kiosk，看到地点菜单搭配图像、图标、标题，并用路径和地标帮助访客记住方向。
- `The Art of Immersion: How Environment Design Shapes Player Experience`：https://vaguely.xyz/posts/the-art-of-immersion-how-environment-design-shapes-player-experience，看到环境叙事强调用物件、磨损、灯光和摆放传达“谁在这里、发生过什么”。

## 输入如何变成想法

我吸收的原则是：首次访问者需要一个低干扰的场景内定位点，告诉他“你在这里、可以去哪里、每个地标对应什么”。它不能变成现代 kiosk 或完整小地图，否则会把铁匠铺欢迎页推向工具化；也不能只是屏幕上的说明文字，否则不符合这个页面已有的空间叙事。

所以我把导览转译成铁匠铺里的木制路牌：三层箭头木板、铆钉、炉火色定位环，放在默认视角左前方。点击后它用老杨的口吻说明四个方向：左边认识老杨，右边看项目，火炉旁试欢迎语，卷轴上看 iLoop 闭环。

没有采用完整 3D portfolio 的大面板镜头缩放，也没有采用博物馆 kiosk 的完整路径系统。理由是当前场景很小，重地图会显得过度，今天只需要一个入口级的方向锚点。

## 今天的想法

新增一个“铺子导览牌 · 你在这里”可点击物件，让第一次进入铁匠铺的人先获得路线感。它本质上仍是欢迎页里的小物件，不改变页面定位，也不新增复杂系统。

## 为什么这么做

这个选择落在画像安全区：新增 `OBJECT_CONFIG` 项、用 `makeProp` 基础几何体做物件、注册现有交互。风险低、可回退，也能承接上一轮的闭环卷轴。

相比新增 NPC 或大改相机，导览牌的收益更直接：它把已有内容组织起来，让访客知道该往哪里点。相比加一段显眼的新手教程，它更符合铁匠铺氛围，像铺子里本来就会立着的木牌。

## 做了哪些事

- 修改 `index.html`：
  - 新增 `OBJECT_CONFIG.guidepost`，名称为“铺子导览牌 · 你在这里”。
  - 在场景初始化中创建并注册 `guidepost`。
  - 在 `makeProp` 中新增木制导览牌几何体：木桩、底座、三层箭头木板、铆钉和炉火色定位环。
  - 给导览牌补了透明 `createHotspot` 命中盒，确保点击木牌附近能稳定打开说明。
- 新增 `.autoloop/inputs/2026-08-12.md`，记录本轮公开外部输入、吸收原则、拒绝候选和转译方案。

Commit: `e998e5430d961665b5c30b4a46d0f2b97a681490`

## 最终效果

本地验证通过：使用 `python3 -m http.server 8123` 启动页面，再用 Playwright Chromium 打开 `http://127.0.0.1:8123/?t=2026-08-12-guidepost-hotspot`。页面 loader 正常隐藏，canvas 存在，点击坐标 `(430, 500)` 命中“铺子导览牌 · 你在这里”，对话框显示预期文案。console 没有 error；只有自动播放限制和软件 WebGL 的 warning，和本次改动无关。

本地截图：`.autoloop/journal/assets/2026-08-12-local.png`

线上无痕验证通过：固定脚本 `.autoloop/engine/verify_web.sh` 确认线上 `index.html` 与当前版本 SHA-256 一致，`online_html_match: true`，Chromium 渲染时 loader 隐藏、canvas 存在、无 console error。仍有自动播放限制和软件 WebGL 的 warning，和本次改动无关。

线上截图：`.autoloop/journal/assets/2026-08-12-online.png`


`AutoLoopRun:2026-08-12_030001`
