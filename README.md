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

### Requirements

Only [Claude Code](https://docs.claude.com/en/docs/claude-code/overview) is mandatory. The skills are markdown — Claude Code loads them itself, so `/squads:plan` and friends work on a bare install. The two items below add the parts that run on their own.

**A POSIX shell — for automatic routing and the guardrails.** Claude Code passes the plugin's hook commands to `sh -c` on macOS and Linux (already present, nothing to do) and to Git Bash on Windows. **Windows users need [Git for Windows](https://git-scm.com/download/win).** Without it Claude Code falls back to PowerShell, which cannot parse the POSIX hook commands, and every hook fails: no `squads-router` injection, no gates, no obvious cause. The skills keep working, so the plugin looks half-dead rather than misconfigured.

**`jq` — for the guardrails to enforce.** Without it the hooks still run and routing still works; the three gates skip and say so (a note at session start, plus a warning on each skipped check). Install with `winget install jqlang.jq` (Windows), `brew install jq` (macOS), or `apt/dnf install jq` (Linux).

| Installed                        | routing | dispatch-check · debug-gate · plan-schema | skills |
| -------------------------------- | ------- | ----------------------------------------- | ------ |
| Claude Code only                 | —       | —                                         | ✓      |
| plus shell (Git Bash on Windows) | ✓       | skipped, announced                        | ✓      |
| plus `jq`                        | ✓       | ✓                                         | ✓      |

Everything else is optional. **Python 3.11+** is used by brainstorm's `scan_context.py` (falls back to grep) and by the repo's own hook test harness, never by the hooks themselves. **Node** is for the repo's own format check, never for using the plugin. No build step.

> Internals: markdown skills plus one bash hook dispatcher (`hooks/squads-hook.sh <rule>`, command-string `hooks/hooks.json`, 10s PreToolUse timeout). Every rule is silent on success, so `SQUADS_PERF=1` opts into one log line per fire under `$PERF_LOG_DIR` (default `~/.claude/squads-perf`) when you need proof a hook ran.

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
npm ci && npm run format:check   # bash -n on hooks + prettier (needs Node for the formatter only)
ruff check .                     # Python lint + the 3.11 floor (target-version in pyproject.toml)
python -m pytest                 # scan_context suite
bash skills/forge-workflow/references/plant-breach-drill.sh   # Script Audit HIGH items
```

## License

[MIT](LICENSE)
