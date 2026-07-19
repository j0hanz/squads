# Squads

![Version](https://img.shields.io/github/package-json/v/j0hanz/squads?style=for-the-badge&label=version)

A multi-agent workflow plugin with seven skills that hand off along one lifecycle.

## Features

Seven skills, each with a single job, that hand off along one lifecycle:

- **parallel-brainstorming**: explore a vague or open problem before any plan exists.
- **plan**: draft a plan or spec, then validate it before execution (draft / validate modes).
- **dispatch-agents**: triages every incoming request first, selects the multi-agent workflow, and executes approved plans across agent fleets.
- **tdd**: implement new logic test-first; flags tests written after the code.
- **parallel-debugging**: reproduce and isolate an unexpected failure before fixing it.
- **review**: get a fresh-eye review on a diff, then resolve the feedback (request / resolve modes).
- **forge-workflow**: forge a reusable dynamic workflow from an approved plan (generates per-project `.claude/workflows/<name>.js` + `docs/workflows/CATALOG.md`; never shipped with the plugin).

## Install

Add the repo as a marketplace and install the plugin into Claude Code:

```bash
/plugin marketplace add j0hanz/squads
/plugin install squads@squads
```

> Requires [Claude Code](https://docs.claude.com/en/docs/claude-code/overview). No build step or runtime dependency; the plugin is markdown skills plus one Node hook.

## Usage

On every session start, clear, and compact, the `squads-router` block (inlined as a literal string in `hooks/session-start.sh`) is injected automatically and routes each task through `dispatch-agents`, whose triage step selects the right workflow by first match. Invoke any skill explicitly through the Skill tool, namespaced as `squads:<name>`:

```text
/squads:parallel-brainstorming  "add offline mode to the editor"
/squads:plan                   "rate-limit the public API"
/squads:tdd                    "parse a duration string into seconds"
```

When unsure which skill fits, invoke `dispatch-agents` — its triage picks for you, preferring upstream (brainstorm or plan) over executing or reviewing.

### Lifecycle

```text
user request → dispatch-agents (Step 0 Triage: pick workflow + fleet)
  ├─ open problem  → parallel-brainstorming → plan (draft) → plan (validate) ─┐
  ├─ clear feature → plan (draft) → plan (validate) ─┬────────────────────────┘
  │                                                  └→ dispatch-agents (multi-task) / tdd (single task)
  ├─ failure       → parallel-debugging → tdd (logic bug) / plan (design-level)
  ├─ bulk / audit  → dispatch-agents patterns (fan out, adversarial verify, loop until done)
  ├─ approved plan → forge-workflow (forge/library branch: generates per-project `.claude/workflows/<name>.js` + `docs/workflows/CATALOG.md`, never shipped)
  └─ verified diff → review (request) → review (resolve) → commit / PR
```

> **Platform requirement**: native dynamic workflows are a hard dependency — Claude Code (CC) ≥ 2.1.154, paid plan required.

## License

[MIT](LICENSE)
