# LoopX Kit

LoopX Kit 是可跨项目、跨机器安装的本地工程质量门工具包。它把通用工作流、`quality-*` agent、模板、hooks 和同步器安装到用户级目录，再由每个项目保留自己的适配层。

## 安装

跨平台推荐：

```bash
git clone git@github.com:rye567/loopx-kit.git
cd loopx-kit
python install.py
```

Windows 也可以使用：

```bat
install.cmd
```

macOS/Linux 也可以使用：

```bash
bash install.sh
```

安装后会写入：

- `~/.loopx`
- macOS/Linux：`~/.local/bin/loopx-sync`
- Windows：`%LOCALAPPDATA%\LoopX\bin\loopx-sync.cmd` 和 `loopx-sync.ps1`
- `~/.codex/skills/loopx`
- `~/.codex/agents/quality-*.toml`
- `~/.claude/skills/loopx`
- `~/.claude/agents/quality-*.md`

Windows 安装器会自动把 `%LOCALAPPDATA%\LoopX\bin` 写入用户 PATH；通常重开终端后即可直接执行 `loopx-sync`。

如果要在当前项目同时生成项目适配层：

```bash
python install.py --project
```

## 使用

在任意项目中执行：

```bash
loopx-sync project
```

然后在 Codex 使用：

```text
$loopx 处理需求：...
```

在 Claude Code 使用：

```text
/loopx 处理需求：...
```

## 更新

```bash
git pull
python install.py
```

## 检查

```bash
loopx-sync doctor
loopx-sync version
```

## 卸载

```bash
python uninstall.py --yes
```

Windows 也可以使用：

```bat
uninstall.cmd --yes
```

## 跨平台约束

LoopX 不依赖 `/data`、`/usr/bin/python3`、`~/.local/bin` 等单一平台路径。同步器会按当前系统生成本机可用的 wrapper、hooks 和用户级安装目录。项目内路径统一使用相对路径，避免把某台机器的绝对路径同步到其它机器。

## 仓库策略

本仓库可以设为 public，方便其它机器直接安装。公开可见不等于允许任何人写入；建议保护 `main` 分支，只允许通过 PR 合并，并要求所有者审批。

本项目暂未声明开源许可证。公开仓库默认仍保留作者权利；如果后续要开放复用/改造/商用，请再补充明确的 `LICENSE`。
