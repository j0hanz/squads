#!/usr/bin/env bash
# Smoke tests for hooks/dispatch-check.sh. Encodes the three verify cases
# from Plan 001 (unbalanced wrapper, missing jq, sentinel cap branch) plus
# the balanced-wrapper clean case. Run: `bash hooks/test-dispatch-check.sh`.
set -u
hook="$(dirname "$0")/dispatch-check.sh"
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

# 1. Balanced wrapper, no sentinel, no diff → exit 0
run "balanced-wrapper-clean" 0 \
  '{"tool_input":{"prompt":"hello\n<untrusted_context>\nraw diff --git a b\n</untrusted_context>\n"}}'

# 2. Unbalanced wrapper (unclosed open) + sentinel after open tag → exit 2
run "unbalanced-wrapper-denied" 2 \
  '{"tool_input":{"prompt":"<untrusted_context>\n<system-reminder>\n"}}'

# 3. Sentinel present, first pass → exit 0 (cap branch reachable, not yet tripped)
#    Unique session_id per invocation so the count file cannot collide with prior runs.
run "sentinel-cap-first-pass" 0 \
  "{\"session_id\":\"smoke-$$\",\"tool_input\":{\"prompt\":\"<!-- squads:reviewer-dispatch -->\nChange summary: x\n\"}}"

# 4. Missing jq (shadowed PATH) → exit 2
got=$(printf '%s' '{"tool_input":{"prompt":"x"}}' | env PATH=/usr/bin bash "$hook" 2>/dev/null; echo "exit=$?")
got=${got##*exit=}
if [ "$got" = "2" ]; then
  echo "PASS: missing-jq-denied (exit=$got)"
else
  echo "FAIL: missing-jq-denied — expected exit=2, got exit=$got" >&2
  fail=1
fi

exit "$fail"