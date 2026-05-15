# LoopX Skill

本目录就是 LoopX 的 skill 包主源。

## 日常使用

1. Claude Code 使用 `/loopx 处理需求：...`；Codex 使用 `$loopx 处理需求：...`。
2. 通用流程改 `workflow.md`、`agents/`、`health.yml`、`risk.yml`、`project-profiles.yml`、`templates/` 或 `schemas/`。
3. 项目专属规则保留在项目自己的 README、AGENTS、CLAUDE 或其它既有文档里；LoopX 运行时先做项目发现。

## 目录

- `SKILL.md`：skill 入口和资源索引。
- `workflow.md`：阶段化质量门主流程。
- `agents/`：阶段角色职责。
- `templates/`：阶段文档模板。
- `schemas/`：运行状态、worklist、阶段结果和 health 结果结构契约。
- `health.yml`、`risk.yml`、`project-profiles.yml`：策略配置。
- `tools/loopx_controller.py`：可选的本地状态控制脚本。
- 阶段文档：`docs/loopx-runs/<date>-<slug>/`
- 运行状态：`.loopx/runs/<run_id>/state.json`、`worklist.yml`、`events.jsonl`、`stage-results/`

## 状态控制器

`tools/loopx_controller.py` 是 LoopX 的本地状态控制器，当前提供最小生产化闭环：

```bash
python tools/loopx_controller.py init "需求描述" --mode auto --risk-tags tenant_scope core_state_transition api_contract
python tools/loopx_controller.py status
python tools/loopx_controller.py validate
python tools/loopx_controller.py record-stage --stage solution_design --status PASS --evidence docs/solution.md
python tools/loopx_controller.py advance --to solution_review
python tools/loopx_controller.py review-feedback --item W1 --return-to solution_design --reason "原因"
python tools/loopx_controller.py can-write --kind business
```

它会创建 `.loopx/runs/<run_id>/` 下的运行状态、worklist 和阶段结果。`validate` 只说明结构合法；`advance` 才负责阶段流转，`can-write` 才负责业务代码写入解锁。控制器只使用 Python 标准库，并使用 `schemas/*.schema.json` 中的结构契约。
