# 铁匠铺 · NPC Voice Panel 3D

真 3D · 360° 旋转 · 可点击交互的老杨铁匠铺欢迎页。

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

## 内容

页面内置老杨、iLoop、近况和火炉四站导览，所有内容都在本仓独立维护；运行时不读取或跳转个人主页。

场景只保留现有铁匠铺和人物 GLB，不再用基础几何体堆叠新家具或陈列装置。新增内容优先进入人物对话。

## 音乐

- 舒缓模式：`assets/music/hearth-and-hammer.mp3`
- 火炉模式：`assets/music/hearthside-ales.mp3`

两份音频末尾均已烘焙 5 秒渐出；切换场景模式时页面再做短交叉淡化。

## 接你的语音逻辑

在 `index.html` 底部找到：

```js
window.onNPCSelected = function(key, options = {}) {
  // 播放对应 NPC 的本地语音
};
```

`key` 是 `master / apprentice / yq`；`yq` 默认只显示台词，不播放语音。

## 操作

- 左键拖拽：360° 旋转视角
- 滚轮：缩放
- 点击 NPC / 火炉 / 巡铺路线：选中 + 弹对话框
- 场景模式 / 音乐 / 炉火强度 / 重置视角：页面按钮与左侧面板

## 本地预览

GLB、音频和 ES Module 需要经 HTTP 打开，起一个简单静态服务：

```bash
# Python
python3 -m http.server 8123
# Node
npx serve
```
