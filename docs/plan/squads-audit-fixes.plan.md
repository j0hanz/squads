Status: APPROVED
Depth: contract
Origin: plan
Review pass: 1

# squads-audit-fixes — plan

Executes the 10 findings in `audit.md`. Specs: `docs/plan/squads-audit-fixes.specs.md`.

Two disjoint file lanes run in parallel from the start: the `squads-hook.sh` chain (TASK-001 → 003 → 004 → 005 → 010) and the `perf-hook.py` chain (TASK-002 → 007). `skills/` doc tasks and `scan_context.py` are independent of both. `hooks.json` is touched by TASK-005 and TASK-006 — serialized.

Verification stays inside each task's own lane. Lane-A tasks assert against the dispatcher directly (`printf '<payload>' | bash hooks/squads-hook.sh <rule>`) rather than extending `perf-hook.py --self-check` — an assertion added there would make lane A write into lane B's file and serialize the whole plan. Lane B keeps `--self-check`, which it owns.

REVISE round 1 applied (3 chunk critics, 7 deduped Meds, 0 Highs): `Validate:` rewritten for TASK-003/004/005/010 to drop the cross-lane write; TASK-009 `Validate:` tightened from presence to placement. Two Dependency-Order Meds rejected — TASK-004 and TASK-005 both write `hooks/squads-hook.sh`, and overlapping `Files:` is serial by contract (`skills/dispatch-agents/SKILL.md:112`), not over-serialization.

## Ordering

```
lane A (hooks/squads-hook.sh):  001 → 003 → 004 → 005 → 010
lane B (hooks/perf-hook.py):    002 → 007
lane C (skills/dispatch-agents): 008 → 009 → 011
lane D (scan_context):           012
join:                            005 → 006 → 013
```

---

### TASK-001: dispatch-check fails open when jq is missing

Depends on: none
Files: hooks/squads-hook.sh
Symbols: dispatch_check
Satisfies: REQ-001
Action: Replace the `command -v jq >/dev/null 2>&1 || deny dispatch-check "jq not found..."` line with a fail-open path that writes `[WARN] squads dispatch-check: jq not found — placeholder hygiene unverified, dispatch allowed. Install jq.` to stderr and exits 0. Apply the same inversion to the two remaining `deny dispatch-check` calls for an unparseable payload and a misordered `<untrusted_context>` block: warn and exit 0, never deny. The single surviving deny is the positive placeholder match.
Validate: `bash -n hooks/squads-hook.sh && printf '{"tool_name":"Agent","tool_input":{"prompt":"do it"}}' | PATH=/usr/bin bash hooks/squads-hook.sh dispatch-check; echo "exit=$?"`
Expected result: `bash -n` clean; exit 0 on a clean payload; a payload with `{{x}}` still exits 2 naming the placeholder.

### TASK-002: perf wrapper fails open and announces every gate it did not run

Depends on: none
Files: hooks/perf-hook.py
Symbols: run_rule, main
Satisfies: REQ-001, REQ-003
Action: In `run_rule`'s `TimeoutExpired` branch, drop the `dispatch-check` fail-closed special case — every rule returns exit 0 — and set `err` to `[WARN] squads <rule>: guard timed out after <n>s, gate not applied.` so the timeout reaches stderr instead of only the JSONL record. In the `__main__` exception handler, replace the `dispatch-check` exit-2 branch with the same warn-and-exit-0 shape. Update the module docstring, which currently documents dispatch-check as the one fail-CLOSED guard.
Validate: `python hooks/perf-hook.py --self-check`
Expected result: `self-check OK`; the timeout assertion (currently expecting `code == 2`) is updated in the same edit to expect exit 0 with a `[WARN]` stderr line.

### TASK-003: skipped and expired gates announce themselves

