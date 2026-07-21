#!/usr/bin/env bash
# Resolve a code-review base branch (defaults to repo's default branch).
# Source this file, or copy the loop into the calling script.
#
# Sets the global `DEF` to the first existing default-branch candidate.
# Loop reassigns on each fallback. No output if `DEF` resolves; prints
# an error and exits non-zero if none of the candidates verify.
#
# Usage:  source resolve-base.sh
#         # or inline:
#         for def in "$(git symbolic-ref --short refs/remotes/origin/HEAD 2>/dev/null)" origin/main origin/master origin/develop; do
#           git rev-parse --verify "$def" >/dev/null 2>&1 && break; def=""
#         done
#         [ -n "$def" ] || { echo "could not resolve default branch" >&2; exit 1; }

for def in \
  "$(git symbolic-ref --short refs/remotes/origin/HEAD 2>/dev/null)" \
  origin/main \
  origin/master \
  origin/develop; do
  if git rev-parse --verify "$def" >/dev/null 2>&1; then
    export DEF="$def"
    return 0 2>/dev/null || exit 0
  fi
done

echo "could not resolve default branch — pass explicit base" >&2
return 1 2>/dev/null || exit 1
