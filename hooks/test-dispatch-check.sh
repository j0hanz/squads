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

# 5. Workflow tool_input with an unresolved placeholder in the inline .script → exit 2
#    (exercises the new Workflow matcher + .script body-extraction branch).
run "workflow-placeholder-denied" 2 \
  '{"tool_name":"Workflow","tool_input":{"script":"log({{branch}})"}}'

# 6. Workflow tool_input with a clean inline .script (no placeholder/sentinel/diff) → exit 0.
run "workflow-clean-script" 0 \
  '{"tool_name":"Workflow","tool_input":{"script":"export const meta={}; return {};"}}'

# 7. Workflow .scriptPath pointing at a clean file → exit 0 (file-read branch).
tmp_clean="$(mktemp -t wf-clean-XXXXXX.js 2>/dev/null || mktemp)"
printf 'export const meta={}; return {};\n' > "$tmp_clean"
run "workflow-scriptpath-clean" 0 \
  "{\"tool_name\":\"Workflow\",\"tool_input\":{\"scriptPath\":\"$tmp_clean\"}}"

# 8. Workflow .scriptPath pointing at a file with a placeholder → exit 2.
tmp_ph="$(mktemp -t wf-ph-XXXXXX.js 2>/dev/null || mktemp)"
printf 'log({{branch}})\n' > "$tmp_ph"
run "workflow-scriptpath-placeholder" 2 \
  "{\"tool_name\":\"Workflow\",\"tool_input\":{\"scriptPath\":\"$tmp_ph\"}}"

# 9. Workflow BOTH a clean inline .script and a dirty .scriptPath → exit 2.
#    .scriptPath takes precedence at runtime; the guard must inspect BOTH bodies
#    so a clean inline decoy cannot mask a dirty scriptPath.
run "workflow-both-present-dirty-scriptpath" 2 \
  "{\"tool_name\":\"Workflow\",\"tool_input\":{\"script\":\"export const meta={}; return {};\",\"scriptPath\":\"$tmp_ph\"}}"

# 10. Workflow name-only (neither .script nor .scriptPath) → exit 0
#     (silently uninspectable, REQ-005 SC10-sanctioned).
run "workflow-name-only-uninspectable" 0 \
  '{"tool_name":"Workflow","tool_input":{"name":"some-saved-workflow"}}'

# 11. Workflow .scriptPath pointing at a missing file → exit 2 (fail-closed: the
#     guard must not skip the executed body when the scriptPath is unreadable).
run "workflow-scriptpath-unreadable-denied" 2 \
  '{"tool_name":"Workflow","tool_input":{"scriptPath":"/nonexistent/squads-probe-workflow.js"}}'

# 12. Cross-body <untrusted_context> masking: open tag in inline .script, close
#     tag + placeholder in .scriptPath → exit 2. Concatenation would span the UC
#     block across bodies and strip the {{branch}}; per-body inspection catches
#     the unbalanced wrapper / the placeholder independently.
tmp_uc_ph="$(mktemp -t wf-ucph-XXXXXX.js 2>/dev/null || mktemp)"
printf '{{branch}}\n</untrusted_context>\n' > "$tmp_uc_ph"
run "workflow-cross-body-uc-masking-denied" 2 \
  "{\"tool_name\":\"Workflow\",\"tool_input\":{\"script\":\"<untrusted_context>\\n\",\"scriptPath\":\"$tmp_uc_ph\"}}"

# 13. A UC wrapper in a clean inline .script decoy must NOT mask a raw diff in
#     .scriptPath → exit 2. The raw-diff check runs per body, so the decoy's UC
#     wrapper does not satisfy the scriptPath body's no-UC condition.
tmp_uc_diff="$(mktemp -t wf-ucdiff-XXXXXX.js 2>/dev/null || mktemp)"
printf 'diff --git a b\n+evil\n' > "$tmp_uc_diff"
run "workflow-uc-decoy-masks-rawdiff-denied" 2 \
  "{\"tool_name\":\"Workflow\",\"tool_input\":{\"script\":\"<untrusted_context>\\nbenign\\n</untrusted_context>\\n\",\"scriptPath\":\"$tmp_uc_diff\"}}"

# 14. Workflow .scriptPath pointing at an empty (but readable) file → exit 0
#     (empty body has no placeholder/sentinel/diff; the file was readable, so no
#     fail-closed deny — distinct from the unreadable case 11).
tmp_empty="$(mktemp -t wf-empty-XXXXXX.js 2>/dev/null || mktemp)"
: > "$tmp_empty"
run "workflow-scriptpath-empty-file-ok" 0 \
  "{\"tool_name\":\"Workflow\",\"tool_input\":{\"scriptPath\":\"$tmp_empty\"}}"

rm -f "$tmp_clean" "$tmp_ph" "$tmp_uc_ph" "$tmp_uc_diff" "$tmp_empty"
exit "$fail"