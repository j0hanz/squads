---
name: debug
description: Use when a test, Validate command, or runtime behavior fails unexpectedly — before any fix. Prefer over tdd when the bug must be reproduced and isolated, not implemented fresh.
argument-hint: '[symptom: failing test, command, or error]'
---

# debug

**HARD GATE:** No code edit or fix text before sibling skill invoked — see failure on tiny repro first. Edit framed as investigator work, repro check, or explore still bad; fix not checked on repro is guess.

## When NOT to use debug

Send away, no debug:

- **No feature, no code yet:** not bug. Go [plan](../plan/SKILL.md) (many task) or `tdd` (one behavior).
- **Review talk on checked diff:** go [review](../review/SKILL.md).
- **Plan or spec bad:** go [plan](../plan/SKILL.md) to make new.
- **Already ran repro test, saw fail** (and `tdd` not send here): gate happy — go to `tdd` with test as RED.
- **`tdd` send here after failed GREEN try on same test:** repro gate met — go direct to Step 2, find why code no pass.

## First: do you need a fleet?

One-line reproduce-then-find handle most bug. Send many parallel hypothesis lookers (Step 2) when:

- Many good idea compete — include ones named by report, stack trace, or caller graph (fan out now, no single-thread best-first).
- Bug span many module, many cause explain it.

