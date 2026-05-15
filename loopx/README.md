# LoopX 中立源

本目录是 LoopX 的全局中立源。它不是 Codex 专属规则，也不是 Claude Code 专属规则；这里维护通用工作流、`quality-*` agent 职责、权限策略和文档模板，再同步到不同工具的适配层。

正式主源位于当前用户的 `~/.loopx`。项目内只保留 `.codex/loopx-project/` 作为项目专属适配源。

## 日常使用

1. 任意项目运行：`loopx-sync project` 或 `loopx-sync all`。
2. 通用流程改 `~/.loopx/workflow.md`、`~/.loopx/agents/`、`~/.loopx/permissions.yml`、`~/.loopx/health.yml`、`~/.loopx/risk.yml`、`~/.loopx/project-profiles.yml` 或 `~/.loopx/templates/`。
3. 项目专属规则放在当前项目的 `.codex/loopx-project/`。
4. Claude Code 使用 `/loopx 处理需求：...`；Codex 使用 `$loopx 处理需求：...`。

## 私有落点

- 全局中立源：`~/.loopx/`
- 控制器入口：macOS/Linux 默认 `~/.local/bin/loopx`；Windows 默认 `%LOCALAPPDATA%\LoopX\bin\loopx.cmd`
- 命令入口：macOS/Linux 默认 `~/.local/bin/loopx-sync`；Windows 默认 `%LOCALAPPDATA%\LoopX\bin\loopx-sync.cmd`
- 全局 Codex：`~/.codex/skills/loopx/`、`~/.codex/agents/quality-*.toml`
- 全局 Claude：`~/.claude/skills/loopx/`、`~/.claude/agents/quality-*.md`
- 项目 Codex：`AGENTS.md`、`.codex/config.toml`、`.codex/hooks.json`、`.codex/rules/`、`.codex/hooks/`、`.codex/skills/loopx/`
- Claude Code：`CLAUDE.md`、`.claude/`
- 阶段文档：`docs/loopx-runs/<date>-<slug>/`
- 运行状态：`.loopx/runs/<run_id>/state.json`、`worklist.yml`、`events.jsonl`、`stage-results/`

## 状态控制器

`loopx` 是 LoopX 的本地状态控制器，当前提供最小生产化闭环：

```bash
loopx init "需求描述"
loopx status
loopx validate
```

它会创建并校验 `.loopx/runs/<run_id>/` 下的运行状态、worklist 和阶段结果。校验器只使用 Python 标准库，并使用 `schemas/*.schema.json` 中的结构契约。

同步脚本不会修改 `.gitignore`，也不会执行 `git add/commit/push`。

## 跨平台

通用源不得写死 `/data`、`/usr/bin/python3`、`/Users/...` 或 shell-only 路径。安装器和同步器必须根据当前系统生成 Python 命令、hooks 和 wrapper；Windows 用户不需要手工改 PATH 或脚本路径。
