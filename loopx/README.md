# LoopX 技能

本目录是 LoopX skill 包主源。完整流程契约在 `workflow.md`，本文件只保留入口和目录索引。

## 日常使用

1. Claude Code 使用 `/loopx 处理需求：...`；Codex 使用 `$loopx 处理需求：...`。
2. 通用流程改 `workflow.md`、`agents/`、`health.yml`、`risk.yml`、`project-profiles.yml`、`templates/` 或 `schemas/`。
3. 项目专属规则保留在项目自己的 README、AGENTS、CLAUDE 或其它既有文档里；LoopX 运行时先做项目发现。

## 目录

- `SKILL.md`：skill 入口和不可跳过规则。
- `workflow.md`：阶段化工程工作流主流程。
- `standards/`：工程标准和版本化规则目录 `standards/catalog.yml`。
- `agents/`：阶段角色职责。
- `templates/`：阶段文档模板。
- `schemas/`：运行状态、工作项、阶段结果、规则目录、项目策略和六类阶段产物契约。
- `health.yml`、`risk.yml`、`project-profiles.yml`：健康检查、风险映射和项目类型配置。
- `templates/loopx-policy.yml`：可选项目策略示例；LoopX 不会自动写入项目。
- `tools/loopx_controller.py`：本地状态控制器。
- 用户状态目录 `<project-id>/<run_id>/run.json`：新运行的单文件容器；项目内的 `docs/loopx/runs/<run_id>/` 只作为旧运行兼容格式，不自动迁移或删除。
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

新运行的逻辑产物位于单文件容器内。用 `import-artifact --source <文件> --target artifacts/<名称>` 收纳已编辑的 interview/spec 或其他运行产物；结构化阶段产物可直接用 `record-stage --artifact-file 类型=<文件>` 导入并记录。`LOOPX_STATE_DIR` 可指定状态根，`LOOPX_STATE_BACKEND=project` 可创建旧目录格式的新运行。

需要用户确认的阶段，agent `PASS` 会先落为 `NEED_HUMAN`；用户确认后用 `confirm-stage` 转为 `PASS`。业务写入前用 `can-write` 检查写入条件：

```bash
python tools/loopx_controller.py confirm-stage --stage requirement_interview --evidence "user confirmed interview"
python tools/loopx_controller.py confirm-stage --stage solution_review --evidence "user confirmed solution review"
python tools/loopx_controller.py can-write --kind business
```

经验沉淀默认只记录 `docs/loopx/runs/<run_id>/artifacts/compound-capture.md`。只有用户确认或项目配置允许时，才用 `--write-project-doc` 写入 `docs/loopx/solutions/<category>/<slug>.md`。
