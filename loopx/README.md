# LoopX 技能

本目录是 LoopX skill 包主源。完整流程契约在 `workflow.md`，本文件只保留入口和目录索引。

## 日常使用

1. Claude Code 使用 `/loopx 处理需求：...`；Codex 使用 `$loopx 处理需求：...`。
2. 通用流程改 `workflow.md`、`agents/`、`health.yml`、`risk.yml`、`project-profiles.yml`、`templates/` 或 `schemas/`。
3. 项目专属规则保留在项目自己的 README、AGENTS、CLAUDE 或其它既有文档里；LoopX 运行时先做项目发现。

## 目录

- `SKILL.md`：skill 入口和不可跳过规则。
- `workflow.md`：阶段化工程工作流主流程。
- `agents/`：阶段角色职责。
- `templates/`：阶段文档模板。
- `schemas/`：运行状态、worklist、阶段结果、health、interview、spec、mode、tracking、compound learning 契约。
- `health.yml`、`risk.yml`、`project-profiles.yml`：策略配置。
- `tools/loopx_controller.py`：本地状态控制器。
- `docs/loopx/runs/<run_id>/`：controller 状态、worklist、events、stage-results 和自动生成 artifact；收口时中间状态（events、repair-tickets）归档到 `artifacts/archive/`，该目录不进版本库。
- `docs/loopx/solutions/<category>/<slug>.md`：显式允许后写入的长期复用学习。

## 状态控制器

控制器只依赖 Python 标准库。完整命令流见 `workflow.md`；常用命令如下：

```bash
python tools/loopx_controller.py init "需求描述" --mode auto --risk-tags api_contract
python tools/loopx_controller.py status --tracking
python tools/loopx_controller.py validate --strict
python tools/loopx_controller.py gate <run_id>
python tools/loopx_controller.py compound <run_id> --decision skipped --reason "本次无可复用学习点"
```

`init` 会自动执行环境检查，写入 `stage-results/00-environment-check.json`，并把当前阶段推进到 `requirement_intake`，不需要人工确认。

`interview` 会把需求采访问题输出给用户；必须把用户回答写入 `interview.md`，且文件不再包含“待用户回答/未回答”等占位后，才能记录 `requirement_interview PASS`。

需要用户确认的阶段，agent `PASS` 会先落为 `NEED_HUMAN`；用户确认后用 `confirm-stage` 转为 `PASS`。业务写入前用 `can-write` 检查写入条件：

```bash
python tools/loopx_controller.py confirm-stage --stage requirement_interview --evidence "user confirmed interview"
python tools/loopx_controller.py confirm-stage --stage solution_review --evidence "user confirmed solution review"
python tools/loopx_controller.py can-write --kind business
```

Compound Capture 默认只记录 `docs/loopx/runs/<run_id>/artifacts/compound-capture.md`。只有用户确认或项目配置允许时，才用 `--write-project-doc` 写入 `docs/loopx/solutions/<category>/<slug>.md`。
