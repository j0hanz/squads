---
name: release-plugin
description: Use when cutting a new version release for the squads Claude Code plugin — version bump, tag, or GitHub release.
---

# Plugin Release

Version-bump-and-ship workflow for **this repo only** — squads is a Claude Code
plugin installed via `/plugin marketplace add j0hanz/squads`, not an npm
package. If new steps show up that this file doesn't cover, update this file
rather than reinventing them ad hoc.

## Files that carry the version (all 3, kept in sync)

| File                              | Field                                        |
| --------------------------------- | -------------------------------------------- |
| `package.json`                    | `"version"`                                  |
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

1. **Bump** all 3 files to the same `<NEW>` version.
2. **Verify** (scope to the 3 manifests — `package-lock.json` also carries the version and would inflate the count):
   ```bash
   git grep -n "\"version\": \"<NEW>\"" -- package.json .claude-plugin/plugin.json .claude-plugin/marketplace.json   # must print exactly 3 lines
   git grep -n "\"version\": \"<OLD>\"" -- package.json .claude-plugin/plugin.json .claude-plugin/marketplace.json   # must print zero
   ```
3. **Validate**: run exactly `claude plugin validate . --strict` — must pass before committing.
4. **Commit** (stage only the 3 version files):
   ```bash
   git add package.json .claude-plugin/plugin.json .claude-plugin/marketplace.json
   git commit -m "chore: bump version to <NEW>"
   ```
5. **Tag**: `git tag -a v<NEW> -m "Version <NEW>"`.
6. **Confirm with the user before pushing** — push is visible to others and not easily reversible.
7. **Push**: `git push origin master && git push origin v<NEW>`.
8. **Release**: `gh release create v<NEW> --title "v<NEW>" --notes "<notes>"`, notes summarizing the commits since `<last-tag>` grouped by fix/feat/etc.
9. **Finalize**: `git status` must show a clean working tree.

## Explicitly out of scope for this repo

- `npm publish` — not npm-distributed.
- CHANGELOG.md / changelog-generation script — doesn't exist here.
- Discord release notification — doesn't exist here.
- `plugin/`, `.codex-plugin/`, `openclaw/` manifests — this repo doesn't have them; only the 3 files in the table above.
