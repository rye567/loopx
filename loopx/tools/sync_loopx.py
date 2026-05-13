#!/usr/bin/env python3
import json
import os
import shutil
import sys
from pathlib import Path


SOURCE = Path(__file__).resolve().parents[1]
PROJECT = Path.cwd().resolve()
HOME = Path.home()
GLOBAL_LOOPX = HOME / ".loopx"
CODEX_HOME = Path(os.environ.get("CODEX_HOME", HOME / ".codex"))
CLAUDE_HOME = HOME / ".claude"
LOCAL_BIN = HOME / ".local" / "bin"

AGENTS = [
    ("quality-project-manager", "project-manager.md", "opus", "high", "项目分配：识别范围、模块、风险、依赖和验收标准。"),
    ("quality-solution-designer", "solution-designer.md", "opus", "xhigh", "方案设计：给出方案、数据流、接口、兼容策略和影响范围。"),
    ("quality-solution-reviewer", "solution-reviewer.md", "opus", "xhigh", "方案审核：审核需求匹配、项目规则、模块边界、风险和可测试性。"),
    ("quality-test-designer", "test-designer.md", "opus", "high", "测试用例设计：设计业务/API 数据、断言、清理和清理验证。"),
    ("quality-test-reviewer", "test-reviewer.md", "opus", "high", "测试用例审核：审核覆盖率、清理策略和残余风险。"),
    ("quality-development-orchestrator", "development.md", "sonnet", "medium", "开发阶段：auto 修改代码、补测试并运行编译和定向测试。"),
    ("quality-code-reviewer", "code-reviewer.md", "opus", "xhigh", "代码审查：审查 diff、回归、缺失测试、模块边界和安全风险。"),
    ("quality-test-runner", "test-runner.md", "sonnet", "medium", "测试执行：按用例准备数据、执行、断言、清理并输出报告。"),
]


def source_label():
    if SOURCE == GLOBAL_LOOPX:
        return "~/.loopx"
    try:
        return str(SOURCE.relative_to(PROJECT))
    except ValueError:
        return str(SOURCE)


def read(rel):
    return (SOURCE / rel).read_text(encoding="utf-8")


def read_project(rel):
    path = PROJECT / ".codex" / "loopx-project" / rel
    if path.exists():
        return path.read_text(encoding="utf-8")
    return ""


def write(root, rel, text):
    path = root / rel
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text.rstrip() + "\n", encoding="utf-8")
    print(f"write {path}")


def copy_templates(root, rel):
    target = root / rel
    target.mkdir(parents=True, exist_ok=True)
    for template in sorted((SOURCE / "templates").glob("*.md")):
        shutil.copy2(template, target / template.name)
        print(f"copy {target / template.name}")


def generated_notice():
    return f"本文件由 `{source_label()}` 生成；请修改全局中立源 `~/.loopx` 后重新同步。\n"


def generic_project_harness(project_name=None):
    current_project = f"当前项目：`{project_name}`。\n\n" if project_name else ""
    return f"""# 项目规则入口

{current_project}本项目未提供 `.codex/loopx-project/project-harness.md`，LoopX 必须先进行项目发现：

1. 优先读取 `AGENTS.md`、`CLAUDE.md`、`README*`、构建文件和主配置。
2. 使用 `rg --files` 定位模块、入口、测试、API 契约和依赖边界。
3. 没有模块地图时，项目分配阶段必须先输出发现到的模块关系。
4. 没有项目专属 reviewer 时，使用全局 `quality-*` agent 继续执行，并记录“无项目专属 reviewer”。
"""


def project_harness():
    return read_project("project-harness.md") or generic_project_harness(PROJECT.name)


