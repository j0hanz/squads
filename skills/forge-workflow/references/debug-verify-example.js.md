# Annotated `debug-verify` example script

Look-only. Show thing, not real tool. `debug-verify` script have six rules / four marks as words inside.

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

// Invariant 6 — agent-count cap per recipe. Recipe default scale is
// N hypotheses × 2 skeptics (SKILL.md Recipe Catalog); across MAX_ROUNDS the
// skeptic fan-out alone is hypotheses.length * SKEPTICS_PER * MAX_ROUNDS.
// Abort before exceeding; silent caps read as full coverage.
const TOTAL_CAP = hypotheses.length * SKEPTICS_PER * MAX_ROUNDS;
let dispatched = 0;
function willDispatch(n) {
  if (dispatched + n > TOTAL_CAP) {
    console.error(
      `agent-count cap exceeded (${dispatched + n} > ${TOTAL_CAP}); aborting before dispatch, truncating remaining work.`,
    );
    return false;
  }
  dispatched += n;
  return true;
}

for (let round = 1; round <= MAX_ROUNDS; round++) {
  // ===== each stage: investigator (blind, per-hyp) → truncation → skeptic → quorum =====
  // Stage A — investigators: one agent() per hypothesis, blind to each other.
  if (!willDispatch(hypotheses.length)) break;
  const investigations = await Promise.all(
    hypotheses.map((hyp) =>
      agent({
        description: `Investigate hypothesis: ${hyp}. You are read-only; do not write, edit, create, modify, or delete any file. Report root cause only.`,
        model: 'haiku',
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
    // empty round (nothing new after dedupe) — not a no-survivor round; just advance
    continue;
  }

  // Stage C — skeptics: SKEPTICS_PER fresh skeptics per claim, prompted to REFUTE.
  if (!willDispatch(bareClaims.length * SKEPTICS_PER)) break;
  const verdicts = await Promise.all(
    bareClaims.flatMap((c) =>
      Array.from({ length: SKEPTICS_PER }, (_, i) =>
        agent({
          description: `Skeptic ${i} for claim: ${c.claim}. You are read-only; do not write, edit, create, modify, or delete any file. Refute this claim or abstain.`,
          model: 'haiku',
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
  // (empty rounds no longer increment noSurvivorRounds — they are a "nothing new"
  //  signal, distinct from a no-survivor round; only survivors.length === 0 counts)
  if (noSurvivorRounds >= 2) break;
}

return {
  status: roundLog.some((r) => r.survivors > 0) ? 'PASS' : 'PARTIAL', // a surviving claim = active confirmation (canon: unconfirmed → PARTIAL, not PASS)
  completed: [],
  skipped: [],
  findings: roundLog,
  commands: [],
  artifacts: [],
};
```

Four marks above: **each stage** (Stage A/B/C/D mark), **truncation point** (Stage B word), **quorum tally** (Stage D word), **stop condition** (loop-bottom word). Agent-count rule (Invariant 6) live in `willDispatch` guard before Stage A and Stage C.
