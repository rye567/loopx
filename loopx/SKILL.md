---
name: loopx
description: 当用户要求 LoopX、质量门、阶段化工程审核、完整 loop、风险分级实现、跨模块变更或结构化项目交付时使用。
---

# LoopX

跨 Codex 和 Claude Code 的工程质量门 skill。`loopx/` 是唯一主源；完整流程契约见 `workflow.md`。

## 不可跳过规则

1. 先初始化状态机，不要手工猜执行深度；环境检查由控制器在 `init` 时自动执行并记录为 `PASS`，不得等待人工确认：

```bash
python loopx/tools/loopx_controller.py init "需求描述" --mode auto --risk-tags tenant_scope core_state_transition api_contract
python loopx/tools/loopx_controller.py status --tracking
```

2. 只能用控制器推进：`interview`、`spec`、`mode --select ...`、`record-stage`、`confirm-stage`、`advance --to ...` 或 `next`。不要手改 `state.json` 把阶段伪造成 `PASS`。
3. `interview` 必须把问题展示给用户，并把用户回答写入 `interview.md`；空采访或仍含“待用户回答/未回答”的采访不得记录 `PASS`。
4. `solution_review` 未经 `confirm-stage` 变为 `PASS` 前禁止开发；业务写入前必须运行：

```bash
python loopx/tools/loopx_controller.py can-write --kind business
```

5. 阶段文档和分析文档必须写入项目根目录下的 `docs/loopx/<date>-<slug>/`；`.loopx/runs/<run_id>/` 只存控制器状态、worklist、events、stage-results 和自动生成 artifact。
6. Review 不通过或用户指出问题时，必须创建返工任务并回到 owner 阶段：

```bash
python loopx/tools/loopx_controller.py fail-review --from solution_review --return-to solution_design --item W1 --reason "原因"
python loopx/tools/loopx_controller.py claim-stage solution_design
python loopx/tools/loopx_controller.py close-repair --item W1 --artifact stage-results/06-solution-design.json --revision 2 --change "修正说明"
```

7. `validate PASS` 只代表结构合法，不代表 LoopX 流程通过；最终放行还需要阶段 `PASS`、写入闸门、health gate 和未覆盖项说明。
8. 确认门阶段的 agent `PASS` 会先落为 `NEED_HUMAN`；用户确认后运行 `confirm-stage --stage <stage> --evidence "..."` 才能继续。代码审查、测试审核和发布就绪 `PASS` 后不需要人工确认，可继续进入下一阶段。

## 入口

- Codex：`$loopx ...`
- Claude Code：`/loopx ...`
- 命中质量门、完整 loop、阶段化开发、跨模块、SQL/MQ、权限、租户或核心状态流转时，优先判断是否进入 LoopX。

## 必读资源

- `workflow.md`：唯一完整流程契约。
- `project-harness.md`：项目发现和默认 harness。
- `risk.yml`、`health.yml`、`project-profiles.yml`：风险、健康检查和 profile 策略。
- `agents/`：阶段角色边界。
- `templates/`：阶段文档模板。
- `schemas/`：state、stage-result、worklist、health、interview、spec、mode、tracking 契约。
- `tools/loopx_controller.py`：本地状态控制器。

## 执行流程

1. 做项目发现：README、构建文件、主配置、源码结构和测试目录；`init` 后环境检查应已自动 `PASS`，当前阶段进入 `requirement_intake`。
2. 按 `risk.yml` 准备风险标签，用 `init --mode auto --risk-tags ...` 选择执行深度。
3. 按 `workflow.md` 阶段顺序推进；每阶段读取对应 `agents/`、必要时使用 `templates/`；阶段文档写入 `docs/loopx/<date>-<slug>/`；需求采访阶段必须先向用户提问并等待回答。
4. 阶段结束写入 `stage-results/*.json`；`requirement_interview` 和 `solution_review` 确认门停在 `NEED_HUMAN`，用户确认后用 `confirm-stage` 转为 `PASS`。
5. 进入下一阶段前用 `advance --to ...` 或 `next`；最终用 `gate`、`git-gate`、`close` 收口。
6. 最终结论区分本地通过、本地阻塞、未覆盖/需 CI 验证。

## 状态控制器

常用命令索引：

```bash
python loopx/tools/loopx_controller.py status --tracking
python loopx/tools/loopx_controller.py validate --strict
python loopx/tools/loopx_controller.py gate <run_id>
python loopx/tools/loopx_controller.py git-gate <run_id>
python loopx/tools/loopx_controller.py close <run_id>
```

如果当前工作目录就是 skill 目录，使用相对路径，例如 `python tools/loopx_controller.py validate`。完整命令流以 `workflow.md` 为准。

## 项目接入

不要生成或覆盖项目的 `.codex`、`.claude`、`AGENTS.md`、`CLAUDE.md` 文件。项目需要本地提醒时，只手动加入一小段说明：使用已安装的 `loopx` skill，并在执行阶段前读取项目已有文档和配置。

## 生产约束

- 不为通过流程而降低断言、跳过证据、隐藏失败或伪造 `PASS`。
- 高风险动作仍需显式确认，包括 git commit/push、强推、生产/联调写入、破坏性删除和真实外部系统调用。
- 遇到已有用户改动时协同处理，不得无授权回滚。
- 需求采访未经实际提问、回答写入和用户 `confirm-stage --stage requirement_interview` 确认前，不得生成或通过 Spec。
- 没有硬证据时，最终报告必须写明未覆盖或需要 CI 验证。
