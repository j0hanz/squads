#!/usr/bin/env bash
# SessionStart hook: inline the squads router paragraph into session context.
# The router text lives inline as a literal string below (no skill file read).
set -uo pipefail

if ! command -v jq >/dev/null 2>&1; then
  echo 'squads: jq not found — dispatch-check and debug-gate will DENY dispatch and edits this session (fail-closed). Install jq: Windows — winget install jqlang.jq; macOS — brew install jq; Linux — apt/dnf install jq.' >&2
else
  hooks_json="${BASH_SOURCE[0]%/*}/hooks.json"
  jq -r '.hooks.PreToolUse[] | . as $p | .hooks[] | "squads hooks wired: \(.command | sub("^.*/hooks/"; "") | sub("[^A-Za-z-].*$"; "")) [\($p.matcher)]"' "$hooks_json" >&2
fi

router='Route every incoming task or user request to [dispatch-agents](../dispatch-agents/SKILL.md); its Step 0 Governor classifies the request (first match wins) and picks the workflow + fleet shape. Skip only for pure conversation or a one-shot edit answerable direct.'

echo "Skill names below invoke via the Skill tool as 'squads:<name>' (e.g. /dispatch-agents -> squads:dispatch-agents)."
echo
echo '<squads-router>'
printf '%s\n' "$router"
echo '</squads-router>'

# Composed-mode preflight reminder — a hook banner holding the literal composed-mode condition.
reminder='Composed-mode preflight (Governor checks at dispatch): Claude Code >= 2.1.154, paid plan, dynamic workflows not disabled — else composed OFF, inline only.'
printf '%s\n' "$reminder"