def global_project_harness():
    return """# 项目规则入口

这是全局 LoopX 的通用项目发现规则，不包含任何具体业务项目的模块地图。

执行 LoopX 前必须先读取当前项目自己的 harness，例如 `AGENTS.md`、`CLAUDE.md`、README、构建文件和主配置。

如果项目没有专属 harness：

1. 先用 `rg --files`、构建文件和配置文件发现模块、入口、测试和依赖边界。
2. 项目分配阶段必须输出模块发现结果和不确定点。
3. 没有项目专属 reviewer 时，使用全局 `quality-*` agent 继续执行，并记录降级原因。
4. 测试执行仍必须覆盖业务/API 数据准备、执行入口、断言、清理动作和清理验证。
"""


def generic_agents_md():
    return f"""# {PROJECT.name} Codex Harness
本文件由 LoopX 生成，是 Codex 在本项目执行任务时的项目入口。

## 项目发现
1. 计划或编辑前先读取本文件、README、构建文件和主要配置。
2. 使用 `rg --files`、依赖清单和测试目录定位模块、入口、契约和验证命令。
3. 若项目没有明确模块地图，先在项目分配阶段补充模块发现结果。
4. 遇到已有用户改动时必须保留并协同处理，禁止无授权回滚。

## 通用工程规则
1. 遵守 KISS、SOLID、DRY、YAGNI、高内聚低耦合和单一职责。
2. 类文件原则上不超过 400 行；单个方法原则上不超过 40 行。
3. 不引入无需求的新框架、新中间件或大规模重构。
4. 不硬编码密钥、账号、租户、环境地址、生产数据或时间窗口。
5. 不为通过测试而削弱断言、删除测试、吞异常或隐藏失败。

## LoopX
1. 用户要求质量门、完整 loop、阶段文档或 `$loopx` 时，使用全局 `loopx` skill。
2. `$loopx` 即表示授权阶段子 agent 和推荐模型策略，除非用户明确禁用。
3. 当前 LoopX 处于验证期：方案审核、测试用例审核、代码审查和测试执行 PASS 后必须等待用户确认，不能全自动进入下一阶段。
4. 本地执行必须先做环境检查，区分代码问题、测试设计问题和环境问题。
5. 开发阶段默认 auto：用户确认测试用例审核通过后，可自动修改受影响代码/测试/阶段文档，并运行编译、单元测试和定向测试。
6. git commit/push、清库、强删、越权写入、生产/联调写入和真实外部系统调用仍需确认。
7. 测试用例和测试报告必须覆盖业务/API 数据准备、runId/数据前缀、执行入口、断言、清理动作和清理验证。
8. 最终结论必须区分本地通过、本地阻塞、未覆盖/需 CI 验证。
9. 整个流程完成前必须执行 `/health`，并把结果写入最终测试报告。
"""


def codex_agents_md():
    return read_project("codex-agents.md") or generic_agents_md()


def claude_md():
    project_text = read_project("claude.md")
    if project_text:
        return project_text
    return f"""# {PROJECT.name} Claude Harness

本文件由 LoopX 生成，是 Claude Code 在本项目执行任务时的项目入口。

请始终读取并遵守 @AGENTS.md。

## LoopX

当用户输入 `/loopx` 或 `$loopx` 时，读取 @.claude/skills/loopx/SKILL.md，并执行阶段化质量门。

- 阶段文档写入 `docs/loopx-runs/<date>-<slug>/`。
- 当前 LoopX 处于验证期：方案审核、测试用例审核、代码审查和测试执行 PASS 后必须等待用户确认，不能全自动进入下一阶段。
- 本地执行必须先做环境检查；最终结论必须区分本地通过、本地阻塞、未覆盖/需 CI 验证。
- 整个流程完成前必须执行 `/health`，并把结果写入最终测试报告。
- 开发阶段默认 auto：用户确认测试用例审核通过后，可自动修改受影响代码/测试/阶段文档，并运行编译、单元测试和定向测试。
- 仍需确认：git commit/push、强推、清库、强删、越权目录写入、生产/联调环境写入、真实外部系统调用。
"""


