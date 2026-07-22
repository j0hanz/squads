#!/usr/bin/env bash
# Self-check for check-anchors.sh. A green check-anchors run only proves the
# script ran — not that it can catch anything. This plants known-bad input in a
# temp tree and asserts the failure paths actually fire, plus the two slug cases
# the skill cross-links depend on (a dropped em-dash and a dropped ampersand
# each leave the surrounding spaces, so both collapse to a double hyphen).
set -u

script=$(cd "$(dirname "$0")" && pwd)/check-anchors.sh
tmp=$(mktemp -d) || exit 1
# Guard the empty case too: an unset $tmp would turn every "$tmp/..." path below
# into an absolute path at the filesystem root.
[ -n "$tmp" ] || exit 1
trap 'rm -rf "$tmp"' EXIT

mkdir -p "$tmp/scripts" "$tmp/skills/alpha" "$tmp/skills/beta"
cp "$script" "$tmp/scripts/check-anchors.sh"

cat >"$tmp/skills/beta/SKILL.md" <<'EOF'
# beta

## Invariants — apply to every dispatch

## Model & fan-out policy

### Step 1: Discovery
EOF

fail=0

# assert <label> <expected-exit> [substring the output must contain]
assert() {
  local label=$1
  local want=$2
  local needle=${3:-}
  local out rc
  out=$(bash "$tmp/scripts/check-anchors.sh" 2>&1)
  rc=$?
  if [ "$rc" -ne "$want" ]; then
    echo "FAIL $label — exit $rc, wanted $want"
    echo "$out"
    fail=1
    return
  fi
  if [ -n "$needle" ] && ! printf '%s' "$out" | grep -qF "$needle"; then
    echo "FAIL $label — output missing '$needle'"
    echo "$out"
    fail=1
    return
  fi
  echo "ok   $label"
}

# 1. Clean tree passes, and the tricky slugs resolve.
cat >"$tmp/skills/alpha/SKILL.md" <<'EOF'
# alpha

See [inv](../beta/SKILL.md#invariants--apply-to-every-dispatch),
[model](../beta/SKILL.md#model--fan-out-policy),
[step](../beta/SKILL.md#step-1-discovery).
EOF
assert "clean tree passes; em-dash and ampersand slugs resolve" 0

# 2. A broken anchor fails, and the message names it.
cat >>"$tmp/skills/alpha/SKILL.md" <<'EOF'

Broken: [x](../beta/SKILL.md#no-such-heading)
EOF
assert "broken anchor fails and is named" 1 "#no-such-heading"

# 3. A link to a file that does not exist fails.
cat >"$tmp/skills/alpha/SKILL.md" <<'EOF'
# alpha

[gone](../ghost/SKILL.md#whatever)
EOF
assert "missing target file fails" 1 "missing file"

[ "$fail" -eq 0 ] && echo "check-anchors-selfcheck: all assertions passed"
exit $fail
