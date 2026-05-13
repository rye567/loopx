# LoopX 中立源

本目录是 LoopX 的全局中立源。它不是 Codex 专属规则，也不是 Claude Code 专属规则；这里维护通用工作流、`quality-*` agent 职责、权限策略和文档模板，再同步到不同工具的适配层。

正式主源位于 `~/.loopx`。项目内只保留 `.codex/loopx-project/` 作为项目专属适配源。

## 日常使用

1. 任意项目运行：`loopx-sync project` 或 `loopx-sync all`。
2. 通用流程改 `~/.loopx/workflow.md`、`~/.loopx/agents/`、`~/.loopx/permissions.yml` 或 `~/.loopx/templates/`。
3. 项目专属规则放在当前项目的 `.codex/loopx-project/`。
4. Claude Code 使用 `/loopx 处理需求：...`；Codex 使用 `$loopx 处理需求：...`。

## 私有落点

- 全局中立源：`~/.loopx/`
- 全局 Codex：`~/.codex/skills/loopx/`、`~/.codex/agents/quality-*.toml`
- 全局 Claude：`~/.claude/skills/loopx/`、`~/.claude/agents/quality-*.md`
- 项目 Codex：`AGENTS.md`、`.codex/config.toml`、`.codex/hooks.json`、`.codex/rules/`、`.codex/hooks/`、`.codex/skills/loopx/`
- Claude Code：`CLAUDE.md`、`.claude/`
- 阶段文档：`docs/loopx-runs/<date>-<slug>/`

同步脚本不会修改 `.gitignore`，也不会执行 `git add/commit/push`。