def skill_body(project=False):
    parts = [
        read("workflow.md"),
        project_harness() if project else global_project_harness(),
        "## 模板\n\n阶段文档模板位于本技能的 `assets/templates/` 目录。",
    ]
    return "\n\n".join(parts)


def codex_skill(project=False):
    return "\n\n".join([
        "---\nname: loopx\ndescription: 用于阶段化工程质量门：项目分配、方案、审核、测试用例、开发、代码审查和测试报告。\nmetadata:\n  short-description: 运行阶段化工程质量门\n---",
        "# LoopX",
        generated_notice(),
        skill_body(project=project),
    ])


def claude_skill(project=False):
    return "\n\n".join([
        "---\nname: loopx\ndescription: 阶段化工程质量门：项目分配、方案、审核、测试用例、开发、代码审查和测试报告。\n---",
        "# LoopX",
        generated_notice(),
        skill_body(project=project),
    ])


def claude_command():
    return """---
description: 运行 LoopX 阶段化质量门
allowed-tools: Task, Read, Grep, Glob, Edit, MultiEdit, Write, Bash
---

请读取 @CLAUDE.md、@AGENTS.md、@.claude/skills/loopx/SKILL.md。

按 LoopX 执行需求：$ARGUMENTS

默认允许阶段子 agent；先做本地环境检查；审核/验证阶段 PASS 后必须等待用户确认；开发阶段 auto，可改代码、补测试、运行编译和定向测试；流程完成前必须执行 /health。最终结论区分本地通过/阻塞/CI 未覆盖，高风险动作仍需确认。
"""


def claude_settings_json():
    data = {
        "defaultMode": "acceptEdits",
        "permissions": {
            "allow": [
                "Bash(rg:*)",
                "Bash(git status:*)",
                "Bash(git diff:*)",
                "Bash(mvn compile)",
                "Bash(mvn test)",
                "Bash(mvn -pl * -am -DskipTests compile)",
                "Bash(mvn -pl * -am -Dtest=* -DfailIfNoTests=false test)",
            ],
            "ask": [
                "Bash(git commit:*)",
                "Bash(git push:*)",
                "Bash(git push --force-with-lease:*)",
                "Bash(mvn clean:*)",
                "Bash(rm -rf:*)",
            ],
            "deny": [
                "Bash(git reset --hard:*)",
                "Bash(git push --force:*)",
                "Read(./.env)",
                "Read(./.env.*)",
            ],
        },
        "hooks": {
            "UserPromptSubmit": [{"hooks": [{"type": "command", "command": "python3 .claude/hooks/user_prompt_loopx.py"}]}],
            "PreToolUse": [{"matcher": "Bash", "hooks": [{"type": "command", "command": "python3 .claude/hooks/pre_tool_use_policy.py"}]}],
            "Stop": [{"hooks": [{"type": "command", "command": "python3 .claude/hooks/stop_loopx_check.py"}]}],
        },
    }
    return json.dumps(data, ensure_ascii=False, indent=2)


def codex_config():
    return '''approval_policy = "on-request"
sandbox_mode = "workspace-write"

[features]
codex_hooks = true

[sandbox_workspace_write]
network_access = false
'''


def codex_hooks_json():
    data = {
        "hooks": {
            "UserPromptSubmit": [{
                "hooks": [{
                    "type": "command",
                    "command": "/usr/bin/python3 \"$(git rev-parse --show-toplevel)/.codex/hooks/user_prompt_quality_gate.py\"",
                    "timeout": 10,
                    "statusMessage": "检查 LoopX 触发条件",
                }],
            }],
            "PreToolUse": [{
                "matcher": "^Bash$",
                "hooks": [{
                    "type": "command",
                    "command": "/usr/bin/python3 \"$(git rev-parse --show-toplevel)/.codex/hooks/pre_tool_use_policy.py\"",
                    "timeout": 10,
                    "statusMessage": "检查命令策略",
                }],
            }],
            "Stop": [{
                "hooks": [{
                    "type": "command",
                    "command": "/usr/bin/python3 \"$(git rev-parse --show-toplevel)/.codex/hooks/stop_quality_gate_check.py\"",
                    "timeout": 10,
                    "statusMessage": "检查 LoopX 阶段文档",
                }],
            }],
        }
    }
    return json.dumps(data, ensure_ascii=False, indent=2)


