---
name: loopx
description: 当用户要求 LoopX、质量门、阶段化工程审核、完整 loop、风险分级实现、跨模块变更或结构化项目交付时使用。
---

# LoopX

LoopX 是跨 Codex 和 Claude Code 的工程质量门 skill。`loopx/` 目录就是唯一主源；用 Git 维护和更新，不再生成任何工具专属适配层。

## 入口

- Codex 中使用 `$loopx ...` 触发。
- Claude Code 中使用 `/loopx ...` 触发。
- 用户提到“质量门”“完整 loop”“阶段化开发”“跨模块”“SQL/MQ”“权限”“租户”“核心状态流转”或高风险改动时，优先判断是否进入 LoopX。

## 必读资源

计划或编辑前先读取这些资源：

- `workflow.md`：阶段化质量门主流程。
- `project-harness.md`：项目发现和默认 harness 规则。
- `risk.yml`、`health.yml`、`project-profiles.yml`：风险、健康检查和项目 profile 策略。
- `agents/`：各质量角色的职责边界。
- `templates/`：阶段文档模板。
- `schemas/`：运行状态、阶段结果、worklist 和 health 结果结构契约。

## 执行流程

1. 先从当前项目的 README、构建文件、主配置、源码结构和测试目录完成项目发现。
2. 按 `risk.yml` 判断执行深度：`LIGHT`、`STANDARD` 或 `FULL`。
3. 按 `workflow.md` 的阶段顺序推进，并在每个阶段读取 `agents/` 中对应角色说明。
4. 当执行深度要求阶段产物时，使用 `templates/` 输出阶段文档。
5. 进入下一阶段前，用 `schemas/` 校验运行状态、worklist 和阶段结果结构。
6. 最终结论必须区分本地验证结果、环境阻塞、未覆盖项和需要 CI/远端验证的部分。

## 状态控制器

需要持久化本地运行状态时，优先使用随 skill 附带的控制器脚本：

```bash
python loopx/tools/loopx_controller.py init "需求描述"
python loopx/tools/loopx_controller.py status
python loopx/tools/loopx_controller.py validate
```

如果当前工作目录就是 skill 目录，使用相对路径即可，例如 `python tools/loopx_controller.py validate`。

## 项目接入

不要生成或覆盖项目的 `.codex`、`.claude`、`AGENTS.md`、`CLAUDE.md` 文件。项目需要本地提醒时，只手动加入一小段说明：使用已安装的 `loopx` skill，并在执行阶段前读取项目已有文档和配置。

## 生产约束

- 不为通过流程而降低断言、跳过证据、隐藏失败或伪造 `PASS`。
- 高风险动作仍需显式确认，包括 git commit/push、强推、生产/联调写入、破坏性删除和真实外部系统调用。
- 遇到已有用户改动时协同处理，不得无授权回滚。
- 没有硬证据时，最终报告必须写明未覆盖或需要 CI 验证。
