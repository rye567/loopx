# LoopX 工作流

当用户输入 `$loopx`、`/loopx`、完整 loop、多 agent loop、阶段化开发、测试先行实现或“项目分配到测试报告”时，执行本工作流。

## 调用契约

`$loopx 处理需求：...` 或 `/loopx 处理需求：...` 表示用户授权执行 LoopX 工作流，并允许按阶段委派子 agent。用户不需要额外补充“允许子 agent”或“按推荐模型”。

默认行为：

1. `init` 必须自动完成环境检查并落库 `environment_check PASS`；未显式输出 `mode: LIGHT|STANDARD|FULL` 前，不得写业务代码、测试、配置或 SQL。
2. 阶段状态只允许 `PASS`、`CHANGES_REQUIRED`、`BLOCKED`、`SKIPPED`、`ACCEPTED_RISK`、`NEED_HUMAN`；`SKIPPED` 仅允许显式 `LIGHT` 或配置允许，`ACCEPTED_RISK` 仅允许用户明确接受风险。
3. 除 `PASS`、合法 `SKIPPED` 或用户明确 `ACCEPTED_RISK` 外，不得进入下一阶段。
4. 同一阶段最多自动返工 2 次，第 3 次仍失败则 `BLOCKED`。
5. 方案设计和方案审核必须给出影响范围。
6. 测试用例必须包含业务/API 数据准备、执行入口、断言、清理动作和清理验证。
7. 开发阶段默认 auto：满足写入条件后，可直接修改受影响代码、测试和阶段文档，并运行编译、单元测试和定向测试。
8. auto 不跳过 sandbox、permissions、hooks 或高风险审批。
9. 高风险动作仍需确认：git commit/push、强推、清库、无 WHERE 删除、生产/联调写入、越权目录写入、破坏性删除、真实外部系统调用。
10. 当前处于 LoopX 验证期：只有需求采访和方案审核 `PASS` 后必须暂停并请求用户确认；代码审查、测试审核、测试执行、健康门和发布就绪 `PASS` 后不需要人工确认。
11. 本地 `PASS` 只代表本地验证通过；没有接入 PR/CI 时，最终报告必须显式写出“CI/远端未覆盖”。
12. 整个 LoopX 流程完成前必须执行 `/health`；未执行、失败或无法运行时，不得宣称最终完整通过。
13. `/health` 不强依赖三方插件；核心健康检查必须在零插件环境下可运行，三方工具只能作为增强检查。
14. 缺失三方工具时不得伪装为 `PASS`：可选检查标记 `SKIPPED`，由 CI 覆盖的检查标记 `CI_REQUIRED`，必需检查缺失标记 `BLOCKED`。

## 写入保护

- 阶段文档和分析文档可以在对应阶段写入，统一写入项目根目录下的 `docs/loopx/<date>-<slug>/`；`docs/loopx/runs/<run_id>/` 只用于 controller 状态、worklist、events、stage-results 和自动生成 artifact。
- 未声明执行深度前，不得进行开发写入。
- `STANDARD` 和 `FULL` 未通过方案审核，不得进入开发；未通过测试用例审核，不得进入开发。
- `STANDARD` 和 `FULL` 只有到 `10. 开发` 且上游放行条件满足时，才允许开发写入。
- `LIGHT` 只有在项目分配结果中显式输出 `mode: LIGHT`、影响范围、跳过的审核门和最小验证计划，且 `stage_result.status=PASS` 后，才允许轻量开发写入。
- 非显式 `LIGHT` 不得走轻流程；执行中发现实际影响超过 `LIGHT` 条件时，必须立即停止写入，升级为 `STANDARD` 或 `FULL`，并回到对应阶段重新执行。
- `CHANGES_REQUIRED` 或 `BLOCKED` 状态下不得继续后续阶段；只能修正 `return_to` 指定阶段、补充证据或等待用户处理。

## 人工确认门

以下阶段 `PASS` 后必须等待用户确认，不得全自动继续：

- 需求采访必须先向用户输出问题，收集回答并更新 `interview.md`；未回答时不得记录 `PASS`。
- 方案审核通过后，确认是否进入测试用例设计。

