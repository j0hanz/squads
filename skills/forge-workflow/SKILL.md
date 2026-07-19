---
name: forge-workflow
description: Compose and generate native dynamic workflow scripts for bulk multi-agent orchestration — fan-out audits, adversarial verify, generate-and-filter, tournament, classify-and-act, loop-until-done, and debug-verify. Use when a bulk or fan-out job is recurring or large enough to warrant a saved `/command` workflow, or when parallel-debugging needs the debug-verify recipe. Not for one-off small fleets — dispatch-agents handles those inline.
argument-hint: '<feature description or recipe name>'
---

# forge-workflow

Forge composes native dynamic workflow scripts from a small canon of orchestration shapes and a recipe catalog. Output is a saved `.claude/workflows/<name>.js` plus a `docs/workflows/CATALOG.md` entry. The plugin ships markdown only — forge generates scripts at runtime; nothing generated is shipped with the plugin.

Three core sections define the contract every generated script must satisfy, the canon of shapes (single source, cited by other skills), and the recipe catalog that maps an archetype to a composition.

## Generation Contract

Every generated script embeds these six invariants. They are mechanical, not prose — the script code enforces them at runtime.

1. **Judge ≠ generator — separate agent() calls.** The agent that adjudicates (skeptic, judge, validator) and the agent that generated the work under review are two distinct `agent()` calls with isolated context. The generating agent's reasoning never flows into the adjudicating agent's prompt — only the bare output does. In-thread "verification" of a generated artifact is self-review, not verification, and is rejected at audit.

2. **In-script bare-claim truncation between generator and skeptic.** Between the generator stage and the skeptic stage, the script truncates each candidate claim to a one-line bare form — `root cause is <X> at <file:line>, classified as <logic|design-level>` for debug-verify, or `<claim> at <file:line>, classified as <class>` elsewhere. Any claim lacking the `(file:line, classification)` tuple is truncated or dropped before the skeptic reads it. Smuggling the generator's reasoning into the claim defeats judge ≠ generator while satisfying every literal rule; truncation in code, not in prompt, is the enforcement.

3. **Each `agent()` call's `schema` mirrors the Handoff Contract fields.** Every `agent()` invocation declares a `schema` with exactly the six keys of the [Handoff Contract](../dispatch-agents/SKILL.md#handoff-contract): `status/completed/skipped/findings/commands/artifacts`. A return missing `status` or `findings` is treated as FAIL — discard, retry once, then route to parallel-debugging. No ad-hoc return shapes.

4. **`args` parameterization with declared defaults.** Every workflow reads an `args` object at the top and declares a default for every field. Smoke-slice runs the same script with a small `args`; production scales by overriding `args` only. No hardcoded counts, prompts, or paths in stage bodies — all parameterized.

5. **Stage→model routing per the role→tier table.** Each stage's `agent()` `model` param is set per the [Model tier](../dispatch-agents/SKILL.md#model-tier) role→tier map in dispatch-agents (cheap → `haiku`, strong → `sonnet`, strongest → `opus`, unknown → omit and inherit). `CLAUDE_CODE_SUBAGENT_MODEL` overrides all. The script comments each stage with its role and tier; degraded-state policy (promote/demote with logging) is applied inline.

6. **Agent-count cap per recipe.** Each recipe archetype declares a default agent scale in the Recipe Catalog. The script computes total agent dispatches and aborts before exceeding the cap, logging the truncation — silent caps read as full coverage. Cap is declared per archetype, not improvised per run.

## Pattern Canon

This is the single source for the six orchestration shapes and the unified quorum rule. dispatch-agents and parallel-debugging cite these anchors; they do not duplicate.

Pick first fit; compose when the task demands it.

| Pattern                  | Shape                                                                                                              | Use when                                                    |
| ------------------------ | ------------------------------------------------------------------------------------------------------------------ | ----------------------------------------------------------- |
| **Fan out & synthesize** | One agent per independent chunk → barrier → merge with provenance                                                  | Research, audits, due diligence, per-file/per-folder sweeps |
| **Adversarial verify**   | 2+ fresh skeptics per finding, prompted to _refute_ it; quorum table below determines outcome                      | Any finding or claim about to be acted on or shipped        |
| **Generate & filter**    | One agent overgenerates (40+, not 5) → separate judge scores against rubric                                        | Taste bottlenecks: names, titles, bulk candidate sets       |
| **Tournament**           | Pairwise fresh-context matches, winners advance bracket-style                                                      | Ranking large sets without one bloated, biased context      |
| **Classify & act**       | Cheap classifier routes each item to its handler; dedupe before acting                                             | Mixed-type inboxes, triage, heterogeneous queues            |
| **Loop until done**      | Keep dispatching rounds until condition holds — stop on 2 consecutive empty rounds OR absolute ceiling (see below) | Flaky bugs, unknown-size discovery                          |

