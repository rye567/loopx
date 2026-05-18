# LoopX Kit

LoopX Kit 是用 Git 维护的跨工具工程质量门 skill 包。`loopx/` 是唯一主源，可安装到 Codex 或 Claude Code 的 skills 目录；完整流程契约见 `loopx/workflow.md`。

## 安装

```bash
git clone git@github.com:rye567/loopx-kit.git
cd loopx-kit
```

把 `loopx/` 目录复制或符号链接到目标工具的 skills 目录，并保留目录名为 `loopx`。本仓库不再生成工具专属适配层。

## 使用

```text
Codex: $loopx 处理需求：...
Claude Code: /loopx 处理需求：...
```

项目内如需提示入口，可以加入：

```text
当用户要求 LoopX、质量门或完整阶段化交付时，使用已安装的 loopx skill；先读取当前项目 README、构建文件、主要配置和测试目录，再按 LoopX 阶段执行。
```

## 状态控制器

控制器把运行过程持久化到 `.loopx/runs/<run_id>/`，包括 `state.json`、`worklist.yml`、`events.jsonl`、`stage-results/` 和 `repair-tickets/`。完整命令流见 `loopx/workflow.md`；常用入口如下：

```bash
python loopx/tools/loopx_controller.py init "需求描述" --mode auto --risk-tags api_contract
python loopx/tools/loopx_controller.py status --tracking
python loopx/tools/loopx_controller.py validate --strict
python loopx/tools/loopx_controller.py gate <run_id>
```

确认门阶段的 agent `PASS` 会先落为 `NEED_HUMAN`，必须用 `confirm-stage` 写入用户确认后才变为 `PASS`。业务写入要求 `solution_review` 和 `test_review` 都已确认通过：

```bash
python loopx/tools/loopx_controller.py confirm-stage --stage solution_review --evidence "user confirmed solution review"
python loopx/tools/loopx_controller.py can-write --kind business
```

## 更新

```bash
git pull
```

## 跨平台约束

LoopX 不依赖 `/data`、`/usr/bin/python3`、`~/.local/bin` 等单一平台路径。skill 内脚本使用相对资源路径，避免把某台机器的绝对路径带到其它机器。

## 仓库策略

建议保护 `main` 分支，只允许通过 PR 合并，并要求所有者审批。本项目暂未声明开源许可证；公开可见不等于自动授权复用、改造或商用。
