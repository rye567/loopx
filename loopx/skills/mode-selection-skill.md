# 执行等级选择技能

## 目的

根据风险、影响范围和项目约束推荐并记录 `LIGHT`、`STANDARD` 或 `FULL`。

## 输入

- 用户需求、采访结果、`risk.yml`、风险标签、模块影响和用户选择/降级理由。

## 步骤

1. 读取关键触发器、评分规则和阈值。
2. 计算推荐等级并记录理由。
3. 记录用户选择；低于推荐等级时记录 accepted risk。
4. 输出 `mode_selection` 和 `stage_result`。

## 输出

- `mode_decision.recommended`、`selected`、推荐理由、accepted risk 和下一阶段结论。

## 通过标准

- 推荐可追溯；用户选择已记录；降级有 accepted risk；阶段结果合法。

## 失败处理

风险输入不足返回 `CHANGES_REQUIRED`；需用户确认返回 `NEED_HUMAN`；关键触发器被静默降级返回 `BLOCKED`。
