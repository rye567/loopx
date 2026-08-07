---
name: loopx
description: 当用户要求 LoopX、阶段化工程审核、完整 loop、风险分级实现、跨模块变更或结构化项目交付时使用。
---

# LoopX

LoopX 是 Codex 和 Claude Code 可共用的阶段化工程工作流。`loopx/` 是唯一主源；完整流程契约见 `workflow.md`。

## 不可跳过规则

1. 先初始化状态机，不手工猜执行深度；仅当本次运行显式激活兼容 Provider 且需要从外部引用加载需求时，先执行通用 `before_init` Hook。环境检查由 controller 在 `init` 时自动执行并记录为 `PASS`：
```bash
python loopx/tools/loopx_controller.py init "需求描述" --mode auto --risk-tags tenant_scope core_state_transition api_contract
python loopx/tools/loopx_controller.py status --tracking
```

2. 只能用 controller 推进：`interview`、`spec`、`mode --select ...`、`record-stage`、`confirm-stage`、`advance --to ...` 或 `next`；不要手改 `state.json` 伪造 `PASS`。
3. `interview` 必须先把问题展示给用户，并把回答写入 `interview.md`；仍含“待用户回答/未回答”时不得记录 `PASS`。
4. `solution_review` 未经 `confirm-stage` 变为 `PASS` 前禁止开发；业务写入前必须运行：
```bash
python loopx/tools/loopx_controller.py can-write --kind business
```

5. 阶段文档和分析文档写入 `docs/loopx/<date>-<slug>/`；`docs/loopx/runs/<run_id>/` 只存 controller 状态、worklist、events、stage-results 和自动生成 artifact，收口时中间状态（events、repair-tickets）自动归档到 `artifacts/archive/`。
6. Review 不通过或用户指出问题时，必须创建返工任务并回到 owner 阶段：

```bash
python loopx/tools/loopx_controller.py fail-review --from solution_review --return-to solution_design --item W1 --reason "原因"
python loopx/tools/loopx_controller.py claim-stage solution_design
python loopx/tools/loopx_controller.py close-repair --item W1 --artifact stage-results/06-solution-design.json --revision 2 --change "修正说明"
```

7. `validate PASS` 只代表结构合法，不代表 LoopX 流程通过；最终放行还需要阶段 `PASS`、写入保护检查、health 检查和未覆盖项说明。
8. 需求采访和方案审核通过后先落为 `NEED_HUMAN`；用户确认后运行 `confirm-stage --stage requirement_interview` 或对应阶段才能继续。代码审查、测试审核和发布就绪 `PASS` 后可继续；可选 Provider 只按 `workflow.md` 的通用契约执行，不得新增阶段或绕过人工门。

## 入口

- Codex：`$loopx ...`
- Claude Code：`/loopx ...`
- 命中完整 loop、阶段化开发、跨模块、SQL/MQ、权限、租户或核心状态流转时，优先判断是否进入 LoopX。

## 必读资源

- `workflow.md`：完整流程契约。
- `project-harness.md`：项目发现和默认 harness。
- `risk.yml`、`health.yml`、`project-profiles.yml`：风险、健康检查和 profile 策略。
- `agents/`、`templates/`、`schemas/`：角色边界、阶段模板和结构契约。
- `tools/loopx_controller.py`：本地状态控制器。

## 执行流程

1. 做项目发现：README、构建文件、主配置、源码结构和测试目录。
2. 准备风险标签，用 `init --mode auto --risk-tags ...` 选择执行深度。
3. 按 `workflow.md` 阶段顺序推进，并在已激活 Provider 订阅的生命周期事件调用它；需求采访必须先向用户提问并等待回答。
4. 阶段结束写入 `stage-results/*.json`；需求采访和方案审核需要用户确认。
5. 进入下一阶段前用 `advance --to ...` 或 `next`；最终用 `gate`、`git-gate`、`compound`、`close` 收口。
6. 收口前记录 Compound Capture：默认只写 run artifact；用户确认或项目配置允许时才写 `docs/loopx/solutions/<category>/<slug>.md`。
7. 最终结论区分本地通过、本地阻塞、未覆盖/需 CI 验证，并单列可选 Provider 状态。

## 状态控制器
```bash
python loopx/tools/loopx_controller.py status --tracking
python loopx/tools/loopx_controller.py validate --strict
python loopx/tools/loopx_controller.py gate <run_id>
python loopx/tools/loopx_controller.py git-gate <run_id>
python loopx/tools/loopx_controller.py compound <run_id> --decision skipped --reason "本次无可复用学习点"
python loopx/tools/loopx_controller.py close <run_id>
```

如果当前工作目录就是 skill 目录，使用相对路径，例如 `python tools/loopx_controller.py validate`。

## 项目接入

不要生成或覆盖项目的 `.codex`、`.claude`、`AGENTS.md`、`CLAUDE.md`。项目需要本地提醒时，只手动加入一小段说明：使用已安装的 `loopx` skill，并在执行阶段前读取项目已有文档和配置。
