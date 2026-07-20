# squads hooks redesign — Specs

Status: DRAFT
Depth: blueprint
Origin: plan

Source: [Design Brief](../design/2026-07-20-squads-hooks-redesign-design.md) (Approach C, user-locked, Phase 5 APPROVED). These requirements are fixed by the locked design; the [plan](squads-hooks-redesign.plan.md) sequences their implementation.

#### REQ-001: Consolidate four hook scripts into one dispatcher

Detail: Replace `hooks/dispatch-check.sh`, `hooks/debug-gate.sh`, `hooks/session-start.sh`, `hooks/session-end.sh` with one `hooks/squads-hook.sh` dispatcher. Shared lib sourced at top: `state_dir`, `b64d` (tries `base64 -d` then `base64 -D`), `jq_fail_closed`, `atomic_write` (mktemp + mv). One rule function per `<rule>` subcommand; `case "$1" in <rule>) <fn> ;; esac` dispatch. Rewrite `hooks/hooks.json` to exec form: `"command": "bash", "args": ["${CLAUDE_PLUGIN_ROOT}/hooks/squads-hook.sh", "<rule>"]` (or the single-string `bash "${CLAUDE_PLUGIN_ROOT}/hooks/squads-hook.sh" <rule>` equivalent). Drop the stale bare `Task` matcher (current tools are TaskCreate/Update/List/Get/Stop); keep `Agent|SendMessage|Workflow`.

#### REQ-002: Fix all HIGH/MED audit defects in the four existing rules

Detail: `dispatch-check` — read `.session_id` raw (drop the `// "no-session-id"` default so the empty-sid skip fires); add `.tool_input.description` to the inspected bodies; scan Workflow `.script`/`.scriptPath` bodies for the `squads:reviewer-dispatch` sentinel (not just the Task prompt); widen the raw-diff matcher from `*'diff --git'*` to also catch `^--- ` / `^+++ ` / `^diff -`; `flock … || deny` (actionable, not silent `exit 2`); validate the count-file integer before arithmetic; atomic mktemp+mv write (keep the symlink-defense rm-first); hash fallback fail-closed when no hash tool exists; hash the full `Change summary:` block (multiline), not just `head -n1`. `debug-gate` — fail-close on empty `tool_name` with an actionable deny; add bare `test.*`/`spec.*`/`tests.*` to the exemption glob; header comment lists `tdd / plan / review` as the gate-lifting skills. `session-start` — wiring banner enumerates ALL hook events (SessionStart/PreToolUse/PostToolUse/SubagentStop/SessionEnd), not just PreToolUse; `jq … 2>/dev/null || true`; dirname-based `hooks.json` path. `session-end` — correct the misleading empty-id comment; widen the cleanup glob to `squads-*-${sid}*` so it sweeps the new ethos-rule state files.

#### REQ-003: tdd-gate rule (RED before GREEN)

Detail: PreToolUse guard on `Write|Edit|MultiEdit|NotebookEdit`. Deny a non-test, non-md production-code edit unless the `${TMPDIR:-/tmp}/squads-tdd-red-<sid>` flag exists. Exempt glob mirrors `debug-gate`'s test/spec/md list PLUS bare `test.*`/`spec.*`/`tests.*`. 120min `find -mmin +120` expiry on the flag. Deny message names the rule + a one-line remediation. Wired into `hooks.json`.

#### REQ-004: tdd-arm rule (arm the RED flag on test failure)

Detail: PostToolUseFailure guard on `Bash` (design correction: Claude Code fires `PostToolUse` only on exit 0 — a non-zero Bash triggers `PostToolUseFailure`, whose payload carries an `error` string and `is_interrupt` flag, not a numeric `exit_code`; a `PostToolUse` tdd-arm would never observe a failing test). Arm (`touch ${TMPDIR:-/tmp}/squads-tdd-red-<sid>`) on any non-interrupt Bash failure — over-arm is safe (the flag only permits `tdd-gate` edits, never blocks), so no test-command narrowing (Simplicity First). 120min `find -mmin +120` expiry backstop on the flag. Passive hook: jq missing → degrade silently (no gate to fail-close on). Wired into `hooks.json`.

#### REQ-005: return-shape rule (Handoff-Contract returns)

Detail: SubagentStop guard. Two return shapes selected by content: a reviewer (detected by its mandated `## Code Review Result` header — the `squads:reviewer-dispatch` sentinel lives in the dispatch prompt, which is NOT in the SubagentStop payload, so detection is by the response header the review skill requires) must carry the 5 review headers (`## Code Review Result`, `**Status**: PASS|FAIL`, `### Blocking Issues`, `### Advisory Issues`, `### What Was Checked`); any other subagent must carry `^status:\s*(PASS|FAIL|PARTIAL)` + `^findings:`. The review format uses `**Status**:`, not `status:`, so the two shapes are alternatives, not additive. 1st malformed → `exit 2` + stderr reminder (forces one retry); 2nd malformed → `exit 0` + stdout abort diagnostic ("squads return-shape: subagent did not return Handoff-Contract shape after retry — abort, route to parallel-debugging"). Distinguishing 1st from 2nd requires a per-subagent state file `squads-return-shape-<sid>-<agent_id>` under `${TMPDIR:-/tmp}`: touch on 1st malformed, check-and-allow on 2nd, 120min `find -mmin +120` expiry. The `<agent_id>` keying field is read from the SubagentStop payload (fall back to a hash of `last_assistant_message` if no agent id). Wired into `hooks.json`.