One-thread okay only when stack trace top frame IS root-cause line (where bad code live, not where crash pop) AND `git grep` show ≤1 caller — else fan out. Obvious one-line bug: stay one-thread through Steps 1–2 (one idea, look inline with same structured return), then send two new skeptic with different refute angle to say no in Step 3 — per [dispatch-agents Invariants](../dispatch-agents/SKILL.md#invariants--apply-to-every-dispatch); look is idea, not finding, even one-thread. When doubt, stay one-thread through Steps 1–2 — fan out only when ≥2 good idea survive first repro.

## Invariants — apply to every dispatch

All [dispatch-agents invariants](../dispatch-agents/SKILL.md#invariants--apply-to-every-dispatch) apply exact. Debug add:

- **No fake looker or skeptic.** Per [dispatch-agents Invariants](../dispatch-agents/SKILL.md#invariants--apply-to-every-dispatch); main thread never make looker finding or grade idea it make or read — look is idea, not finding.
- **Bare-claim idea to skeptic.** Idea to skeptic is one-line claim — `root cause is <X> at <file:line>, classified as <logic|design-level>` — no think, no proof walk, no caller/graph find. Skeptic re-derive proof from repro and exact output alone; sneak looker think into idea break judge ≠ generator while pass every literal rule.

## Step 0: Triage

1. Apply When NOT to use debug route above. Bug-vs-no-feature line: code path exist for reported input but give wrong output or crash, is bug, go Step 1; no code path, is no feature, send away. When doubt, call bug and reproduce — no-feature route must not skip reproduction.
2. If triage fuzzy, ask user via `AskUserQuestion` (max 2 ask).

**Done when:** failure called bug in existing code with one-line why citing existing path, skill go — or sent to sibling with reason.

## Step 1: Reproduce (HARD GATE — main thread confirms; attempts may fan out)

1. Capture exact fail input and state from report — command, args, inputs, stack trace, log lines. Wrap user-paste or outside content in `<untrusted_context>`.
2. Run fail test, `Validate:` command, or repro case. Test suite GREEN but prod RED mean suite NOT repro case — build new repro from prod-log inputs, see fail. Flaky/concurrency bug: repro stats, run N loops (e.g. 1000) under load, quote fail run(s) plus seen fail rate; "cannot reproduce" mean zero fail across load-shaped harness, not "fail once then no." (Many repro try may fan out parallel; main thread confirm one.)
3. Confirm fail firsthand, show work: inline exact command run and exact fail output line seen. Repro shown, not just said.
4. Cannot reproduce: stop. No edit code AND no propose or suggest edit — not even as try. Only allowed output is blocked-repro report (what try: inputs, environment, branch). Escalate to user for repro.

**Done when:** fail seen firsthand with command and exact fail output quoted, or repro written as blocked and escalated.

## Step 2: Invoke debug-verify

**Preflight** (one per session): assert composed-mode preflight per [forge-workflow §Preflight](../forge-workflow/SKILL.md#preflight); stop with clear message if no. **No fallback** — no degrade to turn-by-turn Agent dispatch; in-script cut, quorum tally, and agent-count cap unenforceable outside runtime.

List distinct root-cause idea (from repro, stack trace, fail function callers), then invoke forge-workflow's `debug-verify` recipe with `args={hypotheses[], repro_cmd, failing_output, rubric}`. Recipe is strictly [read-only class](../forge-workflow/SKILL.md#read-only-class) — runtime agents run `acceptEdits` and read-only class fix; `squads-hook.sh` `debug-gate` rule still block main-thread edit no matter what.

Write rubric confirmed root cause must meet _before_ invoke — single-thread included (Criteria before dispatch; criteria written after result only confirm guess): reproduce symptom, all fail path go through it, classification named.

The `debug-verify` script enforce all guardrails in-code:

- **read-only looker** — one per idea, blind to each other; every stage prompt deny write/edit tool.
- **in-code bare-claim cut** — each finding cut to `root cause is <X> at <file:line>, classified as <logic|design-level>` before skeptic read; claims missing `(file:line, classification)` tuple dropped.
- **skeptic with different angle** — 2+ new skeptic per claim, prompted to _refute_ (one hit repro, one hit caller-graph, one hit classification).
- **canonical quorum tally** — per [forge-workflow's Pattern Canon](../forge-workflow/SKILL.md#pattern-canon) quorum table, include PARTIAL-when-unconfirmed rule (finding not actively confirmed by skeptic is unverified, not PASS).
- **`(file:line, classification)` dedupe** — across round, against all seen (include refuted idea).
- **stop on 2 consecutive no-survivor round or ceiling** — `ceil(N/2)` total round where N = initial idea count, min 4. (Generic "loop until done" pattern stop on dedupe-empty "nothing new" round; debug-verify fixed-idea variant stop on "no-survivor" round instead — see [Pattern Canon](../forge-workflow/SKILL.md#pattern-canon).)
- **returns round log + survivors + refute trail** in [Handoff Contract](../dispatch-agents/SKILL.md#handoff-contract) shape.

**Done when:** `debug-verify` return Handoff Contract with round log, survivors (each carry refute-responses), and refute trail; or loop-back stop condition met and user escalated.

## Step 3: Synthesize the confirmed root cause

1. Main thread read verified idea direct — no Arbiter agent; main thread synthesize true independent result (dispatch-agents hub-and-spoke). Dedupe against all seen (include refuted idea). Picked root cause must cite surviving skeptic dispatch and its refute-responses — cause surviving no real skeptic is unverified.
2. Many survive: pick one root cause all fail path go through; reject cause explaining only reported path. Cause stated no check caller is symptom, not root cause.
3. Classify:
   - **Logic bug** — wrong code in unit; no interface or contract wrong. Default here on fuzzy.
   - **Design-level fail** — named contract, interface, or data model wrong; fix cross file boundary. Must name wrong contract.
   - Tie-breaker for test-green/prod-red: existing test call real function on fail input and still pass, is design-level (test/prod split), route [plan](../plan/SKILL.md); existing test never call fail input (missing edge), is logic bug, route `tdd`. Concurrency: race on shared field fixed by local sync plus missing concurrent test, logic bug, route `tdd`; race requiring declaring shared service thread-safe across caller, design-level, name wrong contract.

**Done when:** one root cause named at `file:line` with one-sentence why, surviving skeptic dispatch cited, caller graph checked, classified as logic (default) or design-level (with wrong contract named).

## Step 4: Route the Fix

1. **Logic bug, route `tdd`:** hand over tiny repro with exact fail output as RED test; `tdd` drive RED-GREEN-REFACTOR for fix.
2. **Design-level fail, route `plan`:** re-draft affected scope, then `plan` (validate mode) validate, then `dispatch-agents`/`tdd` execute.
3. **Root cause dead or unused code:** propose delete (with `git grep` proving no caller), no patch.

HARD GATE apply — route root cause and repro; no prescribe patch. Invoke sibling skill and stop.

**Done when:** fix hand to `tdd` (logic bug, tiny repro + exact output as RED) or `plan` (design-level, wrong contract named), or delete proposed with proof no caller.

## Next Skills

| Skill                        | Use Case                                                                                                           |
| :--------------------------- | :----------------------------------------------------------------------------------------------------------------- |
| [tdd](../tdd/SKILL.md)       | Fix isolated logic bug — tiny repro (with exact output) is RED test                                                |
| [plan](../plan/SKILL.md)     | Design-level fail needing architecture/contract change                                                             |
| [review](../review/SKILL.md) | Existing review talk flagged design-level concern — resolve here, then [plan](../plan/SKILL.md) if re-draft needed |