Depends on: TASK-001
Files: hooks/squads-hook.sh
Symbols: debug_gate, pre_tool
Satisfies: REQ-003
Action: In `debug_gate`, print `squads debug-gate: flag expired (>120min) — gate lifted; re-invoke squads:debug if still mid-debug.` to stderr immediately before `rm -f "$flag"`. In `pre_tool`, replace the bare `command -v jq >/dev/null 2>&1 || exit 0` with a warn-then-exit-0 that names both skipped gates: `squads pre-tool: jq not found — debug-gate and plan-schema not applied.` Both stay exit 0.
Validate: `bash -n hooks/squads-hook.sh && f="${TMPDIR:-/tmp}/squads-debug-gate-vt3"; touch -d '3 hours ago' "$f"; printf '{"tool_name":"Write","tool_input":{"file_path":"src/x.go"},"session_id":"vt3"}' | bash hooks/squads-hook.sh pre-tool; echo "exit=$?"; rm -f "$f"`
Expected result: `bash -n` clean; `exit=0` with the expiry line on stderr — the edit is allowed and announced, not denied and not silent.

### TASK-004: dispatch-check warns on non-haiku model

Depends on: TASK-003
Files: hooks/squads-hook.sh
Symbols: dispatch_check
Satisfies: REQ-002
Action: Extend the jq extraction in `dispatch_check` to read `.tool_input.model` alongside the nine body fields it already reads, keeping it out of the placeholder-linted body string. Emit `[WARN] squads dispatch-check: model '<m>' is not haiku — flat-haiku cost model void (skills/squads/SKILL.md:69).` on stderr when the field is present and not `haiku`, and the canonical `[WARN] model param unavailable — agents inherit session model; flat-haiku cost model void` when absent. Warn only; the exit code is unchanged by this check.
Validate: `bash -n hooks/squads-hook.sh && for m in '"model":"haiku",' '"model":"opus",' ''; do printf '{"tool_name":"Agent","tool_input":{%s"prompt":"go"}}' "$m" | bash hooks/squads-hook.sh dispatch-check; echo "exit=$?"; done`
Expected result: three `exit=0`; haiku silent, opus warns `is not haiku` on stderr, absent model emits the canonical `model param unavailable` warning.

### TASK-005: PostToolUse shape-checks subagent returns

Depends on: TASK-004
Files: hooks/squads-hook.sh, hooks/hooks.json
Symbols: post_tool, PostToolUse.matcher
Satisfies: REQ-004
Action: Add `Agent` to the `PostToolUse` matcher in `hooks.json`. In `post_tool`, add an `Agent` case that reads `.tool_response` and checks for the Handoff Contract keys `status` and `findings`; missing either writes `squads handoff: return missing <keys> — discard and retry once per skills/squads/SKILL.md:43.` to stderr and exits 2 (feedback-only, matching the existing plan-schema post-tool path). Non-JSON or absent `tool_response` exits 0 silently — a free-text return is not a contract violation the hook can prove.
Validate: `bash -n hooks/squads-hook.sh && for r in '{"status":"PASS","findings":[]}' '{"status":"PASS"}' '"just text"'; do printf '{"tool_name":"Agent","tool_response":%s}' "$r" | bash hooks/squads-hook.sh post-tool; echo "exit=$?"; done`
Expected result: `exit=0` silent for both keys present; `exit=2` naming `findings` for the second; `exit=0` silent for the plain string.

### TASK-006: perf wrapper becomes opt-in

Depends on: TASK-005
Files: hooks/hooks.json
Symbols: SessionStart, PreToolUse, PostToolUse, PreCompact
Satisfies: REQ-005
Action: Invert all five command strings: run `bash squads-hook.sh <rule>` unconditionally unless `SQUADS_PERF=1`, in which case route through `perf-hook.py <rule>` with the existing python/python3 probe. Delete the `SQUADS_FAST` branch — the fast path is now the default and needs no flag.
Validate: `npm run format:check && printf '{"source":"startup"}' | bash hooks/squads-hook.sh session-start | head -1`
Expected result: format check passes; the session-start arm still emits the Skill-tool naming line, proving the default path runs the bare dispatcher.

### TASK-007: cut the perf wrapper to passthrough-and-log