控制器层面使用中间状态表达人工确认：agent 在 `requirement_interview` 或 `solution_review` 记录 `PASS` 时，实际落库为 `NEED_HUMAN`，`next_action` 为 `confirm-stage --stage <stage>`。只有用户确认后执行 `confirm-stage`，该阶段才会变为 `PASS` 并允许继续推进。代码审查、测试审核和发布就绪 `PASS` 后不需要人工确认，可继续进入下一阶段。需求采访确认是生成 Spec 的前置条件：`requirement_interview NEED_HUMAN -> confirm-stage -> requirement_interview PASS -> spec_draft`。

如果用户明确说“本次全自动”“跳过人工确认”或“恢复自动推进”，才可以取消本次确认门。高风险动作仍必须单独确认。

## 阶段

0. 环境检查：由 controller 在 `init` 时自动执行并记录为 `PASS`；覆盖项目根、Python controller 运行时和基础状态目录。JDK/语言运行时、构建工具、目标模块、验证命令和依赖服务缺口可在后续阶段继续补充为阻塞证据。
1. 需求接收：记录原始需求、范围线索和初始风险。
2. 需求采访：根据原始问题或需求向用户提问，确认业务规则、验收标准、边界情况和开放问题；未得到回答不得生成或通过 Spec。
3. Spec 草稿：把采访结果沉淀为可测试的需求规格。
4. Spec 审核：检查完整性、歧义、范围和可测试性。
5. 执行等级选择：确认 `LIGHT`、`STANDARD` 或 `FULL`，记录 accepted risk。
6. 方案设计：方案、数据流、接口、迁移/兼容计划、影响范围。
7. 方案审核：需求匹配、设计原则、项目 harness、风险审核结论。
8. 测试用例设计：业务/API 数据准备、执行入口、断言、清理。
9. 测试用例审核：覆盖率、清理策略、风险闭环。
10. 开发：实现、补测试、集成、最小必要验证。
11. 通用质量审计：检查写入条件、阶段证据、worklist、设计/实现/验证一致性。
12. 代码审查：diff 审查、缺陷、缺失测试、模块边界和剩余风险。
13. 测试执行：逐条对照测试用例执行并输出报告。
14. 健康门：流程完成前执行 `/health`，把结果写入健康检查报告和最终结论。
15. 发布就绪：检查发布、回滚、CI/远端覆盖和剩余风险。
16. 最终报告：汇总阶段证据、验证结果、未覆盖项和下一步。

## 风险分级

执行分级时必须优先读取 `risk.yml`：

- 命中 `critical_triggers` 中任一风险标签，直接选择 `FULL`。
- 未命中关键触发项时，按 `score_rules` 对识别到的风险标签求和，并按 `thresholds` 选择 `LIGHT`、`STANDARD` 或 `FULL`。
- 如果 `risk.yml` 不存在、无法读取或字段不完整，降级使用下列自然语言规则，并在项目分配结果中记录降级原因。

- `LIGHT`：显式分级 -> 影响范围 -> 跳过门说明 -> 轻量开发 -> 最小验证 -> 轻量审查 -> 最终结论。
- `STANDARD`：环境检查 -> 项目分配 -> 方案 -> 测试 -> 实现 -> 审计 -> 审查 -> 验证。
- `FULL`：环境检查 + 完整 00-10 阶段。适用于 API 契约、SQL、MQ、认证授权、租户/数据权限、核心业务状态、跨模块、迁移或需求不清晰的变更。

## 阶段状态机

每个阶段完成后必须输出 `stage_result`：

```yaml
stage_result:
  stage:
  status:
  return_to:
  next_action:
  affected_work_items: []
  evidence: []
  user_confirmation_required:
  blocked_reason:
```

每个非 `PASS` 结果必须包含失败原因、影响范围、证据、`return_to` 目标阶段、需要修正的 worklist item 和是否需要用户确认。Agent 不得只写“未通过”而不写下一步去向。

合法推进：

