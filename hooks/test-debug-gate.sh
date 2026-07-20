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

# Portable backdate: BSD first, then GNU, then give up. Fixes case (f) on
# macOS/BSD where `touch -d` and `date -d` do not exist.
backdate() {  # backdate <file>
  touch -t "$(date -v-3H +%Y%m%d%H%M 2>/dev/null)" "$1" 2>/dev/null \
    || touch -d '3 hours ago' "$1" 2>/dev/null \
    || true
}

# (f) flag aged >120min → flag cleared, Edit → exit 0.
SID="dbg-$$-f"
ff="$(flagfile "$SID")"
: > "$ff"
# Backdate the flag mtime to 3 hours ago so find -mmin +120 fires.
backdate "$ff"
run "aged-flag-cleared-edit-ok" 0 \
  "{\"session_id\":\"$SID\",\"tool_name\":\"Edit\",\"tool_input\":{\"file_path\":\"src/app.js\"}}"

# (g) flag set + Skill squads:dispatch-agents does NOT lift the gate; subsequent
# Edit on a production file → exit 2 (dispatch-agents is a triage step, not a
# hand-off to tdd/plan, so reproduce-first still binds).
SID="dbg-$$-g"
: > "$(flagfile "$SID")"
run "dispatch-agents-does-not-lift-flag" 0 \
  "{\"session_id\":\"$SID\",\"tool_name\":\"Skill\",\"tool_input\":{\"skill\":\"squads:dispatch-agents\"}}"
run "dispatch-agents-then-edit-denied" 2 \
  "{\"session_id\":\"$SID\",\"tool_name\":\"Edit\",\"tool_input\":{\"file_path\":\"src/app.js\"}}"

# (h) bare "test.js" filename is NOT exempt — the glob requires a delimiter
# (test_ / _test / .test.) so a file literally named test.js is denied and
# documented; extend the glob only if the user says otherwise.
SID="dbg-$$-h"
: > "$(flagfile "$SID")"
run "bare-test-js-denied" 2 \
  "{\"session_id\":\"$SID\",\"tool_name\":\"Edit\",\"tool_input\":{\"file_path\":\"test.js\"}}"

# (i) NotebookEdit on test_*.ipynb → exit 0 (test-file exempt via notebook_path).
SID="dbg-$$-i"
: > "$(flagfile "$SID")"
run "notebookedit-test-ipynb-exempt" 0 \
  "{\"session_id\":\"$SID\",\"tool_name\":\"NotebookEdit\",\"tool_input\":{\"notebook_path\":\"test_analysis.ipynb\"}}"

# (j) NotebookEdit on a production analysis.ipynb → exit 2 (gate denies).
SID="dbg-$$-j"
: > "$(flagfile "$SID")"
run "notebookedit-production-ipynb-denied" 2 \
  "{\"session_id\":\"$SID\",\"tool_name\":\"NotebookEdit\",\"tool_input\":{\"notebook_path\":\"analysis.ipynb\"}}"

# (k) Skill squads:plan lifts the flag; subsequent Edit → exit 0.
SID="dbg-$$-k"
: > "$(flagfile "$SID")"
run "plan-skill-lifts-flag" 0 \
  "{\"session_id\":\"$SID\",\"tool_name\":\"Skill\",\"tool_input\":{\"skill\":\"squads:plan\"}}"
run "plan-lifts-flag-edit-ok" 0 \
  "{\"session_id\":\"$SID\",\"tool_name\":\"Edit\",\"tool_input\":{\"file_path\":\"src/app.js\"}}"

# (l) Skill squads:review lifts the flag; subsequent Edit → exit 0.
SID="dbg-$$-l"
: > "$(flagfile "$SID")"
run "review-skill-lifts-flag" 0 \
  "{\"session_id\":\"$SID\",\"tool_name\":\"Skill\",\"tool_input\":{\"skill\":\"squads:review\"}}"
run "review-lifts-flag-edit-ok" 0 \
  "{\"session_id\":\"$SID\",\"tool_name\":\"Edit\",\"tool_input\":{\"file_path\":\"src/app.js\"}}"

