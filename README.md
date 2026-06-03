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
    └── npc_yq.glb          YQ
```

## 资源补充

从 https://seed3d.bytedance.net 下载 GLB → 重命名 → 丢进 `assets/` 即可。

资源没补齐前用**彩色胶囊体占位**，不阻塞开发。

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
