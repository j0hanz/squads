---
name: forge-workflow
description: Use when a bulk or fan-out job is recurring or big enough to warrant a saved `/command` workflow, or when debug needs the debug-verify recipe. Not for one-off small fleets — use dispatch-agents.
argument-hint: '<feature description or recipe name>'
---

# forge-workflow

Forge generates native dynamic workflow scripts from a small canon of orchestration shapes and a recipe catalog. Output: `.claude/workflows/<name>.js` plus a `docs/workflows/CATALOG.md` entry. Plugin ships markdown only — forge generates scripts at runtime; nothing generated ships with the plugin.

## Generation Contract

Every generated script embeds these six invariants — mechanical, enforced by script code at runtime, not prose.

1. **Judge ≠ generator — separate `agent()` calls.** Per [dispatch-agents Invariants](../dispatch-agents/SKILL.md#invariants--apply-to-every-dispatch): adjudicating and generating agents are distinct `agent()` calls with isolated context; in-thread "verification" is rejected at audit.

2. **In-script bare-claim truncation between generator and skeptic.** The script truncates each candidate claim to one-line bare form — `root cause is <X> at <file:line>, classified as <logic|design-level>` for debug-verify, `<claim> at <file:line>, classified as <class>` elsewhere. Claims lacking the `(file:line, classification)` tuple are dropped before skeptics read them. Truncation in code, not prompt, is the enforcement — smuggled generator reasoning defeats judge ≠ generator while satisfying every literal rule.

3. **Each `agent()` call's `schema` mirrors the Handoff Contract.** Every `agent()` declares a `schema` with exactly the six [Handoff Contract](../dispatch-agents/SKILL.md#handoff-contract) keys: `status/completed/skipped/findings/commands/artifacts`. The missing-`status`/`findings` FAIL rule is defined at source — cite, don't duplicate. No ad-hoc return shapes.

4. **`args` parameterization with declared defaults.** Every workflow reads `args` at top and declares a default for every field. Smoke-slice runs the same script with small `args`; production scales by overriding `args` only. No hardcoded counts, prompts, or paths in stage bodies.

5. **Model: `haiku`, per the [Model & fan-out policy](../dispatch-agents/SKILL.md#model--fan-out-policy).** Every stage sets `model: 'haiku'`; unavailable → inherit session model. No per-stage tier routing, no promote/demote. `CLAUDE_CODE_SUBAGENT_MODEL` still overrides all.

6. **Agent-count cap per recipe.** Each recipe archetype declares its default agent scale in the Recipe Catalog. The script computes total dispatches and aborts before exceeding the cap, logging the truncation — silent caps read as full coverage. Cap declared per archetype, never improvised per run.

## Pattern Canon

Single source for the six orchestration shapes and the unified quorum rule. dispatch-agents and debug cite these anchors; they do not duplicate.

Pick the first fit; compose when the task demands it.

| Pattern                  | Shape                                                                                                                                        | Use when                                                    |
| ------------------------ | -------------------------------------------------------------------------------------------------------------------------------------------- | ----------------------------------------------------------- |
| **Fan out & synthesize** | One agent per independent chunk → barrier → merge with provenance                                                                            | Research, audits, due diligence, per-file/per-folder sweeps |
| **Adversarial verify**   | 2+ fresh skeptics per finding, prompted to _refute_ it; quorum table below determines outcome                                                | Any finding or claim about to be acted on or shipped        |
| **Generate & filter**    | One agent overgenerates beyond the obvious — typically 10-20 for naming, 40+ only for bulk title sets → separate judge scores against rubric | Taste bottlenecks: names, titles, bulk candidate sets       |
| **Tournament**           | Pairwise fresh-context matches, winners advance bracket-style                                                                                | Ranking large sets without one bloated, biased context      |
| **Classify & act**       | Classifier routes each item to its handler; dedupe before acting                                                                             | Mixed-type inboxes, triage, heterogeneous queues            |
| **Loop until done**      | Keep dispatching rounds until condition holds — stop on 2 consecutive empty rounds OR absolute ceiling (see below)                           | Flaky bugs, unknown-size discovery                          |

**Adversarial verify — quorum table:**

| Skeptics | Finding dies when | Tie-break     |
| -------- | ----------------- | ------------- |
| 2        | ≥ 1 refutes       | Add 1 skeptic |
| 3        | ≥ 2 refute        | N/A           |
| 4+       | > 50% refute      | N/A           |

Abstain counts as 0.5 refutation. A finding not actively confirmed by at least one skeptic is unverified (PARTIAL, not PASS).

**Loop until done — absolute ceiling:** `ceil(N / 2)` total rounds, N = initial item count, no minimum floor. Stop on 2 consecutive empty rounds or diminishing returns (3 rounds yielding only 1 new item). Log every round; silence ≠ convergence.

Canonical composition: **fan out → adversarially verify each finding → loop until 2 consecutive rounds find nothing new** (dedupe-empty). The `debug-verify` variant instead stops on 2 consecutive **no-survivor** rounds (all claims refuted) — its hypotheses are fixed at invocation — and uses a minimum floor of 4, since its stop is unreachable at ceil(N/2) < 2. Dedupe against everything already seen (including rejected findings) by `file:line` between rounds, or it never converges.

Exploring _design approaches_ is not a Generate & filter job — [brainstorm](../brainstorm/SKILL.md) governs there; ideation phases forbid subagents.

## Recipe Catalog

Each recipe maps an archetype to composition, default agent scale, `args` signature with defaults, and class. A generated workflow is fetch-class, edit-class, or read-only class; fetch and edit are mutually exclusive, read-only is neither. Recipes duplicating a lifecycle mandate (plan draft/validate, tdd RED-GREEN, review 2-pass) are rejected at forge time.

| Recipe               | Composition                                                         | Default scale              | `args` signature                                      | Class     |
| -------------------- | ------------------------------------------------------------------- | -------------------------- | ----------------------------------------------------- | --------- |
| `fan-out-synthesize` | one investigator per chunk → barrier → synthesizer merges           | 10 investigators + 1 synth | `{chunks: [], merge_prompt, per_chunk_prompt?}`       | read-only |
| `adversarial-verify` | per finding: N skeptics → quorum tally                              | 2 skeptics per finding     | `{findings: [], skeptics_per_finding: 2, rubric}`     | read-only |
| `generate-filter`    | one generator overgenerates → one judge scores against rubric       | 1 generator + 1 judge      | `{prompt, count: 40, rubric}`                         | read-only |
| `tournament`         | pairwise fresh-context matches, bracket-style                       | 8 candidates               | `{candidates: [], criteria, bracket_size?}`           | read-only |
| `classify-act`       | classifier routes each item to its handler                          | 1 classifier + N handlers  | `{items: [], handlers: [], dedupe: true}`             | edit      |
| `loop-until-done`    | rounds of fan-out → dedupe by `file:line` → ceiling                 | 4 rounds, 5 agents/round   | `{seed, rubric, max_rounds?}`                         | read-only |
| `debug-verify`       | per-hyp investigators → bare-claim trunc → skeptics → quorum → loop | N hypotheses × 2 skeptics  | `{hypotheses: [], repro_cmd, failing_output, rubric}` | read-only |

**`debug-verify`** is consumed by [debug](../debug/SKILL.md) Step 2: one blind investigator per hypothesis; in-code truncation to `root cause is <X> at <file:line>, classified as <logic|design-level>` before skeptics read; skeptics with distinct refutation angles per claim; canonical quorum per round; `(file:line, classification)` dedupe across rounds; stop on 2 consecutive no-survivor rounds or ceiling; returns round log + survivors + refutation trail in [Handoff Contract](../dispatch-agents/SKILL.md#handoff-contract) shape. Strictly read-only class — see below.

### Read-only class

A recipe is **read-only class** when no stage's `agent()` prompt permits file writes/edits and no stage fetches external content. `debug-verify` is read-only by definition: runtime agents run `acceptEdits` and hooks do not fire inside the runtime, so a drifted generation letting agents edit mid-debug would bypass debug-gate. Compensation: the Script Audit Checklist's no-write clause verifies every stage prompt denies write/edit tools before save, and the `squads-hook.sh` `pre-tool` rule (whose `debug_gate` function implements the debug HARD GATE) still blocks main-thread edits regardless. Read-only recipes are safe to smoke-slice and re-run — bounded cost, no state mutation.

## Procedure

One session-scoped pass per workflow. Steps sequential; each gates the next.

1. **Preflight** (once per session, see §Preflight) — assert native dynamic workflows available; abort with clear message if not. No fallback.
2. **Interview** — elicit job shape: goal, input size, fetch vs. edit, recurrence. Match to a Recipe Catalog archetype; none fit → compose from Pattern Canon and say so. **Spec path:** when dispatch supplies a Composition Spec, SKIP the interview and adopt the Spec's `stages`/`class`/`budget_tokens`/`agent_cap` directly — Script Audit (step 5) and smoke-slice (step 6) still run, non-skippable.
3. **Recipe** — pick the catalog row; carry its composition, default scale, `args` signature, and class forward. Reject any recipe duplicating a lifecycle mandate (see §Script Audit Checklist).
4. **Native codegen** — emit `.claude/workflows/<name>.js` embedding all six Generation Contract invariants: distinct `agent()` per stage with Handoff-Contract `schema`, `args` defaults at top, `model: 'haiku'` per stage, agent-count cap computed and asserted.
5. **Script Audit Checklist** — run it (§Script Audit Checklist). Failed HIGH items block save.
6. **Smoke-slice run** — execute the same script with a small `args` slice. Failure blocks save; fix and re-run until green. Auto-mode (spec path): retry once; second failure FAILs out to debug.
7. **Name check against the `/` command namespace** — before save, confirm `<name>` doesn't collide with an existing slash command (built-in or plugin). Collision → ask user to rename (auto-mode: auto-suffix, never block on prompt).
8. **Save ask-before-overwrite** — `.claude/workflows/<name>.js` exists → ask before overwrite; never overwrite silently (auto-mode: auto-suffix).
9. **CATALOG.md append** — add row to `docs/workflows/CATALOG.md`: name, recipe, `args` signature, scale, class, last-verified date.

**First-use starters.** No `docs/workflows/CATALOG.md` (or empty) → offer three starters and compose one on pick: `debug-verify`, `fan-out-synthesize`, `adversarial-verify`. Each maps 1:1 to its catalog row; no improvisation. Skipped when a Composition Spec is supplied.

## Script Audit Checklist

Run before save. Failed HIGH items block save; lower items warn and continue.

**HIGH — no-write clause grep (read-only class).** For every read-only-class recipe (incl. `debug-verify`), grep each `agent()` description string for write/edit verbs (`write`, `edit`, `create`, `modify`, `patch`, `overwrite`, `delete`, `remove`). Every agent description must explicitly deny write/edit — e.g. "You are read-only; do not write, edit, create, modify, or delete any file." A stage prompt silent on writes fails. Runtime agents run `acceptEdits` and hooks don't fire inside the runtime — prompt denial is the only guard.

**HIGH — recipe-vs-script required-stage diff.** Diff the declared stage list against stages present in the generated script: Recipe Catalog composition column for recipe stacks; Composition Spec `stages[]` for composed stacks with no catalog row (same semantics). Every required stage must appear as a distinct `agent()` call (or barrier). Dropped or merged stages fail — generation variance dropping a required stage is the top cause of bad workflows.

**Inline one-liners** (each failure blocks save):

- **fetch-OR-edit mutual exclusion** — grep `WebFetch`/`fetch` against `Edit`/`Write`/`NotebookEdit` across the script; both sets non-empty fails.
- **`args` defaults present** — every field read in a stage body has a default in the top `args` destructure; no undefined-arg paths.
- **agent-count cap respected** — total `agent()` dispatches ≤ recipe default scale; abort-before-exceed logic present and logs truncation.
- **smoke-slice ran** — step 6 produced a green (PASS) Handoff Contract; attach its `status` to the audit record.
- **ask-before-overwrite present** — save path confirms with user before overwriting an existing `.claude/workflows/<name>.js`.
- **lifecycle-mandate rejection** — recipes duplicating plan draft/validate, tdd RED-GREEN, or review 2-pass are rejected at forge time, not run time. One owner per lifecycle phase (`plan`, `tdd`, `review`); a parallel implementation would silently diverge from the canonical mandate.

### Plant-breach drill

Runnable drill exercising both HIGH items: plants two breach inputs in a temp dir and asserts the checklist catches each — (1) a write-breach investigator prompt (`agent()` description containing "write the fix") caught by the no-write grep; (2) a stage-omitted script caught by the required-stage diff. Run `references/plant-breach-drill.sh` as-is.

## Annotated `debug-verify` example script

Reference-only, not a shipped artifact. See `references/debug-verify-example.js.md` — representative script with four required inline annotations: each stage, truncation point, quorum tally, stop condition.

## Preflight

Once per session, before any other Procedure step.

- **Check:** Claude Code version ≥ **2.1.154** AND paid plan AND dynamic workflows not disabled. Runtime is a plugin-level hard dependency for bulk and debug fan-out.
- **On failure:** abort with "Native dynamic workflows unavailable (need CC ≥ 2.1.154, paid plan, not disabled). Cannot forge. No fallback."
- **No fallback:** user decision recorded in the design brief — one execution path. Never degrade to turn-by-turn Agent dispatches; the invariants (in-script truncation, quorum tally, agent-count cap) are unenforceable outside the runtime. Forge refuses to generate a workflow it cannot smoke-slice natively.

## Next Skills

| Skill                                          | Use Case                                                                 |
| :--------------------------------------------- | :----------------------------------------------------------------------- |
| [dispatch-agents](../dispatch-agents/SKILL.md) | Governor and one-off small fleets; cite this canon for shapes and quorum |
| [debug](../debug/SKILL.md)                     | Consumes the `debug-verify` recipe and the canonical quorum table        |
