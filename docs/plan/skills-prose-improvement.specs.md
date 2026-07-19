# skills-prose-improvement — Specs

Status: DRAFT
Depth: contract
Source: docs/design/2026-07-19-skills-prose-improvement-design.md

## Scope

In-place rewrite of all 9 `skills/*/SKILL.md` for clarity, token efficiency, cross-skill consistency. No renames, no new files, no hook edits (hook touched only as `bash -n` sanity check). Defect-class commits, bisectable. Risk-ordered: highest-regression-risk edits first.

## Requirements

#### REQ-001: HARD GATE form unified

Detail: Every skill that declares a HARD GATE uses the `**HARD GATE:**` line form (matching parallel-debugging and tdd). parallel-brainstorming's `<HARD-GATE>...</HARD-GATE>` XML block is converted to that line form, content preserved. No skill uses the XML-block form after this work.

#### REQ-002: Phase-vs-Step is a documented exception, not a forced unify

Detail: parallel-brainstorming keeps `Phase 1-6` (cyclic ideation loop: 1→2→checkpoint→3→4→5→6 with a REVISE loop). All other skills keep `Step 0-5` / `Step 1-5` (linear execution). brainstorming gains a one-line note explaining why Phase, not Step. No phase/step renumbering anywhere.

#### REQ-003: Required sections present with documented exceptions

Detail: Every workflow skill exposes `Strict Rules` (or its equivalent `Invariants`) and `Next Skills`. Exceptions, not force-fills: dispatch-agents uses `Invariants` as its strict-rules equivalent (no duplicate `Strict Rules`); using-squads is a router preamble (exempt from both). dispatch-agents gains a `Next Skills` table (genuinely missing). request-code-review groups its inline rules under `Strict Rules`.

#### REQ-004: Duplicated invariant/rule statements trimmed, signals preserved

Detail: parallel-debugging's restated invariants block trims to a one-line reference to dispatch-agents invariants plus the two debugging-specific additions kept inline verbatim. tdd's two autonomous-invocation paragraphs merge into one shared-structure paragraph plus a one-line per-origin delta. No load-bearing signal (debugging-specific additions, the stub-skip delta, all gates) is deleted.

#### REQ-005: Verbose prose tightened without semantic change

Detail: Wording compressed in tdd red-flags, dispatch-agents `Executing an approved plan` / `Long-running builds`, and parallel-debugging step bodies. Every gate, `**Done when:**` criterion, and (for red-flags) every signal line is preserved. No new sections, no reordering.

#### REQ-006: Frontmatter descriptions audited, not semantically edited

Detail: All 9 `description:` fields audited for format consistency. No semantic edit. If a format divergence is found, a format-only edit is applied; any semantic change is flagged for user sign-off, not done. using-squads' router-shaped description is an intentional exception. If no divergence, the task is a no-op recorded in the commit message.

#### REQ-007: dispatch-check hook coupling preserved

Detail: request-code-review's dispatch template (the `fresh-eyed reviewer` marker, the `{{plan_summary}}` / `{{diff}}` placeholder syntax, the `<untrusted_context>` wrapper) is not edited. `hooks/dispatch-check.sh` is not edited. A wording change to the template would require a lockstep hook edit; that is out of scope unless a concrete template defect is identified (none is). `bash -n hooks/dispatch-check.sh` is run as a drift sanity check.