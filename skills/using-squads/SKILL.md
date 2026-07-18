---
name: using-squads
description: Entry skill for the `squads` plugin, routing to the right skill for your current task or situation.
user-invocable: false
disable-model-invocation: true
argument-hint: '[task or situation to route]'
---

# using-squads

## Entry decision — first match wins

| You arrive with…                                                                                                     | Start with                                                   |
| :------------------------------------------------------------------------------------------------------------------- | :----------------------------------------------------------- |
| Vague requirements, open solution space, or ≥2 distinct architectural approaches                                     | [parallel-brainstorming](../parallel-brainstorming/SKILL.md) |
| A clear feature or change needing a plan or spec                                                                     | [request-plan](../request-plan/SKILL.md)                     |
| A plan/specs pair to validate before execution                                                                       | [receive-plan](../receive-plan/SKILL.md)                     |
| An APPROVED `docs/plan/*.plan.md` ready to execute (multi-task)                                                      | [dispatch-agents](../dispatch-agents/SKILL.md)               |
| New logic to implement, or a TDD red flag (trivially-passing test, code before its test, GREEN with no observed RED) | [tdd](../tdd/SKILL.md)                                       |
| A test, `Validate:` command, or runtime failing unexpectedly — before any fix                                        | [parallel-debugging](../parallel-debugging/SKILL.md)         |
| A verified diff needing a fresh-eye review before merge                                                              | [request-code-review](../request-code-review/SKILL.md)       |
| Review feedback (human, bot, or subagent) to resolve                                                                 | [receive-code-review](../receive-code-review/SKILL.md)       |

If two rows could fit, the earlier one wins: ideation precedes planning, planning precedes execution, a bug precedes its fix. When in doubt, start upstream (brainstorm/plan) over mid-workflow (execute/review).

## Lifecycle — how skills hand off

```
parallel-brainstorming → request-plan → receive-plan → dispatch-agents / tdd
                                                       ↓
                                  parallel-debugging ← (Validate or runtime failure)
                                                       ↓
                                  tdd (logic bug) / request-plan (design-level)
                                                       ↓
                              request-code-review → receive-code-review → commit / PR
```

This only orients; each skill states its own exit routes in its "Next Skills" table.
