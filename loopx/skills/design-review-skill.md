# 方案审核技能

## 目的

在开发开始前审核拟定方案。

## 输入

- 需求产物。
- 方案设计产物。
- 项目 harness。
- 风险标准和质量标准。

## 步骤

1. 检查需求到方案的覆盖关系。
2. 检查模块边界、写入范围和依赖影响。
3. 检查可测试性和验证可行性。
4. 检查安全、权限、数据、兼容和回滚风险。
5. 输出明确的门禁结果和返回目标。

## 输出

```yaml
result: PASS|CHANGES_REQUIRED|BLOCKED|SKIPPED|ACCEPTED_RISK
blocking_issues: []
non_blocking_issues: []
required_actions: []
return_to: solution_design
next_action: test_design
```

## 通过标准

- 没有未解决的阻塞问题。
- 方案覆盖验收标准。
- 验证计划能产出硬证据。
- 写入范围有边界。

## 失败处理

`CHANGES_REQUIRED` 返回方案设计。`BLOCKED` 等待用户或环境决策。