Depends on: TASK-002
Files: hooks/perf-hook.py
Symbols: report, load_records, durations, pct, gate_of, self_check
Satisfies: REQ-005, REQ-010
Action: Delete the `report` renderer and its helpers (`report`, `load_records`, `durations`, `pct`, `gate_of`) and the `report` argv branch — reading a JSONL log is `jq`'s job, not a shipped 200-line renderer. Remove the unused `import os as _os`. Replace the 8-second sleep stub in `self_check` with a stub that exceeds a locally-lowered timeout so the assertion costs under a second. Give the `with suppress(Exception)` around logging a one-line stderr note on failure so the observability path cannot degrade unobserved.
Validate: `ruff check . && python hooks/perf-hook.py --self-check`
Expected result: `ruff` clean, `self-check OK`, file under 400 lines, and `--self-check` wall-clock under 10s.

### TASK-008: delete the dead INLINE fleet-shape list

Depends on: none
Files: skills/dispatch-agents/SKILL.md
Symbols: #inline-branch--fleet-shapes, #governor-threshold-table
Satisfies: REQ-006
Action: Remove the entire `### INLINE branch — fleet shapes` section, including the `tdd` row (describes a dispatch `tdd` never makes) and the `debug` row (describes composed shape while `debug/SKILL.md:56` forbids the Agent-dispatch fallback). Remove the Threshold Table rows `Lifecycle match (per <squads-router>)` and `Trivial: single file · one edit · typo · ≤ 1 item` — both unreachable under direct-route, and the hand-off instruction at line 13 already covers a lifecycle task that lands here. Keep the mode-picking rows and the paragraph stating the cutoffs.
Validate: `grep -c "INLINE branch\|Lifecycle match\|Trivial: single file" skills/dispatch-agents/SKILL.md; grep -rn "#inline-branch" skills/ | wc -l`
Expected result: first count 0; second count 0 (no surviving link to the removed anchor anywhere under `skills/`).

### TASK-009: shrink the Governor struct to its real decisions

Depends on: TASK-008
Files: skills/dispatch-agents/SKILL.md
Symbols: #governor-output-struct
Satisfies: REQ-007
Action: Reduce the Governor output struct from seven fields to `{mode, class, reason}` — the three it actually decides. Move `budget_tokens`, `agent_cap`, and `success_criteria` into the Composition Spec only, where forge consumes them, and keep the existing "guidance only, never runtime-enforced" sentence attached to them there. Drop `route` and `shape` from the struct; `route` is the router's output and `shape` is the Composition Spec's `stages`.
Validate: `awk '/^### Governor output struct/,/^### Composition Spec/' skills/dispatch-agents/SKILL.md | grep -c "budget_tokens\|agent_cap\|route:\|shape:"; awk '/^### Composition Spec/,0' skills/dispatch-agents/SKILL.md | grep -c "budget_tokens\|agent_cap"`
Expected result: first count `0` (none of the four survive in the Governor struct section); second count `2` or more (both fields live in the Composition Spec section).

### TASK-010: plan-schema enforces a Files: ceiling

Depends on: TASK-005
Files: hooks/squads-hook.sh
Symbols: plan_schema_violations
Satisfies: REQ-008
Action: In the existing awk pass, when a line starts with `Files:`, count comma-separated entries for the current `TASK-NNN`. After the block ends, emit a violation when the count exceeds 3, formatted `TASK-NNN: Files: lists N paths (max 3) — decompose per the granularity rule.` Reuses the block-tracking the awk already does; no second parser.
Validate: `bash -n hooks/squads-hook.sh && for f in 'a.go, b.go, c.go, d.go' 'a.go'; do printf '{"tool_name":"Write","tool_input":{"file_path":"docs/plan/t.plan.md","content":"Origin: plan\n### TASK-001: x\nDepends on: none\nFiles: %s\nSymbols: s\nSatisfies: REQ-001\nAction: do\nValidate: t\nExpected result: ok\n"}}' "$f" | bash hooks/squads-hook.sh pre-tool; echo "exit=$?"; done`
Expected result: first iteration `exit=2` with stderr naming `TASK-001` and the count 4; second iteration `exit=0` silent.

### TASK-011: state the Files: ceiling in the granularity rule

