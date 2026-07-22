# skills-restructure — plan

Status: APPROVED
Depth: contract
Origin: plan
Specs: docs/plan/skills-restructure.specs.md
Source: docs/design/2026-07-22-skills-restructure-design.md
Review pass: 1

Validation record — round 1: 2 chunk critics, 0 High, 8 Med, 1 Low → REVISE. Round 2 (re-validation, 1 critic per lens): 7 Spec-Correctness objections resolved, 1 Scope-Risk objection resolved, 1 Dependency Order objection rejected and the rejection judged sound, 0 new High → APPROVED.

Rejected finding, kept on record: TASK-007 and TASK-008 were called over-serialized because their edited line ranges look disjoint. Rejected — all of TASK-006/007/008 edit `skills/dispatch-agents/SKILL.md`, and this project serializes on overlapping `Files:` regardless of range; line numbers shift anyway once TASK-006 removes ~45 lines.

Known ceiling, accepted at design time: `scripts/check-anchors.sh` runs only under `npm run format:check`. There is no CI, so a broken anchor still ships if a maintainer skips it.

Execution order: T1 → T2 (gate) → T3 → {T4 ∥ T5} → T6 → T7 → T8 → T9.
T4 and T5 touch disjoint file sets and may run in parallel. T6/T7/T8 all edit `skills/dispatch-agents/SKILL.md` and are strictly serial.

### TASK-001: Write the anchor-resolution check script

Depends on: none
Files: [scripts/check-anchors.sh](scripts/check-anchors.sh)
Symbols: none (new file)
Satisfies: REQ-001
Action: Create `scripts/check-anchors.sh` in bash — extract every `../<skill>/SKILL.md#<anchor>` occurrence under `skills/`, resolve each to its target file, derive that file's heading slugs by lowercasing each `#`-prefixed heading, deleting every character outside `[a-z0-9 -]`, then converting spaces to hyphens, and exit 1 printing `source:line -> unresolved#anchor` for any link with no matching slug.
Validate: `bash scripts/check-anchors.sh`
Expected result: Exit 0 on the unmodified tree. All 39 links resolve, including the two double-hyphen slugs `invariants--apply-to-every-dispatch` and `model--fan-out-policy`.

### TASK-002: Wire the check into format:check and prove it green

