# LoopX Standards

This directory defines the standard delivery track that LoopX agents, skills and harness checks must follow.

Use these files as the stable contract before adding more automation:

1. `requirement-standard.md` turns fuzzy requests into executable scope.
2. `development-standard.md` constrains code changes and implementation behavior.
3. `testing-standard.md` defines test design, data, assertions and cleanup.
4. `quality-standard.md` defines machine-checkable gates and evidence rules.
5. `release-standard.md` defines release readiness, rollback and operational evidence.

Each standard should be treated as a gate contract: every agent output needs clear input, output, pass criteria, failure handling and evidence.
