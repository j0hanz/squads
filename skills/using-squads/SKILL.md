---
name: using-squads
description: Router preamble injected by the session-start hook — routes every incoming task to dispatch-agents for triage and workflow selection. Never invoked directly.
user-invocable: false
disable-model-invocation: true
---

# using-squads

## Entry — triage through dispatch-agents first

Route every incoming task or user request to [dispatch-agents](../dispatch-agents/SKILL.md) first. Its Step 0 Triage classifies the request (first match wins) and selects the workflow and fleet shape — brainstorm, plan, execute, debug, or review. Skip it only for pure conversation or a one-shot edit answerable directly.

## Lifecycle — how skills hand off

```
user request → dispatch-agents (Step 0 Triage: pick workflow + fleet)
  ├─ open problem  → parallel-brainstorming → request-plan → receive-plan ─┐
  ├─ clear feature → request-plan → receive-plan ─┬──────────────────────┘
  │                                               └→ dispatch-agents (multi-task) / tdd (single task)
  ├─ failure       → parallel-debugging → tdd (logic bug) / request-plan (design-level)
  ├─ bulk / audit  → dispatch-agents patterns (fan out, adversarial verify, loop until done)
  └─ verified diff → request-code-review → receive-code-review → commit / PR
```

This only orients; each skill states its own exit routes in its "Next Skills" table.
