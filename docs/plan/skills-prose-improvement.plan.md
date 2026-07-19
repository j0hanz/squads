# skills-prose-improvement — Plan

Status: DRAFT
Depth: contract
Specs: docs/plan/skills-prose-improvement.specs.md
Source design: docs/design/2026-07-19-skills-prose-improvement-design.md

## Execution order

Risk-ordered, defect-class commits, one task = one bisectable commit. Same-file tasks serialize (reads-parallel/writes-serial); first parallel wave = TASK-001, 002, 004, 006, 007 (distinct files). Commit each task; do not combine.

## Tasks

### TASK-001: Trim parallel-debugging invariants block to reference + debugging-only additions

Depends on: none
Files: [skills/parallel-debugging/SKILL.md](skills/parallel-debugging/SKILL.md)
Symbols: [#invariants--apply-to-every-dispatch](skills/parallel-debugging/SKILL.md#invariants--apply-to-every-dispatch)
Satisfies: REQ-004
Action: Replace the restated invariants in the `## Invariants` block with a one-line reference to `../dispatch-agents/SKILL.md#invariants--apply-to-every-dispatch`. Keep only the two debugging-specific bullets (`No mocked investigators or skeptics`, `Bare-claim hypotheses to skeptics`) inline, verbatim. Do not delete `Reproduction shown, not asserted` from Step 1 (different section).
Validate: `grep -c "No mocked investigators" skills/parallel-debugging/SKILL.md` outputs `1` AND `grep -c "Bare-claim hypotheses" skills/parallel-debugging/SKILL.md` outputs `1` AND `awk '/^## Invariants/,/^## Step 0/' skills/parallel-debugging/SKILL.md | wc -l` is less than before the edit AND `bash -n hooks/dispatch-check.sh` exits 0.
Expected result: Invariants block shrinks; both debugging-specific additions present; hook script still parses.

### TASK-002: Merge tdd autonomous-invocation paragraphs to one + per-origin delta

Depends on: none
Files: [skills/tdd/SKILL.md](skills/tdd/SKILL.md)
Symbols: [#autonomous-invocation-approved-plan-handoff](skills/tdd/SKILL.md#autonomous-invocation-approved-plan-handoff)
Satisfies: REQ-004
Action: Collapse the `receive-plan`/`dispatch-agents` paragraph and the `parallel-debugging` paragraph under `## Autonomous invocation (approved-plan handoff)` into one shared-structure paragraph plus a one-line per-origin delta. Preserve every gate: skip Step 0, skip Pre-TDD `AskUserQuestion`, enter at RED, N-1 + Red Flags unchanged; for parallel-debugging handoff also skip Step 1 sub-step 2 (stub) and run repro against existing code.
Validate: `grep -c "receive-plan" skills/tdd/SKILL.md` ≥ 1 AND `grep -c "parallel-debugging" skills/tdd/SKILL.md` ≥ 1 AND `grep -c "Pre-TDD" skills/tdd/SKILL.md` ≥ 1 AND `grep -c "Step 1 sub-step 2" skills/tdd/SKILL.md` outputs `1` AND `grep -cE "N-1|Red Flags" skills/tdd/SKILL.md` ≥ 1.
Expected result: One heading, one merged paragraph; all three origins and every gate still named.

### TASK-003: Tighten tdd red-flags wording, preserve every signal line

Depends on: TASK-002
Files: [skills/tdd/SKILL.md](skills/tdd/SKILL.md)
Symbols: [#red-flags--stop-rationalizing-delete-and-restart](skills/tdd/SKILL.md#red-flags--stop-rationalizing-delete-and-restart)
Satisfies: REQ-005
Action: Compress verbose phrasing on each red-flag bullet. Do not delete, merge, or fold any signal into another. Each of the 7 existing flags stays its own bullet.
Validate: `awk '/^## Red Flags/,/^## Next Skills/' skills/tdd/SKILL.md | grep -cE '^- '` outputs `7` AND `grep -c "trivially passes" skills/tdd/SKILL.md` outputs `1` AND `grep -cE "tests-after|retrofitted" skills/tdd/SKILL.md` outputs `1` AND `grep -c "too simple to test" skills/tdd/SKILL.md` outputs `1` AND `grep -c "N-1 check because" skills/tdd/SKILL.md` outputs `1` AND `grep -c "GREEN that arrives on the first run" skills/tdd/SKILL.md` outputs `1`.
Expected result: 7 signal lines preserved; wording tighter.

### TASK-004: Convert parallel-brainstorming HARD-GATE block to `**HARD GATE:**` line

Depends on: none
Files: [skills/parallel-brainstorming/SKILL.md](skills/parallel-brainstorming/SKILL.md)
Symbols: none
Satisfies: REQ-001
Action: Replace the `<HARD-GATE>...</HARD-GATE>` block (top of body) with a top-of-body `**HARD GATE:**` line matching the parallel-debugging/tdd form. Content preserved: no code/plan proposal until Phase 6 brief from Phase 4 lock (+ Phase 5 `APPROVED` if it ran); sketch-in-doc still design work; bug-fix/typo/one-line exemption; ambiguous-request rule (treat as design, run Phase 1).
Validate: `grep -c "<HARD-GATE>" skills/parallel-brainstorming/SKILL.md` outputs `0` AND `grep -c "^\*\*HARD GATE:\*\*" skills/parallel-brainstorming/SKILL.md` outputs `1` AND `grep -c "Phase 6" skills/parallel-brainstorming/SKILL.md` ≥ 1 AND `grep -c "Phase 1" skills/parallel-brainstorming/SKILL.md` ≥ 1.
Expected result: One HARD GATE line; XML-block form gone; content intact.

### TASK-005: Add Phase-vs-Step documented-exception note to parallel-brainstorming

Depends on: TASK-004
Files: [skills/parallel-brainstorming/SKILL.md](skills/parallel-brainstorming/SKILL.md)
Symbols: [#process-flow](skills/parallel-brainstorming/SKILL.md#process-flow)
Satisfies: REQ-002
Action: Add a single one-line note at the top of `## Process Flow` explaining this skill uses `Phase 1-6` (cyclic ideation loop with checkpoint and REVISE loop) while other skills use linear `Step 0-5`. Do not renumber phases.
Validate: `grep -cE "Phase.*not Step|Phase.*cyclic|cyclic.*Phase" skills/parallel-brainstorming/SKILL.md` outputs `1` AND `grep -cE "^## Phase [1-6]" skills/parallel-brainstorming/SKILL.md` outputs `6`.
Expected result: Note present; six phase headings unchanged.

### TASK-006: Group request-code-review inline rules into Strict Rules (isolation guard)

Depends on: none
Files: [skills/request-code-review/SKILL.md](skills/request-code-review/SKILL.md)
Symbols: none
Satisfies: REQ-003, REQ-007
Action: Add a `## Strict Rules` section aggregating rules currently inline in Steps 1-3 (read-only/fresh-context reviewer, fill every `{{...}}` before dispatch, verbatim handoff, no direct fixes on FAIL, 2-pass cap depends on `Review pass: N`). ISOLATION GUARD: do not edit lines 34-52 (the `#### Dispatch prompt` fenced block containing `fresh-eyed reviewer`, `{{plan_summary}}`, `{{diff}}`, `<untrusted_context>`). Do not reword the dispatch prompt.
Validate: `grep -c "^## Strict Rules" skills/request-code-review/SKILL.md` outputs `1` AND `grep -c "fresh-eyed reviewer" skills/request-code-review/SKILL.md` outputs `1` AND `grep -c "{{plan_summary}}" skills/request-code-review/SKILL.md` outputs `1` AND `grep -c "{{diff}}" skills/request-code-review/SKILL.md` outputs `1` AND `git diff --unified=0 skills/request-code-review/SKILL.md | grep -E '^\+|^-' | grep -E 'fresh-eyed reviewer|\{\{plan_summary\}\}|\{\{diff\}\}|<untrusted_context>'` outputs nothing AND `bash -n hooks/dispatch-check.sh` exits 0.
Expected result: Strict Rules section present; dispatch template markers byte-identical; hook parses.

### TASK-007: Add Next Skills table to dispatch-agents

Depends on: none
Files: [skills/dispatch-agents/SKILL.md](skills/dispatch-agents/SKILL.md)
Symbols: none
Satisfies: REQ-003
Action: Append a `## Next Skills` table listing the sibling skills (`parallel-brainstorming`, `request-plan`, `receive-plan`, `tdd`, `parallel-debugging`, `request-code-review`, `receive-code-review`) with one-line use-cases, mirroring the table format in parallel-debugging/tdd. Do NOT add a duplicate `## Strict Rules` (the `## Invariants` block is the equivalent). Do NOT add `Reproduction shown, not asserted` (lives in parallel-debugging).
Validate: `grep -c "^## Next Skills" skills/dispatch-agents/SKILL.md` outputs `1` AND `grep -c "^## Strict Rules" skills/dispatch-agents/SKILL.md` outputs `0` AND `grep -oE '\]\(\.\./[^/]+/SKILL\.md\)' skills/dispatch-agents/SKILL.md | sed 's|](../||;s|/SKILL.md)||' | while read s; do test -f "skills/$s/SKILL.md" || echo "MISSING $s"; done` outputs nothing.
Expected result: Next Skills table present; every link target resolves; no duplicate Strict Rules.

### TASK-008: Tighten dispatch-agents exec/long-running prose

Depends on: TASK-007
Files: [skills/dispatch-agents/SKILL.md](skills/dispatch-agents/SKILL.md)
Symbols: [#executing-an-approved-plan](skills/dispatch-agents/SKILL.md#executing-an-approved-plan), [#long-running-builds](skills/dispatch-agents/SKILL.md#long-running-builds)
Satisfies: REQ-005
Action: Tighten wording in `## Executing an approved plan` and `## Long-running builds` only. No semantic change to: `Depends on:` order rule, `Files:` parallel-vs-serial rule, `Validate:` structured return, `Satisfies:` spec handoff, three-role orchestrator/worker/validator split.
Validate: `grep -c "Depends on:" skills/dispatch-agents/SKILL.md` unchanged from pre-edit count AND `grep -c "Validate:" skills/dispatch-agents/SKILL.md` unchanged AND `grep -cE "Orchestrator|Worker|Validator" skills/dispatch-agents/SKILL.md` ≥ 3 AND `git diff --stat -- skills/dispatch-agents/SKILL.md` confined to the two named sections on manual review.
Expected result: Tighter prose; all rule semantics preserved.

### TASK-009: Tighten parallel-debugging step prose, preserve gates

Depends on: TASK-001
Files: [skills/parallel-debugging/SKILL.md](skills/parallel-debugging/SKILL.md)
Symbols: none
Satisfies: REQ-005
Action: Tighten verbose wording in `## When NOT to use parallel-debugging`, `## First: do you need a fleet?`, and Step bodies 0-5. Preserve the `**HARD GATE:**` line, `Reproduction shown, not asserted` (Step 1), and every `**Done when:**` criterion verbatim in meaning. Excludes the Invariants block (TASK-001) and Strict Rules block.
Validate: `grep -c "HARD GATE" skills/parallel-debugging/SKILL.md` outputs `1` AND `grep -c "Reproduction shown, not asserted" skills/parallel-debugging/SKILL.md` outputs `1` AND `grep -cE "^\*\*Done when:\*\*" skills/parallel-debugging/SKILL.md` outputs `6` AND `bash -n hooks/dispatch-check.sh` exits 0.
Expected result: Tighter step prose; HARD GATE, reproduce-gate wording, and six Done-when criteria intact.

### TASK-010: Frontmatter description format-consistency audit

Depends on: TASK-003, TASK-005, TASK-008, TASK-009
Files: [skills/dispatch-agents/SKILL.md, skills/parallel-brainstorming/SKILL.md, skills/parallel-debugging/SKILL.md, skills/tdd/SKILL.md, skills/request-plan/SKILL.md, skills/receive-plan/SKILL.md, skills/request-code-review/SKILL.md, skills/receive-code-review/SKILL.md, skills/using-squads/SKILL.md](skills/dispatch-agents/SKILL.md)
Symbols: none
Satisfies: REQ-006
Action: Audit all 9 `description:` fields for format consistency (pattern: `Use when ...` plus `Prefer over ...` / `Not for ...`). If no format divergence, make no edit and record the no-op in the commit message. If a format divergence exists, apply a format-only edit only. Any semantic change is flagged for user sign-off, not done. using-squads' router-shaped description is an intentional exception, not edited.
Validate: `git diff --unified=0 'skills/*/SKILL.md' | grep -E '^[+-]description:'` is either empty (no-op) or touches only `description:` lines without changing trigger keywords (manual confirm).
Expected result: Descriptions audited; zero or format-only diffs; no semantic trigger-keyword change.