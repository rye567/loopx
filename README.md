# LoopX Kit

LoopX Kit 是一个用 Git 维护的跨工具工程质量门 skill 包。`loopx/` 是唯一主源，可分别安装到 Codex 和 Claude Code 的 skills 目录；更新时只需要对本仓库执行 `git pull`。

## 安装

克隆仓库：

```bash
git clone git@github.com:rye567/loopx-kit.git
cd loopx-kit
```

把 `loopx/` 目录复制或符号链接到目标工具的 skills 目录，并保留目录名为 `loopx`。Codex 和 Claude Code 各自按自己的 skill 机制安装即可；本仓库不再生成工具专属适配层。

## 使用

在 Codex 使用：

```text
$loopx 处理需求：...
```

在 Claude Code 使用：

```text
/loopx 处理需求：...
```

项目内如需提示入口，可以手动加入一小段说明：

```text
当用户要求 LoopX、质量门或完整阶段化交付时，使用已安装的 loopx skill；先读取当前项目 README、构建文件、主要配置和测试目录，再按 LoopX 阶段执行。
```

## 状态控制器

LoopX 也提供一个本地状态控制器，用于把运行过程从纯提示词约束推进到可校验状态文件：

```bash
python loopx/tools/loopx_controller.py init "需求描述" --mode auto --risk-tags tenant_scope core_state_transition api_contract
python loopx/tools/loopx_controller.py status
python loopx/tools/loopx_controller.py validate
python loopx/tools/loopx_controller.py record-stage --stage solution_design --status PASS --evidence docs/solution.md
python loopx/tools/loopx_controller.py advance --to solution_review
python loopx/tools/loopx_controller.py can-write --kind business
```

控制器会创建 `.loopx/runs/<run_id>/state.json`、`worklist.yml`、`events.jsonl` 和 `stage-results/`。`validate` 只校验 run state、worklist 和阶段结果的结构合法性；阶段推进和业务写入必须分别通过 `advance` 与 `can-write` 闸门。控制器只依赖 Python 标准库。

## 更新

```bash
git pull
```

## 跨平台约束

LoopX 不依赖 `/data`、`/usr/bin/python3`、`~/.local/bin` 等单一平台路径。skill 内脚本使用相对资源路径，避免把某台机器的绝对路径带到其它机器。

## 仓库策略

本仓库可以设为 public，方便其它机器直接安装。公开可见不等于允许任何人写入；建议保护 `main` 分支，只允许通过 PR 合并，并要求所有者审批。

本项目暂未声明开源许可证。公开仓库默认仍保留作者权利；如果后续要开放复用/改造/商用，请再补充明确的 `LICENSE`。
