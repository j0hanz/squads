# Squads

![Version](https://img.shields.io/github/package-json/v/j0hanz/squads?style=for-the-badge&label=version)

A multi-agent workflow plugin with seven skills that hand off along one lifecycle.

## Features

Seven skills, each with a single job, that hand off along one lifecycle:

- **brainstorm**: explore a vague or open problem before any plan exists.
- **plan**: draft a plan or spec, then validate it before execution (draft / validate modes).
- **dispatch-agents**: sizes and runs a fan-out fleet — bulk/audit work and approved plans — picking inline vs composed. Not a mandatory first hop; lifecycle work routes directly to its skill.
- **tdd**: implement new logic test-first; flags tests written after the code.
- **debug**: reproduce and isolate an unexpected failure before fixing it.
- **review**: get a fresh-eye review on a diff, then resolve the feedback (request / resolve modes).
- **forge-workflow**: forge a reusable dynamic workflow from an approved plan (generates per-project `.claude/workflows/<name>.js` + `docs/workflows/CATALOG.md`; never shipped with the plugin).

## Install

Add the repo as a marketplace and install the plugin into Claude Code:

```bash
/plugin marketplace add j0hanz/squads
/plugin install squads@squads
```

> Requires [Claude Code](https://docs.claude.com/en/docs/claude-code/overview) and `jq` on PATH (`dispatch-check` fails closed without it, the edit-path gates fail open — Windows: `winget install jqlang.jq`; macOS: `brew install jq`; Linux: `apt/dnf install jq`). No build step or Node runtime; the plugin is markdown skills plus one bash hook dispatcher (`hooks/squads-hook.sh <rule>`, command-string `hooks/hooks.json`, 10s PreToolUse timeout). Note: a command-hook timeout is a non-blocking error (fail-OPEN) and is unfixable, only mitigated.

## Usage

On every session start, clear, and compact, the `squads-router` block (inlined as a literal string in the `session-start` arm of `hooks/squads-hook.sh`) is injected automatically and routes each task **by first match directly to the skill that owns it** — no mandatory first hop. Fan-out and bulk work, plus approved plans, go to `dispatch-agents`, whose Governor picks inline vs composed and sizes the fleet. Invoke any skill explicitly through the Skill tool, namespaced as `squads:<name>`:

```text
/squads:brainstorm  "add offline mode to the editor"
/squads:plan                   "rate-limit the public API"
/squads:tdd                    "parse a duration string into seconds"
```

When unsure which skill fits, the injected `squads-router` names the first-match route (preferring upstream — brainstorm or plan — over executing or reviewing); for a fan-out or bulk job, `dispatch-agents` sizes the fleet.

### Lifecycle

```text
user request → squads-router: first match, invoke the skill directly
  ├─ open problem  → brainstorm → plan (draft) → plan (validate) ─┐
  ├─ clear feature → plan (draft) → plan (validate) ─┬────────────────────────┘
  │                                                  └→ dispatch-agents (multi-task) / tdd (single task)
  ├─ failure       → debug → tdd (logic bug) / plan (design-level)
  ├─ bulk / audit  → dispatch-agents patterns (fan out, adversarial verify, loop until done)
  ├─ approved plan → dispatch-agents (execute task graph) · forge-workflow (recurring bulk: generates per-project `.claude/workflows/<name>.js` + `docs/workflows/CATALOG.md`, never shipped)
  └─ verified diff → review (request) → review (resolve) → commit / PR
```

> **Platform requirement**: composed mode — forge-workflow scripts, the `debug-verify` quorum, and large fan-out — needs native dynamic workflows (Claude Code ≥ 2.1.154, paid plan). Without them the plugin still runs **inline**: lifecycle skills, small fleets, and single-thread debug all work, but the mechanically-enforced composed path is off — `debug` degrades to single-thread reproduce-and-isolate (no skeptic quorum) and bulk fan-out stays inline. You get the process discipline, not the in-runtime enforcement.

## Development

No build step. Checks:

```bash
npm ci && npm run format:check   # bash -n on hooks + cross-skill anchor check + prettier (needs Node for the formatter only)
ruff check .                     # Python lint (config in pyproject.toml)
python -m pytest                 # scan_context suite
```

## License

[MIT](LICENSE)