| 当前阶段 | `PASS` 后 | `CHANGES_REQUIRED` 后 | `BLOCKED` 后 |
|---|---|---|---|
| 0 环境检查 | 自动 PASS 到 1 需求接收 | 0 环境检查 | 等用户处理环境/权限/依赖 |
| 1 需求接收 | 2 需求采访 | 1 需求接收 | 等用户澄清原始需求 |
| 2 需求采访 | NEED_HUMAN，`confirm-stage` 后到 3 | 2 需求采访 | 等用户补充关键问题 |
| 3 Spec 草稿 | 4 Spec 审核 | 3 Spec 草稿 | 等用户处理规格阻塞 |
| 4 Spec 审核 | 5 执行等级选择 | 3 Spec 草稿 | 等用户处理规格争议 |
| 5 执行等级选择 | 6 方案设计 | 5 执行等级选择 | 等用户确认执行等级或 accepted risk |
| 6 方案设计 | 7 方案审核 | 6 方案设计 | 等用户决策 |
| 7 方案审核 | NEED_HUMAN，`confirm-stage` 后到 8 | 6 方案设计 | 等用户处理 |
| 8 测试用例设计 | 9 测试用例审核 | 8 测试用例设计 | 等用户补充用例 |
| 9 测试用例审核 | 10 开发 | 8 测试用例设计 | 等用户处理 |
| 10 开发 | 11 通用质量审计 | 10 开发 | 等用户处理 |
| 11 通用质量审计 | 12 代码审查 | 6/8/10，按失败原因选择 | 等用户处理 |
| 12 代码审查 | 13 测试执行 | 10 开发 | 等用户处理 |
| 13 测试执行 | 14 健康门 | 8/10，按失败原因选择 | 等用户处理 |
| 14 健康门 | 15 发布就绪 | 对应责任阶段 | 等用户处理 |
| 15 发布就绪 | 16 最终报告 | 对应责任阶段 | 等用户处理 |
| 16 最终报告 | 完成 | 对应责任阶段 | 等用户处理 |

审核失败反馈规则：

- 需求采访失败：`return_to: 需求采访`，不得生成或通过 Spec。
- Spec 审核失败：`return_to: Spec 草稿`。
- 执行等级选择降级：必须记录 `ACCEPTED_RISK` 和用户接受原因。
- 方案审核失败：`return_to: 方案设计`。
- 测试用例审核失败：`return_to: 测试用例设计`。
- 开发自检失败：`return_to: 开发`。
- 通用质量审计失败：方案缺陷回方案设计，实现缺陷回开发，验证缺陷回测试用例设计，需求边界不清则回 Spec 或 `BLOCKED`。
- 代码审查失败：`return_to: 开发`。
- 测试执行失败：实现错误回开发，测试设计缺失回测试用例设计，环境问题 `BLOCKED`。
- 健康门或发布就绪失败：根据失败项回到对应责任阶段；工具不可用但非必需时只能记录未覆盖，不能宣称完整通过。

## Worklist 状态

项目分配阶段必须创建或更新 worklist；后续阶段必须同步每个 item 的状态。

每个 worklist item 至少包含：`id`、`title`、`status`、`risk_tags`、`owner_agent`、`read_scope`、`write_scope`、`dependencies`、`validation`、`evidence`、`failed_by`、`return_to`、`required_changes`。

`/health` 和最终报告必须检查：

- 是否仍有 `CHANGES_REQUIRED` 或 `BLOCKED` item。
- 是否有 `ACCEPTED_RISK`，以及用户是否明确接受。
- 是否所有必需验证都有硬证据。
- 是否所有数据清理都有清理验证。

## Controller 和 Schema

生产化运行优先使用 bundled controller 脚本持久化状态：

```bash
python tools/loopx_controller.py init "需求描述" --mode auto --risk-tags tenant_scope core_state_transition api_contract
python tools/loopx_controller.py status
python tools/loopx_controller.py status --tracking
python tools/loopx_controller.py interview <run_id>
# 回答 interview 命令输出的问题，并把回答写入 docs/loopx/runs/<run_id>/artifacts/interview.md 后才能记录 PASS
python tools/loopx_controller.py record-stage --run-id <run_id> --stage requirement_interview --status PASS --evidence docs/loopx/runs/<run_id>/artifacts/interview.md
python tools/loopx_controller.py confirm-stage --run-id <run_id> --stage requirement_interview --evidence "user confirmed interview"
python tools/loopx_controller.py spec <run_id>
python tools/loopx_controller.py record-stage --run-id <run_id> --stage spec_draft --status PASS --evidence docs/loopx/runs/<run_id>/artifacts/spec.md
python tools/loopx_controller.py record-stage --run-id <run_id> --stage spec_review --status PASS --evidence docs/loopx/runs/<run_id>/artifacts/spec.md
python tools/loopx_controller.py mode <run_id> --select FULL
python tools/loopx_controller.py next <run_id>
python tools/loopx_controller.py validate
python tools/loopx_controller.py validate --strict
python tools/loopx_controller.py gate <run_id>
python tools/loopx_controller.py git-gate <run_id>
python tools/loopx_controller.py close <run_id>
python tools/loopx_controller.py compound <run_id> --decision skipped --reason "本次无可复用学习点"
python tools/loopx_controller.py compound <run_id> --decision captured --category workflow --title "标题" --summary "摘要" --learning "学习点" --prevention "预防规则" --applies-to loopx/tools --write-project-doc
python tools/loopx_controller.py validate-learning docs/loopx/runs/<run_id>/artifacts/compound-capture.md
python tools/loopx_controller.py record-stage --stage solution_design --status PASS --evidence docs/solution.md
python tools/loopx_controller.py advance --to solution_review
python tools/loopx_controller.py record-stage --stage solution_review --status PASS --evidence stage-results/07-solution-review.json
python tools/loopx_controller.py confirm-stage --stage solution_review --evidence "user confirmed solution review"
python tools/loopx_controller.py fail-review --from solution_review --return-to solution_design --item W1 --reason "原因"
python tools/loopx_controller.py claim-stage solution_design
python tools/loopx_controller.py close-repair --item W1 --artifact stage-results/06-solution-design.json --revision 2 --change "修正说明"
python tools/loopx_controller.py can-write --kind business
```

