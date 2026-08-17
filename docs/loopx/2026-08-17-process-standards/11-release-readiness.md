# 11 发布就绪

## 发布标识

```yaml
release:
  id: REL-20260817-001
  requirement_id: LOOPX-PROCESS-STANDARDS
  risk_level: FULL
```

## 结论

- 状态：PASS（本地发布准备）。
- 用户影响：LoopX 从只有阶段编排扩展为版本化标准、结构化产物、证据复核、风险分级、配置健康检查和可回归的 v2 执行契约。
- 兼容性：无 `contract_version` 的历史运行继续按 v1 处理；新运行默认使用 v2。
- 生产依赖：无新增。
- 数据库和 API：无数据库结构变更，无网络 API 契约变更。
- 高风险外部动作：未执行提交、推送、发布或生产写入。
- 下一阶段：最终报告。

## 变更摘要

- 新增工程原则、架构、安全、性能、可靠性与可观测性标准，并完善需求、开发、测试、质量和发布标准。
- 新增规则目录、风险 profile、项目策略模板、8 类结构化产物定义和固定策略快照。
- 控制器新增 v2 分派、产物与证据校验、工作项同步、严格复核、多文件失败恢复和健康检查命令。
- 文档、模板、智能体说明、技能说明、README 和 manifest 与新契约保持一致。
- 自动化测试覆盖 v1 兼容、v2 全阶段、策略、证据、安全路径、失败恢复、健康检查和自然中文输出。

## 运行影响

```yaml
config_changes:
  - loopx/health.yml
  - loopx/risk.yml
  - loopx/project-profiles.yml
  - loopx/standards/catalog.yml
database_changes: []
api_contract_changes: []
external_dependencies: []
compatibility_notes:
  - 历史 v1 运行不需要快照或结构化产物
  - 新 v2 运行必须提供对应阶段的结构化产物和真实证据
```

## 验证覆盖

```yaml
local_validation:
  - 116/116 自动化测试通过
  - LoopX 包完整性检查通过
  - 生产与测试 Python 模块编译通过
  - 17 个 JSON 结构定义可解析
  - Git 差异检查通过
  - 配置驱动健康检查通过
ci_required:
  - 在现有 CI 配置中运行全量测试和包检查
manual_validation:
  - 发布前确认版本号、发布说明和目标渠道
not_covered:
  - 真实 CI 执行
  - 远端环境和跨平台文件系统
  - 外部项目工具适配
  - 真实发布与发布后监控
```

## 回滚计划

1. 发布前保留当前可用版本与资源清单。
2. 如 v2 新运行异常，停止创建新运行，保留现场文件，恢复上一版 LoopX 包。
3. 重新运行 v1 兼容测试、包完整性检查和严格复核，确认恢复结果。
4. 不篡改已存在运行的 `contract_version`，不通过手写状态伪造兼容路径。

## 观测与后续检查

- 指标：包检查结果、全量测试通过数、健康检查总状态、阶段记录失败数和未解决工作项数。
- 日志：控制器事件、阶段结果和健康结果文件。
- 发布后检查：本次未发布，因此未执行；实际发布后应重跑包检查、小型 v1/v2 运行与健康检查。

## 剩余风险

- 当前结论只代表本地就绪，不代表 CI、远端、跨平台或发布后已验证。
- 外部项目自定义命令的超时和脱敏逻辑已有单元测试，但尚未在多类真实工具中抽样。

## 阶段结果

```yaml
stage_result:
  stage: release_readiness
  status: PASS
  return_to: ""
  next_action: final_report
  affected_work_items: []
  evidence:
    - docs/loopx/2026-08-17-process-standards/11-release-readiness.md
    - docs/loopx/2026-08-17-process-standards/09-test-report.md
    - docs/loopx/2026-08-17-process-standards/10-health-check.md
  user_confirmation_required: false
  blocked_reason: ""
```
