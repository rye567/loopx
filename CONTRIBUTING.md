# Contributing to LoopX

Thanks for considering contributing to LoopX. This project is a quality-gate skill package for AI coding agents; every change to the workflow contract, controller, or documentation matters to the people who run it.

## Ground rules

- The workflow contract lives in `loopx/workflow.md`, `loopx/standards/`, `loopx/schemas/` and `loopx/templates/`. If you change the contract, update the related tests and documentation in the same PR.
- Run state is maintained by `loopx/tools/loopx_controller*.py`. Do not introduce hand-written run state or bypass the controller in examples and docs.
- Follow the existing code style: match the surrounding code's comment density, naming, and idiom.

## Development setup

```bash
git clone git@github.com:rye567/loopx.git
cd loopx
```

The project only depends on the Python standard library. Run the test suite:

```bash
python3 -m unittest discover -s tests
```

Check the packaged skill assets (standards, skills, agents, templates, schemas):

```bash
python3 loopx/tools/loopx_check.py package --root .
```

Try the controller locally:

```bash
python3 loopx/tools/loopx_controller.py --help
```

## What to work on

Open issues are a good starting point. Common useful contributions:

- Regression tests for controller behavior (stage transitions, confirmation gates, repair loops, strict validation).
- Documentation fixes and contract clarifications in `workflow.md` or the standards.
- Tooling improvements for the controller or the package harness.
- Examples showing LoopX applied to a real project.

## Submitting changes

1. Fork the repository and create a feature branch (`git checkout -b fix/...` or `feat/...`).
2. Make your changes. Add or update tests for behavior changes.
3. Run the full test suite and the package check locally; both must pass.
4. Commit with a clear message following the existing style (`feat:`, `fix:`, `refactor:`, `chore:`, `docs:`).
5. Open a pull request. Describe what changed and why, and mention the affected contract or stage if any.

## Reporting issues

Before opening an issue, search for an existing one. Include:

- What you were trying to do.
- The command(s) you ran and the output (especially controller or check output).
- Expected behavior vs. actual behavior.
- Your environment (macOS/Linux/Windows, Python version, tool version).

Security issues should be reported privately — see [SECURITY.md](SECURITY.md).