def codex_rules():
    return '''# LoopX 项目命令执行策略。
# 作用：当命令需要跳出沙箱或触发审批时，Codex 会用这些规则决定允许、询问或禁止。
# 本文件由 LoopX 中立源生成；请修改 ~/.loopx 后重新同步。

prefix_rule(
    pattern = ["mvn", "test"],
    decision = "allow",
    justification = "允许自动运行 Maven 测试，这是开发阶段的安全验证动作。",
)

prefix_rule(
    pattern = ["mvn", "compile"],
    decision = "allow",
    justification = "允许自动运行 Maven 编译，这是开发阶段的安全验证动作。",
)

prefix_rule(
    pattern = ["git", "reset", "--hard"],
    decision = "forbidden",
    justification = "禁止丢弃用户或 agent 的工作。需要先查看 git diff/status，并明确询问后才能回滚指定文件。",
)

prefix_rule(
    pattern = ["git", "push", "--force"],
    decision = "forbidden",
    justification = "禁止强推。强推会改写远端历史，需要走明确的分支级审批和更安全的发布流程。",
)

prefix_rule(
    pattern = ["git", "push", "--force-with-lease"],
    decision = "prompt",
    justification = "force-with-lease 仍会改写远端历史，执行前必须获得明确确认。",
)

prefix_rule(
    pattern = ["rm", "-rf"],
    decision = "prompt",
    justification = "递归删除风险较高，执行前必须确认删除范围和原因。",
)

prefix_rule(
    pattern = ["mvn", "clean"],
    decision = "prompt",
    justification = "mvn clean 会删除构建产物并可能显著增加验证耗时，执行前需要确认。",
)

prefix_rule(
    pattern = ["git", "commit"],
    decision = "prompt",
    justification = "创建提交前需要确认已暂存内容和提交意图。",
)

prefix_rule(
    pattern = ["git", "push"],
    decision = "prompt",
    justification = "推送远端必须由用户明确决定。",
)
'''


def claude_agent_file(name, source_file, model, effort, description):
    body = read(f"agents/{source_file}")
    return f"""---
name: {name}
description: {description}
tools: Read, Grep, Glob, Edit, MultiEdit, Write, Bash, Task
model: {model}
effort: {effort}
---

{generated_notice()}
{body}
"""


def codex_agent_file(name, source_file, effort, description):
    body = read(f"agents/{source_file}")
    escaped_description = json.dumps(description, ensure_ascii=False)
    return f'''name = "{name}"
description = {escaped_description}
developer_instructions = """
{generated_notice()}推荐运行模型：Codex 5.5（model: gpt-5.5），reasoning_effort={effort}。

{body}
"""
'''


def user_prompt_hook(claude=False):
    prefix = "LoopX" if claude else "Codex LoopX"
    return f'''#!/usr/bin/env python3
import json
import re
import sys


payload = json.load(sys.stdin)
prompt = payload.get("prompt", "") or ""
patterns = [r"/loopx", r"\\$loopx", r"质量门", r"完整\\s*loop", r"跨模块", r"\\bSQL\\b", r"\\bMQ\\b", r"租户", r"权限", r"同步", r"订单"]

if any(re.search(p, prompt, re.IGNORECASE) for p in patterns):
    context = (
        "{prefix} 提醒：请读取项目 harness 和 loopx skill。"
        "/loopx 或 $loopx 表示授权阶段子 agent；审核/验证阶段 PASS 后必须等待用户确认。"
        "本地执行先做环境检查；开发阶段 auto，可改代码、补测试、运行编译和定向测试。"
        "流程完成前必须执行 /health。最终结论必须区分本地通过、本地阻塞、未覆盖/需 CI 验证。"
        "测试必须包含业务/API 数据准备、执行入口、断言、清理和清理验证。"
    )
    print(json.dumps({{
        "hookSpecificOutput": {{
            "hookEventName": "UserPromptSubmit",
            "additionalContext": context
        }}
    }}, ensure_ascii=False))
'''


