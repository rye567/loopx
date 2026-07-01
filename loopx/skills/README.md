# LoopX 技能

LoopX 技能是小而可复用的能力契约。智能体组合这些技能，质量检查校验它们的输出。

每个技能必须定义：

- 目的
- 输入
- 步骤
- 输出
- 通过标准
- 失败处理
- harness 期望的证据

保持技能窄而清楚。不要把需求、设计、测试、审核和发布职责塞进一个万能开发技能。

## 前置检查技能顺序

进入实现前按顺序使用：

1. `requirement-interview-skill.md`
2. `spec-generation-skill.md`
3. `spec-review-skill.md`
4. `mode-selection-skill.md`
5. `stage-tracking-skill.md`

控制器可以用 `validate --strict` 校验已持久化的输出。
