#!/usr/bin/env bash
# SessionEnd hook: delete this session's guard state files (debug-gate flag,
# reviewer-dispatch count files). The 120-minute expiry inside each guard
# remains the backstop for crashed sessions where this hook never fires.
set -uo pipefail

command -v jq >/dev/null 2>&1 || exit 0 # no jq -> guards never wrote state

# Read hook input once; jq consumes stdin. Fail-safe: missing fields -> "unknown".
input=$(cat)
m_sid=$(printf '%s' "$input" | jq -r '.session_id // "unknown"' 2>/dev/null)
m_reason=$(printf '%s' "$input" | jq -r '.reason // "unknown"' 2>/dev/null)
printf 'squads session-end: %s reason=%s\n' "$m_sid" "$m_reason"

session_id=$(printf '%s' "$input" | jq -r '.session_id // empty' 2>/dev/null | tr -cd 'a-zA-Z0-9-')
# Empty id -> bail. Never glob without the id: that would delete other
# sessions' state. Fallback-named files ("unknown"/"no-session-id") are
# left to the 120-minute expiry.
[[ -n "$session_id" ]] || exit 0

tmp="${TMPDIR:-/tmp}"
rm -f "$tmp/squads-debug-gate-$session_id" "$tmp/squads-review-count-$session_id-"*
exit 0
