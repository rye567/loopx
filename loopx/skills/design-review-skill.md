# 方案审核技能

## 目的

在开发前审核方案是否可实现、可测试、可回滚。

## 输入

- 需求产物、方案设计、项目 harness、风险标准和质量标准。

## 步骤

1. 检查需求覆盖、模块边界、写入范围和依赖影响。
2. 检查安全、权限、数据、兼容、回滚和验证可行性。
3. 输出检查结果、问题清单和返回目标。

## 输出

- `PASS|CHANGES_REQUIRED|BLOCKED|SKIPPED|ACCEPTED_RISK`。
- blocking/non-blocking issues、required actions、`return_to`、`next_action`。

## 通过标准

- 无阻塞问题；方案覆盖验收标准；验证计划能产出硬证据；写入范围有边界。

## 失败处理

`CHANGES_REQUIRED` 返回方案设计；`BLOCKED` 等待用户或环境决策。
