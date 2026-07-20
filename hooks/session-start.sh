#!/usr/bin/env bash
# SessionStart hook: inline the squads router paragraph into session context.
# The router text lives inline as a literal string below (no skill file read).
# Refuses to inject content containing reserved sentinels, so the router
# block cannot be spoofed.
set -uo pipefail

if ! command -v jq >/dev/null 2>&1; then
  echo 'squads: WARNING — jq not found; dispatch-check and debug-gate guards are inactive this session. Fix: winget install jqlang.jq'
  echo
else
  hooks_json="${BASH_SOURCE[0]%/*}/hooks.json"
  jq -r '"squads hooks wired: dispatch-check[\(.hooks.PreToolUse[0].matcher)] debug-gate[\(.hooks.PreToolUse[1].matcher)]"' "$hooks_json"
fi

# squads_sentinel_clean <text> -> 0 if clean, 1 if a reserved sentinel is
# found. Hardcodes the 3 reserved sentinels (single source of truth) and
# returns status — never exits — so the two call sites keep divergent
# control flow (router aborts injection; reminder skips one line).
squads_sentinel_clean() {
  ! grep -qF -e '<squads-router>' -e '</squads-router>' -e '<system-reminder' <<<"$1"
}

router='Route every incoming task or user request to [dispatch-agents](../dispatch-agents/SKILL.md); its Step 0 Governor classifies the request (first match wins) and picks the workflow + fleet shape. Skip only for pure conversation or a one-shot edit answerable direct.'

if ! squads_sentinel_clean "$router"; then
  echo 'squads: refusing to inject router content containing reserved sentinels' >&2
  exit 0
fi

echo "Skill names below invoke via the Skill tool as 'squads:<name>' (e.g. /dispatch-agents -> squads:dispatch-agents)."
echo
echo '<squads-router>'
printf '%s\n' "$router"
echo '</squads-router>'

# Composed-mode preflight reminder — a session banner holding the literal
# condition (DRY is skill-prose-only; this is a hook banner, not skill prose).
# Routed through its OWN sentinel-rejection guard — it does not ride on the
# router guard above; two distinct guard call sites.
reminder='Composed-mode preflight (Governor checks at dispatch): Claude Code >= 2.1.154, paid plan, dynamic workflows not disabled — else composed OFF, inline only.'

if squads_sentinel_clean "$reminder"; then
  printf '%s\n' "$reminder"
else
  echo 'squads: refusing to inject reminder containing reserved sentinels' >&2
fi