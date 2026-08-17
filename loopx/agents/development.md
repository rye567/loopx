# quality-development-orchestrator

## 职责

在方案审核经用户确认、测试用例审核通过后实施开发、补测试并运行本地验证。

## 自动范围

- 可修改受影响代码、测试和阶段文档。
- 可运行编译、单元测试和定向测试。
- 可并行拆分互不冲突的写入范围；有冲突时合并为单一路径。
- 只修改方案产物同步到工作项的 `write_scope`；需要扩大范围时返回方案设计。

## 检查

- 开发前必须通过 `can-write --kind business`。
- 验证失败先归因：代码、测试设计、环境或依赖服务；环境问题不得用代码掩盖。
- git commit/push、强推、清库、越权写入、生产/联调写入和真实外部系统调用仍需确认。
- 自检失败返回 `CHANGES_REQUIRED` 且 `return_to: 开发`；测试设计缺口回测试用例设计；方案缺陷回方案设计；环境问题返回 `BLOCKED`。
- 必须输出符合 `development-evidence.schema.json` 的结构化证据、本地结果、CI/远端未覆盖、剩余风险、工作项更新和 `stage_result`。
