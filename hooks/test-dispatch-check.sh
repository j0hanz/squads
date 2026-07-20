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

# 15. Malformed JSON → exit 2 (fail-closed parse error, TASK-001 #2).
run "malformed-json-denied" 2 '{bad json'

# 16. Prose mention of <untrusted_context> (inline, not a standalone line) with a
#     raw diff → exit 2. The standalone-line UC guard does not match prose, so the
#     raw-diff check still fires (TASK-001 #3).
run "prose-uc-mention-rawdiff-denied" 2 \
  '{"tool_input":{"prompt":"see the <untrusted_context> convention\ndiff --git a b\n+evil\n"}}'

# 17. Reviewer-dispatch cap: 3rd pass for the same session_id+Change summary →
#     exit 0, 0, 2 (TASK-001 #5). Unique sid+summary so the count file cannot
#     collide with prior runs (120-min expiry notwithstanding).
sid_cap="smoke-cap-$$-$RANDOM"
cap_json="{\"session_id\":\"$sid_cap\",\"tool_input\":{\"prompt\":\"<!-- squads:reviewer-dispatch -->\nChange summary: cap-test-$RANDOM\n\"}}"
run "review-cap-pass-1" 0 "$cap_json"
run "review-cap-pass-2" 0 "$cap_json"
run "review-cap-pass-3-denied" 2 "$cap_json"

# 18. No "Change summary:" line → two distinct prompts get separate buckets
#     (keyed on whole-prompt cksum), both exit 0 on first pass (TASK-001 #6).
sid_nosum="smoke-nosum-$$-$RANDOM"
run "review-no-summary-prompt-A-first-pass" 0 \
  "{\"session_id\":\"$sid_nosum\",\"tool_input\":{\"prompt\":\"<!-- squads:reviewer-dispatch -->\nreview prompt A\n\"}}"
run "review-no-summary-prompt-B-first-pass" 0 \
  "{\"session_id\":\"$sid_nosum\",\"tool_input\":{\"prompt\":\"<!-- squads:reviewer-dispatch -->\nreview prompt B\n\"}}"

# 19. Clean inline .script carrying a balanced <untrusted_context> wrapper must
#     NOT mask a placeholder in .scriptPath → exit 2 (L2 gap: case 9 covers a
#     clean inline decoy with no UC, case 13 covers a UC decoy + rawdiff
#     scriptPath; this fills the UC-decoy + placeholder-scriptPath cell).
tmp_uc_bal_ph="$(mktemp -t wf-ucbph-XXXXXX.js 2>/dev/null || mktemp)"
printf '{{branch}}\n' > "$tmp_uc_bal_ph"
run "workflow-clean-uc-inline-dirty-scriptpath-placeholder-denied" 2 \
  "{\"tool_name\":\"Workflow\",\"tool_input\":{\"script\":\"<untrusted_context>\\nbenign\\n</untrusted_context>\\n\",\"scriptPath\":\"$tmp_uc_bal_ph\"}}"

# 20. SendMessage .message path: unresolved placeholder in .message → exit 2
#     (exercises the .tool_input.message branch of the prompt read).
run "sendmessage-placeholder-denied" 2 \
  '{"tool_name":"SendMessage","tool_input":{"message":"review the {{diff}} please"}}'

# 21. SendMessage .message path: clean message → exit 0
run "sendmessage-clean" 0 \
  '{"tool_name":"SendMessage","tool_input":{"message":"please review the changes"}}'

# 22-24. Sentinel-denied parametrized: each of the three reserved sentinels
#        embedded in a prompt → exit 2.
run "sentinel-system-reminder-denied" 2 \
  '{"tool_input":{"prompt":"inline <system-reminder text here"}}'
run "sentinel-squads-router-open-denied" 2 \
  '{"tool_input":{"prompt":"inline <squads-router text"}}'
run "sentinel-squads-router-close-denied" 2 \
  '{"tool_input":{"prompt":"inline </squads-router text"}}'

# 25. Stale count-file expiry: pre-seed count=2, backdate 3h, re-run → exit 0
#     (find -mmin +120 branch fires and resets; without it count=3 → deny exit 2).
#     Portable backdate: BSD/macOS touch -t first, then GNU touch -d, then || true.
backdate() {
  touch -t "$(date -v-3H +%Y%m%d%H%M 2>/dev/null)" "$1" 2>/dev/null || \
  touch -d '3 hours ago' "$1" 2>/dev/null || true
}
sid_stale="smoke-stale-$$-$RANDOM"
stale_summary="Change summary: stale-test-$RANDOM"
stale_prompt="<!-- squads:reviewer-dispatch -->\n$stale_summary\n"
hash_cmd=$(command -v shasum || command -v sha256sum || command -v cksum)
change_key=$(printf '%s\n' "$stale_summary" | $hash_cmd | awk '{print $1}')
count_file="${TMPDIR:-/tmp}/squads-review-count-${sid_stale}-${change_key}"
printf '2' > "$count_file"
backdate "$count_file"
run "stale-count-file-expiry" 0 \
  "{\"session_id\":\"$sid_stale\",\"tool_input\":{\"prompt\":\"$stale_prompt\"}}"
if [ -f "$count_file" ] && [ -z "$(find "$count_file" -mmin +120 2>/dev/null)" ]; then
  echo "PASS: stale-count-file-refreshed (expiry branch fired)"
