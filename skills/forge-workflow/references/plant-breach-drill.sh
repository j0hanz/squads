#!/usr/bin/env bash
# Plant-breach drill — exercises the two HIGH Script Audit Checklist items:
#   (1) no-write clause grep flags an investigator prompt permitting writes;
#   (2) recipe-vs-script required-stage diff flags a script missing a required stage.
# Runs as-is: `bash references/plant-breach-drill.sh`.
set -u
tmp=$(mktemp -d)
trap 'rm -rf "$tmp"' EXIT

# Breach #1: write-breach investigator prompt — an agent() description containing "write the fix".
cat > "$tmp/investigator.txt" <<'EOF'
Investigate the hypothesis. You may write the fix directly into the source file if confident.
EOF

# HIGH item 1 — no-write clause grep: flags any investigator prompt permitting writes.
if ! grep -qiE "write|edit|patch|fix the|create|modify|delete|overwrite" "$tmp/investigator.txt"; then
  echo "FAIL: write-breach not caught" >&2
  exit 1
fi

# Breach #2: stage-omitted script — recipe declares refute, generated script misses it.
printf 'stages: investigate, refute, tally\n' > "$tmp/recipe.txt"
cat > "$tmp/script.js" <<'EOF'
// Stage: investigate
agent({ description: "investigator" });
// Stage: tally
agent({ description: "tally" });
EOF

# HIGH item 2 — recipe-vs-script required-stage diff: every recipe stage must appear in the script.
stages=$(sed -n 's/^stages: //p' "$tmp/recipe.txt" | tr ',' ' ')
missing=""
for stage in $stages; do
  if ! grep -qiE "Stage: $stage" "$tmp/script.js"; then
    missing="$missing $stage"
  fi
done

if [ -z "$missing" ]; then
  echo "FAIL: stage-omission not caught" >&2
  exit 1
fi

echo "both breaches caught"
exit 0