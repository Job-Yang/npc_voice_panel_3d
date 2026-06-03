#!/usr/bin/env bash
# ============================================================
#  GLB 批量压缩脚本
#  用法：
#    cd 到本目录后执行  ./compress.sh
#    或在任意目录执行   bash /path/to/assets/compress.sh
#
#  逻辑：
#    1. 扫描脚本所在目录下所有 .glb
#    2. 跳过已压缩文件（文件名带 .min.glb 后缀的）
#    3. 跳过本轮已生成的产物（防止重复压自己）
#    4. 备份原文件到 ./_backup_originals/
#    5. 用 gltf-transform 减面 + 贴图 webp + draco 几何压缩
#    6. 替换原文件
#
#  多次执行安全：原文件已被替换为压缩版，再跑会被识别成"已压过"
#  跳过；备份目录里始终保留第一次的原始版本。
# ============================================================

set -e

# 切到脚本所在目录
cd "$(dirname "$0")"

# 检查依赖
if ! command -v gltf-transform &> /dev/null; then
  echo "❌ 没装 gltf-transform，先跑："
  echo "   npm install -g @gltf-transform/cli"
  exit 1
fi

BACKUP_DIR="./_backup_originals"
mkdir -p "$BACKUP_DIR"

# 压缩参数（可调）
SIMPLIFY_RATIO="${SIMPLIFY_RATIO:-0.1}"   # 保留面数比例，0.05 更狠，0.2 更保守
TEX_SIZE="${TEX_SIZE:-2048}"              # 贴图最大边长，2048=2K
MARKER_KEY="MIRA_COMPRESSED_V1"           # 标记字符串，用于识别已压缩文件

echo "🔧 压缩参数：simplify_ratio=$SIMPLIFY_RATIO, texture_size=$TEX_SIZE"
echo ""

shopt -s nullglob
glb_files=( *.glb )

if [ ${#glb_files[@]} -eq 0 ]; then
  echo "⚠️  当前目录没有 .glb 文件"
  exit 0
fi

for f in "${glb_files[@]}"; do
  # 跳过中间产物（如果上次跑崩了留下来的）
  if [[ "$f" == *.tmp.glb ]] || [[ "$f" == *.step1.glb ]]; then
    echo "⏭  跳过中间文件：$f"
    continue
  fi

  # 通过文件末尾标记识别是否已压缩
  if tail -c 200 "$f" 2>/dev/null | grep -q "$MARKER_KEY"; then
    echo "✅ 已压缩，跳过：$f"
    continue
  fi

  echo "▶️  处理 $f ..."
  orig_size=$(du -h "$f" | cut -f1)

  # 备份原文件（只在第一次备份，已存在不覆盖）
  if [ ! -f "$BACKUP_DIR/$f" ]; then
    cp "$f" "$BACKUP_DIR/$f"
    echo "   📦 已备份原文件到 $BACKUP_DIR/$f"
  fi

  # Step 1: 优化（减面 + 贴图压缩）
  gltf-transform optimize "$f" "$f.step1.glb" \
    --simplify-ratio "$SIMPLIFY_RATIO" \
    --texture-compress webp \
    --texture-size "$TEX_SIZE" \
    --compress draco \
    2>&1 | sed 's/^/   /'

  # 在文件末尾追加标记（GLB 末尾可以加自定义 chunk，简单起见这里直接 append）
  # 注意：GLB 严格规范不允许多余数据，但 three.js 的 GLTFLoader 会忽略尾部多余字节
  printf "%s" "$MARKER_KEY" >> "$f.step1.glb"

  # 替换原文件
  mv "$f.step1.glb" "$f"
  new_size=$(du -h "$f" | cut -f1)

  echo "   ✅ $f: $orig_size → $new_size"
  echo ""
done

echo "🎉 全部完成。原文件备份在 $BACKUP_DIR/"
echo "💡 想恢复某个原文件：cp $BACKUP_DIR/xxx.glb ./xxx.glb"
echo "💡 想调整压缩强度："
echo "   SIMPLIFY_RATIO=0.05 ./compress.sh     # 更狠（保留 5%）"
echo "   SIMPLIFY_RATIO=0.2  ./compress.sh     # 更保守（保留 20%）"
