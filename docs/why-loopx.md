# Why your AI coding agent needs quality gates (not just a good prompt)

*Draft blog post. Repo: https://github.com/rye567/loopx*

AI coding agents are fast. That is exactly the problem.

A prompt-driven agent will happily tell you "done", mark a review as passed,
and edit business logic — all before anyone checked whether the requirement was
understood, whether the acceptance criteria exist, or whether the design
touches something risky.

This is not a prompt-quality problem. It is a **process problem**. And process
problems need process tooling, not better prompting.

## The failure modes we kept seeing

1. **Requirements skipped.** The agent starts coding from a vague prompt and
   invents acceptance criteria along the way.
2. **Reviews hand-waved.** "Reviewed, looks good" with no evidence of what was
   checked.
3. **High-risk edits too early.** API contracts, tenant boundaries, state
   machines and SQL/MQ flows get modified before the design was examined.
4. **"Done" is a chat message.** No artifact trail, no way to audit what
   happened after the conversation ended.

## What LoopX does differently

LoopX is a skill package that works with **both Codex and Claude Code**. It
forces risky changes through a staged workflow backed by a local controller:

```
request
  -> environment check
  -> requirement intake
  -> requirement interview (human confirmation gate)
  -> spec draft -> spec review
  -> mode selection (LIGHT / STANDARD / FULL, risk-driven)
  -> solution design -> solution review (human confirmation gate)
  -> test design -> test review
  -> development        <- business writes unlocked only here
  -> quality audit -> code review -> test execution
  -> health gate -> release readiness
  -> final report -> close
```

The key idea: **the agent's own claims are not the source of truth.** A local
controller persists run state, and nothing advances without recorded evidence:

- `record-stage --status PASS` writes a JSON stage result with evidence and a
  tracking snapshot; strict validation (`validate --strict`, `gate`) rejects
  runs where state, worklist and artifacts disagree.
- Confirmation gates (`requirement_interview`, `solution_review`) store `PASS`
  as `NEED_HUMAN` — a human must run `confirm-stage` before the run moves on.
- `can-write --kind business` locks business writes until the review gates are
  satisfied. An agent cannot "just start coding".
- A repair loop (`fail-review` / `claim-stage` / `close-repair`) sends failed
  reviews back to the owning stage with a ticket, and blocks the stage after
  too many failed auto repairs (`BLOCKED`).
- Risk tags (`api_contract`, `tenant_scope`, `core_state_transition`, ...)
  drive mode selection: LIGHT skips review gates legally, FULL requires every
  gate to pass.

## How it compares to Claude Code hooks

Hooks are great for **single-point checks** (block a command, run a linter).
LoopX is a **state machine**: it tracks where you are in the workflow, what has
evidence, and what may not happen yet. You can combine both — hooks as hard
enforcement, LoopX as the workflow contract.

## Try it in 5 minutes

```bash
git clone git@github.com:rye567/loopx.git
cd loopx
python3 loopx/tools/loopx_controller.py init \
  "Add dark mode toggle" --run-id demo --project .
```

Follow the interactive demo in [`docs/demo.md`](demo.md) — a full LIGHT-mode
run from `init` to `close` takes about 20 commands and produces a complete,
auditable artifact trail.

## When NOT to use it

- One-line copy changes.
- Throwaway prototypes.
- Exploratory spikes with no release intent.

For everything where "looks done" is not good enough — cross-module changes,
API contracts, permissions, tenant boundaries, state machines, SQL/MQ flows —
LoopX gives you a paper trail before the code ships.

*LoopX is MIT licensed and developed in the open. Contributions welcome: see
[CONTRIBUTING.md](../CONTRIBUTING.md).*
