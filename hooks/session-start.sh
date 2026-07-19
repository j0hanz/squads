#!/usr/bin/env bash
# SessionStart hook: inline the squads router paragraph into session context.
# The router text lives inline as a literal string below (no skill file read).
# Refuses to inject content containing reserved sentinels, so the router
# block cannot be spoofed.
set -uo pipefail

if ! command -v jq >/dev/null 2>&1; then
  echo 'squads: WARNING — jq not found; dispatch-check and debug-gate guards are inactive this session. Fix: winget install jqlang.jq'
  echo
fi

router='Route every incoming task or user request to [dispatch-agents](../dispatch-agents/SKILL.md); its Step 0 Governor classifies the request (first match wins) and picks the workflow + fleet shape. Skip only for pure conversation or a one-shot edit answerable direct.'

if grep -qF -e '<squads-router>' -e '</squads-router>' -e '<system-reminder' <<<"$router"; then
  echo 'squads: refusing to inject router content containing reserved sentinels' >&2
  exit 0
fi

echo "Skill names below invoke via the Skill tool as 'squads:<name>' (e.g. /dispatch-agents -> squads:dispatch-agents)."
echo
echo '<squads-router>'
printf '%s\n' "$router"
echo '</squads-router>'