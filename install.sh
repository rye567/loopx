#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SOURCE="$ROOT/loopx"
LOOPX_HOME="${LOOPX_HOME:-$HOME/.loopx}"
LOCAL_BIN="${LOOPX_BIN_DIR:-$HOME/.local/bin}"
RUN_PROJECT=0

for arg in "$@"; do
  case "$arg" in
    --project)
      RUN_PROJECT=1
      ;;
    -h|--help)
      cat <<'USAGE'
用法：bash install.sh [--project]

安装 LoopX 全局核心到当前用户：
  ~/.loopx
  ~/.local/bin/loopx-sync
  ~/.codex/skills/loopx
  ~/.codex/agents/quality-*.toml
  ~/.claude/skills/loopx
  ~/.claude/agents/quality-*.md

选项：
  --project  安装全局核心后，在当前目录执行 loopx-sync project
USAGE
      exit 0
      ;;
    *)
      echo "未知参数：$arg" >&2
      exit 2
      ;;
  esac
done

if ! command -v python3 >/dev/null 2>&1; then
  echo "需要 python3 才能安装 LoopX。" >&2
  exit 1
fi

if [ ! -f "$SOURCE/tools/sync_loopx.py" ]; then
  echo "缺少 $SOURCE/tools/sync_loopx.py，安装包不完整。" >&2
  exit 1
fi

mkdir -p "$LOOPX_HOME" "$LOCAL_BIN"

if command -v rsync >/dev/null 2>&1; then
  rsync -a --exclude '.DS_Store' --exclude '__pycache__' --exclude '*.pyc' "$SOURCE/" "$LOOPX_HOME/"
else
  (cd "$SOURCE" && tar cf - .) | (cd "$LOOPX_HOME" && tar xf -)
fi

cat > "$LOCAL_BIN/loopx-sync" <<WRAPPER
#!/usr/bin/env bash
set -euo pipefail
exec python3 "$LOOPX_HOME/tools/sync_loopx.py" "\$@"
WRAPPER
chmod +x "$LOCAL_BIN/loopx-sync"

"$LOCAL_BIN/loopx-sync" global

if [ "$RUN_PROJECT" -eq 1 ]; then
  "$LOCAL_BIN/loopx-sync" project
fi

case ":$PATH:" in
  *":$LOCAL_BIN:"*) ;;
  *) echo "提示：$LOCAL_BIN 不在 PATH 中，请把它加入 shell 配置后重新打开终端。" ;;
esac

echo "LoopX 安装完成。可运行：loopx-sync doctor"
