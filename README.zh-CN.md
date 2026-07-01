# LoopX Kit

AI 编程 Agent 的工程质量门。

[English README](README.md)

LoopX 是一个用 Git 维护的 Codex / Claude Code 通用 skill 包。它把 AI 编程任务从“收到需求就开始改代码”拉回到可审计的工程流程：需求采访、规格说明、人工确认的方案评审、测试设计、实现、代码评审和发布门禁。

当 Agent 要修改跨模块行为、API 契约、权限边界、租户隔离、状态机、SQL/MQ 流程，或者任何“看起来完成了”还不够的变更时，就适合使用 LoopX。

## 为什么需要 LoopX

AI 编程 Agent 很快，但常见问题也很明显：跳过需求澄清、臆造验收标准、没有证据就标记评审通过，或者在方案和测试还没确认前直接改业务逻辑。LoopX 提供本地控制器和阶段化工作流，让每个重要变更在进入代码前都留下可检查的产物。

| 没有 LoopX | 使用 LoopX |
| --- | --- |
| Agent 根据模糊提示直接开写 | 先进行需求接入和需求采访 |
| 验收标准靠聊天上下文隐含 | 生成并评审明确的 Spec |
| 评审容易被口头带过 | 评审门必须记录证据 |
| 高风险写入过早发生 | 评审门通过前阻止业务写入 |
| “完成”只是一句聊天回复 | 最终门禁记录本地验证、风险缺口和发布准备度 |

## 工作流

```text
需求
  -> 环境检查
  -> 需求接入
  -> 需求采访
  -> Spec 草稿
  -> Spec 评审
  -> 模式选择
  -> 方案设计
  -> 方案评审
  -> 测试设计
  -> 测试评审
  -> 实现
  -> 代码评审
  -> 验证
  -> 发布准备
```

完整流程契约见 [`loopx/workflow.md`](loopx/workflow.md)。控制器会把每次运行持久化到 `docs/loopx/runs/<run_id>/`，仅存 controller 状态、worklist、events、stage-results 和自动生成 artifact。

## 安装

克隆仓库：

```bash
git clone git@github.com:rye567/loopx-kit.git
cd loopx-kit
```

把 [`loopx/`](loopx/) 目录复制或链接到目标工具的 skills 目录，并保留目录名为 `loopx`。

推荐使用实时链接，这样更新仓库后 Codex 和 Claude Code 会直接读到最新组件。

Windows PowerShell：

```powershell
# Codex
New-Item -ItemType Junction `
  -Path "$HOME\.codex\skills\loopx" `
  -Target "E:\workspace\loopx-kit\loopx"

# Claude Code
New-Item -ItemType Junction `
  -Path "$HOME\.claude\skills\loopx" `
  -Target "E:\workspace\loopx-kit\loopx"
```

Unix-like 系统：

```bash
ln -s "$PWD/loopx" "$HOME/.codex/skills/loopx"
ln -s "$PWD/loopx" "$HOME/.claude/skills/loopx"
```

## 使用

```text
Codex: $loopx 处理这个需求：...
Claude Code: /loopx 处理这个需求：...
```

如果项目内需要提示 Agent 使用 LoopX，可以在项目文档中加入：

```text
当用户要求 LoopX、质量门或完整阶段化交付时，使用已安装的 loopx skill。先读取当前项目 README、构建文件、主要配置、源码结构和测试目录，再按 LoopX 阶段执行。
```

## 控制器快速开始

初始化一次运行：

```bash
python loopx/tools/loopx_controller.py init "增加租户级 API 访问控制" --mode auto --risk-tags tenant_scope api_contract
```

查看进度：

```bash
python loopx/tools/loopx_controller.py status --tracking
```

执行验证和门禁：

```bash
python loopx/tools/loopx_controller.py validate --strict
python loopx/tools/loopx_controller.py gate <run_id>
python loopx/tools/loopx_controller.py git-gate <run_id>
python loopx/tools/loopx_controller.py close <run_id>
```

写入业务逻辑前，LoopX 要求相关人工确认评审门已经通过：

```bash
python loopx/tools/loopx_controller.py can-write --kind business
```

## 包含内容

- `loopx/SKILL.md`：Codex 和 Claude Code 的 skill 入口
- `loopx/workflow.md`：阶段化工作流契约
- `loopx/agents/`：各质量阶段的角色说明
- `loopx/templates/`：需求采访、Spec、评审和发布报告模板
- `loopx/schemas/`：状态、阶段结果、追踪、模式选择和 Spec 的 JSON Schema
- `loopx/tools/loopx_controller.py`：本地状态控制器
- `loopx/tools/loopx_check.py`：健康检查和包检查
- `tests/`：控制器和 skill 包的回归测试

## 适用场景

LoopX 适合：

- 变更跨越模块或责任边界。
- 模糊需求需要沉淀为明确 Spec。
- 评审证据比 Agent 自信更重要。
- 项目涉及安全、租户、权限、数据或状态流转风险。
- 多个 Agent 或多个工具需要共用一套工作流契约。

LoopX 可能不适合：

- 一行文案修改。
- 一次性原型。
- 没有发布意图的纯探索实验。

## 推荐 GitHub Topics

`codex`, `claude-code`, `ai-agents`, `agent-workflow`, `quality-gate`, `developer-tools`, `automation`, `python`, `prompt-engineering`

## 更新

```bash
git pull
```

如果通过链接或 Junction 安装，仓库更新会立即对 Codex 和 Claude Code 生效。

## 许可证

MIT。见 [`LICENSE`](LICENSE)。