def pre_tool_hook(claude=False):
    if claude:
        deny = '''print(json.dumps({
            "decision": "block",
            "reason": reason,
            "hookSpecificOutput": {
                "hookEventName": "PreToolUse",
                "permissionDecision": "deny",
                "permissionDecisionReason": reason
            }
        }, ensure_ascii=False))'''
    else:
        deny = '''print(json.dumps({
            "hookSpecificOutput": {
                "hookEventName": "PreToolUse",
                "permissionDecision": "deny",
                "permissionDecisionReason": reason
            }
        }, ensure_ascii=False))'''
    return f'''#!/usr/bin/env python3
import json
import re
import sys


BLOCK_PATTERNS = [
    (r"\\bgit\\s+reset\\s+--hard\\b", "禁止执行 git reset --hard；请先查看差异，并在明确授权后只回滚指定文件。"),
    (r"\\bgit\\s+push\\s+--force\\b", "禁止执行 git push --force；强推必须走明确审查过的发布流程。"),
    (r"\\b(drop|truncate)\\s+(database|schema|table)\\b", "禁止执行破坏性数据库 DDL；必须先有审查过的迁移和回滚方案。"),
    (r"\\bdelete\\s+from\\s+\\S+\\s*;?\\s*$", "禁止执行没有明显 WHERE 条件的 DELETE 语句。"),
    (r"\\brm\\s+-rf\\s+(/|~|\\$HOME)\\b", "禁止对根目录或用户主目录执行递归删除。"),
]


payload = json.load(sys.stdin)
tool_input = payload.get("tool_input") or {{}}
command = ""
if isinstance(tool_input, dict):
    command = tool_input.get("command") or tool_input.get("cmd") or ""

for pattern, reason in BLOCK_PATTERNS:
    if re.search(pattern, command, re.IGNORECASE | re.DOTALL):
        {deny}
        break
'''


def stop_hook(claude=False):
    if claude:
        response = '''print(json.dumps({
        "decision": "block",
        "reason": "检测到代码/配置/SQL 变更并宣称完成，但没有阶段文档；请补齐 LoopX 文档或说明这是 LIGHT 轻量需求。"
    }, ensure_ascii=False))'''
    else:
        response = '''print(json.dumps({
        "continue": True,
        "systemMessage": (
            "质量门提醒：检测到代码/配置/SQL 有变更，但没有看到 LoopX 阶段文档。"
            "如果这是 STANDARD/FULL 需求，请补齐任务分配、测试用例、审查和测试报告；"
            "如果这是 LIGHT 轻量需求，请在最终回复说明为什么无需完整质量门。"
        )
    }, ensure_ascii=False))'''
    return f'''#!/usr/bin/env python3
import json
import os
import subprocess
import sys


def git_status(cwd):
    try:
        result = subprocess.run(["git", "status", "--short"], cwd=cwd, text=True, capture_output=True, timeout=5, check=False)
        return result.stdout.splitlines()
    except Exception:
        return []


payload = json.load(sys.stdin)
cwd = payload.get("cwd") or os.getcwd()
last = payload.get("last_assistant_message") or ""
status = git_status(cwd)
tracked_changes = [line for line in status if not line.startswith("??")]
touched_code = any(
    line[3:].endswith((".java", ".xml", ".sql", ".yml", ".yaml", ".properties"))
    and not line[3:].startswith(".codex/")
    and not line[3:].startswith(".claude/")
    for line in tracked_changes
)
touched_run_docs = any("docs/codex-runs/" in line or "docs/loopx-runs/" in line for line in status)
mentions_done = any(word in last.lower() for word in ["complete", "completed", "done", "pass", "完成", "通过"])

if touched_code and mentions_done and not touched_run_docs:
    {response}
'''


