---
name: tdd
description: Use when new logic requires implementation, or a TDD red flag appears — trivially passing test, code before its test, or GREEN with no observed RED. Prefer parallel-debugging when the failure is in existing code, not fresh behavior.
argument-hint: '[feature or behavior to implement]'
---

# tdd

Autonomous TDD execution. **HARD GATE:** No implementation code WITHOUT a failing test — observe RED before every GREEN; a GREEN you never saw fail tests nothing.

## When NOT to use TDD

Escape hatches from the HARD GATE. Never self-invoke one silently — confirm via `AskUserQuestion` first (the tool supplies a free-text "Other"). Autonomous invocation (no user to ask): escape hatches cannot be confirmed — apply full TDD, unless the approved task's `Action:` text explicitly marks the work pure UI/CSS (and only that category); then skip TDD and state the reason in the [structured return](../dispatch-agents/SKILL.md#handoff-contract). Zero-logic boilerplate is not an autonomous escape hatch — if in doubt, write the test. Match the user's request to one of the escape-hatch categories below, then confirm via `AskUserQuestion`:

**Escape-hatch categories:**

- **Exploratory Spikes:** Implementation path unknown; throwaway code to "find the shape." **Mandatory:** once found, the spike MUST be discarded (`git stash drop`/delete, not committed) and re-implemented through RED-GREEN-REFACTOR. A spike is a sketch, never the shipped diff.
- **Trivial One-Liners:** Pure data mappings or standard boilerplate with zero logic.
- **Pure UI/CSS:** Visual styling needing manual "eye-balling," not logical assertions.

1. **Recommended** — Skip TDD: [matching category] because [specific reason].
2. **Alternative** — Use full TDD anyway + reason the escape hatch doesn't apply.

## Autonomous invocation (approved-plan handoff)

When invoked by `plan` (validate mode)/`dispatch-agents` (an APPROVED `docs/plan/<name>.plan.md` task) or by `parallel-debugging` (a minimal repro as the RED test), skip Step 0 and the Pre-TDD `AskUserQuestion` gates — scope, interface, and the reproducing case are already locked. Derive the interface/behavior and test path from the handoff, state them in one line, and enter the TDD Cycle at RED. All other gates (observed RED, N-1 check, Red Flags) still apply unchanged.

Per-origin delta:

- **`plan`/`dispatch-agents`:** derive interface, error conditions, and test path from the task block's `Action:`, `Satisfies:` (REQ text), `Files:`, and `Validate:`.
- **`parallel-debugging`:** derive the behavior under test from the repro and its verbatim failing output; skip Step 1 sub-step 2 (stub) — the implementation already exists and is the source of the failure, so run the repro test against the existing code and confirm RED.

## Step 0: Confirm Scope

**action:** `AskUserQuestion`.
_Skip this step entirely for an approved-plan handoff — see Autonomous invocation._

1. **Recommended:** Start TDD for [feature].
2. **Alternative:** Explore first, then start TDD — state why exploration is needed before code.

**Done when:** the user confirms the feature scope and entry point (start TDD vs explore-first).

## Pre-TDD: Define the Interface

**action:** `AskUserQuestion` to lock the shape before writing a test against it.
_For an approved-plan handoff, derive these from the task block instead of asking — see Autonomous invocation._

1. **Recommended:** `name(inputs) -> output`.
2. **Alternative:** Propose a different shape and justify it.

- Enumerate expected error conditions.
- Provide 2-3 call-site examples.
- State the target test file path.
- Start the **behavior list**: happy path + the enumerated errors; it grows by one edge case per RED cycle and is the coverage gauge for REFACTOR.
- **Gate:** run the relevant existing tests first — establish a clean baseline before adding new tests. If the baseline is RED, stop: route the pre-existing failure to `parallel-debugging`, or get user confirmation to proceed with the failing tests recorded and excluded from this cycle's GREEN criterion.

**Done when:** interface details, errors, and test path are locked and the user confirms.

## Step 1: RED (Failing Test)

_If JavaScript/TypeScript, read `${CLAUDE_PLUGIN_ROOT}/skills/tdd/references/js-ts-patterns.md` fully._
_CLAUDE_PLUGIN_ROOT is valid here because the plugin root contains skills/, so the harness-loaded path resolves._

