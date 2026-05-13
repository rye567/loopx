#!/usr/bin/env bash
set -euo pipefail

if [ "${1:-}" != "--yes" ]; then
  cat <<'USAGE'
这会删除当前用户的 LoopX 全局安装：
  ~/.loopx
  ~/.local/bin/loopx-sync
  ~/.codex/skills/loopx
  ~/.codex/agents/quality-*.toml
  ~/.claude/skills/loopx
  ~/.claude/agents/quality-*.md

确认执行：
  bash uninstall.sh --yes
USAGE
  exit 2
fi

rm -rf "$HOME/.loopx"
rm -f "$HOME/.local/bin/loopx-sync"
rm -rf "$HOME/.codex/skills/loopx"
rm -f "$HOME"/.codex/agents/quality-*.toml
rm -rf "$HOME/.claude/skills/loopx"
rm -f "$HOME"/.claude/agents/quality-*.md

echo "LoopX 已卸载。项目内 AGENTS.md、CLAUDE.md、.codex、.claude 不会被自动删除。"