**Adversarial verify — quorum table:**

| Skeptics | Finding dies when | Tie-break     |
| -------- | ----------------- | ------------- |
| 2        | ≥ 1 refutes       | Add 1 skeptic |
| 3        | ≥ 2 refute        | N/A           |
| 4+       | > 50% refute      | N/A           |

Abstain counts as 0.5 refutation toward threshold. A finding not actively confirmed by at least one skeptic is treated as unverified (PARTIAL, not PASS).

**Loop until done — absolute ceiling:** `ceil(N / 2)` total rounds where N = initial item count, minimum 4. Additionally: if 3 consecutive rounds each yield only 1 new item, stop (diminishing-returns signal). Log every round; silence ≠ convergence.

Canonical composition: **fan out → adversarially verify each finding → loop until 2 consecutive rounds find nothing new**. Dedupe against everything already seen (including rejected findings) by `file:line` between rounds, or it never converges.

Exploring _design approaches_ isn't a Generate & filter job — [parallel-brainstorming](../parallel-brainstorming/SKILL.md) governs there; ideation phases forbid subagents.

## Recipe Catalog

Each recipe maps an archetype to a composition, a default agent scale, an `args` signature with defaults, and a fetch-or-edit class. A generated workflow is either fetch-class (agents may fetch external content, wrapped in `<untrusted_context>`) OR edit-class (agents may edit files), never both. Read-only class (below) is neither. Recipes duplicating a lifecycle mandate (plan draft/validate, tdd RED-GREEN, review 2-pass) are rejected at forge time.

| Recipe               | Composition                                                         | Default scale              | `args` signature                                      | Class     |
| -------------------- | ------------------------------------------------------------------- | -------------------------- | ----------------------------------------------------- | --------- |
| `fan-out-synthesize` | one investigator per chunk → barrier → synthesizer merges           | 10 investigators + 1 synth | `{chunks: [], merge_prompt, per_chunk_prompt?}`       | read-only |
| `adversarial-verify` | per finding: N skeptics → quorum tally                              | 2 skeptics per finding     | `{findings: [], skeptics_per_finding: 2, rubric}`     | read-only |
| `generate-filter`    | one generator overgenerates → one judge scores against rubric       | 1 generator + 1 judge      | `{prompt, count: 40, rubric}`                         | read-only |
| `tournament`         | pairwise fresh-context matches, bracket-style                       | 8 candidates               | `{candidates: [], criteria, bracket_size?}`           | read-only |
| `classify-act`       | cheap classifier routes each item to its handler                    | 1 classifier + N handlers  | `{items: [], handlers: [], dedupe: true}`             | edit      |
| `loop-until-done`    | rounds of fan-out → dedupe by `file:line` → ceiling                 | 4 rounds, 5 agents/round   | `{seed, rubric, max_rounds?}`                         | read-only |
| `debug-verify`       | per-hyp investigators → bare-claim trunc → skeptics → quorum → loop | N hypotheses × 2 skeptics  | `{hypotheses: [], repro_cmd, failing_output, rubric}` | read-only |

