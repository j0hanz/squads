# routing-correctness — plan

Status: APPROVED
Depth: contract
Origin: plan
Notes: validate REVISE round 1 — M1 (TASK-001 REQ-001 split documented in Action: dispatch-agents side here, squads side in TASK-008), M2 (TASK-002 Validate + "all stated, never silent" surfacing grep), M3 (TASK-005 Validate + quadrant markers: rev-parse / both signals / AskUserQuestion / empty-arg default) accepted & revised; M4 (TASK-007 serial on TASK-006) rejected with rationale — same-file writes serial per Files-overlap rule, no worktree isolation in inline execution. Caveat: REQ-005 determinism gate load-bearing on TASK-009 read-only pass (covered in TASK-009 Action).

Source design brief: [docs/design/2026-07-21-routing-correctness-design.md](../design/2026-07-21-routing-correctness-design.md)

Canonical routing source = `skills/dispatch-agents/SKILL.md`. Edits there first, mirror in `skills/squads/SKILL.md` after. Same-file tasks are serial (overlapping `Files:`); cross-file tasks parallel where disjoint. All edits are markdown prose/table changes — no code, no runtime. `Validate:` commands are grep assertions confirming the new content is present (and old content gone where required). All paths workspace-relative from `C:\squads`. Markdown files have no code symbols; `Symbols:` cites the nearest heading anchor.

### TASK-001: Anchor guards + precedence line in dispatch-agents

