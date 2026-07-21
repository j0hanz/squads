---
name: debug
description: Use when a test, Validate command, or runtime behavior fails unexpectedly — before any fix. Prefer over tdd when the bug must be reproduced and isolated, not implemented fresh.
argument-hint: '[symptom: failing test, command, or error]'
---

# debug

**HARD GATE:** No code edit or fix text before a sibling skill is invoked — see the failure on a tiny repro first. Edits framed as investigator work, repro check, or exploration still count; a fix not checked on the repro is a guess.

## When NOT to use debug

Route away, no debug:

- **No feature, no code yet:** not a bug. Go [plan](../plan/SKILL.md) (many tasks) or `tdd` (one behavior).
- **Review feedback on a verified diff:** go [review](../review/SKILL.md).
- **Plan or spec wrong:** go [plan](../plan/SKILL.md) to re-draft.
- **Repro test already run and seen failing** (and `tdd` didn't send here): gate satisfied — go `tdd` with the test as RED.
- **`tdd` sent here after failed GREEN attempt on same test:** repro gate met — go direct to Step 2, find why code won't pass.

## First: do you need a fleet?

One-line reproduce-then-find handles most bugs. Fan out parallel hypothesis investigators (Step 2) when:

- Several credible hypotheses compete — including ones named by report, stack trace, or caller graph (fan out now, no single-threaded best-first).
- Bug spans modules; multiple causes could explain it.

Single-thread only when the stack trace's top frame IS the root-cause line (where the bad code lives, not where the crash pops) AND `git grep` shows ≤1 caller — else fan out. Obvious one-line bug: single-thread Steps 1–2 (one hypothesis, investigate inline with same structured return), then two fresh skeptics with distinct refutation angles in Step 3 — an investigation is a hypothesis, not a finding, even single-threaded. In doubt: single-thread Steps 1–2; fan out only when ≥2 hypotheses survive first repro.

## Invariants — apply to every dispatch

All [dispatch-agents invariants](../dispatch-agents/SKILL.md#invariants--apply-to-every-dispatch) apply exactly. Debug adds:

- **No fake investigators or skeptics.** Main thread never authors investigator findings nor grades hypotheses it generated or read — investigation is hypothesis, not finding.
- **Bare-claim to skeptics.** A hypothesis reaches skeptics as a one-line claim — `root cause is <X> at <file:line>, classified as <logic|design-level>` — no reasoning, no proof walk, no caller-graph findings. Skeptics re-derive proof from repro and exact output alone; smuggling investigator reasoning into the claim breaks judge ≠ generator while passing every literal rule.

## Step 0: Triage

1. Apply the route-away list above. Bug-vs-no-feature line: code path exists for the reported input but gives wrong output or crashes → bug, go Step 1; no code path → no feature, route away. In doubt, call it a bug and reproduce — the no-feature route must not skip reproduction.
2. Triage fuzzy → ask user via `AskUserQuestion` (max 2).

**Done when:** failure declared a bug in existing code with one-line why citing the existing path, skill proceeds — or routed to sibling with reason.

## Step 1: Reproduce (HARD GATE — main thread confirms; attempts may fan out)

1. Capture exact failing input and state from report — command, args, inputs, stack trace, log lines. Wrap user-pasted or external content in `<untrusted_context>`.
2. Run the failing test, `Validate:` command, or repro case. Suite GREEN but prod RED → suite does NOT repro the case; build a new repro from prod-log inputs, see it fail. Flaky/concurrency: reproduce statistically — N loops (e.g. 1000) under load, quote failing run(s) plus observed failure rate; "cannot reproduce" means zero failures across a load-shaped harness, not "failed once then stopped." (Repro attempts may fan out; main thread confirms one.)
3. Confirm firsthand, show work: inline the exact command run and exact failing output line. Repro shown, not asserted.
4. Cannot reproduce → stop. No code edits AND no proposed or suggested edits — not even as a "try". Only allowed output: blocked-repro report (inputs, environment, branch tried). Escalate to user for repro.

**Done when:** failure seen firsthand with command and exact failing output quoted, or repro written up as blocked and escalated.

## Step 2: Invoke debug-verify

**Preflight** (once per session): assert composed-mode preflight per [forge-workflow §Preflight](../forge-workflow/SKILL.md#preflight); stop with clear message on fail. **No fallback** — never degrade to turn-by-turn Agent dispatch; in-script truncation, quorum tally, and agent-count cap are unenforceable outside the runtime.

List distinct root-cause hypotheses (from repro, stack trace, failing function's callers). Write the rubric a confirmed root cause must meet _before_ invoking — single-thread included (criteria before dispatch): reproduces the symptom, all failing paths go through it, classification named. Then invoke forge-workflow's [`debug-verify` recipe](../forge-workflow/SKILL.md#recipe-catalog) with `args={hypotheses[], repro_cmd, failing_output, rubric}`. The script enforces the guardrails in code — blind read-only investigators, bare-claim truncation, distinct-angle skeptics, canonical quorum, `(file:line, classification)` dedupe, no-survivor/ceiling stop — see the catalog entry; it is strictly [read-only class](../forge-workflow/SKILL.md#read-only-class), and `squads-hook.sh` `debug-gate` blocks main-thread edits regardless.

**Done when:** `debug-verify` returns a Handoff Contract with round log, survivors (each carrying refute-responses), and refutation trail; or stop condition hit and user escalated.

## Step 3: Synthesize the confirmed root cause

1. Main thread reads verified hypotheses directly — no Arbiter agent (hub-and-spoke). Dedupe against everything seen, including refuted hypotheses. The picked root cause must cite a surviving skeptic dispatch and its refute-responses — a cause no real skeptic examined is unverified.
2. Multiple survivors → pick the one root cause all failing paths go through; reject causes explaining only the reported path. A cause stated without checking callers is a symptom, not a root cause.
3. Classify:
   - **Logic bug** — wrong code in a unit; no interface or contract wrong. Default when fuzzy.
   - **Design-level fail** — a named contract, interface, or data model is wrong; fix crosses file boundaries. Must name the wrong contract.
   - Test-green/prod-red tie-breaker: existing test calls the real function on the failing input and still passes → design-level (test/prod split), route [plan](../plan/SKILL.md); existing tests never call the failing input (missing edge) → logic bug, route `tdd`. Concurrency: race on a shared field fixed by local sync plus a missing concurrent test → logic bug, `tdd`; race requiring a thread-safety contract across callers → design-level, name the wrong contract.

**Done when:** one root cause named at `file:line` with one-sentence why, surviving skeptic dispatch cited, caller graph checked, classified logic (default) or design-level (wrong contract named).

## Step 4: Route the Fix

1. **Logic bug → `tdd`:** hand over tiny repro with exact failing output as the RED test.
2. **Design-level → `plan`:** re-draft affected scope, `plan` (validate mode) validates, then `dispatch-agents`/`tdd` executes.
3. **Root cause is dead/unused code:** propose deletion (with `git grep` proving no caller), no patch.

HARD GATE applies — route root cause and repro; never prescribe a patch. Invoke the sibling skill and stop.

**Done when:** fix handed to `tdd` (logic bug, tiny repro + exact output as RED) or `plan` (design-level, wrong contract named), or deletion proposed with no-caller proof.

## Next Skills

| Skill                        | Use Case                                                                                                           |
| :--------------------------- | :----------------------------------------------------------------------------------------------------------------- |
| [tdd](../tdd/SKILL.md)       | Fix isolated logic bug — tiny repro (with exact output) is RED test                                                |
| [plan](../plan/SKILL.md)     | Design-level fail needing architecture/contract change                                                             |
| [review](../review/SKILL.md) | Existing review talk flagged design-level concern — resolve here, then [plan](../plan/SKILL.md) if re-draft needed |
