---
name: parallel-brainstorming
description: Use when requirements are vague or the solution space is open before a plan exists. Prefer over request-plan when two or more distinct architectural approaches are in play.
argument-hint: '[feature request or problem to explore]'
---

# parallel-brainstorming

<HARD-GATE>
Don't propose code, file changes, or concrete implementation plan for new feature or ambiguous
request until Phase 6 produces a Design Brief for an approach the user locked in Phase 4 (and,
if Phase 5 ran, that Phase 5 marked `APPROVED`). Sketching approach in doc is still
design work — needs Phase 1 Discovery first. Doesn't apply to bug fixes, typos, one-line
config changes with no design space.
When in doubt whether the request is a bug fix or a feature, treat it as design work and run Phase 1 — the bug-fix exemption must not be used to skip Discovery.
</HARD-GATE>

## Process Flow

1 → (2 if ambiguous) → Creative Checkpoint → 3 → 4 → (5 if flagged: APPROVED → 6, REVISE → loop in 5, REJECT → 3 or stop) → 6

## Phase 1: Framing & Discovery

- **No Silent Skips:** If task needs zero discovery, name exact step skipped (Probe, Scan, or Understanding Lock) and explain why — never skip silently.
- **Probe:** Identify target users; ask clarifying questions if request ambiguous.
- **Scan:** Run `python ${CLAUDE_SKILL_DIR}/scripts/scan_context.py <noun1> <noun2> ... --cwd '<root>' | python ${CLAUDE_SKILL_DIR}/scripts/compress_report.py` (fallback to `Grep` if it fails).
- **Report:** Extract Related Files (with recent commits and test coverage), Interface Shapes, Design Docs, Analogous Features, Constraints, Scope (S/M/L/XL) with reasoning, and Unknowns.
- **Zero-Code Check:** Stop and offer exit if existing code/config already solves this.
- **Understanding Lock:** Summarize problem and understanding. Ask user (via `AskUserQuestion`) only if an Unknowns item blocks approach generation or Scope is L/XL; otherwise proceed to Creative Checkpoint.
- **Routing:**
  - Scope XL → offer to split into independent sub-features and re-run this skill per slice; if the user declines, set the Phase 5 flag and continue with the XL scope.
  - Ambiguous → Go to Phase 2.
  - Scope L/XL, or any scope with a hard non-functional constraint (security, data-loss, perf SLO) → Set Phase 5 Flag.

**Done when:** Context Report lists Related Files, Interface Shapes, Design Docs, Analogous Features, Constraints, Scope (S/M/L/XL), and Unknowns, and zero-code check answered.

## Phase 2: Clarification

- **Resolve with user:** clarify ambiguous terms via `AskUserQuestion`, max 4 questions total, 2-3 options each.
- **Glossary:** Save resolved definitions to `glossary.md` at the repository root (never `CONTEXT.md`).
- **Visuals:** Offer diagram only if layout or data flow requires it. Wait for reply.

**Done when:** ambiguous terms resolved with user and saved to `glossary.md`.

## Creative Checkpoint (Pre-Ideation)

- **Evaluate:** Look for 10x simpler or zero-code solution.
- **Seed:** If found, use as "Approach A" (Minimalist lane) in Phase 3.

**Done when:** 10x/zero-code candidate seeded as Approach A, or confirmed none exists and proceeding to Phase 3 unseeded.

## Phase 3: Multi-Lane Divergent Ideation

- **Single-Shot Generation:** Generate 2-3 distinct approaches in one response. **Don't spawn subagents.** Always include the Minimalist lens — it seeds Approach A in Phase 4; pick 1-2 additional lenses from the list.
- **Context:** Use feature description and Context Report to inform all perspectives.
- **Lenses (assign one per approach):**

1. _Conventional:_ Use existing codebase patterns.
2. _Radical:_ Best outcome, ignoring legacy constraints.
3. _Minimalist:_ Smallest working change (Seeded by Checkpoint).
4. _Constraint-First:_ Optimize for hardest non-functional constraint (e.g., speed, scale).
5. _Analogous:_ Copy and adapt similar existing feature.

- **Output (per approach):** Idea, core mechanism, winning factor, key risk, first step.

**Done when:** 2-3 distinct approaches generated in one response (one Minimalist), each with idea, core mechanism, winning factor, key risk, first step.

## Phase 4: Convergence & Synthesis

- **Synthesize:** Group similar ideas. Combine strong mechanisms with risk-mitigations from other lanes.
- **Distill:** Present 2-3 distinct approaches. Approach A must be Minimalist. For each: What, Gains, Costs, Fit, First Step.
- **Approval Lock:** Present 2-3 distilled approaches to user via `AskUserQuestion` to lock one — hard-to-reverse decision committing Phase 6's Design Brief. **Await decision. Don't guess.**
- **Routing:** If Phase 5 flag set → Phase 5. Otherwise → Phase 6.

