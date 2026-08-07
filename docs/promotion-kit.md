# LoopX Promotion Kit

Ready-to-post copy for announcing LoopX. Pick the version that fits the channel.
All copy assumes the repo is https://github.com/rye567/loopx.

---

## Hacker News — Show HN

Title:

> Show HN: LoopX – quality gates for AI coding agents (Codex + Claude Code)

Body:

> Agents are fast, but "done" from an agent is just a chat message. LoopX is a
> skill package (works with both Codex and Claude Code) that forces risky AI
> coding work through a staged workflow backed by a local state controller:
> requirement interview → spec → review gates → test design → implementation →
> validation → release readiness.
>
> What makes it different from a prompt or a hook:
> - Agent claims are not the source of truth. Every stage writes a JSON result
>   with evidence; strict validation rejects runs where state/worklist/artifacts
>   disagree.
> - Business writes are locked until review gates pass (`can-write`).
> - Human confirmation gates store PASS as NEED_HUMAN — nothing advances until
>   a human confirms.
> - Risk tags drive mode selection (LIGHT/STANDARD/FULL); LIGHT skips review
>   gates legally, FULL requires everything.
> - Repair loop: failed reviews return to the owning stage with a ticket, and a
>   stage blocks after too many failed auto repairs.
>
> 71 regression tests, zero runtime dependencies (stdlib only), MIT.
> 5-minute demo: https://github.com/rye567/loopx/blob/main/docs/demo.md
>
> Happy to answer questions — especially about how this holds up on real
> cross-module changes.

---

## Reddit — r/ClaudeAI / r/ChatGPTCoding

Title:

> I built quality gates for AI coding agents (Claude Code + Codex) — agents
> claim "done", LoopX makes them prove it

Body:

> After watching agents skip requirements, invent acceptance criteria and edit
> business logic before the design was checked, I built LoopX: a staged
> workflow + local controller that works with Claude Code and Codex.
>
> - Each stage requires recorded evidence; strict validation rejects
>   inconsistent runs
> - `requirement_interview` and `solution_review` PASS stay as NEED_HUMAN
>   until you confirm
> - Business writes are locked until review gates pass
> - Risk-based mode: LIGHT skips review gates, FULL requires all of them
> - Failed reviews create repair tickets routed to the owning stage
>
> Repo: https://github.com/rye567/loopx (MIT, stdlib only, 71 tests)
> Demo: https://github.com/rye567/loopx/blob/main/docs/demo.md
>
> What do you use to keep agents from "shipping vibes"? Hooks? Reviewers? Or
> do you trust the agent's word? Curious how others handle this.

---

## 掘金 / 知乎 — 中文版

标题：

> 你的 AI 编程 Agent 需要质量门禁，而不是更好的提示词

正文：

> AI 编程 Agent 很快，但这恰恰是问题所在。一个纯提示词驱动的 Agent 会
> 愉快地告诉你"做完了"、把评审标记为通过、直接改业务代码——而没人检查
> 过需求是否被理解、验收标准是否存在、改动是否触碰了高风险区域。
>
> 这不是提示词质量问题，是流程问题。LoopX 是一个同时支持 Codex 和
> Claude Code 的 skill 包，用本地控制器把高风险变更强制推过阶段化流程：
> 需求采访 → 规格 → 评审门 → 测试设计 → 实现 → 验证 → 发布就绪。
>
> 核心思路：Agent 自己的话不是事实来源。
> - 每个阶段必须写入带证据的 JSON 阶段结果，strict 校验拒绝状态不一致
> - 需求采访、方案评审的 PASS 会落为 NEED_HUMAN，必须人工 confirm-stage
> - 评审门通过前 `can-write` 锁定业务写入
> - 风险标签驱动 LIGHT/STANDARD/FULL 分级，LIGHT 合法跳过评审门，
>   FULL 要求全部门禁
> - 失败评审生成返工票据回到责任阶段，连续返工超限自动 BLOCKED
>
> 71 个回归测试、零运行时依赖（纯标准库）、MIT 协议。
> 5 分钟演示：https://github.com/rye567/loopx/blob/main/docs/demo.md
>
> 你用什么防止 Agent"带节奏式交付"？欢迎讨论。

---

## X / Twitter（2 条备选）

1. AI agents tell you "done" — but done is just a chat message.
   LoopX adds quality gates to Codex & Claude Code: evidence per stage, human
   confirmation on review gates, locked business writes until reviews pass.
   MIT, stdlib only, 71 tests. https://github.com/rye567/loopx

2. "Looks done" is not good enough. LoopX is a staged workflow + local
   controller for AI coding agents: interview → spec → review → test → ship,
   with a paper trail at every step. Try the 5-minute demo:
   https://github.com/rye567/loopx/blob/main/docs/demo.md

---

## Pointers

- Demo: `docs/demo.md`
- Blog post draft: `docs/why-loopx.md`
- Release notes: https://github.com/rye567/loopx/releases/tag/v0.1.0
- Topics: `quality-gate`, `codex`, `claude-code`, `ai-agents`, `agent-workflow`
