#!/usr/bin/env bash
# SessionEnd hook: delete this session's guard state files (debug-gate flag,
# reviewer-dispatch count files). The 120-minute expiry inside each guard
# remains the backstop for crashed sessions where this hook never fires.
set -uo pipefail

command -v jq >/dev/null 2>&1 || exit 0 # no jq -> guards never wrote state

# Read hook input once; jq consumes stdin. Sanitize the id once and reuse it.
input=$(cat)
session_id=$(printf '%s' "$input" | jq -r '.session_id // empty' 2>/dev/null | tr -cd 'a-zA-Z0-9-')
reason=$(printf '%s' "$input" | jq -r '.reason // "unknown"' 2>/dev/null)
printf 'squads session-end: %s reason=%s\n' "$session_id" "$reason"

# Empty id bails because the glob is a no-op: it yields a literal double-dash
# prefix matching neither other sessions nor the no-session-id fallback.
[[ -n "$session_id" ]] || exit 0

tmp="${TMPDIR:-/tmp}"
rm -f "$tmp/squads-debug-gate-$session_id" "$tmp/squads-review-count-$session_id-"*
exit 0
