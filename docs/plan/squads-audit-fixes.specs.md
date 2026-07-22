Status: APPROVED
Depth: contract
Origin: plan

# squads-audit-fixes — specs

Source: `audit.md` (principle audit of `hooks/` + `skills/`, 2026-07-22). Scope is the 10 ranked findings plus housekeeping. No behavior outside `hooks/` and `skills/brainstorm/scripts/` changes.

## Requirements

#### REQ-001: A dispatch guard never blocks dispatch

Detail: `dispatch-check` MUST fail OPEN on every infrastructure failure — missing `jq`, unparseable payload, child timeout, wrapper crash — emitting a `[WARN]` line on stderr and exiting 0. Placeholder leakage degrades one subagent; a blocked dispatch removes the fleet. Only a positively-detected unresolved `{{...}}` may deny.

#### REQ-002: The dispatch seam asserts what is cheap and mechanical

Detail: `dispatch-check` MUST inspect `.tool_input.model` and warn (never deny) when a dispatched agent is not `haiku`, per the flat model policy in `skills/squads/SKILL.md:69`. Absent model param warns with the canonical `[WARN] model param unavailable` text so the flat-haiku cost model is never voided silently.

#### REQ-003: A gate that does not run says so

Detail: Any guard skipped, expired, or timed out MUST write one line to stderr naming itself and the reason. Covers the 120-minute debug-gate expiry, the missing-`jq` skip of the edit-path gates, and the `perf-hook.py` child-timeout fail-open. A JSONL record is not a signal; stderr is.

#### REQ-004: Subagent returns are shape-checked at the seam that sees them

Detail: `PostToolUse` MUST match `Agent` and verify the return carries the Handoff Contract's `status` and `findings` keys (`skills/squads/SKILL.md:43`). Feedback-only — stderr plus exit 2, never a deny; a malformed return is the model's to retry, not the hook's to block.

#### REQ-005: Observability is opt-in, not the default path

Detail: `hooks.json` MUST run the bare bash dispatcher by default and route through `perf-hook.py` only when `SQUADS_PERF=1`. The wrapper MUST shrink to the passthrough-and-log core; the report renderer moves out of the hot path or is deleted.

#### REQ-006: `dispatch-agents` documents only the work that runs there

Detail: The INLINE fleet-shape list and the Threshold Table rows unreachable under direct-route MUST be removed. No row may describe a dispatch the destination skill does not make (`tdd` dispatches zero agents; inline `debug` dispatches zero agents).

#### REQ-007: The Governor struct matches the decisions the Governor makes

Detail: Fields declared "guidance only, never runtime-enforced" MUST NOT be presented as Governor-set and final. Either the mode cutoff derives from a real task signal, or the struct shrinks to the fields actually decided.

#### REQ-008: Job size is enforced where the parser already runs

Detail: `plan_schema` MUST count comma-separated `Files:` entries per `### TASK-NNN:` block and deny above a stated ceiling, naming the task and the count. Field-label presence is not a size check; the granularity rule in `skills/dispatch-agents/SKILL.md:131` needs a mechanism on the path that writes plans.

#### REQ-009: `scan_context.py` reports what it dropped

Detail: `ScanResult` MUST carry a `truncated` mapping of `kept/total` for every capped field (`interface_shapes`, `constraints`, `unknowns`, `analogous_features`, `related_files`). Emitted in the JSON so the Context Report and its downstream Scope estimate never read a capped list as full coverage.

#### REQ-010: Housekeeping does not accumulate

Detail: Remove the unused `import os as _os`, stop swallowing logging exceptions without a trace, and cut the 8-second wall-clock timeout assertion from `--self-check` to a stubbed short timeout.

## Out of scope (deliberate, recorded)

- `dispatch_check` false-positive on a legitimate `{{ }}` template literal inside a `Workflow` `script` payload — REQ-001 makes the failure mode a warning, which removes the harm. No separate fix.
- `skills/review/SKILL.md:39` fixed 2 reviewers — defensible constant for a merge gate. No change.
- The hook layer's absence inside the native workflow runtime — a platform fact, already documented at `skills/dispatch-agents/SKILL.md:82`. Not fixable here.
