---
name: tdd
description: Use when new logic requires implementation, or a TDD red flag appears — trivially passing test, code before its test, or GREEN with no observed RED. Prefer debug when the failure is in existing code, not fresh behavior.
argument-hint: '[feature or behavior to implement]'
---

# tdd

Auto TDD. **HARD GATE:** No code WITHOUT fail test. See RED before GREEN. GREEN not seen fail test nothing.

## When NOT to use TDD

Escape hatch from HARD GATE. Never self-invoke silent. Confirm via `AskUserQuestion` first. Auto invoke (no user): escape hatch no confirm. Do full TDD, unless approved task `Action:` text say pure UI/CSS. Then skip TDD, say reason in [structured return](../dispatch-agents/SKILL.md#handoff-contract). Zero-logic boilerplate no auto escape hatch. Doubt? Write test. Match user request to escape-hatch category below, confirm via `AskUserQuestion`:

**Escape-hatch categories:**

- **Exploratory Spikes:** Code path unknown. Throwaway code "find shape." **Mandatory:** once found, spike MUST be thrown away (`git stash drop`/delete, no commit). Re-make through RED-GREEN-REFACTOR. Spike is sketch, not shipped diff.
- **Trivial One-Liners:** Pure data map or standard boilerplate, zero logic.
- **Pure UI/CSS:** Visual style need manual "eye-balling", no logic assert.

1. **Recommended** — Skip TDD: [matching category] because [specific reason].
2. **Alternative** — Use full TDD anyway + reason escape hatch no apply.

## Autonomous invocation (approved-plan handoff)

Invoked by `plan`/`dispatch-agents` (an APPROVED `docs/plan/<name>.plan.md` task) or `debug`. Skip Step 0 and Pre-TDD `AskUserQuestion` gates. Scope, interface, repro case locked. Derive interface/behavior and test path from handoff. State in one line. Enter TDD Cycle at RED. Other gates (observed RED, N-1 check, Red Flags) still apply.

Per-origin delta:

- **`plan`/`dispatch-agents`:** derive interface, error, test path from task block `Action:`, `Satisfies:`, `Files:`, `Validate:`.
- **`debug`:** derive behavior from repro and verbatim fail output. Skip Step 1 sub-step 2 (stub) — implementation already exist, is source of fail. Run repro test against existing code, confirm RED.

## Step 0: Confirm Scope

**action:** `AskUserQuestion`.
_Skip for approved-plan handoff — see Autonomous invocation._

1. **Recommended:** Start TDD for [feature].
2. **Alternative:** Explore first, then start TDD — state why explore needed before code.

**Done when:** user confirm feature scope and entry point.

## Pre-TDD: Define the Interface

**action:** `AskUserQuestion` to lock shape before test.
_For approved-plan handoff, derive from task block, no ask._

1. **Recommended:** `name(inputs) -> output`.
2. **Alternative:** Propose different shape, justify.

- List expected errors.
- Give 2-3 call-site examples.
- State target test file path.
- Start **behavior list**: happy path + errors. Grows one edge case per RED cycle. Coverage gauge for REFACTOR.
- **Gate:** run existing tests first. Clean baseline. If baseline RED, stop: route pre-existing fail to `debug`, or get user confirm to proceed with fail tests excluded from cycle's GREEN.

**Done when:** interface details, errors, test path locked and user confirm.

## Step 1: RED (Failing Test)

_If JS/TS, read `${CLAUDE_PLUGIN_ROOT}/skills/tdd/references/js-ts-patterns.md` fully._
_CLAUDE_PLUGIN_ROOT valid here. Plugin root contains skills/, path resolves._

1.1. Write smallest test for one behavior.
1.2. Stub implementation (e.g. `return null`) — enough to compile/run. (Skip in `debug` handoff — implementation exist.)
1.3. Run test.
1.4. **Gate:** confirm FAILURE. Test pass immediately test nothing — delete and rewrite.

**Done when:** test runs and fail for targeted behavior (RED confirmed), not environment.

## Step 2: GREEN (Make It Pass)

_If unsure, read `${CLAUDE_PLUGIN_ROOT}/skills/tdd/references/minimal-impl-examples.md` fully (examples Python, principle any language)._

1. Checkpoint working tree before edit.
2. Write smallest implementation satisfy test — no speculative generality.
3. No code "just in case" — only what current test need.
4. 3 fail attempts same test → escalate to `debug` (reproduce, re-isolate root cause) or [plan](../plan/SKILL.md) (if design wrong).

### N-1 Test (False-Green Elimination)

**Gate:** run check on FIRST behavior of session. For next behaviors, harness trusted — skip N-1 revert/restore unless test arrived GREEN first run with no observed RED.

Before trust passing test:

1. Revert implementation to Step 1 stub (or remove body, leave signature).
2. Run test — confirm RED.
3. Restore implementation.
4. Run test — confirm GREEN.

**Done when:** test pass on minimal implementation and N-1 check hold (revert → RED, restore → GREEN).

## Step 3: REFACTOR (Clean Up)

- **Gate:** only proceed while GREEN.
- Improve structure (naming, dedup) no change behavior.
- Never mix behavior fix with refactor — separate passes.
- Re-run tests after every refactor. Must stay GREEN.
- **Done when:** one full pass over diff yield no rename, dedup, or extraction to act on AND relevant tests GREEN. Then evaluate coverage against behavior list (gaps → back to RED; else hand off).

## Strict Rules

- Mock only true externals (databases, APIs, network) — never mock code under test.
- No second test until first complete full RED-GREEN-REFACTOR cycle.
- If test wrong (not implementation), return to RED, state why, rewrite — no edit test to force pass (see Red Flags).

## Red Flags — Stop Rationalizing, Delete and Restart

Any of these mean left TDD — fix same every time. No argue; no "adapt" what wrote.

- Implementation written before or without fail test for behavior it adds (HARD GATE violation).
- Test trivially pass without exercise logic (e.g. assert constant stub returns, mock unit itself, never call code path).
- Tests retrofitted to written code ("tests-after"), or test edited to force pass.
- Self-talk: "too simple to test", "manually tested it", "tests after achieve same purpose", "spirit matters", "this different because...".
- Skip N-1 check on first behavior because "obviously would fail" — test not seen fail test nothing.
- GREEN arrive first run with no RED observed for behavior.
- Keep code-first output "as reference" or "to adapt" instead of delete.

**All of these mean:** delete code-first implementation, re-enter cycle at RED, run test confirm fail before re-implement.

## Next Skills

Full behavior-list coverage and clean REFACTOR. Run full test suite one final time, report results. If final run fail: fail in behavior just built re-enter cycle at RED; unrelated new fail route to `debug`. Never report done over failing suite.

| Skill                        | Use Case                                                       |
| :--------------------------- | :------------------------------------------------------------- |
| [review](../review/SKILL.md) | Fresh-eye review of completed diff                             |
| [debug](../debug/SKILL.md)   | Stuck GREEN (Step 2 escalation) or unrelated final-run failure |
| [plan](../plan/SKILL.md)     | Design itself proved wrong mid-cycle                           |
