# 00 需求接收

## 需求摘要

- 需求 id：REQ-20260817-001
- 标题：把 LoopX 从阶段流程框架升级为可执行的工程标准体系
- 用户 / 角色：LoopX 维护者与使用 LoopX 的研发团队
- 当前问题：LoopX 已具备阶段状态机、人工确认、返工和写入保护，但方案设计、开发、测试、安全、性能、扩展性等标准仍以分散的自然语言检查为主，缺少统一适用规则、量化指标、阶段专属 schema 和可阻断的语义校验。
- 期望结果：保留现有阶段主流程，通过标准目录、风险适用策略、结构契约和 controller/health 校验，使阶段 `PASS` 同时具备内容和证据基础。

## 范围

### 范围内

- 定义 LoopX 工程原则及架构、安全、性能、可靠性/可观测性标准。
- 完善现有需求、开发、测试、质量、发布标准。
- 建立风险标签到必需规则集、检查方式和失败返回阶段的映射。
- 扩充方案、测试、开发、质量和性能/安全结果的模板与 schema。
- 强化 controller、health 和 package harness 的阶段专属语义校验。
- 更新相关 agent、skill、README、manifest 检查和回归测试。
- 保持核心流程零三方插件可运行，外部工具只作为 profile 或可选增强检查。

### 范围外

- 不增加新的正式主阶段。
- 本轮方案确认前不修改 controller、schema、模板或标准实现。
- 不为所有项目强制统一的延迟、吞吐量、代码覆盖率或复杂度数值。
- 不自动安装扫描器、性能工具或 CI 连接器。
- 不执行 commit、push、发布或真实外部系统调用。

## 验收标准

| ID | 标准 | 可观察证据 |
| --- | --- | --- |
| AC-001 | 标准规则具有稳定 ID、适用条件、强制级别、证据、检查方式、失败状态和 `return_to` | 标准目录及 schema 校验测试 |
| AC-002 | 方案设计覆盖简单性、边界、安全、性能、扩展/兼容、可靠性、可观测性和回滚，允许带理由的 `N/A` | 方案模板、solution schema 和正反例测试 |
| AC-003 | 测试设计建立验收标准与风险规则的追踪，保留数据准备、断言、清理和清理验证契约 | 测试模板、test-plan schema 和校验测试 |
| AC-004 | 性能目标由 Spec 或项目 profile 提供，至少表达指标、目标、负载、环境、基线和回退预算 | performance schema 和缺失目标阻断测试 |
| AC-005 | 安全风险映射到明确控制和验证证据，缺失必需工具不能伪装为 `PASS` | security rule pack、结果 schema 和降级策略测试 |
| AC-006 | `record-stage PASS` 和 `validate --strict` 能拒绝缺少必需内容、空证据或无效证据路径的适用阶段 | controller 回归测试 |
| AC-007 | `health.yml` 的核心检查被程序化消费并汇总实际结果 | health 执行测试及报告证据 |
| AC-008 | LIGHT 仍保持轻量；STANDARD/FULL 按风险应用规则包；旧 run 和既有命令有明确兼容策略 | 模式、迁移和兼容回归测试 |

## 边界场景

- 文档或轻量变更不应被无关的性能、安全或架构规则阻塞。
- FULL 不代表所有规则无条件适用；不适用项必须记录理由。
- 项目没有 lint、覆盖率、安全或性能工具时，应按 required、CI-backed、optional 三类处理。
- 项目自身阈值与 LoopX 基线不一致时，必须解析出唯一有效策略并记录来源。
- 既有 run、阶段结果和手写 evidence 字符串需要兼容或迁移策略。

## 非功能需求

- 安全：校验器不得读取或输出凭据；安全规则采用风险驱动和 fail-closed 的必需检查策略。
- 性能：规则解析和结构校验不应引入外部网络依赖；具体性能预算在 Spec 阶段确认。
- 兼容：保留现有 17 阶段、CLI 主命令和零插件核心路径；破坏性 schema 变更必须版本化。
- 可观测性：每个检查结果包含规则 ID、实际值、目标值、状态、证据和返回阶段。
- 可靠性：单个可选检查不可用时不得导致误报 `PASS`；必需检查不可用时阻断。

## 风险和依赖

```yaml
risk_tags:
  - core_state_transition
  - api_contract
  - ambiguous_requirement
dependencies:
  - 现有 LoopX workflow、controller、schema、template、agent 和 tests
  - 项目 harness 与可选 profile 命令
open_questions:
  - 第一版是否同时实现标准文档、schema 和 controller 内容检查，还是拆成两个版本？
  - 是否允许新增一个机器可读的标准目录文件，例如 standards/catalog.yml？
  - 旧 run 的兼容目标是只读可验证，还是允许继续推进到 close？
  - 第一版是否纳入真实 lint、coverage、安全、性能命令，还是先实现契约和执行接口？
```

## 阶段结果

```yaml
stage_result:
  stage: requirement_intake
  status: PASS
  return_to: ""
  next_action: requirement_interview
  affected_work_items: []
  evidence:
    - docs/loopx/2026-08-17-process-standards/00-requirement-intake.md
  user_confirmation_required: false
  blocked_reason: ""
```
