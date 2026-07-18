#!/usr/bin/env bash
# Self-check for the squads hooks: bash hooks/test-hooks.sh
set -uo pipefail

hooks_dir=$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)
tmp=$(mktemp -d)
trap 'rm -rf "$tmp"' EXIT
mkdir -p "$tmp/docs/plan"
plan="$tmp/docs/plan/x.plan.md"
specs="$tmp/docs/plan/x.specs.md"

fails=0

check() { # name, expected exit code, script, json stdin
  local name=$1 expected=$2 script=$3 json=$4 rc=0
  printf '%s' "$json" | bash "$hooks_dir/$script" >/dev/null 2>&1 || rc=$?
  if [[ "$rc" -ne "$expected" ]]; then
    echo "FAIL: $name (exit $rc, want $expected)"
    fails=1
  fi
}

plan_json() { # event, extra tool_input fields as jq object body
  jq -n --arg fp "$plan" --arg ev "$1" --argjson extra "${2:-{\}}" \
    '{hook_event_name: $ev, tool_input: ({file_path: $fp} + $extra)}'
}

valid_task() {
  cat <<EOF
### $1: A

Depends on: $2
Files: a
Symbols: a
Satisfies: REQ-001
Action: a
Validate: \`x\`
Expected result: y
EOF
}

printf '#### REQ-001: A\n\nDetail: a\n' >"$specs"

{ printf 'Status: DRAFT\nDepth: contract\n\n'; valid_task TASK-001 none; } >"$plan"
check 'valid plan passes' 0 plan-check.sh "$(plan_json PostToolUse)"

{ printf 'Status: DRAFT\nDepth: contract\n\n'; valid_task TASK-001 TASK-009 | grep -v '^Validate:'; } >"$plan"
check 'missing field + dangling dep fails' 2 plan-check.sh "$(plan_json PostToolUse)"

{ printf 'Status: DRAFT\nDepth: contract\n\n'; valid_task TASK-001 TASK-002; echo; valid_task TASK-002 TASK-001; } >"$plan"
check 'dependency cycle fails' 2 plan-check.sh "$(plan_json PostToolUse)"

check 'plan born APPROVED denied' 2 plan-check.sh \
  "$(jq -n --arg fp "$tmp/docs/plan/new.plan.md" '{hook_event_name: "PreToolUse", tool_input: {file_path: $fp, content: "Status: APPROVED\n"}}')"

printf 'Status: DRAFT\nDepth: sketch\n' >"$plan"
check 'sketch flipped APPROVED denied' 2 plan-check.sh "$(plan_json PreToolUse '{"new_string": "Status: APPROVED"}')"

printf 'Status: DRAFT\nDepth: contract\n' >"$plan"
check 'contract flip allowed' 0 plan-check.sh "$(plan_json PreToolUse '{"new_string": "Status: APPROVED"}')"

check 'non-plan path ignored' 0 plan-check.sh \
  '{"hook_event_name": "PostToolUse", "tool_input": {"file_path": "src/main.ts"}}'

check 'garbage stdin ignored' 0 plan-check.sh 'not json'

check 'placeholder denied' 2 dispatch-check.sh '{"tool_input": {"prompt": "review {{diff}}"}}'
check 'sentinel denied' 2 dispatch-check.sh '{"tool_input": {"prompt": "x <system-reminder>y"}}'
check 'clean prompt allowed' 0 dispatch-check.sh '{"tool_input": {"prompt": "clean spec"}}'

if ! bash "$hooks_dir/session-start.sh" | grep -q '<squads-router>'; then
  echo 'FAIL: session-start emits router block'
  fails=1
fi

if [[ "$fails" -eq 0 ]]; then
  echo 'all hook self-checks passed'
else
  exit 1
fi
