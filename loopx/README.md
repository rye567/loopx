# LoopX 技能

## 前置门禁最小闭环

控制器现在会在每次运行中持久化需求采访、规格、执行等级选择和追踪元数据：

```bash
python tools/loopx_controller.py init "需求描述" --mode auto --risk-tags api_contract
python tools/loopx_controller.py status --tracking
python tools/loopx_controller.py interview <run_id>
python tools/loopx_controller.py record-stage --run-id <run_id> --stage requirement_interview --status PASS --evidence .loopx/runs/<run_id>/artifacts/interview.md
python tools/loopx_controller.py spec <run_id>
python tools/loopx_controller.py record-stage --run-id <run_id> --stage spec_draft --status PASS --evidence .loopx/runs/<run_id>/artifacts/spec.md
python tools/loopx_controller.py record-stage --run-id <run_id> --stage spec_review --status PASS --evidence .loopx/runs/<run_id>/artifacts/spec.md
python tools/loopx_controller.py mode <run_id> --select FULL
python tools/loopx_controller.py next <run_id>
python tools/loopx_controller.py validate --strict
python tools/loopx_controller.py gate <run_id>
python tools/loopx_controller.py git-gate <run_id>
python tools/loopx_controller.py close <run_id>
```

`advance --to solution_design` 会在 `requirement_interview`、`spec_review` 和 `mode_selection` 通过前被阻止。

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
- `schemas/`：运行状态、worklist、阶段结果、health 结果，以及 interview/spec/mode/tracking 前置门禁结构契约。
- `health.yml`、`risk.yml`、`project-profiles.yml`：策略配置。
- `tools/loopx_controller.py`：可选的本地状态控制脚本。
- 阶段文档：`docs/loopx-runs/<date>-<slug>/`
- 运行状态：`.loopx/runs/<run_id>/state.json`、`worklist.yml`、`events.jsonl`、`stage-results/`

## 状态控制器

`tools/loopx_controller.py` 是 LoopX 的本地状态控制器，当前提供最小生产化闭环：

```bash
python tools/loopx_controller.py init "需求描述" --mode auto --risk-tags tenant_scope core_state_transition api_contract
python tools/loopx_controller.py status
python tools/loopx_controller.py status --tracking
python tools/loopx_controller.py interview <run_id>
python tools/loopx_controller.py record-stage --run-id <run_id> --stage requirement_interview --status PASS --evidence .loopx/runs/<run_id>/artifacts/interview.md
python tools/loopx_controller.py spec <run_id>
python tools/loopx_controller.py record-stage --run-id <run_id> --stage spec_draft --status PASS --evidence .loopx/runs/<run_id>/artifacts/spec.md
python tools/loopx_controller.py record-stage --run-id <run_id> --stage spec_review --status PASS --evidence .loopx/runs/<run_id>/artifacts/spec.md
python tools/loopx_controller.py mode <run_id> --select FULL
python tools/loopx_controller.py next <run_id>
python tools/loopx_controller.py validate
python tools/loopx_controller.py validate --strict
python tools/loopx_controller.py gate <run_id>
python tools/loopx_controller.py git-gate <run_id>
python tools/loopx_controller.py close <run_id>
python tools/loopx_controller.py record-stage --stage solution_design --status PASS --evidence docs/solution.md
python tools/loopx_controller.py advance --to solution_review
python tools/loopx_controller.py fail-review --from solution_review --return-to solution_design --item W1 --reason "原因"
python tools/loopx_controller.py claim-stage solution_design
python tools/loopx_controller.py close-repair --item W1 --artifact stage-results/06-solution-design.json --revision 2 --change "修正说明"
python tools/loopx_controller.py can-write --kind business
```

它会创建 `.loopx/runs/<run_id>/` 下的运行状态、worklist、阶段结果和返工任务。`validate` 只说明结构合法；`gate` 运行严格流程门；`git-gate` 读取本地 Git 变更并写入 diff summary；`close` 在最终报告和严格门都通过后关闭整个 run，并生成 `artifacts/close-evidence.json`。`advance` 负责阶段流转，`fail-review`/`claim-stage`/`close-repair` 负责 review-driven repair loop，`can-write` 负责业务代码写入解锁。控制器只使用 Python 标准库，并使用 `schemas/*.schema.json` 中的结构契约。
