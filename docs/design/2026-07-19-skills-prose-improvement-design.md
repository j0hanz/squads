# Skills Prose Improvement — Design Brief

- **Approach:** In-place per-skill rewrite of all 9 `skills/*/SKILL.md`. Unify what is genuinely uniform, document exceptions, fill true section gaps, tighten verbose prose. No new files, no indirection, no skill renames.
- **Why:** Chosen over a shared `CONVENTIONS.md` (Approach A) because skills load one SKILL.md at a time when model-invoked — linking out for invariants drops behavior from context. Chosen over Approach C because a non-normative index file rots if nobody audits it. B keeps every skill self-contained (load-safe) and fixes clarity, token efficiency, and cross-skill consistency by direct edit.
- **Scope:** L. 9 prose files, `skills/*/SKILL.md` only. No renames, no hook edits except as a lockstep pair with the request-code-review template, no `AGENTS.md`/`README.md`/`hooks/` prose changes unless a consistency edit requires it (call out explicitly if so).
- **Constraints:**
  - **No skill renames** — `hooks.json`/`dispatch-check` parse skill names/paths; renaming breaks sessions. Out of scope.
  - **Frontmatter `description` edits = format/consistency only.** Descriptions drive model auto-trigger routing; a semantic rewrite could silently stop a skill firing. Any non-format description change flagged for user sign-off, or skipped.
  - **dispatch-check hook coupling.** `hooks/dispatch-check.sh` keys its re-review cap on the literal `fresh-eyed reviewer` marker in request-code-review's embedded dispatch prompt, and scans for `{{...}}` placeholders + bare `diff --git` outside `<untrusted_context>`. Editing the request-code-review template (lines 36-52) must preserve: (a) the `fresh-eyed reviewer` string, (b) `{{plan_summary}}`/`{{diff}}` placeholder syntax, (c) the `<untrusted_context>` wrapper around `{{diff}}`. If any must change, update `dispatch-check.sh` in the same commit.
  - **`<squads-router>`/`<system-reminder` sentinels** must not appear in any SKILL.md prose that could flow into a dispatch prompt — dispatch-check denies them. None currently do; don't introduce.
- **Interface:** unchanged. All 9 skills keep their frontmatter shape (`name`, `description`, `argument-hint`) and markdown body. Relative `Next Skills` link paths stay valid.
- **Architecture:** flat, one file per skill, no new shared file. Canonical-wording rules below are applied in place across all 9; drift prevented by uniformity in this pass, not by indirection.

### Canonical-wording rules (applied across all 9)

1. **HARD GATE form:** unify to `**HARD GATE:**` (matches parallel-debugging, tdd). brainstorming's `<HARD-GATE>` block becomes a `**HARD GATE:**` line at top — same content, one form everywhere.
2. **Phase vs Step — documented exception, NOT a forced unify.** brainstorming keeps `Phase 1-6` (cyclic ideation loop: `1→2→checkpoint→3→4→5→6`). All others keep `Step 0-5`/`Step 1-5` (linear execution). Add a one-line note to brainstorming explaining why Phase, not Step.
3. **Required sections — with exceptions.** Target: every skill has `Strict Rules` (or equivalent `Invariants`) and `Next Skills`. Exceptions documented, not force-filled:
   - dispatch-agents: `Invariants` block IS its strict-rules equivalent — do NOT add a duplicate `Strict Rules`. DO add a `Next Skills` table (genuinely missing).
   - using-squads: 10-line router preamble — no `Strict Rules`/`Next Skills`; document as intentional (router, not a workflow skill).
   - request-code-review: add `Strict Rules` if its rules aren't already grouped; it has rules inline in steps — group them only if clarity gains, else leave.
4. **Dedup by trimming, not linking.** parallel-debugging's restated invariants block (lines 30-36) trims to a one-line reference to dispatch-agents invariants + keeps only the two debugging-specific additions (no mocked investigators; bare-claim hypotheses). Keeps load-safety: the reference is a pointer, the additions stay inline. Same for "Reproduction shown, not asserted" — keep in parallel-debugging Step 1 (it's the reproduce gate's wording), don't delete; but don't restate in dispatch-agents.
5. **tdd red-flags list — compress wording, preserve every signal as a distinct line.** No line deleted; verbose phrasing tightened.
6. **tdd autonomous-invocation paragraph — dedup.** The receive-plan-handoff and parallel-debugging-handoff paragraphs share structure; merge to one paragraph + a one-line per-origin delta, keeping all gates.

### Defect-class ordering (one commit per class, bisectable)

1. HARD GATE form unification (brainstorming `<HARD-GATE>` → `**HARD GATE:**`).
2. Phase-vs-Step documented exception note (brainstorming only).
3. Section gaps: `Next Skills` added to dispatch-agents; `Strict Rules` grouped where missing and clarity gains.
4. Dedup trims: parallel-debugging invariants block; tdd autonomous-invocation paragraph.
5. Verbose-prose tightening: tdd red-flags (wording only), dispatch-agents exec/long-running sections, parallel-debugging steps.
6. Frontmatter description format/consistency pass only (skip unless inconsistency demands).

- **Risks:**
  - _Description edits break auto-trigger_ — mitigated by format-only scope + sign-off gate.
  - _Trimming deletes a load-bearing signal_ — mitigated by preserve-every-line rule for tdd red-flags; dedup is wording, not deletion of invariant statements (debugging-specific additions stay inline).
  - _Large diff hard to review_ — mitigated by defect-class commit ordering; each commit uniform and small.
  - _Drift returns after this pass_ — accepted trade-off vs Approach A's load-context risk; documented exceptions + canonical-wording rules above are the reference for future edits.
- **First Step:** Commit class 1 — convert brainstorming's `<HARD-GATE>...</HARD-GATE>` block (lines 9-12) to a top-of-body `**HARD GATE:**` line matching the parallel-debugging/tdd form, same content. Verify the skill still reads correctly, then proceed to class 2.