**`debug-verify`** is consumed by [parallel-debugging](../parallel-debugging/SKILL.md) for the Steps 2–3 collapse (slice 3 of the workflow-generation design): investigators spawn one per hypothesis (blind), the script truncates each finding to `root cause is <X> at <file:line>, classified as <logic|design-level>` in code before skeptics read it, skeptics spawn with distinct refutation angles per claim, the canonical quorum table tallies each round, loops dedupe by `(file:line, classification)`, stop on 2 consecutive no-survivor rounds or the ceiling, and return round log + survivors + refutation trail in [Handoff Contract](../dispatch-agents/SKILL.md#handoff-contract) shape. It is strictly read-only class — see below.

### Read-only class

A recipe is **read-only class** when no stage's `agent()` prompt permits file writes or edits, and no stage fetches external content. The `debug-verify` recipe is read-only class by definition: runtime agents run with `acceptEdits` and hooks do not fire inside the runtime, so a drifted generation that let an agent edit code mid-debug would bypass the debug-gate. The read-only class compensates: script audit (TASK-002) verifies every stage prompt denies write/edit tools before save, and `debug-gate.sh` still blocks main-thread edits regardless. Read-only-class recipes are safe to smoke-slice and re-run — bounded cost, no state mutation.

## Next Skills

| Skill                                                | Use Case                                                                |
| :--------------------------------------------------- | :---------------------------------------------------------------------- |
| [dispatch-agents](../dispatch-agents/SKILL.md)       | Triage and one-off small fleets; cites this canon for shapes and quorum |
| [parallel-debugging](../parallel-debugging/SKILL.md) | Consumes the `debug-verify` recipe and the canonical quorum table       |

## Procedure

Forge runs one session-scoped pass per workflow. Steps are sequential; each gates the next.

1. **Preflight** (once per session, see § Preflight below) — assert native dynamic workflows available; abort with a clear message if not. No fallback.
2. **Interview** — elicit the job shape from the user: goal, input size, fetch vs. edit, recurrence. Match to a Recipe Catalog archetype; if none fits, compose from the Pattern Canon and say so.
3. **Recipe** — pick the catalog row; carry its composition, default scale, `args` signature, and fetch-or-edit class forward. Reject at forge time any recipe that duplicates an approved lifecycle mandate (plan draft/validate, tdd RED-GREEN, review 2-pass) — see § Script Audit Checklist.
4. **Native codegen** — emit a `.claude/workflows/<name>.js` script that embeds the six Generation Contract invariants. Every stage is a distinct `agent()` call with a Handoff-Contract `schema`; `args` with defaults at the top; stage→model routing per dispatch-agents' role→tier table; agent-count cap computed and asserted.
5. **Script Audit Checklist** — run the checklist (see § Script Audit Checklist). HIGH items gate save; failed HIGH items block save.
6. **Smoke-slice run** — execute the same script with a small `args` slice. A failed smoke-slice blocks save. Re-run after fixes; do not proceed until green.
7. **Name check against the `/` command namespace** — before save, confirm `<name>` does not collide with an existing slash command (built-in or plugin). Collision → ask user to rename.
8. **Save ask-before-overwrite** — if `.claude/workflows/<name>.js` already exists, ask before overwriting; never overwrite silently.
9. **CATALOG.md append** — append a row to `docs/workflows/CATALOG.md` (name, recipe, `args` signature, scale, fetch/edit class, last-verified date).

**First-use starters.** When the session has no `docs/workflows/CATALOG.md` (or it is empty), forge offers the three starter workflows and composes one on pick: `debug-verify`, `fan-out-synthesize`, `adversarial-verify`. Each starter maps 1:1 to its Recipe Catalog row; no improvisation.

## Script Audit Checklist

Run before save. HIGH items gate save; a failed HIGH item blocks save. Lower items warn and continue.

**HIGH — no-write clause grep (read-only class).** For every read-only-class recipe (incl. `debug-verify`), grep each `agent()` description string for write/edit verbs (`write`, `edit`, `create`, `modify`, `patch`, `overwrite`, `delete`, `remove`). Every investigator/agent description must explicitly deny write/edit — e.g. "You are read-only; do not write, edit, create, modify, or delete any file." A stage prompt that is silent on writes fails this check. Rationale: runtime agents run `acceptEdits` and hooks do not fire inside the runtime; the prompt denial is the only guard.

**HIGH — recipe-vs-script required-stage diff.** Diff the recipe's declared stage list (Recipe Catalog composition column) against the stages present in the generated script. Every required stage must appear as a distinct `agent()` call (or barrier). A dropped or merged stage fails this check — generation variance that drops a required stage is the top cause of bad workflows.

**Inline one-liners** (each must pass; each failure blocks save):

- **fetch-OR-edit mutual exclusion** — a script is fetch-class OR edit-class, never both; grep `WebFetch`/`fetch` against `Edit`/`Write`/`NotebookEdit` across the script; both sets non-empty fails.
- **`args` defaults present** — every field read in a stage body has a default declared at the top `args` destructure; no undefined-arg paths.
- **agent-count cap respected** — total `agent()` dispatches ≤ recipe default scale; abort-before-exceed logic present and logs truncation.
- **smoke-slice ran** — the smoke-slice run from step 6 produced a green (PASS) Handoff Contract; attach its `status` to the audit record.
- **ask-before-overwrite present** — save path confirms with the user before overwriting an existing `.claude/workflows/<name>.js`.
- **lifecycle-mandate rejection** — a recipe duplicating one approved lifecycle mandate (plan draft/validate, tdd RED-GREEN, review 2-pass) is rejected at forge time, not run time. The lifecycle mandates are owned by `plan`, `tdd`, `review` respectively; forge refuses to generate a workflow whose stage list reproduces any of them. Rationale: one owner per lifecycle phase; a parallel workflow implementation would silently diverge from the canonical mandate.

### Plant-breach drill

A runnable drill that exercises the two HIGH items above. It plants two breach inputs in a temp dir and asserts the checklist catches each: (1) a write-breach investigator prompt (`agent()` description containing "write the fix") — the no-write clause grep must flag it; (2) a stage-omitted script (a generated script missing a required stage named in its recipe) — the recipe-vs-script required-stage diff must flag it. Extracts and runs as-is.

<!-- drill:start -->

```bash
set -u
tmp=$(mktemp -d)
trap 'rm -rf "$tmp"' EXIT

# Breach #1: write-breach investigator prompt — an agent() description containing "write the fix".
cat > "$tmp/investigator.txt" <<'EOF'
Investigate the hypothesis. You may write the fix directly into the source file if confident.
EOF

# HIGH item 1 — no-write clause grep: flags any investigator prompt permitting writes.
if ! grep -qiE "write|edit|patch|fix the|create|modify|delete|overwrite" "$tmp/investigator.txt"; then
  echo "FAIL: write-breach not caught" >&2
  exit 1
fi

# Breach #2: stage-omitted script — recipe declares refute, generated script misses it.
printf 'stages: investigate, refute, tally\n' > "$tmp/recipe.txt"
cat > "$tmp/script.js" <<'EOF'
// Stage: investigate
agent({ description: "investigator" });
// Stage: tally
agent({ description: "tally" });
EOF

# HIGH item 2 — recipe-vs-script required-stage diff: every recipe stage must appear in the script.
stages=$(sed -n 's/^stages: //p' "$tmp/recipe.txt" | tr ',' ' ')
missing=""
for stage in $stages; do
  if ! grep -qiE "Stage: $stage" "$tmp/script.js"; then
    missing="$missing $stage"
  fi
done

if [ -z "$missing" ]; then
  echo "FAIL: stage-omission not caught" >&2
  exit 1
fi

echo "both breaches caught"
exit 0
```

<!-- drill:end -->

## Annotated `debug-verify` example script

Reference-only. This is a markdown code block showing a representative `debug-verify` workflow script with the four required annotations as inline comments. It is illustrative documentation inside this skill — the plugin still ships markdown only; nothing here is a shipped artifact.

```javascript
// debug-verify.js — illustrative, not shipped. Read-only class.
// Args: { hypotheses: [], repro_cmd, failing_output, rubric }
const args = workflow.args || {};
const hypotheses = args.hypotheses || [];
const repro_cmd = args.repro_cmd || '';
const failing_output = args.failing_output || '';
const rubric = args.rubric || 'refute the root-cause claim with minimal reproducer';
const SKEPTICS_PER = 2; // recipe default
const MAX_ROUNDS = Math.max(4, Math.ceil(hypotheses.length / 2)); // loop ceiling

const handoffSchema = {
  type: 'object',
  properties: {
    status: { type: 'string' },
    completed: { type: 'array' },
    skipped: { type: 'array' },
    findings: { type: 'array' },
    commands: { type: 'array' },
    artifacts: { type: 'array' },
  },
  required: ['status', 'findings'],
};

let seen = new Set(); // (file:line, classification) dedupe across rounds
let roundLog = [];
let noSurvivorRounds = 0;

for (let round = 1; round <= MAX_ROUNDS; round++) {
  // ===== each stage: investigator (blind, per-hyp) → truncation → skeptic → quorum =====
  // Stage A — investigators: one agent() per hypothesis, blind to each other.
  const investigations = await Promise.all(
    hypotheses.map((hyp) =>
      agent({
        description: `Investigate hypothesis: ${hyp}. You are read-only; do not write, edit, create, modify, or delete any file. Report root cause only.`,
        model: 'sonnet', // strong tier per role→tier table
        schema: handoffSchema,
        prompt: `Repro: ${repro_cmd}\nFailing output:\n${failing_output}\nHypothesis: ${hyp}\nReturn a Handoff Contract.`,
      }),
    ),
  );

  // Stage B — in-script bare-claim truncation between generator and skeptic.
  // ===== truncation point: generator reasoning stripped here, only bare claim passes =====
  const bareClaims = investigations
    .flatMap((r) =>
      (r.findings || []).map((f) => {
        // Truncate to: "root cause is <X> at <file:line>, classified as <logic|design-level>"
        const m = /root cause is (.+?) at ([^,\s]+:\d+), classified as (logic|design-level)/.exec(
          f.summary || '',
        );
        if (!m) return null; // drop claims lacking the (file:line, classification) tuple
        return { claim: m[0], file_line: m[2], classification: m[3] };
      }),
    )
    .filter(Boolean)
    .filter((c) => {
      const k = `${c.file_line}|${c.classification}`;
      if (seen.has(k)) return false;
      seen.add(k);
      return true;
    });

  if (bareClaims.length === 0) {
    noSurvivorRounds++;
    if (noSurvivorRounds >= 2) break;
    continue;
  }
  noSurvivorRounds = 0;

  // Stage C — skeptics: SKEPTICS_PER fresh skeptics per claim, prompted to REFUTE.
  const verdicts = await Promise.all(
    bareClaims.flatMap((c) =>
      Array.from({ length: SKEPTICS_PER }, (_, i) =>
        agent({
          description: `Skeptic ${i} for claim: ${c.claim}. You are read-only; do not write, edit, create, modify, or delete any file. Refute this claim or abstain.`,
          model: 'sonnet',
          schema: handoffSchema,
          prompt: `Claim: ${c.claim}\nRubric: ${rubric}\nAngle ${i}: attack from a different refutation angle. Return CONFIRMED/REFUTED/ABSTAIN in findings.`,
        }),
      ),
    ),
  );

  // Stage D — quorum tally per the canonical table.
  // ===== quorum tally: 2 skeptics → dies if ≥1 refutes; abstain = 0.5 refutation =====
  const survivors = bareClaims.filter((c, i) => {
    const vs = verdicts.slice(i * SKEPTICS_PER, (i + 1) * SKEPTICS_PER);
    const refutes = vs.filter((v) =>
      (v.findings || []).some((f) => /REFUTED/.test(f.summary || '')),
    ).length;
    const abstains = vs.filter((v) =>
      (v.findings || []).some((f) => /ABSTAIN/.test(f.summary || '')),
    ).length;
    const score = refutes + 0.5 * abstains;
    return score < 1; // 2-skeptic row: dies when ≥1 refutes
  });

  roundLog.push({ round, claims: bareClaims.length, survivors: survivors.length });
  if (survivors.length === 0) noSurvivorRounds++;
  else noSurvivorRounds = 0;

  // ===== stop condition: 2 consecutive no-survivor rounds OR absolute ceiling =====
  if (noSurvivorRounds >= 2) break;
}

return {
  status: roundLog.some((r) => r.survivors > 0) ? 'PARTIAL' : 'PASS',
  completed: [],
  skipped: [],
  findings: roundLog,
  commands: [],
  artifacts: [],
};
```

Four required annotations, marked inline above: **each stage** (Stage A/B/C/D labeled), **truncation point** (Stage B comment), **quorum tally** (Stage D comment), **stop condition** (loop-bottom comment).

## Preflight

Once per session, before any other Procedure step. Asserts native dynamic workflows are available; aborts with a clear message on failure; **no fallback**.

- **Check:** Claude Code version ≥ **2.1.154** AND a paid plan AND dynamic workflows not disabled. The runtime is a plugin-level hard dependency for bulk and debug fan-out.
- **On failure:** abort forge with a clear message — "Native dynamic workflows unavailable (need CC ≥ 2.1.154, paid plan, not disabled). Cannot forge. No fallback." Do not silently degrade to turn-by-turn Agent dispatches; the Procedure's invariants (in-script truncation, quorum tally, agent-count cap) are unenforceable outside the runtime.
- **No fallback:** this is a user decision recorded in the design brief — one execution path. Forge refuses to generate a workflow it cannot smoke-slice in the native runtime.

## Generated artifacts

The Procedure emits two per-project artifacts at CATALOG.md-append time (step 9): the workflow script `.claude/workflows/<name>.js` and a row appended to `docs/workflows/CATALOG.md`. Both are per-project outputs, produced by the forge Procedure in the host project — they are never committed to the plugin repo, and no `.js` ships plugin-wide. The plugin ships markdown only (per AGENTS.md); generated scripts live in the host project's `.claude/workflows/` and are referenced from that project's `docs/workflows/CATALOG.md`.

The per-project `docs/workflows/CATALOG.md` has columns: **name**, **recipe**, **args signature**, **scale**, **fetch/edit class**, **last-verified** date. Each row is produced by the forge Procedure at CATALOG.md-append time, recording the `args` signature, scale, and fetch/edit class carried forward from the chosen Recipe Catalog row, plus the last-verified date stamped on the smoke-slice green run. The column set is fixed; forge appends one row per generated workflow, never rewriting prior rows.

Generated `.claude/workflows/<name>.js` and `docs/workflows/CATALOG.md` are per-project, never committed to the plugin repo; no .js ships plugin-wide.
