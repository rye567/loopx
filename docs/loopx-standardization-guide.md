# LoopX 智能体 / 技能 / Harness 标准化指南

本指南把 LoopX 收敛为一条可生产化执行的交付轨道：标准定义规则，技能提供能力，智能体负责阶段产物，harness 用客观检查守住证据门。

## 核心模型

```text
标准     = 规则、输入输出和通过标准
技能      = 可复用能力
智能体    = 阶段负责人
Harness  = 客观检查和证据门
Controller = 状态和推进负责人
```

## 推荐阶段轨道

```text
需求接收
  -> 环境检查
  -> 项目分配
  -> 方案设计
  -> 方案审核
  -> 测试设计
  -> 测试审核
  -> 开发实现
  -> 质量审计
  -> 代码审查
  -> 测试执行
  -> Health Gate
  -> 发布就绪
  -> 最终报告
```

## 最小生产闭环

先跑小闭环，再扩展更多 agent：

1. 需求负责人输出可测试范围。
2. 方案设计负责人输出有边界的写入范围。
3. 测试设计负责人把验收标准映射为测试用例。
4. 开发负责人只实现已批准范围。
5. 质量审计负责人检查证据、worklist 和阶段结果。
6. 发布负责人准备回滚、监控和人工批准证据。

## 门禁纪律

每个门禁只能返回：

- `PASS`
- `CHANGES_REQUIRED`
- `BLOCKED`
- `SKIPPED`
- `ACCEPTED_RISK`

任何非 `PASS` 结果都必须包含 `return_to` 阶段和 required actions，避免多智能体协作退化成不可追踪的对话。

## Harness 策略

在本仓库内使用：

```bash
python loopx/tools/loopx_check.py kit --root .
```

在目标项目中使用：

```bash
python <loopx-skill-dir>/tools/loopx_check.py project --root <project>
```

harness 只依赖 Python 标准库，便于在三方工具安装前先运行基础检查。
