# Squads

![Version](https://img.shields.io/github/package-json/v/j0hanz/squads?style=for-the-badge&label=version)

A multi-agent workflow plugin with eight skills that hand off along one lifecycle.

## Features

Eight skills, each with a single job, that hand off along one lifecycle:

- **parallel-brainstorming**: explore a vague or open problem before any plan exists.
- **request-plan** / **receive-plan**: draft a plan or spec, then validate it before execution.
- **dispatch-agents**: triages every incoming request first, selects the multi-agent workflow, and executes approved plans across agent fleets.
- **tdd**: implement new logic test-first; flags tests written after the code.
- **parallel-debugging**: reproduce and isolate an unexpected failure before fixing it.
- **request-code-review** / **receive-code-review**: get a fresh-eye review on a diff, then resolve the feedback.

## Install

Add the repo as a marketplace and install the plugin into Claude Code:

```bash
/plugin marketplace add j0hanz/squads
/plugin install squads@squads
```

> Requires [Claude Code](https://docs.claude.com/en/docs/claude-code/overview). No build step or runtime dependency; the plugin is markdown skills plus one Node hook.

## Usage

On every session start, clear, and compact, the `using-squads` router is injected automatically and routes each task through `dispatch-agents`, whose triage step selects the right workflow by first match. Invoke any skill explicitly through the Skill tool, namespaced as `squads:<name>`:

```text
/squads:parallel-brainstorming  "add offline mode to the editor"
/squads:request-plan            "rate-limit the public API"
/squads:tdd                     "parse a duration string into seconds"
```

When unsure which skill fits, invoke `dispatch-agents` — its triage picks for you, preferring upstream (brainstorm or plan) over executing or reviewing.

### Lifecycle

```text
user request → dispatch-agents (Step 0 Triage: pick workflow + fleet)
  ├─ open problem  → parallel-brainstorming → request-plan → receive-plan ─┐
  ├─ clear feature → request-plan → receive-plan ─┬──────────────────────┘
  │                                               └→ dispatch-agents (multi-task) / tdd (single task)
  ├─ failure       → parallel-debugging → tdd (logic bug) / request-plan (design-level)
  ├─ bulk / audit  → dispatch-agents patterns (fan out, adversarial verify, loop until done)
  └─ verified diff → request-code-review → receive-code-review → commit / PR
```

## License

[MIT](LICENSE)
