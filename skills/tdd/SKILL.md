---
name: tdd
description: Use when new logic needs implementation, or a TDD red flag appears — trivially passing test, code before its test, GREEN with no observed RED. Prefer debug when the failure is in existing code.
argument-hint: '[feature or behavior to implement]'
---

# tdd

**HARD GATE:** No code WITHOUT a failing test. See RED before GREEN. GREEN without an observed failing test proves nothing.

## When NOT to use TDD

Escape hatch from the HARD GATE. Never self-invoke silently: match the request to a category below, then confirm via `AskUserQuestion`. Autonomous invocation (no user to ask): no escape hatch — full TDD, unless the approved task's `Action:` text says pure UI/CSS; then skip TDD and state the reason in the [structured return](../squads/SKILL.md#handoff-contract). Zero-logic boilerplate gets no auto escape hatch. Doubt? Write the test.

**Escape-hatch categories:**

- **Exploratory Spikes:** code path unknown; throwaway code to "find the shape." **Mandatory:** once found, the spike MUST be thrown away (`git stash drop`/delete, no commit) and re-built through RED-GREEN-REFACTOR. A spike is a sketch, not a shipped diff.
- **Trivial One-Liners:** pure data mapping or standard boilerplate, zero logic.
- **Pure UI/CSS:** visual styling needing manual eyeballing, no logic to assert.

1. **Recommended** — Skip TDD: [matching category] because [specific reason].
2. **Alternative** — Full TDD anyway + why the escape hatch doesn't apply.

## Autonomous invocation (approved-plan handoff)

Invoked by `plan`/`dispatch-agents` (an APPROVED `docs/plan/<name>.plan.md` task) or `debug`: skip Step 0 and the Pre-TDD `AskUserQuestion` gates — scope, interface, repro case are locked. Derive interface/behavior and test path from the handoff; state it in one line. Enter the TDD Cycle at RED. All other gates (observed RED, N-1 check, Red Flags) still apply.

Per-origin delta:

- **`plan`/`dispatch-agents`:** derive interface, errors, test path from the task block's `Action:`, `Satisfies:`, `Files:`, `Validate:`.
- **`debug`:** derive behavior from the repro and verbatim failing output. Skip Step 1 sub-step 2 (stub) — the implementation exists and is the source of the failure. Run the repro test against existing code, confirm RED.

## Step 0: Confirm Scope

**action:** `AskUserQuestion`. _Skip for approved-plan handoff._

1. **Recommended:** Start TDD for [feature].
2. **Alternative:** Explore first, then TDD — state why exploration is needed before code.

**Done when:** user confirms feature scope and entry point.

## Pre-TDD: Define the Interface

**action:** `AskUserQuestion` to lock the shape before any test. _For approved-plan handoff, derive from the task block, no ask._

1. **Recommended:** `name(inputs) -> output`.
2. **Alternative:** propose a different shape, justify.

- List expected errors.
- Give 2-3 call-site examples.
- State the target test file path.
- Start the **behavior list**: happy path + errors; grows one edge case per RED cycle. Coverage gauge for REFACTOR.
- **Gate:** run existing tests first — clean baseline required. Baseline RED → stop: route pre-existing failures to `debug`, or get user confirmation to proceed with those tests excluded from this cycle's GREEN.

**Done when:** interface, errors, test path locked and confirmed.

## Step 1: RED (Failing Test)

_JS/TS → read `${CLAUDE_PLUGIN_ROOT}/skills/tdd/references/js-ts-patterns.md` fully (plugin root contains skills/, path resolves)._

1. Write the smallest test for one behavior.
2. Stub the implementation (e.g. `return null`) — just enough to compile/run. (Skip in `debug` handoff — implementation exists.)
3. Run the test.
4. **Gate:** confirm FAILURE. A test that passes immediately tests nothing — delete and rewrite.

**Done when:** test runs and fails for the targeted behavior (RED confirmed), not the environment.

## Step 2: GREEN (Make It Pass)

_If unsure, read `${CLAUDE_PLUGIN_ROOT}/skills/tdd/references/minimal-impl-examples.md` fully (examples Python, principle any language)._

1. Checkpoint the working tree before editing.
2. Write the smallest implementation satisfying the test — no speculative generality.
3. No code "just in case" — only what the current test needs.
4. 3 failed attempts on the same test → escalate to `debug` (reproduce, re-isolate root cause) or [plan](../plan/SKILL.md) (design wrong).

### N-1 Test (False-Green Elimination)

**Gate:** run on the FIRST behavior of the session. Later behaviors: harness trusted — skip the revert/restore unless a test arrived GREEN on first run with no observed RED.

Before trusting a passing test:

1. Revert implementation to the Step 1 stub (or remove body, keep signature).
2. Run test — confirm RED.
3. Restore implementation.
4. Run test — confirm GREEN.

**Done when:** test passes on the minimal implementation and the N-1 check holds (revert → RED, restore → GREEN).

## Step 3: REFACTOR (Clean Up)

- **Gate:** only proceed while GREEN.
- Improve structure (naming, dedup) without changing behavior.
- Never mix behavior fixes with refactoring — separate passes.
- Re-run tests after every refactor. Must stay GREEN.
- **Done when:** one full pass over the diff yields no rename, dedup, or extraction to act on AND relevant tests GREEN. Then evaluate coverage against the behavior list (gaps → back to RED; else hand off).

## Strict Rules

- Mock only true externals (databases, APIs, network) — never mock the code under test.
- No second test until the first completes a full RED-GREEN-REFACTOR cycle.
- Test wrong (not the implementation) → return to RED, state why, rewrite — never edit a test to force a pass (see Red Flags).

## Red Flags — Stop Rationalizing, Delete and Restart

Any of these means you left TDD — same fix every time. No arguing; no "adapting" what you wrote.

- Implementation written before or without a failing test for the behavior it adds (HARD GATE violation).
- Test trivially passes without exercising logic (asserts constant stub returns, mocks the unit itself, never calls the code path).
- Tests retrofitted to written code ("tests-after"), or a test edited to force a pass.
- Self-talk: "too simple to test", "manually tested it", "tests after achieve the same purpose", "spirit matters", "this is different because...".
- N-1 check skipped on the first behavior because it "obviously would fail" — a test not seen failing tests nothing.
- GREEN arrives on first run with no RED observed for the behavior. GREEN-without-RED is a test-discipline failure (the test is wrong, not the code) — owned by tdd, not debug.
- Code-first output kept "as reference" or "to adapt" instead of deleted.

**All of these mean:** delete the code-first implementation, re-enter the cycle at RED, run the test and confirm failure before re-implementing.

## Next Skills

On full behavior-list coverage and clean REFACTOR: run the full test suite one final time, report results. Final run fails → failure in the behavior just built re-enters the cycle at RED; unrelated new failure routes to `debug`. Never report done over a failing suite.

| Skill                        | Use Case                                                       |
| :--------------------------- | :------------------------------------------------------------- |
| [review](../review/SKILL.md) | Fresh-eye review of completed diff                             |
| [debug](../debug/SKILL.md)   | Stuck GREEN (Step 2 escalation) or unrelated final-run failure |
| [plan](../plan/SKILL.md)     | Design itself proved wrong mid-cycle                           |