1.1. Write the smallest test for one behavior.
1.2. Stub the implementation (e.g. `return null`) — just enough to compile/run. (Skip in `parallel-debugging` autonomous handoff — implementation already exists; see that paragraph in this skill.)
1.3. Run the test.
1.4. **Gate:** confirm FAILURE. A test that passes immediately tests nothing — delete and rewrite it.

**Done when:** the test runs and fails for the targeted behavior (RED confirmed), not the environment.

## Step 2: GREEN (Make It Pass)

_If unsure how minimal is minimal, read `${CLAUDE_PLUGIN_ROOT}/skills/tdd/references/minimal-impl-examples.md` fully (examples are Python; the principle applies to any language)._

1. Checkpoint the working tree before editing.
2. Write the smallest implementation that satisfies the test — no speculative generality.
3. No code added "just in case" — only what the current test requires.
4. 3 failed attempts on the same test → escalate directly to `parallel-debugging` (reproduce and re-isolate the root cause) or [plan](../plan/SKILL.md) (if the design itself is wrong).

### N-1 Test (False-Green Elimination)

**Gate:** run this check on the FIRST behavior of a session. For subsequent behaviors in the same session, the harness is trusted — skip the N-1 revert/restore unless the test arrived GREEN on first run with no observed RED.

Before trusting a passing test:

1. Revert the implementation to the Step 1 stub (or remove the body, leaving only the signature).
2. Run the test — confirm RED.
3. Restore the implementation.
4. Run the test — confirm GREEN.

**Done when:** the test passes on the minimal implementation and the N-1 check holds (revert → RED, restore → GREEN).

## Step 3: REFACTOR (Clean Up)

- **Gate:** only proceed while GREEN.
- Improve structure (naming, deduplication) without changing behavior.
- Never interleave a behavior fix with a refactor — separate passes.
- Re-run tests after every refactor; must stay GREEN.
- **Done when:** one full pass over the diff yields no rename, deduplication, or extraction you would act on AND the relevant tests GREEN; then evaluate coverage against the behavior list (gaps → back to RED; else hand off).

## Strict Rules

- Mock only true externals (databases, APIs, network) — never mock the code under test.
- No second test until the first has completed its full RED-GREEN-REFACTOR cycle.
- If the test itself is wrong (not the implementation), return to RED, state why, then rewrite it — don't edit a test to force a pass (see Red Flags).

## Red Flags — Stop Rationalizing, Delete and Restart

Any of these means you've left TDD — the fix is the same every time. Don't argue; don't "adapt" what you wrote.

- Implementation written before, or without, a failing test for the behavior it adds (HARD GATE violation).
- The test trivially passes without exercising the logic under test (e.g. asserts a constant the stub returns, mocks the unit itself, or never calls the code path).
- Tests retrofitted to already-written code ("tests-after"), or a test edited to force a pass.
- Self-talk: "too simple to test", "I already manually tested it", "tests after achieve the same purpose", "it's the spirit that matters", "this is different because...".
- Skipping the N-1 check on the first behavior of a session because "it obviously would fail" — a test you haven't seen fail tests nothing.
- A GREEN that arrives on the first run with no RED observed for that behavior.
- Keeping code-first output "as reference" or "to adapt" instead of deleting it.

**All of these mean:** delete the code-first implementation, re-enter the cycle at RED, and run the test to confirm it fails before re-implementing.

## Next Skills

On full behavior-list coverage and a clean REFACTOR, run the full test suite one final time and report the results. If the final run fails: a failure in the behavior just built re-enters the cycle at RED; an unrelated new failure routes to `parallel-debugging`. Never report done over a failing suite.

| Skill                                                | Use Case                                                       |
| :--------------------------------------------------- | :------------------------------------------------------------- |
| [review](../review/SKILL.md)                         | Fresh-eye review of the completed diff                         |
| [parallel-debugging](../parallel-debugging/SKILL.md) | Stuck GREEN (Step 2 escalation) or unrelated final-run failure |
| [plan](../plan/SKILL.md)                             | Design itself proved wrong mid-cycle                           |