# (m) bare Skill "tdd" lifts the flag; subsequent Edit → exit 0.
SID="dbg-$$-m"
: > "$(flagfile "$SID")"
run "bare-tdd-skill-lifts-flag" 0 \
  "{\"session_id\":\"$SID\",\"tool_name\":\"Skill\",\"tool_input\":{\"skill\":\"tdd\"}}"
run "bare-tdd-lifts-flag-edit-ok" 0 \
  "{\"session_id\":\"$SID\",\"tool_name\":\"Edit\",\"tool_input\":{\"file_path\":\"src/app.js\"}}"

# (n) parallel-debugging engage via Skill: start with NO flag, run the Skill,
# assert the flag file now exists, then Edit on a production file → exit 2.
SID="dbg-$$-n"
rm -f "$(flagfile "$SID")"
run "parallel-debugging-skill-sets-flag" 0 \
  "{\"session_id\":\"$SID\",\"tool_name\":\"Skill\",\"tool_input\":{\"skill\":\"squads:parallel-debugging\"}}"
if [[ -f "$(flagfile "$SID")" ]]; then
  echo "PASS: parallel-debugging-skill-creates-flag-file"
else
  echo "FAIL: parallel-debugging-skill-creates-flag-file — flag not created" >&2
  fail=1
fi
run "parallel-debugging-then-edit-denied" 2 \
  "{\"session_id\":\"$SID\",\"tool_name\":\"Edit\",\"tool_input\":{\"file_path\":\"src/app.js\"}}"

# (o) Write arm: flag set + Write on a production file → exit 2.
SID="dbg-$$-o"
: > "$(flagfile "$SID")"
run "write-production-denied" 2 \
  "{\"session_id\":\"$SID\",\"tool_name\":\"Write\",\"tool_input\":{\"file_path\":\"src/app.js\"}}"

# (p) Write arm: flag set + Write on *.md → exit 0 (markdown exempt).
SID="dbg-$$-p"
: > "$(flagfile "$SID")"
run "write-md-exempt" 0 \
  "{\"session_id\":\"$SID\",\"tool_name\":\"Write\",\"tool_input\":{\"file_path\":\"docs/notes.md\"}}"

# (q) MultiEdit arm: flag set + MultiEdit on a production file → exit 2.
SID="dbg-$$-q"
: > "$(flagfile "$SID")"
run "multiedit-production-denied" 2 \
  "{\"session_id\":\"$SID\",\"tool_name\":\"MultiEdit\",\"tool_input\":{\"file_path\":\"src/app.js\"}}"

# (r) jq-missing fail-closed: shadow PATH so jq is absent, run the hook with
# a Write input → exit 2 (mirrors dispatch-check test 4).
SID="dbg-$$-r"
: > "$(flagfile "$SID")"
got=$(printf '%s' "{\"session_id\":\"$SID\",\"tool_name\":\"Write\",\"tool_input\":{\"file_path\":\"src/app.js\"}}" \
  | PATH="/usr/bin:/bin" bash "$hook" 2>/dev/null; echo "exit=$?")
got=${got##*exit=}
if [ "$got" = "2" ]; then
  echo "PASS: jq-missing-fail-closed (exit=$got)"
else
  echo "FAIL: jq-missing-fail-closed — expected exit=2, got exit=$got" >&2
  fail=1
fi

# Cleanup this run's flag files.
rm -f "$(flagfile "dbg-$$-a")" "$(flagfile "dbg-$$-b")" "$(flagfile "dbg-$$-c")" \
      "$(flagfile "dbg-$$-d")" "$(flagfile "dbg-$$-e")" "$(flagfile "dbg-$$-f")" \
      "$(flagfile "dbg-$$-g")" "$(flagfile "dbg-$$-h")" "$(flagfile "dbg-$$-i")" \
      "$(flagfile "dbg-$$-j")" "$(flagfile "dbg-$$-k")" "$(flagfile "dbg-$$-l")" \
      "$(flagfile "dbg-$$-m")" "$(flagfile "dbg-$$-n")" "$(flagfile "dbg-$$-o")" \
      "$(flagfile "dbg-$$-p")" "$(flagfile "dbg-$$-q")" "$(flagfile "dbg-$$-r")"

exit "$fail"