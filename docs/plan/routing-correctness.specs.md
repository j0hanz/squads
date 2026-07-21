# routing-correctness — specs

Status: APPROVED
Depth: contract
Origin: plan

## Requirements

#### REQ-001: Canonical routing source + precedence

Detail: `dispatch-agents` is the canonical routing source. A precedence line stating "dispatch-agents routing tables are canonical; the squads card mirrors — on mismatch, dispatch-agents wins" appears in BOTH `skills/dispatch-agents/SKILL.md` and `skills/squads/SKILL.md`.

#### REQ-002: Routing anchor guards

Detail: `<!-- do not rename: skills link #governor-threshold-table -->` and `<!-- do not rename: skills link #inline-branch-routing-table -->` guard comments are placed above the corresponding headings in `skills/dispatch-agents/SKILL.md`, extending the existing contract-anchor guard convention to routing anchors.

#### REQ-003: Bulk/forge routing redefined

Detail: Bulk routing is redefined to remove the threshold-note vs inline-forge-row contradiction: recurring bulk (any size) routes to `forge-workflow`; one-off bulk ≥ the cutoff routes composed; one-off bulk below the cutoff routes inline fleet. The cutoff is referenced by name ("currently 5"), not hardcoded as a magic number. The below-cutoff inline path is surfaced (stated), not silent. No row in the inline routing table contradicts the Threshold Table bulk rule.

#### REQ-004: brainstorm/plan boundary discriminator

Detail: The brainstorm/plan boundary is a concrete classify-time discriminator: plan when the request names a deliverable artifact (plan/spec/doc for a named feature); brainstorm when the request names a problem to explore with no deliverable shape. The phrase "≥2 architectural approaches" (unknowable at classify time) is removed from the dispatch-agents routing tables and from the `brainstorm` and `plan` skill `description:` frontmatter / body text that restates the boundary.

#### REQ-005: review mode-inference deterministic

Detail: `skills/review/SKILL.md` Step 0 mode inference no longer uses token count. New discriminator: feedback prose or explicit `--resolve` → resolve mode; a ref/path token (`git rev-parse`-verifiable, branch, commit, PR#, file path) → request mode; both signals present → request wins; neither signal → `AskUserQuestion`. This fixes the "review PR #123" multi-token misroute.

#### REQ-006: debug composed-off fallback

Detail: `skills/debug/SKILL.md` Step 2 has an explicit degraded branch: when native dynamic workflows are unavailable (preflight fail), debug falls back to single-thread inline reproduce + isolate (Step 1 repro, one-hypothesis inline investigation) instead of the `debug-verify` recipe; states it is a degraded mode; routes the fix the same way (logic → tdd, design-level → plan). This fallback is orthogonal to test-state (REQ-007) — runtime availability vs test-state are disjoint axes.

#### REQ-007: GREEN-without-RED owner

Detail: The GREEN-without-RED case has a single owner: `tdd` (a test-discipline failure, not a code bug). `tdd` keeps "GREEN with no observed RED → re-enter at RED." `debug`'s "test fails unexpectedly" trigger is narrowed to "test RED unexpectedly" (an actual failure, not a suspicious pass). Both files' triggers and cross-references are audited so no trigger is orphaned and the two skills no longer claim the same input.

#### REQ-008: squads card restated mirror

Detail: `skills/squads/SKILL.md` Route table remains a restated mirror (NOT cite-only) so a model can route from the 40-line card alone. It mirrors the redefined bulk/forge row (REQ-003) and the brainstorm/plan discriminator (REQ-004), carries the precedence line (REQ-001), and retains the pipeline-order line and the Contracts table. Mirror rows match the canonical `dispatch-agents` table cell-for-cell.