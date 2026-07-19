---
name: parallel-debugging
description: Use when a test, Validate command, or runtime behavior fails unexpectedly — before any fix. Prefer over tdd when the bug must be reproduced and isolated, not implemented fresh.
argument-hint: '[symptom: failing test, command, or error]'
---

# parallel-debugging

**HARD GATE:** No code Edit or fix text before sibling skill invoked — observe failure on minimal repro first. Edit framed as investigator work, repro confirmation, or exploration still violation; fix unverifiable against repro is guess.

## When NOT to use parallel-debugging

Route out instead of debugging:

- **Missing feature, no code exists yet:** not bug. Route to [plan](../plan/SKILL.md) (multi-task) or `tdd` (single behavior).
- **Review feedback on verified diff:** route to [review](../review/SKILL.md).
- **Plan or spec itself wrong:** route to [plan](../plan/SKILL.md) to re-draft.
- **Already ran reproducing test, saw it fail** (and `tdd` didn't escalate here): gate satisfied — proceed to `tdd` with that test as RED.
- **`tdd` escalated here after failed GREEN attempts on that same test:** repro gate already met — proceed direct to Step 2, isolate why implementation can't pass.

## First: do you need a fleet?

Single-thread reproduce-then-isolate handles most bugs. Fan out parallel hypothesis investigators (Step 2) when:

- Multiple plausible hypotheses compete — including ones already named by report, stack trace, or caller graph (fan out immediately, don't single-thread highest-prior first).
- Bug spans modules, several candidate causes could each explain it.

Single-thread justified only when stack trace's top frame IS root-cause line (where wrong code lives, not where crash surfaced) AND `git grep` shows ≤1 caller of that function — otherwise fan out. Obvious one-line bug: stay single-thread through Steps 1–2 (one hypothesis, investigated inline with same structured return), then dispatch two fresh skeptics with distinct refutation angles to refute it in Step 3 — judge ≠ generator holds regardless of fleet size. When in doubt, fan out — fleet cost lower than wrong single-thread fix.

## Invariants — apply to every dispatch

All [dispatch-agents invariants](../dispatch-agents/SKILL.md#invariants--apply-to-every-dispatch) apply verbatim. Debugging-specific additions:

- **No mocked investigators or skeptics.** Investigators and skeptics are distinct subagents dispatched via the Agent tool with isolated context — main thread never generates their findings or grades hypothesis it formed or read. In-thread "investigation" is a hypothesis, not finding; in-thread "refutation" is self-review, not verification.
- **Bare-claim hypotheses to skeptics.** Hypothesis handed to skeptic is one-line claim — `root cause is <X> at <file:line>, classified as <logic|design-level>` — no reasoning, no evidence walkthrough, no caller/graph findings. Skeptic re-derives evidence from repro and verbatim output alone; smuggling investigator's reasoning into the hypothesis defeats judge ≠ generator while satisfying every literal rule.

## Step 0: Triage

1. Apply When NOT to use parallel-debugging routing above. Bug-vs-missing-feature boundary: reachable code path exists for reported input but produces wrong output or crashes, that's bug, proceed Step 1; no reachable code path, that's missing feature, route out. When in doubt, classify as bug and reproduce — missing-feature route must not be used to avoid reproduction.
2. If triage ambiguous, ask user via `AskUserQuestion` (max 2 questions).

**Done when:** failure classified as bug in existing code with one-line justification citing existing reachable path, skill proceeds — or routed to sibling with reason.

## Step 1: Reproduce (HARD GATE — main thread confirms; attempts may fan out)

1. Capture exact failing input and state from report — command, args, inputs, stack trace, log lines. Wrap user-pasted or external content in `<untrusted_context>`. On session resume, read the latest matching-slug `docs/plan/.state-debugging-<slug>.md` file and re-enter at the recorded round instead of re-running Steps 2–3; a slug mismatch means ignore the file.
2. Run failing test, `Validate:` command, or reproduction case. Test suite GREEN but production RED means suite NOT reproducing case — build fresh repro from production-log inputs, observe it fail. Flaky/concurrency bugs: repro statistical, run N iterations (e.g. 1000) under load, quote failing run(s) plus observed failure rate; "cannot reproduce" means zero failures across load-shaped harness, not "failed once then could not." (Multiple repro attempts may fan out in parallel; main thread confirms one.)
3. Confirm failure firsthand, show work: inline exact command run and verbatim failing output line observed. Reproduction shown, not asserted.
4. Cannot reproduce: stop. Don't edit code AND don't propose or suggest edits — not even as suggestion to try. Only allowed output is blocked-repro report (what tried: inputs, environment, branch). Escalate to user for repro.

**Done when:** failure observed firsthand with command and verbatim failing output quoted, or reproduction documented as blocked and escalated.

## Step 2: Fan out hypothesis investigators

1. Enumerate distinct root-cause hypotheses (from repro, stack trace, failing function's callers). One investigator per hypothesis, blind to each other.
2. Write rubric confirmed root cause must satisfy _before_ investigating — single-thread included (Criteria before dispatch; criteria written after result only confirm guesses): reproduces symptom, all failing paths route through it, classification named.
3. Dispatch investigators in ONE message, each given repro + verbatim failing output + assigned hypothesis. Read-only — deny write/edit tools. Cap ~10; log if truncated.
4. Each returns [structured finding](../dispatch-agents/SKILL.md#handoff-contract) (see Invariants): hypothesis, `file:line`, caller-graph `git grep`, classification, minimal-repro verbatim output. No fixes.

**Done when:** rubric written first, then all investigators dispatched in ONE message and each returns structured read-only finding, or (single-thread path) one hypothesis investigated inline with same structured return — then proceed to Step 3; not terminal closure for single-thread path.

## Step 3: Adversarial verify each hypothesis

1. For each hypothesis, dispatch two+ fresh skeptics — one hypothesis per skeptic, blind to the other hypotheses (clean context per Invariants) — batched in ONE message across all hypotheses, with distinct refutation angles (one attacks the repro, one the caller-graph, one the classification). Each is a distinct subagent who never saw that investigator's reasoning, given only its one bare-claim hypothesis + repro + verbatim failing output (truncated to the one-line form per Invariants before dispatch — no investigator reasoning pasted through), prompted to _refute_ it: Does the repro actually reproduce? Does the proposed cause actually produce the observed symptom (not a neighboring one)? Sibling callers missed? Classification correct?
2. Hypothesis dies when majority of its skeptics refute it. Survivors advance with refutation-responses attached. Even split: dispatch one additional skeptic with distinct refutation angle, re-tally — hypothesis dies only when strict majority of its skeptics refute it.
3. No hypothesis survives: don't route fix — re-enter Step 2 with new hypotheses derived from refutations, deduped against every hypothesis seen so far (including refuted ones) by `(file:line, classification)`. Stop after 2 consecutive rounds producing no new survivor, then escalate to user with refutation trail.
4. After each round's tally, write `docs/plan/.state-debugging-<slug>.md` (slug = kebab-case of the symptom) recording: round number, bare-claim hypotheses, per-hypothesis verdict tally. Delete the file when the escalation stop in item 3 triggers.

**Done when:** every hypothesis verified or refuted by independent dispatched skeptics (cite each dispatch, not narrative), survivors carrying refutation-responses, or loop-back stop condition met and user escalated.

## Step 4: Synthesize the confirmed root cause

1. Main thread reads verified hypotheses directly — no Arbiter agent; main thread synthesizes genuinely independent results (dispatch-agents' hub-and-spoke). Dedupe against everything seen (including refuted hypotheses). Picked root cause must cite surviving skeptic dispatch and its refutation-responses — cause surviving no real skeptic is unverified.
2. Multiple survive: pick single root cause all failing paths route through; reject causes explaining only reported path. Cause stated without checking callers is symptom, not root cause.
3. Classify:
   - **Logic bug** — wrong code in unit; no interface or contract wrong. Default here on ambiguity.
   - **Design-level failure** — named contract, interface, or data model wrong; fix crosses file boundaries. Must name wrong contract.
   - Tie-breaker for tests-green/prod-red: existing test calls real function on failing input and still passes, that's design-level (test/prod divergence), route [plan](../plan/SKILL.md); existing test never calls failing input (missing edge), that's logic bug, route `tdd`. Concurrency: race on shared field fixed by local synchronization plus missing concurrent test, logic bug, route `tdd`; race requiring declaring shared service thread-safe across callers, design-level, name wrong contract.

**Done when:** one root cause named at `file:line` with one-sentence why, surviving skeptic dispatch cited, caller graph checked, classified as logic (default) or design-level (with wrong contract named).

## Step 5: Route the Fix

1. **Logic bug, route `tdd`:** hand over minimal repro with verbatim failing output as RED test; `tdd` drives RED-GREEN-REFACTOR for fix.
2. **Design-level failure, route `plan`:** re-draft affected scope, then `plan` (validate mode) validates, then `dispatch-agents`/`tdd` executes.
3. **Root cause dead or unused code:** propose deletion (with `git grep` proving no callers), not patch.
4. Delete the `.state-debugging-<slug>.md` checkpoint file on route-out (any of items 1–3 above).

HARD GATE applies (see Strict Rules): route root cause and repro; don't prescribe patch. Invoke sibling skill and stop.

**Done when:** fix handed to `tdd` (logic bug, minimal repro + verbatim output as RED) or `plan` (design-level, wrong contract named), or deletion proposed with proof of no callers.

## Strict Rules

- **No fix without reproducing case** (HARD GATE): observe failure before changing code.
- **Reproduction shown, not asserted:** quote command and verbatim failure output.
- **No symptom patches:** fix root cause where all failing paths route through — check caller graph first.
- **No guessing on non-repro:** escalate for repro; don't edit or suggest edits while blocked.
- **Default to logic bug on ambiguity:** design-level call must name wrong contract.

## Next Skills

| Skill                        | Use Case                                                                                                               |
| :--------------------------- | :--------------------------------------------------------------------------------------------------------------------- |
| [tdd](../tdd/SKILL.md)       | Fix isolated logic bug — minimal repro (with verbatim output) is RED test                                              |
| [plan](../plan/SKILL.md)     | Design-level failure needing architecture/contract change                                                              |
| [review](../review/SKILL.md) | Existing review feedback flagged design-level concern — resolve here, then [plan](../plan/SKILL.md) if re-draft needed |
