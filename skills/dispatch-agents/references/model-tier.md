# Model-tier per role

Canonical role→model tier mapping for dispatched subagents. One swap-point when model pricing or availability shifts. Guidance, not config: where the Agent tool exposes a `model` param, set it per this table; where it doesn't, encode the tier as a prompt instruction ("think carefully, verify before answering" for strong/strongest; "quick best-effort, one pass" for cheap).

| Role                                   | Tier      | Why                                                                 |
| -------------------------------------- | --------- | ------------------------------------------------------------------- |
| Ideator (request-plan)                 | cheap     | Divergent breadth; main thread merges — misses caught downstream    |
| Investigator (parallel-debugging)      | cheap     | Read-only root-cause hunt; volume scales with hypothesis count      |
| Classifier (classify & act)            | cheap     | Mechanical one-label-per-item routing                               |
| Synthesizer (request-plan blueprint)   | strong    | Reconciles competing proposals; judgment over taste                 |
| Skeptic (parallel-debugging)           | strong    | Refutation needs care; cheap skeptic misses the flaw it should find |
| Critic (receive-plan)                  | strong    | 3-lens spec review; a miss cascades into rework                     |
| Reviewer (request-code-review)         | strong    | Fresh-eye correctness/security; weak reviewer ships bugs            |
| Worker (long-running builds)           | strong    | Implements; cheap produces diffs that need costly rework            |
| Orchestrator (long-running builds)     | strong    | Plans milestones; weak plan cascades into bad execution             |
| Validator (long-running builds)        | strongest | Static+behavior check on shipped milestone; last gate before merge  |
| Judge (tournament / generate & filter) | strongest | Final selection; bias/disappointment cost highest                   |

**Default when tier unknown:** inherit. Don't block dispatch on tier doubt — a dispatched subagent at the wrong tier beats no subagent.
