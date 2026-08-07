# LoopX End-to-End Demo

This walkthrough runs a real LoopX run from `init` to `close` in a fresh Git
project, using **LIGHT** mode so review gates are legally skipped. Every output
below is from a real run on macOS with Python 3.13 — copy the commands and you
get the same result.

## Setup

```bash
mkdir loopx-demo && cd loopx-demo
git init
# install LoopX once (or manual: git clone + ln -s "$PWD/loopx" "$HOME/.claude/skills/loopx"):
plugin marketplace add https://github.com/rye567/loopx
plugin install loopx
# then use its controller:
python3 <loopx>/loopx/tools/loopx_controller.py --help
```

## 1. Start the run

```bash
python3 <loopx>/loopx/tools/loopx_controller.py init \
  "Add dark mode toggle to the settings page" --run-id demo-dark-mode --project .
```

Output: environment check auto-passes and the run lands on `requirement_intake`.

```text
created run demo-dark-mode
mode: LIGHT
recommended mode: LIGHT
environment_check: PASS
mode selection: NEED_HUMAN
```

## 2. Requirement intake and interview

```bash
python3 <loopx>/loopx/tools/loopx_controller.py record-stage --run-id demo-dark-mode \
  --stage requirement_intake --status PASS --evidence "requirement recorded" --project .

python3 <loopx>/loopx/tools/loopx_controller.py interview demo-dark-mode --project .
```

`interview` prints the questions. Write the answers into
`docs/loopx/runs/demo-dark-mode/artifacts/interview.md`, then record and confirm:

```bash
python3 <loopx>/loopx/tools/loopx_controller.py record-stage --run-id demo-dark-mode \
  --stage requirement_interview --status PASS \
  --evidence docs/loopx/runs/demo-dark-mode/artifacts/interview.md --project .
python3 <loopx>/loopx/tools/loopx_controller.py confirm-stage --run-id demo-dark-mode \
  --stage requirement_interview --evidence "user confirmed interview" --project .
```

```text
NEED_HUMAN requirement_interview
next_action: confirm-stage --stage requirement_interview
PASS confirmed requirement_interview
next_action: spec_draft
```

`PASS` on a confirmation gate is stored as `NEED_HUMAN`; nothing advances until
a human runs `confirm-stage`.

## 3. Spec and mode selection

```bash
python3 <loopx>/loopx/tools/loopx_controller.py spec demo-dark-mode --project .
python3 <loopx>/loopx/tools/loopx_controller.py record-stage --run-id demo-dark-mode \
  --stage spec_draft --status PASS \
  --evidence docs/loopx/runs/demo-dark-mode/artifacts/spec.md --project .
python3 <loopx>/loopx/tools/loopx_controller.py record-stage --run-id demo-dark-mode \
  --stage spec_review --status SKIPPED --evidence "LIGHT skips spec review" --project .
python3 <loopx>/loopx/tools/loopx_controller.py mode demo-dark-mode --select LIGHT --project .
```

`spec_review` is a review gate — LIGHT mode is allowed to skip it
(`MODE_SKIPPABLE_STAGES`), and `validate --strict`/`gate` accept that.

## 4. Design → development, gated writes

```bash
python3 <loopx>/loopx/tools/loopx_controller.py advance --run-id demo-dark-mode \
  --to solution_design --project .
python3 <loopx>/loopx/tools/loopx_controller.py record-stage --run-id demo-dark-mode \
  --stage solution_design --status PASS --evidence docs/solution.md --project .
python3 <loopx>/loopx/tools/loopx_controller.py record-stage --run-id demo-dark-mode \
  --stage solution_review --status SKIPPED --evidence "LIGHT skips solution review" --project .
python3 <loopx>/loopx/tools/loopx_controller.py record-stage --run-id demo-dark-mode \
  --stage test_design --status PASS --evidence docs/test-cases.md --project .
python3 <loopx>/loopx/tools/loopx_controller.py record-stage --run-id demo-dark-mode \
  --stage test_review --status SKIPPED --evidence "LIGHT skips test review" --project .
python3 <loopx>/loopx/tools/loopx_controller.py advance --run-id demo-dark-mode \
  --to development --project .
```

Before touching business code, ask the controller:

```bash
python3 <loopx>/loopx/tools/loopx_controller.py can-write --run-id demo-dark-mode \
  --kind business --project .
# PASS business writes unlocked
```

## 5. Implement, verify, close

```bash
# ... implement, run tests ...
python3 <loopx>/loopx/tools/loopx_controller.py record-stage --run-id demo-dark-mode \
  --stage development --status PASS --evidence "implemented dark mode toggle" --project .
python3 <loopx>/loopx/tools/loopx_controller.py record-stage --run-id demo-dark-mode \
  --stage quality_audit --status SKIPPED --evidence "LIGHT skips quality audit" --project .
python3 <loopx>/loopx/tools/loopx_controller.py record-stage --run-id demo-dark-mode \
  --stage code_review --status PASS --evidence "reviewed diff" --project .
python3 <loopx>/loopx/tools/loopx_controller.py record-stage --run-id demo-dark-mode \
  --stage test_execution --status PASS --evidence "tests passed" --project .
python3 <loopx>/loopx/tools/loopx_controller.py record-stage --run-id demo-dark-mode \
  --stage health_gate --status PASS --evidence "health check passed" --project .
python3 <loopx>/loopx/tools/loopx_controller.py record-stage --run-id demo-dark-mode \
  --stage release_readiness --status SKIPPED --evidence "LIGHT has no release window" --project .
python3 <loopx>/loopx/tools/loopx_controller.py record-stage --run-id demo-dark-mode \
  --stage final_report --status PASS --evidence docs/final-report.md --project .

python3 <loopx>/loopx/tools/loopx_controller.py git-gate demo-dark-mode --project .
python3 <loopx>/loopx/tools/loopx_controller.py compound demo-dark-mode \
  --decision skipped --reason "routine UI change, no reusable learning" --project .
python3 <loopx>/loopx/tools/loopx_controller.py gate demo-dark-mode --project .
python3 <loopx>/loopx/tools/loopx_controller.py close demo-dark-mode --project .
```

```text
PASS git gate demo-dark-mode
PASS compound capture demo-dark-mode
PASS gate demo-dark-mode
strict validation: PASS
PASS close demo-dark-mode
status: PASS
```

## What you end up with

Under `docs/loopx/runs/demo-dark-mode/`:

- `state.json` — machine-readable run state (the single source of truth)
- `worklist.yml` — human/agent-readable stage list, kept in sync by the controller
- `stage-results/` — one JSON result per recorded stage, each with evidence and a tracking snapshot
- `artifacts/interview.md`, `artifacts/spec.md` — generated, human-reviewed artifacts
- `artifacts/compound-capture.md` — close decision (skipped/captured)
- `artifacts/close-evidence.json` — evidence matrix, Git gate summary, CI/remote coverage note

The whole `docs/loopx/runs/` directory is git-ignored; only `close-evidence.json`
and readable artifacts survive `close` (intermediate files are archived to
`artifacts/archive/`).

Try the same with `--mode STANDARD` or `--mode FULL` — review gates become
mandatory (`PASS` or `ACCEPTED_RISK`), and `SKIPPED` is rejected.
