# 阶段追踪技能

## 目的

把 `state.json`、`worklist.yml` 和阶段结果统一展示成每次更新都能阅读的 LoopX 追踪。

## 输入

- `.loopx/runs/<run_id>/state.json`。
- `.loopx/runs/<run_id>/worklist.yml`。
- `.loopx/runs/<run_id>/stage-results/*.json`。
- 当前阶段、阻塞项和下一步动作。

## 步骤

1. 读取当前 run、mode、spec 状态和 current stage。
2. 按 00-16 阶段顺序展示完成、当前、待办状态。
3. 汇总当前 checklist、blocking issues、accepted risk 和 next action。
4. 在 `stage_result.tracking_snapshot` 中保存快照。
5. 输出人类可读追踪块。

## 输出

- LoopX 追踪文本块。
- `tracking_snapshot` 数据。
- 当前阻塞项和下一步动作。

## 通过标准

- 阶段顺序完整。
- 当前阶段和 `state.json` 一致。
- 已 PASS 阶段有 evidence。
- 阻塞项不被隐藏。

## 失败处理

状态文件缺失或不一致时返回 `BLOCKED`。worklist 缺少阶段列表时返回 `CHANGES_REQUIRED`。发现 PASS 阶段缺少 tracking snapshot 时返回 `CHANGES_REQUIRED`。
