---
name: squads
description: Use when you need the squads skill map — route triggers, pipeline order, contract owners. Not a workflow; it routes each task to the skill that owns it.
disable-model-invocation: true
user-invocable: false
---

# squads

Router card. Each task routes by first match **directly** to the skill that owns it — mirrors the session `<squads-router>` block; no mandatory first hop. [dispatch-agents](../dispatch-agents/SKILL.md) is one destination among these, for fan-out: bulk/audit work and APPROVED plans, where its Governor picks inline vs composed and sizes the fleet.

## Route

This card and the session `<squads-router>` block are the router; the dispatch-agents table adds fleet shapes for work that runs there. Keep them in sync — on conflict, the owning skill's `## Next Skills` table wins.

| Trigger                                                                                               | Skill                                          |
| :---------------------------------------------------------------------------------------------------- | :--------------------------------------------- |
| Bulk/fan-out/whole-repo audit; APPROVED `docs/plan/*.plan.md`; fleet sizing                           | [dispatch-agents](../dispatch-agents/SKILL.md) |
| Problem to explore, no deliverable shape yet                                                          | [brainstorm](../brainstorm/SKILL.md)           |
| Request names a deliverable artifact (plan/spec/doc for a named feature); plan/specs pair to validate | [plan](../plan/SKILL.md)                       |
| Single new logic behavior; TDD red flag                                                               | [tdd](../tdd/SKILL.md)                         |
| Test, `Validate:`, or runtime fails unexpectedly — before any fix                                     | [debug](../debug/SKILL.md)                     |
| Verified diff to review; review feedback to resolve                                                   | [review](../review/SKILL.md)                   |
| Recurring bulk (any size), whole-repo audit, saved `/command` workflow                                | [forge-workflow](../forge-workflow/SKILL.md)   |

Pipeline: `brainstorm → plan → dispatch-agents → {tdd | debug} → review → (FAIL → review resolve, re-review ≤ 2)`. `forge-workflow` orthogonal — composed/bulk runs and saved `/command` workflows, fed by Governor Composition Specs.

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
