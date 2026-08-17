# LoopX 工程标准

本目录同时提供给人阅读的说明和机器可识别的规则目录。标准说明规则的目的、适用场景与证据要求，`catalog.yml` 是规则标识、适用阶段和检查方式的唯一来源。

## 使用顺序

1. 先读 `principles.md`，按正确、安全、简单、兼容、可验证的顺序处理冲突。
2. 根据风险标签，从 `catalog.yml` 选择 common、architecture、security、performance、reliability、observability 和 testing 规则集合。
3. 需求、方案、开发、测试、质量和发布分别使用对应主题标准。
4. 阶段通过必须同时有结构合法的产物和可复核证据；说明文字不能代替实际结果。

## 文件索引

- `requirement-standard.md`：把模糊请求整理成可执行范围。
- `principles.md`：定义跨领域决策顺序和取舍纪律。
- `architecture-standard.md`：约束简单性、模块边界、依赖、兼容和扩展。
- `security-standard.md`：覆盖身份、权限、租户、输入、敏感数据、依赖和外部副作用。
- `performance-standard.md`：定义有效性能指标及其证据。
- `reliability-observability-standard.md`：定义超时、重试、幂等、恢复、日志、指标和告警要求。
- `development-standard.md`：约束代码变更和实现行为。
- `testing-standard.md`：定义测试映射、数据、断言和清理。
- `quality-standard.md`：定义可复核的检查结果和证据规则。
- `release-standard.md`：定义发布准备、回滚和运行证据。

每份标准都必须包含通过标准、失败处理和证据要求。具体规则字段不要在多份文档中重复维护。
