# 复利沉淀技能

## 目的

在一次 LoopX run 收口前记录是否产生可复用知识；有价值才写入长期知识库，避免把普通变更包装成形式主义文档。

## 输入

- `docs/loopx/runs/<run_id>/state.json`、stage-results、worklist、返工票据、测试结果、最终验证结论。
- 本次变更文件、风险标签、失败审查、修复过程和用户确认的学习点。
- 可选目标目录：`docs/loopx/solutions/<category>/<slug>.md`。

## 步骤

1. 判断本次 run 是否产生可复用缺陷修复、架构模式、测试策略、流程经验或风险预防规则。
2. 如果没有复用价值，生成 skipped 决策并写明原因。
3. 如果有复用价值，生成 captured 决策，写明 summary、learning、prevention、risk_tags 和 applies_to。
4. 默认只写 `docs/loopx/runs/<run_id>/artifacts/compound-capture.md`。
5. 只有用户确认或项目配置允许时，才写入 `docs/loopx/solutions/<category>/<slug>.md`。
6. 使用 `validate-learning` 校验 frontmatter 和必需章节。

## 输出

- `docs/loopx/runs/<run_id>/artifacts/compound-capture.md`。
- 可选 `docs/loopx/solutions/<category>/<slug>.md`。
- `state.compound_capture` 决策摘要和 `compound_capture_recorded` event。

## 通过标准

- 每次需要收口的 run 至少有 captured 或 skipped 决策。
- captured 文档包含 `Summary`、`Learning`、`Prevention`，并能通过 `compound-learning.schema.json`。
- skipped 文档包含明确跳过原因。
- 不自动写项目长期知识库，不自动修改 `AGENTS.md` 或 `CLAUDE.md`。

## 失败处理

- 缺少必需字段时返回 `BLOCKED`，补齐 title、summary、learning、prevention 或 reason。
- 文档 schema 不通过时，不得把该 learning 作为长期知识引用。
- 如果学习点与本次变更无关，记录 skipped 并说明不沉淀原因。
