# 方案审核技能

## 目的

在开发前审核方案是否可实现、可测试、可回滚。

## 输入

- 需求产物、方案设计、结构化方案产物、规则快照、项目 harness 和工程标准。

## 步骤

1. 检查需求覆盖、模块边界、写入范围和依赖影响。
2. 检查简单性、安全、权限、数据、性能、扩展、兼容、可靠性、可观测性和回滚。
3. 核对适用规则结果、性能目标来源和证据路径。
4. 输出检查结果、问题清单和返回目标。

## 输出

- `PASS|CHANGES_REQUIRED|BLOCKED|SKIPPED|ACCEPTED_RISK`。
- blocking/non-blocking issues、required actions、`return_to`、`next_action`。

## 通过标准

- 无阻塞问题；方案覆盖验收标准和适用规则；结构化产物合法；验证计划能产出硬证据；写入范围有边界。

## 失败处理

`CHANGES_REQUIRED` 返回方案设计；`BLOCKED` 等待用户或环境决策。
