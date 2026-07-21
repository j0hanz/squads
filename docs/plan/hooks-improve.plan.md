# hooks-improve — Plan

Status: APPROVED
Depth: contract
Origin: plan
Review pass: 1
Source: docs/design/2026-07-21-hooks-improve-design.md
Notes: Round-1 Meds (TASK-003 oversized; newline-strip wording; Validate coverage gap) and Lows (TASK-001 audit scope) resolved in REVISE — TASK-003 split into TASK-003/TASK-004, inline behavioral assertions added to Validate, TASK-001 widened to all four temp candidates. Round-2 re-validation: all findings resolved, no new High.

Audit verdict: TASK-001 run 2026-07-21 — TMPDIR=<unset>; TEMP=C:\Users\PC\AppData\Local\Temp (writable); TMP=C:\Users\PC\AppData\Local\Temp (writable); /tmp (writable, MSYS mount). Current state_dir resolution ${TMPDIR:-/tmp} = /tmp → WRITABLE. TASK-006 = DROP (no code change).

## Tasks

### TASK-001: /tmp probe-write audit

Depends on: none
Files: [docs/plan/hooks-improve.plan.md](docs/plan/hooks-improve.plan.md)
Symbols: [state_dir](hooks/squads-hook.sh#L22)
Satisfies: REQ-007
Action: From Git Bash on this win32 box, probe-write each candidate and record the result. For each of `TMPDIR`, `TEMP`, `TMP`, `/tmp` (where set), run `touch "<dir>/squads-probe-$$" && ls -la "<dir>/squads-probe-$$" && rm "<dir>/squads-probe-$$"` and record writable/unwritable. Separately record the resolved path of the current `state_dir` resolution `${TMPDIR:-/tmp}`. Fill the `Audit verdict:` header line with per-candidate verdicts and the current resolution's writability. This verdict gates TASK-006.
Validate: `for d in "$TMPDIR" "$TEMP" "$TMP" /tmp; do [ -n "$d" ] && (touch "$d/squads-v-$$" 2>/dev/null && rm "$d/squads-v-$$" && echo "$d: writable" || echo "$d: unwritable"); done`
Expected result: Exit 0 prints per-candidate writability; verdict recorded in plan header.

### TASK-002: Add is_plan_path() helper and replace duplicated globs

Depends on: none
Files: [hooks/squads-hook.sh](hooks/squads-hook.sh)
Symbols: [is_exempt_path](hooks/squads-hook.sh#L34), [plan_schema](hooks/squads-hook.sh#L170), [post_tool](hooks/squads-hook.sh#L203)
Satisfies: REQ-002
Action: Add a bash `case`-glob function `is_plan_path()` (sibling of `is_exempt_path`) matching `*/docs/plan/*.plan.md | docs/plan/*.plan.md` after `${1//\\//}` normalization, returning 0 if matched else 1. Replace the inline `case "${file_path//\\//}" in */docs/plan/*.plan.md | docs/plan/*.plan.md)` glob in `plan_schema` with `is_plan_path "$file_path" || return 0`, and the same glob in `post_tool` with `is_plan_path "$file_path" || exit 0`. No semantic change — same bash glob, factored.
Validate: `bash -n hooks/squads-hook.sh && python hooks/perf-hook.py --self-check`
Expected result: `self-check OK`; no syntax error; existing dispatch-check assertions still pass.

### TASK-003: Single-jq scalar extraction + governor/debug gate signature refactor

Depends on: none
Files: [hooks/squads-hook.sh](hooks/squads-hook.sh)
Symbols: [pre_tool](hooks/squads-hook.sh#L186), [governor_gate](hooks/squads-hook.sh#L94), [debug_gate](hooks/squads-hook.sh#L117)
Satisfies: REQ-001, REQ-003, REQ-005
Action: Refactor `pre_tool()`: read stdin once into `$input`; pre-initialize locals `tool="" skill="" sid="" file_path=""`; run one `jq -r '[.tool_name // "", .tool_input.skill // "", .session_id // "", (.tool_input.file_path // .tool_input.notebook_path // "")] | @tsv'` piped to `IFS=$'\t' read -r tool skill sid file_path` (guard `|| true`; jq failure leaves locals empty → fail-open, no `set -u` abort). Change `governor_gate` and `debug_gate` signatures to accept pre-parsed scalars (`governor_gate "$tool" "$skill" "$sid"`, `debug_gate "$tool" "$sid" "$file_path"`) and drop their internal jq re-parses. Leave the `Write` branch and `plan_schema` unchanged for this task (still called with `$input` in the old signature — TASK-004 rewires it). Keep `governor_gate` call before `debug_gate`; add a one-line comment that `deny()`→`exit 2` makes the order structural. Deny message strings verbatim.
Validate: `bash -n hooks/squads-hook.sh && python hooks/perf-hook.py --self-check && printf '{"tool_name":"Skill","tool_input":{"skill":"squads:debug"},"session_id":"probe-sid"}' | bash hooks/squads-hook.sh pre-tool 2>&1 | grep -q 'squads governor-gate:'`
Expected result: `self-check OK`; the inline governor-gate probe exits via the `grep -q` match (governor denies `squads:debug` with no flag set); `set -u` does not abort on jq failure.

### TASK-004: Write-content path + plan_schema signature rewire

Depends on: TASK-002, TASK-003
Files: [hooks/squads-hook.sh](hooks/squads-hook.sh)
Symbols: [pre_tool](hooks/squads-hook.sh#L186), [plan_schema](hooks/squads-hook.sh#L170)
Satisfies: REQ-001, REQ-005
Action: In `pre_tool()`'s `Write` branch, fetch `content=$(jq -r '.tool_input.content // ""' <<<"$input" 2>/dev/null)` (second jq, direct — not via `@tsv`; preserves internal newlines for line-based validation). Change `plan_schema` to take pre-parsed args `plan_schema <file_path> <content>` and call `is_plan_path "$file_path" || return 0` (TASK-002) instead of its inline jq/glob; drop its internal jq for `file_path` and `content`. Update the `pre_tool` Write call to `plan_schema "$file_path" "$content"`. Deny message string verbatim.
Validate: `bash -n hooks/squads-hook.sh && python hooks/perf-hook.py --self-check && printf '{"tool_name":"Write","tool_input":{"file_path":"docs/plan/x.plan.md","content":"no header here"},"session_id":"probe-sid"}' | bash hooks/squads-hook.sh pre-tool 2>&1 | grep -q 'squads plan-schema:'`
Expected result: `self-check OK`; the inline plan-schema probe matches `squads plan-schema:` (malformed plan denied); a clean `Origin:` header passes silently.

### TASK-005: Extend perf-hook.py self-check to cover new pre-tool paths

Depends on: TASK-004
Files: [hooks/perf-hook.py](hooks/perf-hook.py)
Symbols: [self_check](hooks/perf-hook.py#L281), [run_rule](hooks/perf-hook.py#L79)
Satisfies: REQ-006, REQ-005
Action: Extend `self_check()` to assert, via `run_rule` against the real dispatcher: (1) governor-gate — a `Skill` `squads:debug` input with no governor flag set returns exit 2 and stderr starting `squads governor-gate:`; (2) debug-gate — a `squads:debug` Skill input arms the debug flag, then a `Write` to a non-exempt path returns exit 2 with `squads debug-gate:`, and a `Write` to a `*.md` path returns 0; (3) plan-schema — a `Write` to `docs/plan/x.plan.md` with content missing the `Origin:` header returns exit 2 with `squads plan-schema:`; (4) clean pre-tool input returns exit 0 silently. Retain the existing dirty/clean `dispatch-check` assertions. Clean up any `squads-*` flag files created under `${TMPDIR:-/tmp}` in the self-check.
Validate: `python hooks/perf-hook.py --self-check`
Expected result: `self-check OK`; all four new assertions pass; dispatch-check parity retained; no stray `squads-*` flag files left in the temp dir.

### TASK-006: Conditional state_dir() win32 hardening

Depends on: TASK-001
Files: [hooks/squads-hook.sh](hooks/squads-hook.sh)
Symbols: [state_dir](hooks/squads-hook.sh#L22)
Satisfies: REQ-004
Action: If TASK-001 verdict shows the current resolution `${TMPDIR:-/tmp}` is writable, make no code change — record "state_dir() hardening dropped — /tmp writable on this win32 box" in the plan header and stop. If unwritable, rewrite `state_dir()` to probe-write the first writable of `TMPDIR`, `TEMP`, `TMP`, `/tmp` (create+remove a probe file per candidate), echo that dir, and fall through to `/tmp` silent fail-open if none writable. Verify the per-session flag files (`squads-governor-<sid>`, `squads-debug-gate-<sid>`) round-trip on the selected dir.
Validate: `bash -n hooks/squads-hook.sh && python hooks/perf-hook.py --self-check && flag="$(mktemp -p "${TMPDIR:-/tmp}" squads-gov-test-XXXX 2>/dev/null)" && rm -f "$flag" && echo ok`
Expected result: `self-check OK`; probe writes and reads back a `squads-*` file on the selected dir (or unchanged `/tmp` if dropped); exit 0.