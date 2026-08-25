# 铁匠铺 · NPC Voice Panel 3D

真 3D · 360° 旋转 · 可点击交互的 NPC 语音对话面板。

## 目录结构

```
npc_voice_panel_3d/
├── index.html          ← 主文件，直接浏览器打开
└── assets/
    ├── bg_smithy.glb       铁匠铺背景（可选，缺失会用兜底地面）
    ├── npc_master.glb      铁匠老师傅
    ├── npc_apprentice.glb  学徒
    ├── npc_yq.glb          YQ
    └── music/              两种场景模式对应的专业背景音乐
```

## 内容联动

个人主页 `https://jobyang.cn/` 是公开内容事实源。页面加载
`https://jobyang.cn/showcase.js`，把最新项目、文章和手记映射到三个已有 NPC 的对话与链接；加载失败时
使用内置文案，不影响 3D 场景。

场景只保留现有铁匠铺和人物 GLB，不再用基础几何体堆叠新家具或陈列装置。新增内容优先进入人物对话。

## 音乐

- 舒缓模式：`assets/music/hearth-and-hammer.mp3`
- 火炉模式：`assets/music/hearthside-ales.mp3`

两份音频末尾均已烘焙 5 秒渐出；切换场景模式时页面再做短交叉淡化。

## 接你的语音逻辑

在 `index.html` 底部找到：

```js
window.onNPCSelected = function(key, cfg) {
  // TODO: 你的语音播放逻辑写这里
};
```

`key` 是 `master / apprentice / yq`，`cfg.line` 是对话文本。

## 操作

- 左键拖拽：360° 旋转视角
- 滚轮：缩放
- 点击 NPC / 左侧按钮：选中 + 弹对话框
- 自动旋转 / 炉火强度 / 重置视角：左侧面板

## 本地预览

直接双击 `index.html` 即可（ES Module CDN 走的 unpkg.com，需联网）。
若 CORS 报错，起个简单静态服务（任选其一）：

```bash
# Python
python3 -m http.server 8080
# Node
npx serve
```