**Done when:** user locks one of 2-3 distilled approaches (not guessed).

## Phase 5: Persona Critique

- **Trigger:** Phase 5 flag set, or user requested stress test.
- **Simulated Review:** Adopt 3 personas in thought process to evaluate chosen design:

1. _Skeptic:_ Finds edge cases and failure modes.
2. _Constraint Guardian:_ Enforces scale, performance, security rules.
3. _User Advocate:_ Evaluates usability and cognitive load.

- **Severity Rating:** High (Blocks deployment), Med (Worse outcome), Low (Minor). Ignore styling/naming.
- **Resolution:** Record objections. For all High/Med issues, must "Accept & Revise" or "Reject with technical rationale."
- **Self-Arbitration:** Resolve debates yourself. Mark design `APPROVED`, `REVISE`, or `REJECT`.
- **Routing:** `APPROVED` → Phase 6. `REVISE` → revise the design to resolve the objections, then re-run Self-Arbitration (loop until `APPROVED` or `REJECT`). `REJECT` → do not proceed to Phase 6; return to Phase 3 to generate a new approach, or if the whole direction is infeasible, stop and report to the user. Cap REVISE at 2 cycles; if the 3rd Self-Arbitration is still not `APPROVED`, treat it as `REJECT` (→ Phase 3 or stop and report to the user).

**Done when:** every High/Med objection is "Accept & Revise" or "Reject with technical rationale", design marked `APPROVED` (→ Phase 6) or `REJECT` (→ Phase 3 or stop) — `REVISE` is not terminal; it loops back through Self-Arbitration.

## Phase 6: Design Brief

- **Self-Review:** Fix contradictions or scope creep in chosen design before writing.
- **Format:** Write strict `markdown-kv` brief containing: Approach, Why, Scope, Constraints, Interface, Architecture, Risks, First Step.
- **Save:** Present in chat, then write to `docs/design/YYYY-MM-DD-<topic>-design.md`.
- **Commit Guard:** Don't commit as part of brainstorming. If user wants to commit (and optionally push / open PR), do it directly with git/gh once Design Brief approved.

**Done when:** markdown-kv Design Brief (Approach, Why, Scope, Constraints, Interface, Architecture, Risks, First Step) written to `docs/design/YYYY-MM-DD-<topic>-design.md`.

## Worked Example

Request: "add a way for users to save and re-run searches."

1. **Phase 1:** Scan finds existing `Filter` model and one-off "recent searches" list in `localStorage`. Scope: M. No flag (not high-risk, not L/XL).
2. **Creative Checkpoint:** Minimalist seed found — extend `Filter` with `name` + `saved: boolean` column instead of new table.
3. **Phase 3 (Multi-lane generation):** Conventional — new `SavedSearch` table + CRUD API, mirrors `Bookmark` feature. Minimalist — reuse `Filter` + 2 columns, no new endpoints (piggyback on existing filter-list endpoint). Constraint-First — same as Minimalist but adds per-user cap (20 saved searches) to bound query cost.
4. **Phase 4:** Synthesize 2 approaches — Approach A (Minimalist + cap, cheapest) and Approach B (Conventional, more flexible but new table + endpoints). User picks A. Not flagged → skip Phase 5.
5. **Phase 6:** Design Brief written to `docs/design/2026-06-29-saved-searches-design.md`: Approach (extend `Filter`), Why (reuses existing model, smallest diff), Scope (M), Constraints (cap 20/user), Interface (`Filter.saved`, `Filter.name`), Architecture (no new table), Risks (cap needs migration default), First Step (`ALTER TABLE filters ADD COLUMN saved boolean DEFAULT false`).
6. Commit Guard: user declines auto-commit → brief left in chat + on disk; handoff to `request-plan` to formalize tasks.

## Strict Rules

- **No Blended Ideation:** Keep Phase 3 perspectives distinct; don't bleed into each other until Phase 4 synthesis.
- **Never Ship Raw Ideas:** Phase 4 synthesis mandatory. Never present raw brainstormed ideas as final answer.
- **No Empty Rejections:** Require technical reason for any rejected High-severity issue during Phase 5 critique.
- **No Agent-tool subagents for Phase 3 or 5.**

## Next Skills

| Skill                                          | Use Case                                                               |
| :--------------------------------------------- | :--------------------------------------------------------------------- |
| [request-plan](../request-plan/SKILL.md)       | Formalize Design Brief into task plan when auto-commit declined        |
| [dispatch-agents](../dispatch-agents/SKILL.md) | Execute plan once request-plan formalizes and receive-plan APPROVES it |
