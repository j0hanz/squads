#!/usr/bin/env bash
# Plant-breach drill — exercises the two HIGH Script Audit Checklist items:
#   (1) no-write clause grep flags an investigator prompt permitting writes;
#   (2) recipe-vs-script required-stage diff flags a script missing a required stage.
# Runs as-is: `bash references/plant-breach-drill.sh`.
set -u
tmp=$(mktemp -d)
trap 'rm -rf "$tmp"' EXIT

# Breach #1a: write-breach investigator prompt — permits writes outright.
cat > "$tmp/investigator.txt" <<'EOF'
Investigate the hypothesis. You may write the fix directly into the source file if confident.
EOF

# Breach #1b: COMPLIANT denial — must NOT be flagged. The checklist (§Script Audit Checklist › no-write clause grep)
# mandates this exact phrasing, so a naive verb grep would false-positive on it.
cat > "$tmp/compliant.txt" <<'EOF'
You are read-only; do not write, edit, create, modify, or delete any file. Report root cause only.
EOF

# Negation-aware no-write check: strip "do not ..."/"don't ..." denial clauses
# (up to the next sentence boundary) before grepping for write verbs. A verb
# that survives the strip is an actual permission = breach.
strip_denials() {
  sed -E 's/do not[^.]*\./ /g; s/don'"'"'t[^.]*\./ /g; s/Do not[^.]*\./ /g' "$1"
}
VERBS='write|edit|create|modify|patch|overwrite|delete|remove'

# HIGH item 1 — no-write clause grep: flags any investigator prompt permitting writes.
strip_denials "$tmp/investigator.txt" > "$tmp/inv_stripped.txt"
if ! grep -qiE "$VERBS" "$tmp/inv_stripped.txt"; then
  echo "FAIL: write-breach not caught" >&2
  exit 1
fi

# The compliant denial must NOT be flagged after stripping:
strip_denials "$tmp/compliant.txt" > "$tmp/comp_stripped.txt"
if grep -qiE "$VERBS" "$tmp/comp_stripped.txt"; then
  echo "FAIL: compliant denial falsely flagged as a write breach" >&2
  exit 1
fi

# Breach #2: stage-omitted script — recipe declares refute, generated
# script misses its distinct agent() call.
printf 'stages: investigate, refute, tally\n' > "$tmp/recipe.txt"
cat > "$tmp/script.js" <<'EOF'
agent({ description: "investigate stage" });
agent({ description: "tally stage" });
EOF

# HIGH item 2 — recipe-vs-script required-stage diff: every recipe stage
# must appear as a distinct agent() call (§Script Audit Checklist › recipe-vs-script required-stage diff). Match an agent()
# call whose description names the stage, not a // Stage: comment.
stages=$(sed -n 's/^stages: //p' "$tmp/recipe.txt" | tr ',' ' ')
missing=""
for stage in $stages; do
  if ! grep -qiE "agent\([^)]*\"[^\"]*${stage} stage" "$tmp/script.js"; then
    missing="$missing $stage"
  fi
done

if [ -z "$missing" ]; then
  echo "FAIL: stage-omission not caught (missing: nothing)" >&2
  exit 1
fi
case "$missing" in
  *refute*) ;;  # expected: refute is the omitted stage
  *) echo "FAIL: wrong stage flagged as missing: $missing" >&2; exit 1 ;;
esac

echo "both breaches caught"
exit 0