def install_source_to_global():
    if SOURCE == GLOBAL_LOOPX:
        return
    GLOBAL_LOOPX.mkdir(parents=True, exist_ok=True)
    ignore = shutil.ignore_patterns(".DS_Store", "__pycache__", "*.pyc")
    shutil.copytree(SOURCE, GLOBAL_LOOPX, dirs_exist_ok=True, ignore=ignore)
    print(f"copy source {SOURCE} -> {GLOBAL_LOOPX}")


def install_command_wrapper():
    LOCAL_BIN.mkdir(parents=True, exist_ok=True)
    wrapper = LOCAL_BIN / "loopx-sync"
    wrapper.write_text(f'''#!/usr/bin/env bash
set -euo pipefail
exec python3 "{GLOBAL_LOOPX}/tools/sync_loopx.py" "$@"
''', encoding="utf-8")
    wrapper.chmod(0o755)
    print(f"write {wrapper}")


def manifest():
    path = SOURCE / "manifest.json"
    if not path.exists():
        return {}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return {"name": "loopx", "version": "unknown", "manifestError": str(path)}


def print_version():
    data = manifest()
    name = data.get("name", "loopx")
    version = data.get("version", "unknown")
    print(f"{name} {version}")
    print(f"source {SOURCE}")


def doctor():
    checks = []

    def add(label, ok, detail="", required=True):
        checks.append((label, ok, detail, required))

    add("source workflow", (SOURCE / "workflow.md").exists(), str(SOURCE / "workflow.md"))
    add("source agents", len(list((SOURCE / "agents").glob("*.md"))) >= len(AGENTS), str(SOURCE / "agents"))
    add("source templates", len(list((SOURCE / "templates").glob("*.md"))) >= 8, str(SOURCE / "templates"))
    add("sync command", (LOCAL_BIN / "loopx-sync").exists(), str(LOCAL_BIN / "loopx-sync"))
    add("codex skill", (CODEX_HOME / "skills" / "loopx" / "SKILL.md").exists(), str(CODEX_HOME / "skills" / "loopx"))
    add("codex agents", len(list((CODEX_HOME / "agents").glob("quality-*.toml"))) >= len(AGENTS), str(CODEX_HOME / "agents"))
    add("claude skill", (CLAUDE_HOME / "skills" / "loopx" / "SKILL.md").exists(), str(CLAUDE_HOME / "skills" / "loopx"))
    add("claude agents", len(list((CLAUDE_HOME / "agents").glob("quality-*.md"))) >= len(AGENTS), str(CLAUDE_HOME / "agents"))

    project_has_codex = (PROJECT / "AGENTS.md").exists() or (PROJECT / ".codex").exists()
    project_has_claude = (PROJECT / "CLAUDE.md").exists() or (PROJECT / ".claude").exists()
    add("project codex adapter", project_has_codex, str(PROJECT), required=False)
    add("project claude adapter", project_has_claude, str(PROJECT), required=False)

    failed = False
    for label, ok, detail, required in checks:
        mark = "PASS" if ok else ("MISS" if required else "WARN")
        print(f"{mark} {label}: {detail}")
        failed = failed or (required and not ok)

    if failed:
        print("doctor 发现缺失项；通常先运行 loopx-sync global 或 loopx-sync project。", file=sys.stderr)
        sys.exit(1)
    print("doctor ok")


def cleanup_project_quality_agents():
    targets = list((PROJECT / ".codex" / "agents").glob("quality-*.toml"))
    targets += list((PROJECT / ".claude" / "agents").glob("quality-*.md"))
    for path in targets:
        try:
            text = path.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            continue
        if "LoopX" in text or "loopx" in text or "quality-" in path.name:
            path.unlink()
            print(f"remove project duplicate {path}")


