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

1. Capture exact failing input and state from report — command, args, inputs, stack trace, log lines. Wrap user-pasted or external content in `<untrusted_context>`.
2. Run failing test, `Validate:` command, or reproduction case. Test suite GREEN but production RED means suite NOT reproducing case — build fresh repro from production-log inputs, observe it fail. Flaky/concurrency bugs: repro statistical, run N iterations (e.g. 1000) under load, quote failing run(s) plus observed failure rate; "cannot reproduce" means zero failures across load-shaped harness, not "failed once then could not." (Multiple repro attempts may fan out in parallel; main thread confirms one.)
3. Confirm failure firsthand, show work: inline exact command run and verbatim failing output line observed. Reproduction shown, not asserted.
4. Cannot reproduce: stop. Don't edit code AND don't propose or suggest edits — not even as suggestion to try. Only allowed output is blocked-repro report (what tried: inputs, environment, branch). Escalate to user for repro.

**Done when:** failure observed firsthand with command and verbatim failing output quoted, or reproduction documented as blocked and escalated.

## Step 2: Invoke debug-verify

**Preflight** (once per session): assert native dynamic workflows available; abort with a clear message if not. **No fallback** — do not degrade to turn-by-turn Agent dispatches; the in-script truncation, quorum tally, and agent-count cap are unenforceable outside the runtime.

Enumerate distinct root-cause hypotheses (from repro, stack trace, failing function's callers), then invoke forge-workflow's `debug-verify` recipe with `args={hypotheses[], repro_cmd, failing_output, rubric}`. The recipe is strictly [read-only class](../forge-workflow/SKILL.md#read-only-class) — runtime agents run `acceptEdits` and the read-only class compensates; `hooks/debug-gate.sh` still blocks main-thread edits regardless.

Write the rubric confirmed root cause must satisfy _before_ invoking — single-thread included (Criteria before dispatch; criteria written after result only confirm guesses): reproduces symptom, all failing paths route through it, classification named.

The `debug-verify` script enforces all guardrails in-code:

- **read-only investigators** — one per hypothesis, blind to each other; every stage prompt denies write/edit tools.
- **in-code bare-claim truncation** — each finding truncated to `root cause is <X> at <file:line>, classified as <logic|design-level>` before skeptics read it; claims lacking the `(file:line, classification)` tuple are dropped.
- **skeptics with distinct angles** — 2+ fresh skeptics per claim, prompted to _refute_ (one attacks the repro, one the caller-graph, one the classification).
- **canonical quorum tally** — per [forge-workflow's Pattern Canon](../forge-workflow/SKILL.md#pattern-canon) quorum table, including its PARTIAL-when-unconfirmed rule (a finding not actively confirmed by a skeptic is unverified, not PASS).
- **`(file:line, classification)` dedupe** — across rounds, against everything seen (including refuted hypotheses).
- **stop on 2 consecutive no-survivor rounds or ceiling** — `ceil(N/2)` total rounds where N = initial hypothesis count, minimum 4. (The generic "loop until done" pattern stops on dedupe-empty "nothing new" rounds; debug-verify's fixed-hypothesis variant stops on "no-survivor" rounds instead — see [Pattern Canon](../forge-workflow/SKILL.md#pattern-canon).)
- **returns round log + survivors + refutation trail** in [Handoff Contract](../dispatch-agents/SKILL.md#handoff-contract) shape.

**Done when:** `debug-verify` returns a Handoff Contract with round log, survivors (each carrying refutation-responses), and refutation trail; or loop-back stop condition met and user escalated.

## Step 3: Synthesize the confirmed root cause

1. Main thread reads verified hypotheses directly — no Arbiter agent; main thread synthesizes genuinely independent results (dispatch-agents' hub-and-spoke). Dedupe against everything seen (including refuted hypotheses). Picked root cause must cite surviving skeptic dispatch and its refutation-responses — cause surviving no real skeptic is unverified.
2. Multiple survive: pick single root cause all failing paths route through; reject causes explaining only reported path. Cause stated without checking callers is symptom, not root cause.
3. Classify:
   - **Logic bug** — wrong code in unit; no interface or contract wrong. Default here on ambiguity.
   - **Design-level failure** — named contract, interface, or data model wrong; fix crosses file boundaries. Must name wrong contract.
   - Tie-breaker for tests-green/prod-red: existing test calls real function on failing input and still passes, that's design-level (test/prod divergence), route [plan](../plan/SKILL.md); existing test never calls failing input (missing edge), that's logic bug, route `tdd`. Concurrency: race on shared field fixed by local synchronization plus missing concurrent test, logic bug, route `tdd`; race requiring declaring shared service thread-safe across callers, design-level, name wrong contract.

**Done when:** one root cause named at `file:line` with one-sentence why, surviving skeptic dispatch cited, caller graph checked, classified as logic (default) or design-level (with wrong contract named).

## Step 4: Route the Fix

1. **Logic bug, route `tdd`:** hand over minimal repro with verbatim failing output as RED test; `tdd` drives RED-GREEN-REFACTOR for fix.
2. **Design-level failure, route `plan`:** re-draft affected scope, then `plan` (validate mode) validates, then `dispatch-agents`/`tdd` executes.
3. **Root cause dead or unused code:** propose deletion (with `git grep` proving no callers), not patch.

HARD GATE applies — route root cause and repro; don't prescribe patch. Invoke sibling skill and stop.

**Done when:** fix handed to `tdd` (logic bug, minimal repro + verbatim output as RED) or `plan` (design-level, wrong contract named), or deletion proposed with proof of no callers.

## Next Skills

| Skill                        | Use Case                                                                                                               |
| :--------------------------- | :--------------------------------------------------------------------------------------------------------------------- |
| [tdd](../tdd/SKILL.md)       | Fix isolated logic bug — minimal repro (with verbatim output) is RED test                                              |
| [plan](../plan/SKILL.md)     | Design-level failure needing architecture/contract change                                                              |
| [review](../review/SKILL.md) | Existing review feedback flagged design-level concern — resolve here, then [plan](../plan/SKILL.md) if re-draft needed |