控制器的最小状态目录为 `docs/loopx/runs/<run_id>/`，包含 `state.json`、`worklist.yml`、`events.jsonl`、`stage-results/` 和 `artifacts/`。`init` 会自动写入 `stage-results/00-environment-check.json` 并把当前阶段推进到 `requirement_intake`。阶段产物写入后必须能通过 `python tools/loopx_controller.py validate <run_id>` 的结构校验；缺少 schema 必填字段、非法状态、未知阶段或不可解析 worklist 时，不得进入下一阶段。确认门阶段必须先落为 `NEED_HUMAN`，再由 `confirm-stage` 写入确认元数据后变为 `PASS`。

`validate PASS` 只代表结构合法，不代表流程通过。进入下一阶段必须用 `advance --to ...`；遇到 `NEED_HUMAN` 必须等待用户确认并运行 `confirm-stage`，不得用 `advance` 或手改状态隐式批准。收口前必须用 `gate` 通过严格流程门，用 `git-gate` 写入本地 Git 变更摘要，并在 `final_report PASS` 后用 `close` 关闭整个 run。`close` 会生成 `artifacts/close-evidence.json`，记录阶段证据矩阵、Git Gate、CI/远端未覆盖项。业务代码、测试、配置、SQL 或迁移脚本写入前必须用 `can-write --kind business` 得到 `PASS`，且 `solution_review` 必须已确认通过。Review 不通过或用户指出方案、目录、契约、异常、权限、租户或状态流转问题时，必须用 `fail-review` 创建返工任务，`claim-stage` 分配给 `return_to` 的 owner role，修原产物并追加 revision 后用 `close-repair` 关闭返工项；不得只手写 `state.current_stage`。

Compound Capture 是收口辅助能力，不作为正式阶段插入状态机。每次收口前应记录 captured 或 skipped 决策，默认写入 `docs/loopx/runs/<run_id>/artifacts/compound-capture.md`。只有用户确认或项目配置允许时，才写入长期知识库 `docs/loopx/solutions/<category>/<slug>.md`；不得自动修改用户项目的 `AGENTS.md` 或 `CLAUDE.md`。

## 本地执行硬约束

- 测试执行前必须确认本地环境缺口；环境缺失导致的失败标记为 `BLOCKED` 或“环境问题”，不得伪装成代码失败。
- 业务/API 测试数据必须有唯一 `runId` 或前缀，必须说明创建方式、清理方式和清理验证。
- 并行 worker 必须先声明互不冲突的写入范围；不能让多个 worker 修改同一文件、同一 DTO/API 契约或同一测试类。
- 最终结论必须区分：`本地通过`、`本地阻塞`、`未覆盖/需 CI 验证`。
- LLM 审核只是软判断；编译、测试、断言和清理验证才是硬证据。
- `/health` 是最终完成门：测试执行 `PASS` 后、最终回复前必须运行；结果低于项目可接受标准、命令失败或工具不可用时，最终结论必须写明健康检查失败/未覆盖。
- 测试优先使用项目自身工具链；不得为了通过 `/health` 自动安装三方插件或扫描器。
- 如果方案或测试计划依赖三方工具，必须声明该检查是必需检查还是可选增强检查，并说明缺失时的降级策略。
- 验证命令优先来自项目 profile；没有匹配 profile 时，必须通过项目发现推断并记录不确定点。
