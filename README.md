# Squads

![Version](https://img.shields.io/github/package-json/v/j0hanz/squads?style=for-the-badge&label=version)

A Claude Code plugin with skills for collaborative software development. Each skill covers one stage of the development lifecycle, from brainstorming and planning through implementation, debugging, and code review.

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

## Development

These are for contributors working on the plugin itself, not for using it.

### Prerequisites

- Node.js ≥ 22 and npm — only for Prettier formatting.
- Python 3 — only for the skill linter.

### Scripts

| Command                         | Description                                                        |
| ------------------------------- | ------------------------------------------------------------------ |
| `npm run format`                | Format every file with Prettier (`prettier --write .`)             |
| `npm run format:check`          | Check formatting without writing                                   |
| `python scripts/lint_skills.py` | Validate SKILL.md frontmatter, relative links, and contract tokens |

## Contributing

This repo has no `CONTRIBUTING.md` yet. To contribute, open an issue or pull request against [`j0hanz/squads`](https://github.com/j0hanz/squads), and run `python scripts/lint_skills.py` and `npm run format:check` before submitting.

## License

[MIT](LICENSE)
