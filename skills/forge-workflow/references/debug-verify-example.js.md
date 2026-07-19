# Annotated `debug-verify` example script

Reference-only — illustrative, not a shipped artifact. A representative `debug-verify` workflow script with the four required annotations as inline comments.

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