#### REQ-006: plan-schema rule (Canonical Task Block enforcement)

Detail: PreToolUse guard on `Write` to `docs/plan/*.plan.md` paths. Read `tool_input.content`; if `Status: APPROVED` co-occurs with `Depth: sketch` → deny (validate mode rejects sketch plans). Parse `### TASK-NNN:` blocks and require all 7 field labels (`Depends on` / `Files` / `Symbols` / `Satisfies` / `Action` / `Validate` / `Expected result`); deny naming the missing field. Require an `Origin:` header. Edit gap (PreToolUse Edit can't see the full result) is documented in the `plan-schema` header comment of `squads-hook.sh`; Write-only block. Wired into `hooks.json`.

#### REQ-007: Raise timeout; fail-closed survives; document R2 residual

Detail: Raise the PreToolUse command-hook timeout from 10s to 30s. Keep scripts lean (do not regress the single-jq-read-for-N-fields pattern; do not add process spawns). Document the residual platform limit: a command-hook timeout is a non-blocking error (fail-OPEN) and is unfixable, only mitigated. Fail-closed behavior (exit 2 on deny, jq-missing fail-close) must survive the consolidation.

#### REQ-008: Portability (Windows Git Bash + BSD/macOS)

Detail: Add `.gitattributes` with `*.sh text eol=lf` and `*.json text eol=lf`; run `git add --renormalize` scoped to `*.sh` + `*.json`. `b64d` helper tries `base64 -d` then `base64 -D` (BSD/macOS). State files namespaced `squads-<rule>-<sid>[-<key>]` under `${TMPDIR:-/tmp}`; `session-end` cleans `squads-*-<sid>*`; 120min `find -mmin +120` expiry backstop per file (portable across GNU/BSD/Git Bash). `flock` best-effort (absent on Git Bash + macOS) — comment corrected.

#### REQ-009: Actionable denies; set semantics; jq required; no Node

Detail: Every deny names the rule + a one-line remediation. `set -uo pipefail` WITHOUT `-e` is intentional (grep -c / find / jq parse paths return non-zero legitimately) — preserved with a one-line comment so it is not "fixed" later. `jq` required (fail-closed without it, with an actionable install hint covering all three platforms: Windows `winget install jqlang.jq`, macOS `brew install jq`, Linux `apt/dnf install jq`). No Node runtime (correcting the stale "one Node hook" claim); plugin ships markdown + bash only, no build step.

#### REQ-010: bash -n parse guard in format:check

Detail: Extend `package.json` `scripts.format:check` to run `bash -n hooks/*.sh` before `prettier --check .` (single script, no new script): `"format:check": "bash -n hooks/*.sh && prettier --check ."`. R1 mitigation: a consolidated-file parse error is total hook outage, so syntax-check from the first save.

#### REQ-011: Fix stale docs (AGENTS.md + README.md)

Detail: Fix `AGENTS.md` line 3 "the repo is skills plus one Node hook" → the bash-dispatcher reality (no Node, jq required; one `hooks/squads-hook.sh <rule>` dispatcher). Update `README.md` line 28 "the plugin is markdown skills plus one Node hook" → bash dispatcher + exec-form `hooks.json` + 30s timeout + R2 fail-OPEN residual note. Update `README.md` line 32 `hooks/session-start.sh` reference → the router block now lives in the dispatcher. Remove any "Node hook" / "Node runtime" claim from both files.

#### REQ-012: Smoke-test every rule; no orphan rules

Detail: Smoke each rule with synthetic JSON (`echo '{"tool_name":"…","tool_input":{…},"session_id":"t"}' | bash hooks/squads-hook.sh <rule>`) before and after the `hooks.json` swap. Verify via `/hooks` in a fresh session. `bash -n` clean. No orphan rules (final state, verified by TASK-009): every `case` arm in `squads-hook.sh` has exactly one `hooks.json` entry, and every `hooks.json` entry has exactly one `case` arm — checked mechanically (diff case arms vs hooks.json commands), not by prose. The transient stub arms in TASK-002 (inert `exit 0` before TASK-004-007 wire them) are not a violation: no `hooks.json` route reaches them until wired, and TASK-009 verifies the final 8↔8 mapping. `session-end` cleans all `squads-*-<sid>*` state including the new ethos-rule flags.

#### REQ-013: debug-gate +Bash matcher and write-pattern heuristic

Detail: Per the design brief Interface table and risk R4, expand the `debug-gate` PreToolUse matcher to `Skill|Write|Edit|MultiEdit|NotebookEdit|Bash` (add `Bash`). While the debug-gate flag is set, inspect `tool_input.command` for write-to-file subcommands using a conservative pattern list (`sed -i`, `tee`, `printf … >`, `cat … >`, `>`/`>>` redirects to a non-test/non-md path) and deny — route-to-sibling (tdd/plan/review) lifts the flag; 120min expiry. The pattern list is the tunable knob (marked `# ponytail: heuristic — pattern list is the calibration knob`). Wired into `hooks.json` (the debug-gate entry's matcher gains `Bash` in TASK-003).
