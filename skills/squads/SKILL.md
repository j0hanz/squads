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

| Trigger                                                                                                                   | Skill                                                                                                 |
| :------------------------------------------------------------------------------------------------------------------------ | :---------------------------------------------------------------------------------------------------- |
| Bulk/fan-out/whole-repo audit; APPROVED `docs/plan/*.plan.md`; fleet sizing                                               | [dispatch-agents](../dispatch-agents/SKILL.md)                                                        |
| Problem to explore, no deliverable shape yet                                                                              | [brainstorm](../brainstorm/SKILL.md)                                                                  |
| Request names a deliverable artifact (plan/spec/doc for a named feature); plan/specs pair to validate                     | [plan](../plan/SKILL.md)                                                                              |
| Single new logic behavior; TDD red flag                                                                                   | [tdd](../tdd/SKILL.md)                                                                                |
| Test, `Validate:`, or runtime fails unexpectedly — before any fix                                                         | [debug](../debug/SKILL.md)                                                                            |
| Verified diff to review; review feedback to resolve                                                                       | [review](../review/SKILL.md)                                                                          |
| Saved `/command` workflow (recurring bulk big enough to forge once); debug-verify recipe is reached via `debug`, not here | [forge-workflow](../forge-workflow/SKILL.md)                                                          |
| Session resume / crashed pipeline — "resume", "continue", or session start with in-flight artifacts                       | [squads](../squads/SKILL.md#resume) — inspects artifacts, delegates to the owning skill's resume step |

Pipeline: `brainstorm → plan → dispatch-agents → {tdd | debug} → review → (FAIL → review resolve, re-review ≤ 2)`. `forge-workflow` orthogonal — composed/bulk runs and saved `/command` workflows, fed by Governor Composition Specs.

Each skill's `## Next Skills` table owns its outgoing edges; on conflict, skill table wins — update this card to match.

## Contracts

| Contract                                            | Owner                                                                                          |
| :-------------------------------------------------- | :--------------------------------------------------------------------------------------------- |
| Handoff Contract (subagent return)                  | [dispatch-agents #handoff-contract](../dispatch-agents/SKILL.md#handoff-contract)              |
| Dispatch invariants                                 | [dispatch-agents #invariants](../dispatch-agents/SKILL.md#invariants--apply-to-every-dispatch) |
| Model & fan-out policy (flat `haiku`, 5-min budget) | [dispatch-agents #model--fan-out-policy](../dispatch-agents/SKILL.md#model--fan-out-policy)    |
| Pattern Canon, quorum                               | [forge-workflow #pattern-canon](../forge-workflow/SKILL.md#pattern-canon)                      |
| Recipe Catalog                                      | [forge-workflow #recipe-catalog](../forge-workflow/SKILL.md#recipe-catalog)                    |
| `<untrusted_context>` wrap convention               | [plan #step-1-discovery](../plan/SKILL.md#step-1-discovery)                                    |

## Resume

Thin delegator — locate the in-flight pipeline from state artifacts and route to the owning skill's own resume step (cite, don't reimplement). On conflict with a skill's own re-entry rule, the skill wins.

| Artifact present                               | Route to                                       | Resume step                                                      |
| :--------------------------------------------- | :--------------------------------------------- | :--------------------------------------------------------------- |
| `docs/design/.wip-<topic>-phase*.md`           | [brainstorm](../brainstorm/SKILL.md)           | read latest `.wip-*`, skip re-running Phase 1                    |
| `docs/plan/<name>.plan.md`, `Status: DRAFT`    | [plan](../plan/SKILL.md) (validate mode)       | re-validate the pair; REVISE loops per Headless Fallback         |
| `docs/plan/<name>.plan.md`, `Status: APPROVED` | [dispatch-agents](../dispatch-agents/SKILL.md) | re-read plan, re-run each task's `Validate:` in dependency order |
| `docs/plan/<name>.plan.md` + `Review pass: N`  | [review](../review/SKILL.md)                   | re-review pass N; 2-pass cap                                     |
| None of the above                              | fresh pipeline                                 | route per the Route table above                                  |

No new artifact is created here; the row only inspects what the other skills already write. If multiple artifacts exist for different topics, ask the user which pipeline to resume (`AskUserQuestion`, max 4) — never guess.

## Naming

Pipeline skills: plain noun (`brainstorm`, `plan`, `debug`, `review`). Fan-out execution: verb-noun (`dispatch-agents`, `forge-workflow`). `tdd` grandfathered. Fan-out semantics live in `description:` frontmatter, never the name.