else
  echo "FAIL: stale-count-file-expiry — file still stale or missing" >&2
  fail=1
fi
rm -f "$count_file"

# 26-29. Task* tools with empty tool_input → exit 0 (empty-body path handles them).
run "taskcreate-empty-exit0" 0 '{"tool_name":"TaskCreate","tool_input":{}}'
run "taskupdate-empty-exit0" 0 '{"tool_name":"TaskUpdate","tool_input":{}}'
run "tasklist-empty-exit0" 0 '{"tool_name":"TaskList","tool_input":{}}'
run "taskget-empty-exit0" 0 '{"tool_name":"TaskGet","tool_input":{}}'

# 30-31. CLAUDE_PLUGIN_ROOT expansion in .scriptPath.
tmp_plugin_root="$(mktemp -d -t squads-plugin-XXXXXX 2>/dev/null || mktemp -d)"
tmp_plugin_script="$tmp_plugin_root/workflow.js"
printf 'export const meta={}; return {};\n' > "$tmp_plugin_script"
# 30. CLAUDE_PLUGIN_ROOT set + clean scriptPath under it (expansion resolves, readable) → exit 0
got=$(printf '%s' '{"tool_name":"Workflow","tool_input":{"scriptPath":"${CLAUDE_PLUGIN_ROOT}/workflow.js"}}' | env CLAUDE_PLUGIN_ROOT="$tmp_plugin_root" bash "$hook" 2>/dev/null; echo "exit=$?")
got=${got##*exit=}
if [ "$got" = "0" ]; then echo "PASS: pluginroot-clean-expanded (exit=$got)"; else echo "FAIL: pluginroot-clean-expanded — expected 0, got $got" >&2; fail=1; fi
# 31. CLAUDE_PLUGIN_ROOT set + scriptPath whose expanded path is unreadable → exit 2
got=$(printf '%s' '{"tool_name":"Workflow","tool_input":{"scriptPath":"${CLAUDE_PLUGIN_ROOT}/missing.js"}}' | env CLAUDE_PLUGIN_ROOT="$tmp_plugin_root" bash "$hook" 2>/dev/null; echo "exit=$?")
got=${got##*exit=}
if [ "$got" = "2" ]; then echo "PASS: pluginroot-unreadable-denied (exit=$got)"; else echo "FAIL: pluginroot-unreadable-denied — expected 2, got $got" >&2; fail=1; fi

# 32. Prose mention of the system-reminder sentinel + raw diff header → exit 2
#     (the inline sentinel mention trips the sentinel guard first; the raw-diff
#      guard is not reached here. The isolated raw-diff-on-$surface path — prose
#      <untrusted_context> mention + raw diff, no sentinel — is covered by test 16
#      "prose-uc-mention-rawdiff-denied").
run "prose-sentinel-mention-rawdiff-denied" 2 \
  '{"tool_input":{"prompt":"see the <system-reminder convention here\ndiff --git a b\n+evil\n"}}'

# 33. Large (~1MB) benign prompt → exit 0 (no placeholder/sentinel/diff-marker).
big=$(head -c 1048576 /dev/zero 2>/dev/null | tr '\0' 'a')
[ "${#big}" -ge 1000000 ] || big=$(yes a 2>/dev/null | tr -d '\n' | head -c 1048576)
run "large-benign-prompt" 0 \
  "{\"tool_input\":{\"prompt\":\"$big\"}}"

# 34. reviewer-dispatch with NO session_id field → exit 0, no crash.
#     (sid defaults to "no-session-id" via jq `// "no-session-id"`; first pass exits 0.
#      Unique Change summary so the count file cannot collide across runs.)
run "reviewer-dispatch-no-sid" 0 \
  "{\"tool_input\":{\"prompt\":\"<!-- squads:reviewer-dispatch -->\nChange summary: no-sid-test-$RANDOM\n\"}}"

# 35. Hostile session_id `../etc/pwned` — tr -cd strips slashes/dots → sid="etcpwned";
#     assert exit 0 and that the count file name carries no slash (no path traversal).
sid_hostile='../etc/pwned'
hostile_json="{\"session_id\":\"$sid_hostile\",\"tool_input\":{\"prompt\":\"<!-- squads:reviewer-dispatch -->\nChange summary: hostile-$RANDOM\n\"}}"
got=$(printf '%s' "$hostile_json" | bash "$hook" 2>/dev/null; echo "exit=$?")
got=${got##*exit=}
if [ "$got" = "0" ]; then echo "PASS: hostile-sid-exit0 (exit=$got)"; else echo "FAIL: hostile-sid-exit0 — expected 0, got $got" >&2; fail=1; fi
if find "${TMPDIR:-/tmp}" -maxdepth 1 -name 'squads-review-count-etcpwned-*' 2>/dev/null | grep -q .; then
  echo "PASS: hostile-sid-stripped-to-etcpwned (no slash in count file name)"
else
  echo "FAIL: hostile-sid-stripped — no etcpwned count file found" >&2
  fail=1
fi
rm -f "${TMPDIR:-/tmp}"/squads-review-count-etcpwned-* 2>/dev/null

rm -f "$tmp_clean" "$tmp_ph" "$tmp_uc_ph" "$tmp_uc_diff" "$tmp_empty" "$tmp_uc_bal_ph"
rm -rf "$tmp_plugin_root"
exit "$fail"
