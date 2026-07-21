---
name: squads
description: Use when you need the squads skill map — route triggers, pipeline order, contract owners. Not a workflow; concrete tasks go to dispatch-agents.
disable-model-invocation: true
user-invocable: false
---

# squads

Router card. Every concrete task enters [dispatch-agents](../dispatch-agents/SKILL.md) Step 0 Governor first — it picks inline vs composed and routes over this map.

## Route

dispatch-agents routing tables are canonical; the squads card mirrors — on mismatch, dispatch-agents wins.

| Trigger                                                                                               | Skill                                          |
| :---------------------------------------------------------------------------------------------------- | :--------------------------------------------- |
| Any new task/request; APPROVED `docs/plan/*.plan.md`; doubt                                           | [dispatch-agents](../dispatch-agents/SKILL.md) |
| Problem to explore, no deliverable shape yet                                                          | [brainstorm](../brainstorm/SKILL.md)           |
| Request names a deliverable artifact (plan/spec/doc for a named feature); plan/specs pair to validate | [plan](../plan/SKILL.md)                       |
| Single new logic behavior; TDD red flag                                                               | [tdd](../tdd/SKILL.md)                         |
| Test, `Validate:`, or runtime fails unexpectedly — before any fix                                     | [debug](../debug/SKILL.md)                     |
| Verified diff to review; review feedback to resolve                                                   | [review](../review/SKILL.md)                   |
| Recurring bulk (any size), whole-repo audit, saved `/command` workflow                                | [forge-workflow](../forge-workflow/SKILL.md)   |

Pipeline: `brainstorm → plan → dispatch-agents → {tdd | debug} → review → (FAIL re-fix → dispatch-agents)`. `forge-workflow` orthogonal — composed/bulk runs and saved `/command` workflows, fed by Governor Composition Specs.

Each skill's `## Next Skills` table owns its outgoing edges; on conflict, skill table wins — update this card to match.

## Contracts

| Contract                                            | Owner                                                                                          |
| :-------------------------------------------------- | :--------------------------------------------------------------------------------------------- |
| Handoff Contract (subagent return)                  | [dispatch-agents #handoff-contract](../dispatch-agents/SKILL.md#handoff-contract)              |
| Dispatch invariants                                 | [dispatch-agents #invariants](../dispatch-agents/SKILL.md#invariants--apply-to-every-dispatch) |
| Model & fan-out policy (flat `haiku`, 5-min budget) | [dispatch-agents #model--fan-out-policy](../dispatch-agents/SKILL.md#model--fan-out-policy)    |
| Pattern Canon, quorum, recipes                      | [forge-workflow #pattern-canon](../forge-workflow/SKILL.md#pattern-canon)                      |
| `<untrusted_context>` wrap convention               | [plan #step-1-discovery](../plan/SKILL.md#step-1-discovery)                                    |

## Naming

Pipeline skills: plain noun (`brainstorm`, `plan`, `debug`, `review`). Fan-out execution: verb-noun (`dispatch-agents`, `forge-workflow`). `tdd` grandfathered. Fan-out semantics live in `description:` frontmatter, never the name.