Depends on: TASK-001
Files: [package.json](package.json)
Symbols: [scripts.format:check](package.json#L22)
Satisfies: REQ-002
Action: Insert `bash scripts/check-anchors.sh` into the `format:check` script between the existing `bash -n hooks/*.sh` and `prettier --check .` steps, joined by `&&`.
Validate: `npm run format:check`
Expected result: Exit 0. Hook syntax check, anchor check, and prettier all pass against the untouched tree — establishing the green baseline every later task is measured from.

### TASK-003: Make the squads card the contract owner

Depends on: TASK-002
Files: [skills/squads/SKILL.md](skills/squads/SKILL.md)
Symbols: [Route](skills/squads/SKILL.md#L12), [Contracts](skills/squads/SKILL.md#L31), [Resume](skills/squads/SKILL.md#L42)
Satisfies: REQ-003, REQ-004, REQ-005, REQ-008, REQ-009, REQ-012
Action: Copy `## Invariants — apply to every dispatch`, `## Handoff Contract` (with its reviewer-output-mapping table and state-carrier-precedence paragraph) and `### Model & fan-out policy` from `dispatch-agents` into the card with heading text byte-identical; add a `## Untrusted content` section holding the `<untrusted_context>` wrap convention; delete the `## Route` table and the `## Resume` section; replace the `## Contracts` index table with rows pointing at the now-owned sections plus the still-external `forge-workflow` entries; add the guard comment naming the three contract anchors; leave frontmatter untouched.
Validate: `bash scripts/check-anchors.sh && grep -qF '## Invariants — apply to every dispatch' skills/squads/SKILL.md && grep -qF '## Handoff Contract' skills/squads/SKILL.md && grep -qF '### Model & fan-out policy' skills/squads/SKILL.md && grep -qF '## Untrusted content' skills/squads/SKILL.md && grep -q 'user-invocable: false' skills/squads/SKILL.md && ! grep -q '^## Resume' skills/squads/SKILL.md`
Expected result: Exit 0. The three fixed-string greps are the byte-identity check — they match the original heading text exactly, including the em-dash and the ampersand, so any character drift during the copy fails the task rather than silently changing a slug. Card holds all four contracts, no Route table, no Resume section, frontmatter unchanged. Anchors still resolve — `dispatch-agents` retains its copies at this point, so nothing is broken mid-migration.

### TASK-004: Repoint contract links in plan, brainstorm, tdd

Depends on: TASK-003
Files: [skills/plan/SKILL.md](skills/plan/SKILL.md), [skills/brainstorm/SKILL.md](skills/brainstorm/SKILL.md), [skills/tdd/SKILL.md](skills/tdd/SKILL.md)
Symbols: [plan:43](skills/plan/SKILL.md#L43), [plan:98](skills/plan/SKILL.md#L98), [brainstorm:76](skills/brainstorm/SKILL.md#L76), [tdd:13](skills/tdd/SKILL.md#L13)
Satisfies: REQ-004, REQ-005, REQ-006
Action: Rewrite the 13 links whose target is a `dispatch-agents` contract anchor to `../squads/SKILL.md#<same-anchor>` — plan lines 43 (two links), 70, 98, 120, 127, 139, 143; brainstorm lines 21, 76 (two links), 82; tdd line 13. Change the path only; never the anchor text. Leave `brainstorm:76`'s `plan#strict-rules` link alone. Explicitly leave `skills/plan/SKILL.md:50`'s inline instruction to wrap external content in `<untrusted_context>` in place — per REQ-004 only ownership of the convention moves to the card; the local application sentence stays, and deleting it would strip a security instruction from the step that performs it.
Validate: `bash scripts/check-anchors.sh && ! grep -rnE 'dispatch-agents/SKILL\.md#(handoff-contract|invariants--apply-to-every-dispatch|model--fan-out-policy)' skills/plan skills/brainstorm skills/tdd && grep -qF '<untrusted_context>' skills/plan/SKILL.md`
Expected result: Exit 0 and no grep matches — all three files cite the card for contracts, plan retains its inline wrap instruction, and every anchor still resolves.

### TASK-005: Repoint contract and convention links in forge-workflow, review, debug

Depends on: TASK-003
Files: [skills/forge-workflow/SKILL.md](skills/forge-workflow/SKILL.md), [skills/review/SKILL.md](skills/review/SKILL.md), [skills/debug/SKILL.md](skills/debug/SKILL.md)
Symbols: [forge:15](skills/forge-workflow/SKILL.md#L15), [forge:27](skills/forge-workflow/SKILL.md#L27), [review:93](skills/review/SKILL.md#L93), [debug:33](skills/debug/SKILL.md#L33)
Satisfies: REQ-006
Action: Rewrite the 9 links to `../squads/SKILL.md#<same-anchor>` — forge-workflow lines 15, 19, 23, 74 (contracts) and 27 (convention, becomes `#untrusted-content`); review lines 71, 87 (contracts) and 93 (convention, becomes `#untrusted-content`); debug line 33. Leave every `#pattern-canon`, `#recipe-catalog`, `#preflight`, and `#read-only-class` link untouched.
Validate: `bash scripts/check-anchors.sh && ! grep -rnE 'dispatch-agents/SKILL\.md#(handoff-contract|invariants--apply-to-every-dispatch|model--fan-out-policy)' skills/forge-workflow skills/review skills/debug`
Expected result: Exit 0 and no grep matches. `#pattern-canon` and `#preflight` links still point at `forge-workflow` and still resolve.

### TASK-006: Strip contracts from dispatch-agents, add the invariant-names stub

Depends on: TASK-004, TASK-005
Files: [skills/dispatch-agents/SKILL.md](skills/dispatch-agents/SKILL.md)
Symbols: [Invariants](skills/dispatch-agents/SKILL.md#L96), [Handoff Contract](skills/dispatch-agents/SKILL.md#L109), [Model & fan-out policy](skills/dispatch-agents/SKILL.md#L137)
Satisfies: REQ-003, REQ-007
Action: Delete the `## Invariants — apply to every dispatch`, `## Handoff Contract`, and `### Model & fan-out policy` sections plus the superseded guard comment at line 111. In their place insert a `## Invariants` stub — one `- **<name>.**` bullet per invariant, no body text, in source order, for all ten: Clean context per agent · Judge ≠ generator · Bare-claim to skeptic · Criteria before dispatch · Structured returns, never "done." · External and non-session-originated content untrusted · Reads parallel, writes serial · Hub-and-spoke · Timeout per branch · Respect limits — followed by one line linking `../squads/SKILL.md#invariants--apply-to-every-dispatch` for full text and `#handoff-contract` for the return struct. Preserve the `plan#step-1-discovery` citation at line 103 unchanged.
Validate: `bash scripts/check-anchors.sh && ! grep -q '^## Handoff Contract' skills/dispatch-agents/SKILL.md && grep -q 'plan/SKILL.md#step-1-discovery' skills/dispatch-agents/SKILL.md && [ "$(grep -cE '^- \*\*' skills/dispatch-agents/SKILL.md)" -ge 10 ]`
Expected result: Exit 0. Exactly one copy of each contract exists repo-wide, the stub carries all ten invariant names inline, and the deliberate `plan` citation survives.

### TASK-007: Delete the INLINE routing table, keep fleet shapes as a list

Depends on: TASK-006
Files: [skills/dispatch-agents/SKILL.md](skills/dispatch-agents/SKILL.md)
Symbols: [INLINE branch — routing table](skills/dispatch-agents/SKILL.md#L38)
Satisfies: REQ-010, REQ-013
Action: Replace the three-column INLINE branch routing table and its stale guard comment at line 36 with a flat bullet list, one bullet per skill, in the form `- **<skill>** — <Fleet decision text copied verbatim from that row's third column>`, covering all seven rows (brainstorm, plan, approved-plan execution, tdd, debug, review, forge-workflow). Drop the Incoming-request and Workflow columns entirely. Keep the following paragraph's tie-break guidance about lifecycle ordering and fan-out cost.
Validate: `! grep -q 'inline-branch-routing-table' skills/dispatch-agents/SKILL.md && ! grep -q 'Incoming request' skills/dispatch-agents/SKILL.md && [ "$(grep -cE '^\- \*\*(brainstorm|plan|tdd|debug|review|forge-workflow)\*\*' skills/dispatch-agents/SKILL.md)" -ge 6 ] && bash scripts/check-anchors.sh`
Expected result: Exit 0. No routing table remains in the file; the fleet-shape bullets are present for every named skill, so the check fails if the table is deleted without its Fleet-decision content being carried over.

### TASK-008: De-route the Governor Threshold Table lifecycle row

Depends on: TASK-007
Files: [skills/dispatch-agents/SKILL.md](skills/dispatch-agents/SKILL.md)
Symbols: [Governor Threshold Table](skills/dispatch-agents/SKILL.md#L21)
Satisfies: REQ-011, REQ-013
Action: Replace the lifecycle row's enumerated destinations with `Lifecycle match (per <squads-router>) → inline`, keeping the row's mode verdict and deleting all six destination mappings.
Validate: `! grep -qE 'failure→debug|diff/feedback→review|problem-to-explore→brainstorm' skills/dispatch-agents/SKILL.md && grep -qF 'Lifecycle match (per <squads-router>)' skills/dispatch-agents/SKILL.md`
Expected result: Exit 0. The presence check matches the full replacement string including the `<squads-router>` reference, not the bare words `Lifecycle match` which already exist in the file today and would pass vacuously. The table still decides inline-vs-composed; it no longer names destinations.

### TASK-009: Final sweep and prose consistency

Depends on: TASK-008
Files: [README.md](README.md), [AGENTS.md](AGENTS.md), [skills/squads/SKILL.md](skills/squads/SKILL.md)
Symbols: [Features](README.md#L7)
Satisfies: REQ-005, REQ-006, REQ-013
Action: Correct exactly four prose sites, no open-ended sweep. (1) `skills/squads/SKILL.md` — delete the residual "Keep them in sync" sentence and the "on conflict, the owning skill's `## Next Skills` table wins" clause it governed, both obsolete once the duplicate tables are gone. (2) `README.md` — update the `dispatch-agents` bullet, which describes it as picking routes, to describe Governor plus executor only. (3) `README.md` — update any line describing `squads` as a router card to describe it as the contract owner. (4) `AGENTS.md` — leave the source-of-truth paragraph's rule intact but confirm it still reads true now that contracts live in a non-invocable card; edit only if it contradicts that, and do not restate skill behavior.
Validate: `npm run format:check && ! grep -rn 'Keep them in sync' skills/ README.md AGENTS.md && ! grep -rlE '^\| *(Trigger|Incoming request) ' skills/`
Expected result: Exit 0 and no grep matches. The third check is REQ-013's repo-wide verification — no SKILL.md anywhere retains a table whose header column maps an incoming request or trigger to a destination skill, which the per-file checks in TASK-007 and TASK-008 cannot establish. Full gate green: hook syntax, all anchors resolving, prettier clean. Two routing authorities remain — the injected `<squads-router>` block and the per-skill `## Next Skills` tables.
