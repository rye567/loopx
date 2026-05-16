# 执行等级选择技能

## 目的

根据需求风险、影响范围和项目约束推荐并记录 `LIGHT`、`STANDARD` 或 `FULL` 执行等级。

## 输入

- 用户需求和采访结果。
- `risk.yml`。
- 风险标签、涉及模块、是否跨前后端、是否涉及数据/权限/外部 API。
- 用户显式选择或降级理由。

## 步骤

1. 读取 `risk.yml` 的关键触发器、评分规则和阈值。
2. 根据风险标签计算推荐等级。
3. 写明推荐理由和置信度。
4. 记录用户选择。
5. 如果用户选择低于推荐等级，记录 accepted risk 和理由。
6. 输出 `mode_selection` 和 `stage_result`。

## 输出

- `mode_decision.recommended`。
- `mode_decision.selected`。
- 推荐理由和 accepted risk。
- 下一阶段 `solution_design` 的放行或阻塞结论。

## 通过标准

- 推荐等级可追溯到风险输入。
- 用户选择已记录。
- 降级选择有明确 accepted risk。
- `mode_selection` 阶段结果为 `PASS` 或合法的 `ACCEPTED_RISK`。

## 失败处理

风险输入不足时返回 `CHANGES_REQUIRED`。用户需要确认降级风险时返回 `NEED_HUMAN`。命中关键触发器但用户试图静默降级时返回 `BLOCKED`。
