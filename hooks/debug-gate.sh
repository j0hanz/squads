#!/usr/bin/env bash
# Stateful enforcement of parallel-debugging's HARD GATE: while that skill is
# active in this session, code edits are denied until the root cause is routed
# to a sibling skill (tdd / plan) — "no fix before reproduce, isolate".
# Markdown and test files stay editable (investigation notes and repro
# harnesses are legitimate during debugging). The gate is per-session and
# expires after 120 minutes so an abandoned debug run cannot wedge the session.
set -uo pipefail

if ! command -v jq >/dev/null 2>&1; then
  echo "squads debug-gate: jq not found — gate cannot run. Install jq (Windows: winget install jqlang.jq). Edits blocked while jq is missing." >&2
  exit 2
fi

input=$(cat)
tool=$(jq -r '.tool_name // empty' <<<"$input" 2>/dev/null) || exit 0
session_id=$(jq -r '.session_id // "unknown"' <<<"$input" | tr -cd 'a-zA-Z0-9-')
flag="${TMPDIR:-/tmp}/squads-debug-gate-${session_id:-unknown}"

case "$tool" in
  Skill)
    skill=$(jq -r '.tool_input.skill // empty' <<<"$input")
    case "$skill" in
      squads:parallel-debugging | parallel-debugging)
        touch "$flag"
        ;;
      squads:tdd | tdd | squads:plan | plan | \
        squads:review | review)
        # Routing to a debugging hand-off (tdd, plan) or a legit
        # route-out (review: review feedback, not a bug) closes
        # the gate. dispatch-agents is NOT a hand-off — letting it lift
        # the gate bypasses reproduce-first.
        rm -f "$flag"
        ;;
    esac
    ;;

  Write | Edit | NotebookEdit)
    [[ -f "$flag" ]] || exit 0

    if [[ -n "$(find "$flag" -mmin +120 2>/dev/null)" ]]; then
      rm -f "$flag"
      exit 0
    fi

    file_path=$(jq -r '.tool_input.file_path // empty' <<<"$input")
    base=$(basename "${file_path//\\//}")
    case "$base" in
      # Exempt markdown + genuine test/spec files only. Anchor "test"/"spec"
      # as a delimited token (start, end, or beside _ . -) so production files
      # like latest.js / inspect.js / special.py / contest.go are NOT exempted.
      *.md) exit 0 ;;
      test_* | *_test | *_test.* | *.test.* | *.test | \
      *_spec | *_spec.* | *.spec.* | *.spec | \
      *Test | *Test.* | *Spec | *Spec.* | \
      conftest.py | *.stories.* | *.cy.*)
        exit 0 ;;
    esac

    echo "squads debug-gate: parallel-debugging is active — its HARD GATE forbids code edits before the root cause is reproduced, adversarially verified, and routed to tdd (logic bug) or plan (design-level). Invoke the routing skill first; if debugging was abandoned, remove $flag." >&2
    exit 2
    ;;
esac

exit 0