Depends on: TASK-009, TASK-010
Files: skills/dispatch-agents/SKILL.md
Symbols: #execution-recipe-one-small-task-per-agent
Satisfies: REQ-008
Action: Amend the Granularity rule so the prose names the enforced number rather than an adjective: haiku-sized means at most 3 files in `Files:`, one behavior, a runnable `Validate:` — and note that `plan-schema` denies a plan Write above the ceiling. Add the same ceiling to the Scope-Risk lens row in `skills/plan/SKILL.md` only if the existing ">3 files" wording there disagrees; it currently matches, so expect no edit to that file.
Validate: `grep -n "3 files\|max 3" skills/dispatch-agents/SKILL.md skills/plan/SKILL.md`
Expected result: `dispatch-agents` granularity rule names the 3-file ceiling and the enforcing hook; `plan/SKILL.md:135` unchanged.

### TASK-012: scan_context reports what it dropped

Depends on: none
Files: skills/brainstorm/scripts/scan_context.py, skills/brainstorm/scripts/tests/test_scan_context.py
Symbols: ScanResult, scan
Satisfies: REQ-009
Action: Add a `truncated: dict[str, str]` field to `ScanResult`, populated at the cap sites with `"kept/total"` for `related_files`, `interface_shapes`, `constraints`, `unknowns`, and `analogous_features` — record the pre-slice length before each cap and omit entries where nothing was dropped. Add one test asserting a scan that overflows a cap reports the correct `kept/total` and that an under-cap scan reports no entry for that field.
Validate: `python -m pytest && ruff check .`
Expected result: suite green, ruff clean, and `python skills/brainstorm/scripts/scan_context.py <noun> --cwd .` emits a `truncated` key whenever a cap bites.

### TASK-013: README matches the new hook contract

Depends on: TASK-006, TASK-001
Files: README.md
Symbols: Install, Usage
Satisfies: REQ-001, REQ-005
Action: Rewrite the `jq` sentence — it currently states `dispatch-check fails closed without it`, which TASK-001 reverses. State that every gate now fails open with a warning and that `jq` is recommended, not required. Replace the `SQUADS_FAST` mention with `SQUADS_PERF=1` opt-in, and drop the claim that a command-hook timeout is an unfixable fail-open residual — TASK-002 makes it a warned fail-open.
Validate: `grep -n "fails closed\|SQUADS_FAST" README.md`
Expected result: no matches.

## Done when

Every task's `Validate:` exits 0 in dependency order. `python hooks/perf-hook.py --self-check`, `python -m pytest`, `ruff check .`, and `npm run format:check` all pass on the final tree.

## Validation record

- **Step 2 (ideator fan-out) skipped, not silent** — `audit.md` is a locked design with a prescribed fix per finding; plan Step 0 rule 2 sequences inline from a locked design.
- **Step 7 (inline traceability)** — 6/6 categories passed before any critic dispatch.
- **Step 8 round 1** — 3 chunk critics (contract depth, C = ceil(13/5) = 3), fresh + read-only + haiku, one message. Returned 0 High, 7 deduped Med. REVISE.
- **Step 9 round 1 verdict** — REVISE. Med count `7 >= max(2, ceil(3/2))`, and TASK-004/TASK-005 each drew 2 Meds citing the same task.
- **Step 8 re-validation round** — 2 lens critics, not 3: Spec-Correctness had zero prior findings, and dispatching it would have been a fresh sweep, which the re-validation rule forbids. Scope-Risk 5/5 RESOLVED, Dependency Order 2/2 RESOLVED, zero volunteered findings.
- **Step 9 final verdict** — APPROVED. No unresolved prior High or Med, no new High.
- **Rejected findings, recorded** — two Dependency-Order Meds claiming TASK-004/TASK-005 were over-serialized. Both write `hooks/squads-hook.sh`; overlapping `Files:` is serial by contract (`skills/dispatch-agents/SKILL.md:112`). The re-validation critic confirmed the rejection and found the second finding's premise ("completely different files") factually wrong.
- **REVISE round 1, applied** — `Validate:` rewritten for TASK-003/004/005/010 to remove the cross-lane write into `hooks/perf-hook.py`; TASK-009 `Validate:` tightened from presence to placement.
