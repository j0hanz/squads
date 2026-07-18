---
name: request-code-review
description: Use when a verified diff needs a fresh-eye review before merging. Prefer over receive-code-review when requesting a new review rather than acting on feedback.
argument-hint: '[target: branch, commit, or path — omit to review the uncommitted working tree]'
---

# request-code-review

## Strict Rules

- **Fresh context only.** Never review your own diff in-thread; always dispatch a subagent.
- **Read-only reviewer.** Deny write/edit tools in the subagent invocation — it reads, never mutates.
- **Verbatim output.** Never edit, correct, or translate the review; paste it as-is.
- **No direct fixes on FAIL.** Route FAIL to `receive-code-review`; do not patch here.
- **No unresolved placeholders reach the subagent.** Replace every `{{...}}` in the dispatch prompt with real values before dispatching.
- **No working-tree mutation to force clean.** Never `stash`/`checkout`/`reset`; if the tree is dirty in committed mode, abort and report.

## Steps

### Step 1: Verify prerequisites

1. Find covering tests by convention (sibling `*.test.*`/`*.spec.*`/`*_test.*`/`test_*` files of changed files) and by `git grep -l "<changed-exported-symbol>"` for changed exports. Run exactly those; paste fresh output. If any covering test fails, abort and report — never dispatch a review of a failing diff. If no tests cover the diff, say so explicitly and get user confirmation before proceeding; the dispatch summary must note the missing coverage.
2. Pick the review mode and resolve the diff:
   - **Committed** (target is a branch, commit, or path): classify the target first — if `git rev-parse --verify <target>` succeeds it is a branch/commit (`head=<target>`); otherwise it is a path (`head=HEAD`, append `-- <target>` later); if no target was passed, use uncommitted mode. Resolve the default branch with a loop that reassigns on each fallback: `for def in "$(git symbolic-ref --short refs/remotes/origin/HEAD 2>/dev/null)" origin/main origin/master origin/develop; do git rev-parse --verify "$def" 2>/dev/null && break; done`; if `$def` does not verify, abort and report "could not resolve default branch — pass an explicit base". Set `base = git merge-base "$def" "$head"` (or the given base). Run `git status --porcelain`; if dirty, abort and report — committed mode requires a clean tree because the reviewer may Read working-tree files for context. Capture `git diff "$base".."$head"` (append `-- <path>` if a path was given).
   - **Uncommitted** (target is the working tree): capture `git diff` plus `git diff --staged` as the diff text block.
3. Guard against an empty diff:
   - **Committed**: run `git diff --stat "$base".."$head"` (append `-- <path>` if a path was given). If empty, abort and report.
   - **Uncommitted**: run `git diff --stat HEAD` (covers staged + unstaged vs `HEAD`). If that is empty AND `git status --porcelain` shows no untracked (`??`) entries, abort and report. (Untracked files are not in `git diff` but are reviewable changes, so they must not trigger a false abort.)
4. **Done when:** tests are green, a non-empty diff is in hand, and (committed mode) the tree is clean.

### Step 2: Dispatch the reviewer

1. Fill the dispatch prompt below, then dispatch one subagent with write/edit tools denied. `{{plan_summary}}` = one or two sentences stating the change's intent, taken from the plan task or the commit message(s) in `"$base".."$head"`; if neither exists, derive it from the diff before dispatching. `{{diff}}` = the diff captured in Step 1.
2. The subagent must return these headers exactly: `## Code Review Result`, `**Status**: PASS|FAIL`, `### Blocking Issues`, `### Advisory Issues`, `### What Was Checked`.
3. If any header is missing or malformed, retry once with a reminder; a second failure aborts the review.
4. **Done when:** the subagent returns well-formed output with all required headers.

#### Dispatch prompt

```
You are a fresh-eyed reviewer. Review only the diff below; do not edit any files.
Change summary: {{plan_summary}}
{{diff}}
Check correctness, security, edge cases, and reuse/simplification, then reply strictly in this Markdown:
## Code Review Result
**Status**: PASS or FAIL
### Blocking Issues
- (one per line, or "none")
### Advisory Issues
- (one per line, or "none")
### What Was Checked
- (areas you examined)
```

### Step 3: Hand off

1. Paste the subagent's output verbatim to the user.
2. On **PASS**: prompt "Changes are ready — commit and push / open a PR."
3. On **FAIL**: invoke `receive-code-review`, passing along the re-review pass number if one was given (its 2-pass cap depends on it). Do not fix findings directly.
4. **Done when:** the verbatim review is surfaced and the PASS or FAIL route is taken.

## Next Skills

| Skill                                                  | Use Case                                      |
| :----------------------------------------------------- | :-------------------------------------------- |
| [receive-code-review](../receive-code-review/SKILL.md) | Review returned FAIL — resolve findings there |
