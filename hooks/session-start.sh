#!/usr/bin/env bash
# SessionStart hook: inject the using-squads router skill into session context.
# Strips the SKILL.md frontmatter and refuses to inject content containing
# reserved sentinels, so the router block cannot be spoofed from the file.
set -uo pipefail

script_dir=$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)
skill_path="$script_dir/../skills/using-squads/SKILL.md"

if ! command -v jq >/dev/null 2>&1; then
  echo 'squads: WARNING — jq not found; dispatch-check and debug-gate guards are inactive this session. Fix: winget install jqlang.jq'
  echo
fi

if [[ ! -f "$skill_path" ]]; then
  echo "Error reading squads router skill: $skill_path not found" >&2
  exit 0
fi

# Drop YAML frontmatter: a leading --- line through the next --- line.
cleaned=$(awk '
  NR == 1 && /^---\r?$/ { in_fm = 1; next }
  in_fm { if (/^---\r?$/) in_fm = 0; next }
  { print }
' "$skill_path")

if grep -qF -e '<squads-router>' -e '</squads-router>' -e '<system-reminder' <<<"$cleaned"; then
  echo 'squads: refusing to inject router content containing reserved sentinels' >&2
  exit 0
fi

echo "Skill names below invoke via the Skill tool as 'squads:<name>' (e.g. /dispatch-agents -> squads:dispatch-agents)."
echo
echo '<squads-router>'
printf '%s\n' "$cleaned"
echo '</squads-router>'
