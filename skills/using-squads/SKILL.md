---
name: using-squads
description: Entry skill for the `squads` plugin, routing every task to dispatch-agents, which triages it and selects the multi-agent workflow.
user-invocable: false
disable-model-invocation: true
argument-hint: '[task or situation to route]'
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
