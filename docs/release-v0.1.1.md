# LoopX v0.1.1 Release Notes

LoopX v0.1.1 is a patch release that fixes a self-deadlock in the write-protection
gate, and polishes the public repo for installation and discovery.

## Highlights

- **Repair write-lock deadlock fixed**: previously, when a stage such as
  `health_gate` failed with `CHANGES_REQUIRED` and returned to `development`,
  `can-write --kind business` still blocked all business writes — including the
  code changes required to fix that very stage. The repair path deadlocked
  itself.

  Now a `CHANGES_REQUIRED` stage no longer locks business writes when the run
  is at `development` with an open repair ticket whose `return_to=development`
  and with solution/test reviews satisfied. `BLOCKED` stages still always lock
  writes, and ticket-less `CHANGES_REQUIRED` still blocks out-of-band writes.

- **Installable as a plugin**: LoopX now ships `marketplace.json` plus
  `.claude-plugin` / `.codex-plugin` manifests, so ZCode and Claude Code users
  can install it directly:

  ```bash
  plugin marketplace add https://github.com/rye567/loopx
  plugin install loopx
  ```

- README now opens with an end-to-end demo GIF and a Mermaid flow diagram of
  the staged workflow (human confirmation gates and the write-unlock point).

## Upgrade

Plugin users: `plugin update loopx`.
Manual installs: `git pull` in your clone.

Full details: [CHANGELOG.md](CHANGELOG.md).
