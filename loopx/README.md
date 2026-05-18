# LoopX 技能

本目录是 LoopX skill 包主源。完整流程契约在 `workflow.md`，本文件只保留入口和目录索引。

## 日常使用

1. Claude Code 使用 `/loopx 处理需求：...`；Codex 使用 `$loopx 处理需求：...`。
2. 通用流程改 `workflow.md`、`agents/`、`health.yml`、`risk.yml`、`project-profiles.yml`、`templates/` 或 `schemas/`。
3. 项目专属规则保留在项目自己的 README、AGENTS、CLAUDE 或其它既有文档里；LoopX 运行时先做项目发现。

## 目录

- `SKILL.md`：skill 入口和不可跳过规则。
- `workflow.md`：阶段化质量门主流程。
- `agents/`：阶段角色职责。
- `templates/`：阶段文档模板。
- `schemas/`：运行状态、worklist、阶段结果、health、interview、spec、mode、tracking 契约。
- `health.yml`、`risk.yml`、`project-profiles.yml`：策略配置。
- `tools/loopx_controller.py`：本地状态控制器。
- `.loopx/runs/<run_id>/`：运行状态、worklist、事件、阶段结果和返工任务。

## 状态控制器

控制器只依赖 Python 标准库。完整命令流见 `workflow.md`；常用命令如下：

```bash
python tools/loopx_controller.py init "需求描述" --mode auto --risk-tags api_contract
python tools/loopx_controller.py status --tracking
python tools/loopx_controller.py validate --strict
python tools/loopx_controller.py gate <run_id>
```

确认门阶段的 agent `PASS` 会先落为 `NEED_HUMAN`；用户确认后用 `confirm-stage` 转为 `PASS`。业务写入前用 `can-write` 检查门禁：

```bash
python tools/loopx_controller.py confirm-stage --stage solution_review --evidence "user confirmed solution review"
python tools/loopx_controller.py can-write --kind business
```
