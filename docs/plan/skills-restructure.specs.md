# skills-restructure — specs

Status: DRAFT
Depth: contract
Origin: plan
Source: docs/design/2026-07-22-skills-restructure-design.md

#### REQ-001: Anchor-resolution check exists, bash only

Detail: A script `scripts/check-anchors.sh` extracts every `../<skill>/SKILL.md#<anchor>` link under `skills/`, derives each target file's heading slugs with the three-rule transform (lowercase; drop every character outside `[a-z0-9 -]`; spaces to hyphens), and exits non-zero listing any link whose anchor matches no heading. Implemented in bash/grep/sed only — no Node, no new dependency, per the AGENTS.md no-build-step constraint.

#### REQ-002: Check wired into format:check and proven green before any link moves

Detail: `package.json` `format:check` runs the anchor script between the existing `bash -n hooks/*.sh` and `prettier --check .` steps. The script must exit 0 against the current unmodified tree — all 39 links resolving — before any task rewrites a link, so a later red result is attributable to the migration rather than to a pre-existing break.

#### REQ-003: squads card owns the three dispatch contracts

Detail: `skills/squads/SKILL.md` contains the full text of `## Invariants — apply to every dispatch`, `## Handoff Contract` (including the reviewer output mapping table and state-carrier precedence paragraph), and `### Model & fan-out policy`. These sections are removed from `skills/dispatch-agents/SKILL.md`; exactly one copy exists when the plan completes.

#### REQ-004: squads card owns the untrusted-content convention; plan retains Origin: semantics

Detail: Ownership of the `<untrusted_context>` wrap convention moves from `skills/plan/SKILL.md` Step 1 Discovery to a `## Untrusted content` section of `skills/squads/SKILL.md`, which holds the full statement of the convention and is the target every other skill cites. `plan` keeps its own one-line inline instruction to wrap external content — callers state the action locally, they only cite the card for the convention itself — but stops being the cited home, so no skill outside `plan` links `plan#step-1-discovery` for the convention. The `Origin:` header semantics (which content counts as non-session-originated) remain owned by `plan`, so the citation at `skills/dispatch-agents/SKILL.md:103` continues to point at `plan#step-1-discovery`.

#### REQ-005: Moved heading text is byte-identical

Detail: Every moved heading keeps its exact original text so its GitHub slug is unchanged and only the file path in each link differs. Specifically `#invariants--apply-to-every-dispatch`, `#handoff-contract`, and `#model--fan-out-policy` must resolve at the card's path with no anchor rewrite.

#### REQ-006: All 22 external links repointed, zero dead anchors

Detail: The 22 cross-skill links currently targeting `dispatch-agents` contract anchors or `plan#step-1-discovery` for the convention are repointed to `../squads/SKILL.md#<same-anchor>`. Distribution: `plan` 8, `brainstorm` 4, `forge-workflow` 5, `review` 3, `debug` 1, `tdd` 1. On completion `scripts/check-anchors.sh` exits 0.

#### REQ-007: dispatch-agents carries an inline invariant-names stub

Detail: After the contracts move out, `skills/dispatch-agents/SKILL.md` retains a short section listing each invariant by name — one line each, no bodies — followed by a link to the card for full text. A model executing a dispatch sees the complete checklist without following the link; only the rationale lives behind it.

#### REQ-008: Rename guard migrates to the card

Detail: An HTML comment guard on the card names the three contract anchors skills now link (`#handoff-contract`, `#invariants--apply-to-every-dispatch`, `#model--fan-out-policy`). The superseded guard at `skills/dispatch-agents/SKILL.md:111` is removed in the same task that removes the headings it protected — deliberate retirement, not silent drop.

#### REQ-009: Card Route table and Resume section deleted

Detail: The Route table (`skills/squads/SKILL.md:16-25`) and the `## Resume` section (`:42-54`) are removed. Entry routing is owned solely by the `<squads-router>` block injected at `hooks/squads-hook.sh:62-66`; resume is owned by each skill's own re-entry rule, which the deleted table only pointed at. The `#resume` self-link dies with the Route table that contained it.

#### REQ-010: dispatch-agents INLINE routing table deleted, fleet shapes retained

Detail: The three-column INLINE branch routing table (`skills/dispatch-agents/SKILL.md:38-52`) is replaced by a fleet-shape list keyed by skill name. The Incoming-request and Workflow columns are duplication of the injected router and are dropped; the Fleet-decision content is not duplication and is preserved verbatim in list form. The stale guard comment at `:36` is deleted with the table.

#### REQ-011: Governor Threshold Table decides mode only, not destination

Detail: The lifecycle row at `skills/dispatch-agents/SKILL.md:27` currently enumerates routing destinations (`failure→debug`, `diff/feedback→review`, and four more), making it a third routing authority. Its content becomes `Lifecycle match (per <squads-router>) → inline`, preserving the mode decision and dropping the destination list.

#### REQ-012: Card stays non-invocable

Detail: `skills/squads/SKILL.md` frontmatter keeps `disable-model-invocation: true` and `user-invocable: false`. The card is reached by link only. Contracts living in a never-invoked file is the load-bearing assumption of this design; changing the frontmatter would void it.

#### REQ-013: Routing authority count verifiably reduced to two

Detail: On completion the only trigger-to-skill routing tables in the repo are the injected `<squads-router>` block and the per-skill `## Next Skills` tables. No SKILL.md contains a table mapping an incoming request shape to a destination skill, and the card's "keep them in sync" instruction is removed along with the copies it governed. This is a repo-wide claim, so it is verified by a repo-wide grep in TASK-009 — the per-file checks in TASK-007 and TASK-008 establish it only for `dispatch-agents`.
