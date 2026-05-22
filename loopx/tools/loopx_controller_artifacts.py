#!/usr/bin/env python3
"""Artifact rendering and content validation helpers for the LoopX controller."""

import re


def markdown_cell(text):
    return str(text).replace("|", "\\|").replace("\n", " ")


def interview_questions(state):
    requirement = state.get("requirement") or "本次需求"
    mode = state.get("mode")
    risk_tags = set(state.get("risk_tags") or [])
    questions = [
        {
            "priority": "P0",
            "question": "这个需求要解决的具体问题是什么？",
            "reason": f"先确认「{requirement}」的问题定义，避免直接跳到方案。",
            "blocking_stage": "spec_draft",
        },
        {
            "priority": "P0",
            "question": "当前行为、期望行为和受影响用户或角色分别是什么？",
            "reason": "规格需要区分现状、目标和影响对象。",
            "blocking_stage": "spec_draft",
        },
        {
            "priority": "P0",
            "question": "你认为哪些验收标准可以证明这个需求已经完成？",
            "reason": "验收标准决定后续测试和放行证据。",
            "blocking_stage": "spec_draft",
        },
        {
            "priority": "P0",
            "question": "哪些内容明确不在本次范围内？",
            "reason": "范围边界能防止实现阶段扩大工作面。",
            "blocking_stage": "spec_draft",
        },
    ]
    if mode in {"STANDARD", "FULL"}:
        questions.extend([
            {
                "priority": "P1",
                "question": "有哪些边界场景、异常路径或兼容性要求必须覆盖？",
                "reason": "中高等级流程需要提前锁定测试策略。",
                "blocking_stage": "spec_review",
            },
            {
                "priority": "P1",
                "question": "本次变更需要哪些本地验证命令、测试数据或回滚判断？",
                "reason": "验证入口和数据策略会影响开发与测试阶段。",
                "blocking_stage": "test_design",
            },
        ])
    if mode == "FULL":
        questions.extend([
            {
                "priority": "P1",
                "question": "是否涉及迁移、灰度、发布窗口、监控告警或数据清理要求？",
                "reason": "FULL 模式需要提前保留发布与恢复证据。",
                "blocking_stage": "release_readiness",
            },
        ])
    risk_question_map = {
        "api_contract": "接口的请求、响应、错误码和向后兼容要求是什么？",
        "tenant_scope": "这个需求如何区分租户、账号、权限或数据边界？",
        "core_state_transition": "涉及哪些核心状态，以及允许和禁止的状态流转是什么？",
        "db_schema": "是否需要表结构、索引、迁移、回滚或历史数据处理？",
        "mq": "消息的生产、消费、幂等、重试和失败补偿规则是什么？",
        "auth": "认证、授权、角色或敏感操作的约束是什么？",
    }
    for tag in sorted(risk_tags):
        question = risk_question_map.get(tag)
        if question:
            questions.append({
                "priority": "P0",
                "question": question,
                "reason": f"风险标签 `{tag}` 会影响执行等级和后续门禁。",
                "blocking_stage": "spec_draft",
            })
    return questions


def render_interview_question_table(questions):
    lines = ["| 优先级 | 问题 | 为什么需要 | 阻塞阶段 |", "|---|---|---|---|"]
    for item in questions:
        lines.append(
            f"| {markdown_cell(item['priority'])} | {markdown_cell(item['question'])} | "
            f"{markdown_cell(item['reason'])} | {markdown_cell(item['blocking_stage'])} |"
        )
    return "\n".join(lines)


def render_interview_answer_records(questions):
    lines = []
    for item in questions:
        lines.extend([
            f"- 问题：{item['question']}",
            "  回答：待用户回答",
            "  状态：未回答",
        ])
    return "\n".join(lines)


def render_interview_artifact(state):
    questions = interview_questions(state)
    return f"""# 需求采访

## 运行信息

- 运行 ID：{state.get("run_id")}
- 执行等级：{state.get("mode")}
- 原始需求：{state.get("requirement")}

## 已确认事实

- 待采访确认。

## 采访问题

{render_interview_question_table(questions)}

## 回答记录

{render_interview_answer_records(questions)}

## 开放问题

- 待用户回答。

## 采访门禁

```yaml
stage_result:
  stage: requirement_interview
  status: CHANGES_REQUIRED
  next_action: answer interview questions; then record-stage --stage requirement_interview --status PASS and wait for confirm-stage --stage requirement_interview
```
"""


def render_spec_artifact(state):
    return f"""# 需求规格

## 摘要

{state.get("requirement")}

## 背景

## 当前行为

## 期望行为

## 用户 / 角色 / 套餐

## 业务规则

## 验收标准

## 范围内

## 范围外

## 边界情况

## 错误处理

## 前端行为

## 后端行为

## 数据 / 持久化影响

## 外部 API 影响

## 测试策略

## 发布 / 回滚说明

## 开放问题

## 假设

## 执行等级决策

- 推荐等级：{state.get("mode_decision", {}).get("recommended", state.get("mode"))}
- 当前选择：{state.get("mode_decision", {}).get("selected", state.get("mode"))}
"""


SPEC_REQUIRED_SECTIONS = [
    ("Summary", ("## Summary", "## 摘要")),
    ("Expected Behavior", ("## Expected Behavior", "## 期望行为")),
    ("Acceptance Criteria", ("## Acceptance Criteria", "## 验收标准")),
    ("Scope", ("## Scope", "## In Scope", "## 范围内")),
    ("Out of Scope", ("## Out of Scope", "## 范围外")),
    ("Edge Cases", ("## Edge Cases", "## 边界情况")),
    ("Test Strategy", ("## Test Strategy", "## 测试策略")),
    ("Execution Mode", ("## Execution Mode", "## Execution Mode Decision", "## 执行等级", "## 执行等级决策")),
]


def missing_spec_sections(text):
    normalized = text.casefold()
    missing = []
    for section, headings in SPEC_REQUIRED_SECTIONS:
        if not any(heading.casefold() in normalized for heading in headings):
            missing.append(section)
    return missing


def spec_section_content(text, headings):
    matches = list(re.finditer(r"^##\s+(.+?)\s*$", text, re.MULTILINE))
    aliases = {heading.removeprefix("##").strip().casefold() for heading in headings}
    for index, match in enumerate(matches):
        title = match.group(1).strip().casefold()
        if title not in aliases:
            continue
        start = match.end()
        end = matches[index + 1].start() if index + 1 < len(matches) else len(text)
        return text[start:end].strip()
    return None


def empty_spec_sections(text):
    empty = []
    for section, headings in SPEC_REQUIRED_SECTIONS:
        content = spec_section_content(text, headings)
        if content is not None and not content:
            empty.append(section)
    return empty


def interview_has_unanswered_placeholders(text):
    markers = [
        "待用户回答",
        "待采访确认",
        "待确认",
        "未回答",
        "TBD",
        "TODO",
        "å¾…ç”¨æˆ·å›žç­”",
        "å¾…é‡‡è®¿ç¡®è®¤",
    ]
    return any(marker in text for marker in markers)