def cleanup_project_stale_files():
    stale_files = [
        PROJECT / ".codex" / "rules" / ("nebu" + "la-quality-gate.rules"),
    ]
    for path in stale_files:
        if path.exists():
            path.unlink()
            print(f"remove stale {path}")


def sync_project_claude_agents():
    source = PROJECT / ".codex" / "loopx-project" / "claude-agents"
    if not source.exists():
        return
    target = PROJECT / ".claude" / "agents"
    target.mkdir(parents=True, exist_ok=True)
    for agent in sorted(source.glob("*.md")):
        shutil.copy2(agent, target / agent.name)
        print(f"copy project claude agent {target / agent.name}")


def generate_global():
    install_source_to_global()
    install_command_wrapper()
    write(CODEX_HOME, "skills/loopx/SKILL.md", codex_skill(project=False))
    copy_templates(CODEX_HOME, "skills/loopx/assets/templates")
    write(CLAUDE_HOME, "skills/loopx/SKILL.md", claude_skill(project=False))
    copy_templates(CLAUDE_HOME, "skills/loopx/assets/templates")
    for name, source_file, model, claude_effort, description in AGENTS:
        codex_effort = "medium"
        if "solution" in name or name == "quality-code-reviewer":
            codex_effort = "xhigh"
        elif name in {"quality-project-manager", "quality-test-designer", "quality-test-reviewer"}:
            codex_effort = "high"
        write(CODEX_HOME, f"agents/{name}.toml", codex_agent_file(name, source_file, codex_effort, description))
        write(CLAUDE_HOME, f"agents/{name}.md", claude_agent_file(name, source_file, model, claude_effort, description))


def generate_project():
    cleanup_project_quality_agents()
    cleanup_project_stale_files()
    sync_project_claude_agents()
    write(PROJECT, "AGENTS.md", codex_agents_md())
    write(PROJECT, "CLAUDE.md", claude_md())
    write(PROJECT, ".codex/config.toml", codex_config())
    write(PROJECT, ".codex/hooks.json", codex_hooks_json())
    write(PROJECT, ".codex/rules/loopx.rules", codex_rules())
    write(PROJECT, ".codex/skills/loopx/SKILL.md", codex_skill(project=True))
    copy_templates(PROJECT, ".codex/skills/loopx/assets/templates")
    write(PROJECT, ".codex/hooks/user_prompt_quality_gate.py", user_prompt_hook(claude=False))
    write(PROJECT, ".codex/hooks/pre_tool_use_policy.py", pre_tool_hook(claude=False))
    write(PROJECT, ".codex/hooks/stop_quality_gate_check.py", stop_hook(claude=False))
    write(PROJECT, ".claude/settings.json", claude_settings_json())
    write(PROJECT, ".claude/commands/loopx.md", claude_command())
    write(PROJECT, ".claude/skills/loopx/SKILL.md", claude_skill(project=True))
    copy_templates(PROJECT, ".claude/skills/loopx/assets/templates")
    write(PROJECT, ".claude/hooks/user_prompt_loopx.py", user_prompt_hook(claude=True))
    write(PROJECT, ".claude/hooks/pre_tool_use_policy.py", pre_tool_hook(claude=True))
    write(PROJECT, ".claude/hooks/stop_loopx_check.py", stop_hook(claude=True))


def main():
    target = sys.argv[1] if len(sys.argv) > 1 else "project"
    if target not in {"global", "project", "all", "doctor", "version"}:
        print("用法：loopx-sync [global|project|all|doctor|version]", file=sys.stderr)
        sys.exit(2)
    if target == "doctor":
        doctor()
        return
    if target == "version":
        print_version()
        return
    if target in {"global", "all"}:
        generate_global()
    if target in {"project", "all"}:
        generate_project()


if __name__ == "__main__":
    main()
