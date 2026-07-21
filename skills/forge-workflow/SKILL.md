---
name: forge-workflow
description: Use when a bulk or fan-out job is recurring or large enough to warrant a saved `/command` workflow, or when debug needs the debug-verify recipe. Not for one-off small fleets — dispatch-agents handles those inline.
argument-hint: '<feature description or recipe name>'
---

# forge-workflow

Forge make native dynamic workflow script from small canon of orchestration shapes and recipe catalog. Output is saved `.claude/workflows/<name>.js` plus `docs/workflows/CATALOG.md` entry. Plugin ship markdown only — forge make script at runtime; nothing generated ship with plugin.

## Generation Contract

Every generated script embed these six invariants. They mechanical, not prose — script code enforce them at runtime.

1. **Judge ≠ generator — separate `agent()` calls.** Per the [dispatch-agents Invariants](../dispatch-agents/SKILL.md#invariants--apply-to-every-dispatch): adjudicating and generating agents are two distinct `agent()` calls with isolated context, and in-thread "verification" rejected at audit.

2. **In-script bare-claim truncation between generator and skeptic.** Between generator stage and skeptic stage, script truncates each candidate claim to one-line bare form — `root cause is <X> at <file:line>, classified as <logic|design-level>` for debug-verify, or `<claim> at <file:line>, classified as <class>` elsewhere. Any claim lacking the `(file:line, classification)` tuple truncated or dropped before skeptic read it. Smuggling generator's reasoning into claim defeats judge ≠ generator while satisfying every literal rule; truncation in code, not in prompt, is enforcement.

3. **Each `agent()` call's `schema` mirrors the Handoff Contract fields.** Every `agent()` invocation declares a `schema` with exactly six keys of the [Handoff Contract](../dispatch-agents/SKILL.md#handoff-contract): `status/completed/skipped/findings/commands/artifacts`. FAIL rule for return missing `status` or `findings` defined at source — cite, don't duplicate. No ad-hoc return shapes.

4. **`args` parameterization with declared defaults.** Every workflow read `args` object at top and declares default for every field. Smoke-slice run same script with small `args`; production scale by overriding `args` only. No hardcoded counts, prompts, or paths in stage bodies — all parameterized.

5. **Model: `haiku`, per the [Model & fan-out policy](../dispatch-agents/SKILL.md#model--fan-out-policy).** Every stage's `agent()` sets `model: 'haiku'`; unavailable or omitted → inherit session model. No per-stage tier routing, no promote/demote. `CLAUDE_CODE_SUBAGENT_MODEL` still overrides all.

6. **Agent-count cap per recipe.** Each recipe archetype declare default agent scale in Recipe Catalog. Script computes total agent dispatches and aborts before exceeding cap, logging truncation — silent caps read as full coverage. Cap declared per archetype, not improvised per run.

## Pattern Canon

This single source for six orchestration shapes and unified quorum rule. dispatch-agents and debug cite these anchors; they do not duplicate.

Pick first fit; compose when task demands it.

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

Abstain counts as 0.5 refutation toward threshold. Finding not actively confirmed by at least one skeptic treated as unverified (PARTIAL, not PASS).

**Loop until done — absolute ceiling:** `ceil(N / 2)` total rounds where N = initial item count — no minimum floor. Stop on 2 consecutive empty rounds or diminishing-returns signal (3 rounds yielding only 1 new item). Log every round; silence ≠ convergence.

Canonical composition: **fan out → adversarially verify each finding → loop until 2 consecutive rounds find nothing new** (dedupe-empty). The adversarial-verify variant used by `debug-verify` instead stops on 2 consecutive **no-survivor** rounds (all claims refuted), since its hypotheses fixed at invocation. Dedupe against everything already seen (including rejected findings) by `file:line` between rounds, or it never converge. The `debug-verify` variant uses minimum floor of 4 — its 2-consecutive-no-survivor stop unreachable at ceil(N/2) < 2 (N ≤ 2), so floor makes stop condition fire.

Exploring _design approaches_ isn't a Generate & filter job — [brainstorm](../brainstorm/SKILL.md) governs there; ideation phases forbid subagents.

## Recipe Catalog

Each recipe map archetype to composition, default agent scale, `args` signature with defaults, and fetch-or-edit class. Generated workflow is fetch-class, edit-class, or read-only class. Fetch-class and edit-class mutually exclusive (never both); read-only class is neither — see below. Recipes duplicating lifecycle mandate (plan draft/validate, tdd RED-GREEN, review 2-pass) rejected at forge time.

| Recipe               | Composition                                                         | Default scale              | `args` signature                                      | Class     |
| -------------------- | ------------------------------------------------------------------- | -------------------------- | ----------------------------------------------------- | --------- |
| `fan-out-synthesize` | one investigator per chunk → barrier → synthesizer merges           | 10 investigators + 1 synth | `{chunks: [], merge_prompt, per_chunk_prompt?}`       | read-only |
| `adversarial-verify` | per finding: N skeptics → quorum tally                              | 2 skeptics per finding     | `{findings: [], skeptics_per_finding: 2, rubric}`     | read-only |
| `generate-filter`    | one generator overgenerates → one judge scores against rubric       | 1 generator + 1 judge      | `{prompt, count: 40, rubric}`                         | read-only |
| `tournament`         | pairwise fresh-context matches, bracket-style                       | 8 candidates               | `{candidates: [], criteria, bracket_size?}`           | read-only |
| `classify-act`       | classifier routes each item to its handler                          | 1 classifier + N handlers  | `{items: [], handlers: [], dedupe: true}`             | edit      |
| `loop-until-done`    | rounds of fan-out → dedupe by `file:line` → ceiling                 | 4 rounds, 5 agents/round   | `{seed, rubric, max_rounds?}`                         | read-only |
| `debug-verify`       | per-hyp investigators → bare-claim trunc → skeptics → quorum → loop | N hypotheses × 2 skeptics  | `{hypotheses: [], repro_cmd, failing_output, rubric}` | read-only |

**`debug-verify`** consumed by [debug](../debug/SKILL.md) at its Step 2 (invoke debug-verify): investigators spawn one per hypothesis (blind), script truncates each finding to `root cause is <X> at <file:line>, classified as <logic|design-level>` in code before skeptics read it, skeptics spawn with distinct refutation angles per claim, canonical quorum table tallies each round, loops dedupe by `(file:line, classification)`, stop on 2 consecutive no-survivor rounds or ceiling, and return round log + survivors + refutation trail in [Handoff Contract](../dispatch-agents/SKILL.md#handoff-contract) shape. It strictly read-only class — see below.

### Read-only class

Recipe is **read-only class** when no stage's `agent()` prompt permit file writes or edits, and no stage fetch external content. The `debug-verify` recipe is read-only class by definition: runtime agents run with `acceptEdits` and hooks do not fire inside runtime, so drifted generation that let agent edit code mid-debug would bypass debug-gate. Read-only class compensate: Script Audit Checklist's no-write clause verify every stage prompt deny write/edit tools before save, and `squads-hook.sh` `debug-gate` rule still block main-thread edits regardless. Read-only-class recipes safe to smoke-slice and re-run — bounded cost, no state mutation.

## Next Skills

| Skill                                          | Use Case                                                                 |
| :--------------------------------------------- | :----------------------------------------------------------------------- |
| [dispatch-agents](../dispatch-agents/SKILL.md) | Governor and one-off small fleets; cite this canon for shapes and quorum |
| [debug](../debug/SKILL.md)                     | Consumes the `debug-verify` recipe and the canonical quorum table        |

## Procedure

Forge run one session-scoped pass per workflow. Steps sequential; each gate next.

1. **Preflight** (once per session, see § Preflight below) — assert native dynamic workflows available; abort with clear message if not. No fallback.
2. **Interview** — elicit job shape from user: goal, input size, fetch vs. edit, recurrence. Match to Recipe Catalog archetype; if none fit, compose from Pattern Canon and say so. **Spec path:** when dispatch supply Composition Spec, forge recognize it, SKIP this Interview, and adopt Spec's `stages`/`class`/`budget_tokens`/`agent_cap` directly — it still run Script Audit (non-skippable, step 5) and smoke-slice (step 6).
3. **Recipe** — pick catalog row; carry its composition, default scale, `args` signature, and fetch-or-edit class forward. Reject at forge time any recipe that duplicate approved lifecycle mandate (plan draft/validate, tdd RED-GREEN, review 2-pass) — see § Script Audit Checklist.
4. **Native codegen** — emit `.claude/workflows/<name>.js` script that embed six Generation Contract invariants. Every stage distinct `agent()` call with Handoff-Contract `schema`; `args` with defaults at top; every stage's `model: 'haiku'` per [Model & fan-out policy](../dispatch-agents/SKILL.md#model--fan-out-policy); agent-count cap computed and asserted.
5. **Script Audit Checklist** — run checklist (see § Script Audit Checklist). HIGH items gate save; failed HIGH items block save.
6. **Smoke-slice run** — execute same script with small `args` slice. Failed smoke-slice block save. Re-run after fix; do not proceed until green. Auto-mode (spec path): failed smoke-slice retry once; second failure FAIL out to debug.
7. **Name check against the `/` command namespace** — before save, confirm `<name>` not collide with existing slash command (built-in or plugin). Collision → ask user rename (Auto-mode / spec path: auto-suffix instead, never block on prompt).
8. **Save ask-before-overwrite** — if `.claude/workflows/<name>.js` already exist, ask before overwrite; never overwrite silently (Auto-mode / spec path: auto-suffix instead, never overwrite).
9. **CATALOG.md append** — append row to `docs/workflows/CATALOG.md` (name, recipe, `args` signature, scale, fetch/edit class, last-verified date).

**First-use starters.** When session have no `docs/workflows/CATALOG.md` (or it empty), forge offer three starter workflows and compose one on pick: `debug-verify`, `fan-out-synthesize`, `adversarial-verify`. Each starter map 1:1 to its Recipe Catalog row; no improvisation. Skipped when Composition Spec supplied — Spec already define shape.

## Script Audit Checklist

Run before save. HIGH items gate save; failed HIGH item block save. Lower items warn and continue.

**HIGH — no-write clause grep (read-only class).** For every read-only-class recipe (incl. `debug-verify`), grep each `agent()` description string for write/edit verbs (`write`, `edit`, `create`, `modify`, `patch`, `overwrite`, `delete`, `remove`). Every investigator/agent description must explicitly deny write/edit — e.g. "You are read-only; do not write, edit, create, modify, or delete any file." Stage prompt silent on writes fail this check. Rationale: runtime agents run `acceptEdits` and hooks do not fire inside runtime; prompt denial only guard.

**HIGH — recipe-vs-script required-stage diff.** Diff declared stage list against stages present in generated script: Recipe Catalog composition column for recipe stacks; Composition Spec's `stages[]` for composed stacks with no Recipe Catalog row (**spec-vs-script** — same required-stage semantics). Every required stage must appear as distinct `agent()` call (or barrier). Dropped or merged stage fail this check — generation variance that drop required stage is top cause of bad workflows.

**Inline one-liners** (each must pass; each failure block save):

- **fetch-OR-edit mutual exclusion** — script is fetch-class OR edit-class, never both; grep `WebFetch`/`fetch` against `Edit`/`Write`/`NotebookEdit` across script; both sets non-empty fail.
- **`args` defaults present** — every field read in stage body have default declared at top `args` destructure; no undefined-arg paths.
- **agent-count cap respected** — total `agent()` dispatches ≤ recipe default scale; abort-before-exceed logic present and logs truncation.
- **smoke-slice ran** — smoke-slice run from step 6 produce green (PASS) Handoff Contract; attach its `status` to audit record.
- **ask-before-overwrite present** — save path confirm with user before overwriting existing `.claude/workflows/<name>.js`.
- **lifecycle-mandate rejection** — recipe duplicating one approved lifecycle mandate (plan draft/validate, tdd RED-GREEN, review 2-pass) rejected at forge time, not run time. Lifecycle mandates owned by `plan`, `tdd`, `review` respectively; forge refuse to generate workflow whose stage list reproduce any of them. Rationale: one owner per lifecycle phase; parallel workflow implementation would silently diverge from canonical mandate.

### Plant-breach drill

Runnable drill that exercise two HIGH items above. It plant two breach inputs in temp dir and assert checklist catch each: (1) write-breach investigator prompt (`agent()` description containing "write the fix") — no-write clause grep must flag it; (2) stage-omitted script (generated script missing required stage named in its recipe) — recipe-vs-script required-stage diff must flag it. See `references/plant-breach-drill.sh` (runs as-is).

## Annotated `debug-verify` example script

Reference-only — illustrative, not shipped artifact. See `references/debug-verify-example.js.md` for representative `debug-verify` workflow script with four required annotations (each stage, truncation point, quorum tally, stop condition) as inline comments.

## Preflight

Once per session, before any other Procedure step. Assert native dynamic workflows available; abort with clear message on failure; **no fallback**.

- **Check:** Claude Code version ≥ **2.1.154** AND paid plan AND dynamic workflows not disabled. Runtime is plugin-level hard dependency for bulk and debug fan-out.
- **On failure:** abort forge with clear message — "Native dynamic workflows unavailable (need CC ≥ 2.1.154, paid plan, not disabled). Cannot forge. No fallback." Do not silently degrade to turn-by-turn Agent dispatches; Procedure's invariants (in-script truncation, quorum tally, agent-count cap) unenforceable outside runtime.
- **No fallback:** this is user decision recorded in design brief — one execution path. Forge refuse to generate workflow it cannot smoke-slice in native runtime.
