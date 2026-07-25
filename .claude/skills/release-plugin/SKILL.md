---
name: release-plugin
description: Use when cutting a new version release for the squads Claude Code plugin — version bump, tag, or GitHub release.
---

Version-bump-and-ship workflow for **this repo only** — squads is a Claude Code
plugin, not an npm package.

## Files that carry the version (all 4, kept in sync)

| File                              | Field                                        |
| --------------------------------- | -------------------------------------------- |
| `package.json`                    | `"version"`                                  |
| `package-lock.json`               | `"version"`                                  |
| `.claude-plugin/plugin.json`      | `"version"`                                  |
| `.claude-plugin/marketplace.json` | `plugins[0].version` (nested, not top-level) |

## Determine bump type

```bash
git describe --tags --abbrev=0          # last release tag (fails if no tags yet — then this is the first release; use all commits)
git log <last-tag>..HEAD --oneline       # commits since then
```

- Any `feat:` commit → **MINOR**
- Any `!` or `BREAKING CHANGE` → **MAJOR**
- Otherwise (`fix:`, `chore:`, `docs:`, `refactor:`) → **PATCH**

## Steps

1. **Bump** the 3 JSON manifests to the same `<NEW>` version, then sync the lockfile: `npm install --package-lock-only` (rewrites both version fields in `package-lock.json` from `package.json`).
2. **Verify**:
   ```bash
   git grep -n "\"version\": \"<NEW>\"" -- package.json .claude-plugin/plugin.json .claude-plugin/marketplace.json   # must print exactly 3 lines
   git grep -n "\"version\": \"<OLD>\"" -- package.json .claude-plugin/plugin.json .claude-plugin/marketplace.json   # must print zero
   git grep -c "\"version\": \"<NEW>\"" -- package-lock.json   # must print 2
   ```
3. **Validate**: run exactly `claude plugin validate . --strict` — must pass before committing.
4. **Commit** (stage only the 4 version files):
   ```bash
   git add package.json package-lock.json .claude-plugin/plugin.json .claude-plugin/marketplace.json
   git commit -m "chore: bump version to <NEW>"
   ```
5. **Tag**: `git tag -a v<NEW> -m "Version <NEW>"`.
6. **Confirm with the user before pushing** — push is visible to others and not easily reversible.
7. **Push**: `git push origin master && git push origin v<NEW>`.
8. **Release**: `gh release create v<NEW> --title "v<NEW>" --notes "<notes>"`, notes summarizing the commits since `<last-tag>` grouped by fix/feat/etc. `gh release view v<NEW>` must print it.
9. **Finalize**: `git status` must show a clean working tree.

## Out of scope

- `npm publish` — not npm-distributed.
- CHANGELOG.md / changelog-generation script — doesn't exist here.