Depends on: none
Files: [skills/dispatch-agents/SKILL.md](../../skills/dispatch-agents/SKILL.md)
Symbols: [governor-threshold-table](../../skills/dispatch-agents/SKILL.md#governor-threshold-table), [inline-branch-routing-table](../../skills/dispatch-agents/SKILL.md#inline-branch-routing-table)
Satisfies: REQ-001, REQ-002
Action: Insert `<!-- do not rename: skills link #governor-threshold-table -->` immediately above the `### Governor Threshold Table (first-match, decides mode)` heading, and `<!-- do not rename: skills link #inline-branch-routing-table -->` immediately above the `### INLINE branch — routing table` heading. Add a precedence sentence near the top of `## Step 0` (after the first paragraph): "dispatch-agents routing tables are canonical; the squads card mirrors — on mismatch, dispatch-agents wins." Do not alter any table rows in this task. REQ-001 requires the precedence line in BOTH files; this task adds the dispatch-agents side — the squads side is added in TASK-008.
Validate: `grep -q "do not rename: skills link #governor-threshold-table" skills/dispatch-agents/SKILL.md && grep -q "do not rename: skills link #inline-branch-routing-table" skills/dispatch-agents/SKILL.md && grep -q "routing tables are canonical; the squads card mirrors" skills/dispatch-agents/SKILL.md`
Expected result: All three greps match (exit 0); two guard comments sit directly above their headings; precedence sentence present in Step 0.

### TASK-002: Redefine bulk/forge routing in dispatch-agents

Depends on: TASK-001
Files: [skills/dispatch-agents/SKILL.md](../../skills/dispatch-agents/SKILL.md)
Symbols: [governor-threshold-table](../../skills/dispatch-agents/SKILL.md#governor-threshold-table), [inline-branch-routing-table](../../skills/dispatch-agents/SKILL.md#inline-branch-routing-table)
Satisfies: REQ-003
Action: In the Threshold Table, replace the bulk row with: "Bulk: recurring (any size) → composed/forge; one-off ≥ cutoff (currently 5) → composed; one-off < cutoff → inline fleet". In the inline routing table, replace the forge-workflow row's trigger from "Bulk independent items, whole-repo audit…" to "Recurring bulk (any size) → forge-workflow (saved /command workflow); one-off bulk below the cutoff (currently 5) routes inline here". Remove the sentence "bulk requests go composed, never to the inline forge row" from the note under the Threshold Table and replace with "recurring bulk and one-off bulk ≥ the cutoff go composed; one-off bulk below the cutoff routes inline — all stated, never silent." State the cutoff by name ("currently 5") everywhere it appears.
Validate: `grep -q "Recurring bulk" skills/dispatch-agents/SKILL.md && grep -q "one-off bulk below the cutoff" skills/dispatch-agents/SKILL.md && grep -q "all stated, never silent" skills/dispatch-agents/SKILL.md && ! grep -q "never to the inline forge row" skills/dispatch-agents/SKILL.md`
Expected result: Redefinition present; surfacing sentence present; contradictory note sentence removed; cutoff referenced by name.

### TASK-003: brainstorm/plan discriminator in dispatch-agents tables

Depends on: TASK-002
Files: [skills/dispatch-agents/SKILL.md](../../skills/dispatch-agents/SKILL.md)
Symbols: [governor-threshold-table](../../skills/dispatch-agents/SKILL.md#governor-threshold-table), [inline-branch-routing-table](../../skills/dispatch-agents/SKILL.md#inline-branch-routing-table)
Satisfies: REQ-004
Action: In the Threshold Table lifecycle row, replace "vague/≥2 approaches→brainstorm" with "problem-to-explore→brainstorm · named-deliverable→plan". In the inline routing table, replace the brainstorm row trigger "Vague requirements, open solution space, ≥2 distinct architectural approaches" with "Problem to explore, no deliverable shape yet" and the plan row trigger "Clear feature or change needing a plan or spec" with "Request names a deliverable artifact (plan/spec/doc for a named feature)". Keep the rest of both rows (fleet decisions, links) unchanged.
Validate: `grep -q "Problem to explore, no deliverable shape" skills/dispatch-agents/SKILL.md && grep -q "names a deliverable artifact" skills/dispatch-agents/SKILL.md && ! grep -q "≥2 distinct architectural approaches" skills/dispatch-agents/SKILL.md`
Expected result: New discriminator present in both tables; "≥2 distinct architectural approaches" no longer in dispatch-agents.

### TASK-004: Align brainstorm + plan skill descriptions to new discriminator

Depends on: TASK-003
Files: [skills/brainstorm/SKILL.md](../../skills/brainstorm/SKILL.md), [skills/plan/SKILL.md](../../skills/plan/SKILL.md)
Symbols: [brainstorm](../../skills/brainstorm/SKILL.md#brainstorm), [plan](../../skills/plan/SKILL.md#plan)
Satisfies: REQ-004
Action: Update `brainstorm` `description:` frontmatter to use "problem to explore, no deliverable shape yet" instead of "two or more distinct architectural approaches are in play". Update `plan` `description:` to say "named deliverable artifact (plan/spec/doc for a named feature)" instead of "Not when ≥2 architectural approaches are open — use brainstorm first" (keep a boundary pointer to brainstorm but phrased via the new discriminator: "Not when the request is a problem to explore with no deliverable shape — use brainstorm first"). In both files' bodies, replace any restatement of "≥2 approaches" with the deliverable-vs-explore wording. Leave the HARD GATE and process phases untouched.
Validate: `grep -q "no deliverable shape" skills/brainstorm/SKILL.md && grep -q "named deliverable artifact" skills/plan/SKILL.md && ! grep -q "≥2 architectural approaches" skills/brainstorm/SKILL.md && ! grep -q "≥2 architectural approaches" skills/plan/SKILL.md`
Expected result: Both descriptions use the new discriminator; old "≥2 approaches" wording gone from both files.

### TASK-005: review mode-inference deterministic discriminator

Depends on: none
Files: [skills/review/SKILL.md](../../skills/review/SKILL.md)
Symbols: [step-0-infer-mode](../../skills/review/SKILL.md#step-0-infer-mode)
Satisfies: REQ-005
Action: In `## Step 0: Infer Mode`, replace the single-token vs multi-token rule with a four-quadrant discriminator: (a) feedback prose or explicit `--resolve` arg → resolve mode; (b) a ref/path token — `git rev-parse --verify <arg>` succeeds, or arg is a branch/commit/PR# (`#NNN`, `PR NN`)/file path — → request mode; (c) both signals present → request wins; (d) neither signal → `AskUserQuestion`. Keep the uncommitted-working-tree default (empty arg → request mode) explicit. Remove the "single token (no whitespace)" / "multi-token or multi-line" phrasing.
Validate: `grep -q "git rev-parse --verify" skills/review/SKILL.md && grep -q "both signals" skills/review/SKILL.md && grep -q "AskUserQuestion" skills/review/SKILL.md && grep -q "empty arg → request mode" skills/review/SKILL.md && ! grep -q "single token (no whitespace)" skills/review/SKILL.md`
Expected result: New ref/path discriminator present with all four quadrants (ref/path, both→request, neither→AskUserQuestion) and empty-arg default; old token-count rule gone.

### TASK-006: debug composed-off degraded fallback branch

Depends on: none
Files: [skills/debug/SKILL.md](../../skills/debug/SKILL.md)
Symbols: [step-2-invoke-debug-verify](../../skills/debug/SKILL.md#step-2-invoke-debug-verify)
Satisfies: REQ-006
Action: In `## Step 2: Invoke debug-verify`, after the preflight note, add an explicit degraded branch: if preflight fails (native dynamic workflows unavailable), do NOT abort — fall back to single-thread inline reproduce + isolate: run Step 1 repro on the main thread, form ONE hypothesis from the repro/stack/callers, investigate it inline with the same structured return, then route the fix per Step 4 (logic → tdd, design-level → plan). State this is a degraded mode (no skeptic quorum, no in-script truncation guardrails) and that it is orthogonal to test-state classification. Keep the "no fallback" line but scope it to "no fallback to turn-by-turn Agent dispatch *for the debug-verify recipe*"; the inline single-thread path is the documented degraded mode.
Validate: `grep -q "degraded mode" skills/debug/SKILL.md && grep -q "single-thread inline reproduce" skills/debug/SKILL.md`
Expected result: Degraded branch present and scoped; orthogonality to test-state stated.

### TASK-007: GREEN-without-RED owner = tdd; narrow debug trigger

Depends on: TASK-006
Files: [skills/tdd/SKILL.md](../../skills/tdd/SKILL.md), [skills/debug/SKILL.md](../../skills/debug/SKILL.md)
Symbols: [red-flags--stop-rationalizing-delete-and-restart](../../skills/tdd/SKILL.md#red-flags--stop-rationalizing-delete-and-restart), [step-0-triage](../../skills/debug/SKILL.md#step-0-triage)
Satisfies: REQ-007
Action: In `tdd`, keep the existing "GREEN with no observed RED" red-flag text (it is the owner). Add one clarifying sentence: "GREEN-without-RED is a test-discipline failure (the test is wrong, not the code) — owned by tdd, not debug." In `debug`, narrow the trigger phrase "a test, Validate command, or runtime behavior fails unexpectedly" to "a test, Validate command, or runtime behavior goes RED unexpectedly (an actual failure, not a suspicious pass)" in `description:` frontmatter and the Step 0 triage/route-away list. Audit both files: remove or cross-reference any text implying debug owns a suspicious-PASS case; ensure the `debug` "When NOT to use debug" list points GREEN-without-RED to `tdd`. Update `tdd`/`debug` `## Next Skills` rows only if they currently misclaim the boundary. Serial on TASK-006 by the plan `Files:`-overlap rule (both edit `skills/debug/SKILL.md`); the touched sections are disjoint (Step 2 vs description + Step 0) but same-file parallel writes risk conflict without worktree isolation, and inline execution assumes serial — dependency retained.
Validate: `grep -q "owned by tdd, not debug" skills/tdd/SKILL.md && grep -q "goes RED unexpectedly" skills/debug/SKILL.md && grep -q "GREEN-without-RED" skills/debug/SKILL.md`
Expected result: tdd owns the case explicitly; debug trigger narrowed to actual RED; debug file cross-references GREEN-without-RED to tdd.

### TASK-008: squads card restated mirror

Depends on: TASK-001, TASK-002, TASK-003
Files: [skills/squads/SKILL.md](../../skills/squads/SKILL.md)
Symbols: [route](../../skills/squads/SKILL.md#route)
Satisfies: REQ-001, REQ-003, REQ-004, REQ-008
Action: In `## Route`, add the precedence line (REQ-001 wording, same as dispatch-agents). Mirror the redefined bulk/forge routing (recurring → forge, one-off ≥ cutoff → composed, one-off < cutoff → inline; cutoff "currently 5") in the dispatch-agents route row. Mirror the brainstorm/plan discriminator in the brainstorm and plan route rows (problem-to-explore → brainstorm; named-deliverable → plan). Keep the pipeline-order line and the `## Contracts` table unchanged. Keep the table restated (do NOT replace rows with anchor citations). Mirror rows must match the canonical `dispatch-agents` table cell-for-cell.
Validate: `grep -q "routing tables are canonical; the squads card mirrors" skills/squads/SKILL.md && grep -q "Recurring bulk" skills/squads/SKILL.md && grep -q "named deliverable" skills/squads/SKILL.md && grep -q "Pipeline:" skills/squads/SKILL.md`
Expected result: Precedence line + redefined bulk/forge + brainstorm/plan discriminator mirrored; pipeline-order line and Contracts table retained; table restated, not cited.

### TASK-009: Cross-file verification — mirror matches canonical, no orphans, links resolve

Depends on: TASK-004, TASK-005, TASK-007, TASK-008
Files: [skills/dispatch-agents/SKILL.md](../../skills/dispatch-agents/SKILL.md), [skills/squads/SKILL.md](../../skills/squads/SKILL.md), [skills/brainstorm/SKILL.md](../../skills/brainstorm/SKILL.md), [skills/plan/SKILL.md](../../skills/plan/SKILL.md), [skills/review/SKILL.md](../../skills/review/SKILL.md), [skills/debug/SKILL.md](../../skills/debug/SKILL.md), [skills/tdd/SKILL.md](../../skills/tdd/SKILL.md), [skills/forge-workflow/SKILL.md](../../skills/forge-workflow/SKILL.md)
Symbols: [route](../../skills/squads/SKILL.md#route), [governor-threshold-table](../../skills/dispatch-agents/SKILL.md#governor-threshold-table)
Satisfies: REQ-001, REQ-002, REQ-003, REQ-004, REQ-005, REQ-006, REQ-007, REQ-008
Action: Read-only verification across all 8 skills. Confirm: (1) precedence line identical in dispatch-agents and squads; (2) both anchor guard comments present in dispatch-agents; (3) bulk/forge rows in dispatch-agents and squads match cell-for-cell and the cutoff is "currently 5" in both; (4) no "≥2 architectural approaches" / "≥2 distinct architectural approaches" remains in any routing table or skill description; (5) review Step 0 has no token-count rule and has the 4-quadrant discriminator; (6) debug has the degraded branch and a narrowed "RED unexpectedly" trigger; (7) tdd owns GREEN-without-RED and debug cross-references it to tdd; (8) squads Route table is restated (rows present, not replaced by citations), pipeline-order line + Contracts table retained; (9) every `../<skill>/SKILL.md#anchor` link in the touched files resolves (anchor heading exists). Report any mismatch as a finding with file:line.
Validate: `bash -c 'set -e; test "$(grep -c "routing tables are canonical; the squads card mirrors" skills/dispatch-agents/SKILL.md)" -ge 1; test "$(grep -c "routing tables are canonical; the squads card mirrors" skills/squads/SKILL.md)" -ge 1; grep -q "do not rename: skills link #governor-threshold-table" skills/dispatch-agents/SKILL.md; grep -q "do not rename: skills link #inline-branch-routing-table" skills/dispatch-agents/SKILL.md; ! grep -rq "≥2 architectural approaches" skills/; grep -q "git rev-parse --verify" skills/review/SKILL.md; grep -q "degraded mode" skills/debug/SKILL.md; grep -q "owned by tdd, not debug" skills/tdd/SKILL.md; echo OK'`
Expected result: Script prints `OK` (exit 0); all assertions hold; every cited anchor resolves.