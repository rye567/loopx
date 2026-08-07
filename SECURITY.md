# Security Policy

## Reporting a vulnerability

LoopX is a skill package for AI coding agents. A vulnerability here could mean:

- The controller writes run state or artifacts to unexpected locations.
- A crafted project could make the controller execute unexpected commands (e.g., `git-gate` runs `git status`).
- Prompt-injection style abuse where project content steers the workflow into unsafe actions.

**Please do not open a public issue for security problems.** Report privately using GitHub's Security Advisories:

- https://github.com/rye567/loopx/security/advisories

You can report anonymously if you prefer. Include:

- A description of the issue and its impact.
- Steps to reproduce (commands, project structure).
- Suggested fix, if you have one.

## Response

- We aim to acknowledge reports within 3 business days.
- We will work with you to confirm the issue and prepare a fix.
- We will credit you in the advisory unless you prefer to stay anonymous.

## Scope

- In scope: the `loopx/` skill package, `loopx/tools/` controller and harness scripts, and documented commands.
- Out of scope: misconfiguration by the user (e.g., granting a prompt-injected project write access), or issues in third-party tools LoopX integrates with.

## Supported versions

| Version | Supported |
| --- | --- |
| latest release on `main` | ✅ |
| older releases | ⚠️ best effort |
