# hooks-improve — Specs

Status: DRAFT
Depth: contract
Origin: plan
Source: docs/design/2026-07-21-hooks-improve-design.md

## Requirements

#### REQ-001: Single-jq extraction in pre_tool

Detail: `pre_tool()` in `hooks/squads-hook.sh` reads stdin ONCE into `$input`, runs ONE `jq` emitting scalars `tool`, `skill`, `sid`, `file_path` via `@tsv`, consumed with `IFS=$'\t' read -r` into PRE-INITIALIZED (to `""`) locals. jq failure → empty locals → fail-open (no `set -u` abort). `governor_gate` and `debug_gate` consume pre-parsed args instead of re-running jq (TASK-003). On `Write`, a SECOND `jq` on `$input` fetches `content` directly (not via `@tsv`); this preserves INTERNAL newlines for line-based `plan_schema_violations` greps. Trailing-newline stripping by `$(...)` is acceptable and matches the existing `plan_schema` behavior — it does not affect the `^Origin:` or per-TASK field-label line greps. `plan_schema` takes pre-parsed `file_path` + `content` args (TASK-004). Net: 1–2 jq spawns per pre-tool fire (down from ~5).

#### REQ-002: is_plan_path() helper

Detail: A bash `case`-glob function `is_plan_path() { case "${1//\\//}" in */docs/plan/*.plan.md | docs/plan/*.plan.md) return 0 ;; esac; return 1; }` factored from the duplicated glob in `plan_schema` (pre-tool) and `post_tool`. Same bash glob semantics as before — NOT Python, NOT jq.

#### REQ-003: governor-before-debug ordering preserved

Detail: `governor_gate` runs BEFORE `debug_gate` in `pre_tool`. `deny()` calls `exit 2`, structurally preventing `debug_gate` from arming on a denied `squads:debug`. Call order kept with a one-line comment at the call site documenting the invariant. The invariant is asserted behaviorally in TASK-003's Validate (governor deny on a lifecycle Skill with no flag) and in TASK-005's self-check.

#### REQ-004: state_dir() win32 hardening (audit-gated)

Detail: ONLY if TASK-001 audit proves `/tmp` (the current `state_dir` resolution `${TMPDIR:-/tmp}`) unreliable on this win32 box. If unreliable, `state_dir()` probe-writes the first WRITABLE of `TMPDIR`, `TEMP`, `TMP`, `/tmp`, silent fail-open if none. If `/tmp` is writable, the change is DROPPED — record "dropped — /tmp writable" in the plan. Per-session flag files (`squads-governor-<sid>`, `squads-debug-gate-<sid>`) must land on a writable, consistently-resolved dir.

#### REQ-005: Strict compatibility preserved

Detail: Rules (`session-start`, `dispatch-check`, `pre-tool`, `post-tool`), `exit 2` denies, `squads <gate>:` stderr prefixes (governor-gate, debug-gate, dispatch-check, plan-schema), JSONL record shape `{ts,rule,ms,exit?,tool?,skill?,session?,err?,timeout?}`, and the Governor's hook-fire probe (expects exactly the dispatch-check deny) — all unchanged. Deny message strings verbatim. TASK-005's self-check asserts dirty/clean `dispatch-check` parity is retained.

#### REQ-006: perf-hook.py self-check extended

Detail: `perf-hook.py --self-check` covers the new pre-tool paths: governor-gate deny on a lifecycle Skill invocation without the governor flag set, debug-gate arming on `squads:debug`, plan-schema deny on a `Write` to a malformed `docs/plan/*.plan.md`, and dirty/clean `dispatch-check` parity (the existing dispatch-check assertions are retained and still run). Clean up any flag files created under `${TMPDIR:-/tmp}` in the self-check.

#### REQ-007: /tmp probe-write audit (gating step)

Detail: From Git Bash on this win32 box, probe-write each candidate (`TMPDIR`, `TEMP`, `TMP`, `/tmp`) and record per-candidate writability plus the resolved path of the current `state_dir` resolution (`${TMPDIR:-/tmp}`) in the plan header. Outcome gates REQ-006/state_dir task: if the current resolution is writable, the hardening is dropped; if not, the cascade is implemented.