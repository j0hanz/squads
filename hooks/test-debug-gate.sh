#!/usr/bin/env bash
# Smoke tests for hooks/debug-gate.sh across the 6 enumerated behavioral
# branches: flag absent, *.md exempt, test_* exempt, production deny,
# tdd-lifts-flag, aged-flag-clear. Run: `bash hooks/test-debug-gate.sh`.
# Guard/parse paths (jq-missing fail-closed at debug-gate.sh:10-13, empty-
# tool_name early-exit at debug-gate.sh:16) are out of scope — behavioral
# branches only. Each case uses a unique session_id so flag files never collide.
set -u
hook="$(dirname "$0")/debug-gate.sh"
fail=0

run() {  # run <name> <expect_exit> <json>
  local name="$1" expect="$2" json="$3" got
  got=$(printf '%s' "$json" | bash "$hook" 2>/dev/null; echo "exit=$?")
  got=${got##*exit=}
  if [ "$got" = "$expect" ]; then
    echo "PASS: $name (exit=$got)"
  else
    echo "FAIL: $name — expected exit=$expect, got exit=$got" >&2
    fail=1
  fi
}

flagfile() {  # flagfile <session_id> → path (mirrors debug-gate.sh's flag location)
  printf '%s/squads-debug-gate-%s' "${TMPDIR:-/tmp}" "$1"
}

# (a) flag absent + Edit on a production file → exit 0 (gate not engaged).
SID="dbg-$$-a"
rm -f "$(flagfile "$SID")"
run "flag-absent-edit-ok" 0 \
  "{\"session_id\":\"$SID\",\"tool_name\":\"Edit\",\"tool_input\":{\"file_path\":\"src/app.js\"}}"

# (b) flag set + *.md → exit 0 (markdown exempt).
SID="dbg-$$-b"
: > "$(flagfile "$SID")"
run "flag-set-md-exempt" 0 \
  "{\"session_id\":\"$SID\",\"tool_name\":\"Edit\",\"tool_input\":{\"file_path\":\"docs/notes.md\"}}"

# (c) flag set + test_* → exit 0 (genuine test files exempt).
SID="dbg-$$-c"
: > "$(flagfile "$SID")"
run "flag-set-test-exempt" 0 \
  "{\"session_id\":\"$SID\",\"tool_name\":\"Edit\",\"tool_input\":{\"file_path\":\"test_app.py\"}}"

# (d) flag set + production file → exit 2 (gate denies code edits while active).
SID="dbg-$$-d"
: > "$(flagfile "$SID")"
run "flag-set-production-denied" 2 \
  "{\"session_id\":\"$SID\",\"tool_name\":\"Edit\",\"tool_input\":{\"file_path\":\"src/app.js\"}}"

# (e) flag set, then Skill squads:tdd lifts the flag; subsequent Edit → exit 0.
SID="dbg-$$-e"
: > "$(flagfile "$SID")"
run "tdd-skill-lifts-flag" 0 \
  "{\"session_id\":\"$SID\",\"tool_name\":\"Skill\",\"tool_input\":{\"skill\":\"squads:tdd\"}}"
run "tdd-lifts-flag-edit-ok" 0 \
  "{\"session_id\":\"$SID\",\"tool_name\":\"Edit\",\"tool_input\":{\"file_path\":\"src/app.js\"}}"

# (f) flag aged >120min → flag cleared, Edit → exit 0.
SID="dbg-$$-f"
ff="$(flagfile "$SID")"
: > "$ff"
# Backdate the flag mtime to 3 hours ago so find -mmin +120 fires. GNU touch
# (-d) in Git Bash; fall back to -t with a GNU-date-computed timestamp.
touch -d '3 hours ago' "$ff" 2>/dev/null || touch -t "$(date -d '3 hours ago' +%Y%m%d%H%M 2>/dev/null)" "$ff" 2>/dev/null || true
run "aged-flag-cleared-edit-ok" 0 \
  "{\"session_id\":\"$SID\",\"tool_name\":\"Edit\",\"tool_input\":{\"file_path\":\"src/app.js\"}}"

# Cleanup this run's flag files.
rm -f "$(flagfile "dbg-$$-a")" "$(flagfile "dbg-$$-b")" "$(flagfile "dbg-$$-c")" \
      "$(flagfile "dbg-$$-d")" "$(flagfile "dbg-$$-e")" "$(flagfile "dbg-$$-f")"

exit "$fail"