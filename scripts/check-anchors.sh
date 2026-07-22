#!/usr/bin/env bash
# Verify every cross-skill markdown anchor link under skills/ resolves to a real
# heading in its target file. Nothing else checks these — a typo'd anchor is a
# silently dead link, so this runs in `npm run format:check`.
#
# Slug rule (matches GitHub): lowercase, drop every character outside
# [a-z0-9 -], spaces to hyphens. Dropping a character leaves its surrounding
# spaces, which is why "Invariants — apply ..." slugs to "invariants--apply-...".
#
# ponytail: headings inside fenced code blocks are treated as real headings.
# That can only add slugs, never remove one, so it cannot cause a false failure.
# Add fence tracking if a phantom ever collides with a real anchor.
set -u

cd "$(dirname "$0")/.." || exit 1

fail=0
checked=0

while IFS= read -r hit; do
  src=${hit%%:*}
  rest=${hit#*:}
  line=${rest%%:*}
  link=${rest#*:}

  target=skills/${link#../}
  target=${target%%#*}
  anchor=${link#*#}

  checked=$((checked + 1))

  if [ ! -f "$target" ]; then
    echo "$src:$line -> missing file $target"
    fail=1
    continue
  fi

  slugs=$(
    grep -E '^#{1,6} ' "$target" |
      sed 's/^#\{1,6\} //' |
      tr '[:upper:]' '[:lower:]' |
      sed 's/[^a-z0-9 -]//g; s/ /-/g'
  )

  if ! printf '%s\n' "$slugs" | grep -qxF "$anchor"; then
    echo "$src:$line -> unresolved #$anchor in $target"
    fail=1
  fi
done < <(grep -rnoE '\.\./[a-z-]+/SKILL\.md#[a-z0-9-]+' skills/)

echo "check-anchors: $checked link(s) checked"
exit $fail
