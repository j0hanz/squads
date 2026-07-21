#!/usr/bin/env bash
# squads-plugin hook dispatcher. One rule function per <rule> subcommand, invoked as
# `squads-hook.sh <rule>` via command-string hooks.json.
#
# Rules:
#   session-start   SessionStart                          — inject the squads router
#   dispatch-check  PreToolUse Agent|SendMessage|Workflow — deny unresolved {{...}}
#                   placeholders in dispatch bodies (the Governor's hook-fire probe
#                   expects exactly this deny; a clean dispatch is silent by design)
#   pre-tool        PreToolUse Skill|Write|Edit|MultiEdit|NotebookEdit — debug-gate
#                   (parallel-debugging HARD GATE) then plan-schema (Write to a
#                   docs/plan/*.plan.md)
#
# `set -uo pipefail` WITHOUT `-e` is intentional: grep/find return non-zero
# legitimately and must not abort the hook. Do not add `-e`.
set -uo pipefail

state_dir() { printf '%s' "${TMPDIR:-/tmp}"; }

# Every deny names the rule + a one-line remediation, on stderr, then exit 2.
deny() { # deny <rule> <message>
  echo "squads $1: $2" >&2
  exit 2
}

# True if the given basename is markdown or a genuine test/spec file — those stay
# editable while the debug-gate is up (investigation notes and repro harnesses are
# legitimate during debugging). "test"/"spec" anchored as a delimited token so
# production files like latest.js / inspect.js / contest.go are NOT exempt.
is_exempt_path() { # is_exempt_path <basename> → 0 if exempt
  case "$1" in
    *.md | *.MD) return 0 ;;
    test_* | *_test | *_test.* | *.test.* | *.test | \
      *_spec | *_spec.* | *.spec.* | *.spec | \
      *Test | *Test.* | *Spec | *Spec.* | \
      conftest.py | *.stories.* | *.cy.* | \
      test.* | spec.* | tests.*) return 0 ;;
  esac
  return 1
}

# ---------- session-start ----------

session_start() {
  # Reap stale per-session state from crashed sessions (120-min horizon, flat dir).
  find "$(state_dir)" -maxdepth 1 -name 'squads-*' -mmin +120 -exec rm -f {} + 2>/dev/null || true
  if ! command -v jq >/dev/null 2>&1; then
    echo 'squads: jq not found — dispatch-check will DENY dispatches this session. Install jq: Windows — winget install jqlang.jq; macOS — brew install jq; Linux — apt/dnf install jq.' >&2
  fi
  echo "Skill names below invoke via the Skill tool as 'squads:<name>' (e.g. /dispatch-agents -> squads:dispatch-agents)."
  echo
  echo '<squads-router>'
  echo 'Route every incoming task or user request to [dispatch-agents](../dispatch-agents/SKILL.md); its Step 0 Governor classifies the request (first match wins) and picks the workflow + fleet shape. Skip only for pure conversation or a one-shot edit answerable direct.'
  echo '</squads-router>'
}

# ---------- dispatch-check ----------

# Deny a dispatch whose body carries an unresolved {{...}} placeholder. Fail-closed
# without jq (squads is dispatch-first; hygiene unverifiable = blocked, with hint).
# ponytail: an unclosed <untrusted_context> open tag strips the rest of the body from
# linting — add a balance check if that ever bites.
dispatch_check() {
  command -v jq >/dev/null 2>&1 || deny dispatch-check "jq not found — guard cannot run. Install jq (Windows: winget install jqlang.jq; macOS: brew install jq; Linux: apt/dnf install jq) and retry. Blocked."
  local body placeholders
  body=$(jq -r '[.tool_input.prompt // .tool_input.message // "", .tool_input.script // "", .tool_input.description // ""] | join("\n")' 2>/dev/null) || exit 0
  # <untrusted_context> blocks are data to analyze, never instructions — strip them
  # before linting so wrapped third-party content can legitimately contain {{...}}.
  body=$(awk '
    /^<untrusted_context>[[:space:]]*$/ { skip = 1; next }
    /^<\/untrusted_context>[[:space:]]*$/ { skip = 0; next }
    !skip
  ' <<<"$body")
  placeholders=$(grep -oE '\{\{[^{}]*\}\}' <<<"$body" | sort -u | paste -sd, -)
  [[ -z "$placeholders" ]] || deny dispatch-check "dispatch body contains unresolved placeholder(s) $placeholders — replace every {{...}} with real values before dispatching (wrap third-party content in <untrusted_context> if the braces are data)."
  exit 0
}

# ---------- pre-tool ----------

# parallel-debugging HARD GATE: while that skill is active, non-test/non-md edits are
# denied until the root cause is routed to tdd / plan / review (which lifts the flag).
# dispatch-agents is NOT a lift — it bypasses reproduce-first. Per-session flag file,
# 120-min expiry backstop.
debug_gate() { # debug_gate <hook-input-json>
  local input="$1" tool sid skill file_path flag
  tool=$(jq -r '.tool_name // ""' <<<"$input" 2>/dev/null) || return 0
  sid=$(jq -r '.session_id // ""' <<<"$input" 2>/dev/null | tr -cd 'a-zA-Z0-9-')
  flag="$(state_dir)/squads-debug-gate-${sid:-unknown}"
  case "$tool" in
    Skill)
      skill=$(jq -r '.tool_input.skill // ""' <<<"$input" 2>/dev/null)
      case "$skill" in
        squads:parallel-debugging | parallel-debugging) touch "$flag" ;;
        squads:tdd | tdd | squads:plan | plan | squads:review | review) rm -f "$flag" ;;
      esac
      ;;
    Write | Edit | MultiEdit | NotebookEdit)
      [[ -f "$flag" ]] || return 0
      if [[ -n "$(find "$flag" -mmin +120 2>/dev/null)" ]]; then
        rm -f "$flag"
        return 0
      fi
      file_path=$(jq -r '.tool_input.file_path // .tool_input.notebook_path // ""' <<<"$input" 2>/dev/null)
      is_exempt_path "$(basename "${file_path//\\//}")" ||
        deny debug-gate "parallel-debugging is active — its HARD GATE forbids code edits before the root cause is reproduced and routed to tdd (logic bug) or plan (design-level); review also lifts. If debugging was abandoned, remove $flag."
      ;;
  esac
  return 0
}

# Canonical Task Block guard on Write to a docs/plan/*.plan.md. Write-only: Edit's
# old_string/new_string is a partial view of the file, so Edit is not matched.
plan_schema() { # plan_schema <hook-input-json>
  local input="$1" file_path content missing
  file_path=$(jq -r '.tool_input.file_path // ""' <<<"$input" 2>/dev/null) || return 0
  case "${file_path//\\//}" in
    */docs/plan/*.plan.md | docs/plan/*.plan.md) ;;
    *) return 0 ;;
  esac
  content=$(jq -r '.tool_input.content // ""' <<<"$input" 2>/dev/null)
  grep -qE '^Origin:[[:space:]]*\S' <<<"$content" ||
    deny plan-schema "plan missing an 'Origin:' header (e.g. 'Origin: plan' or 'Origin: human')."
  # Every ### TASK-NNN: block must carry all 7 Canonical Task Block field labels.
  missing=$(awk '
    BEGIN { split("Depends on|Files|Symbols|Satisfies|Action|Validate|Expected result", a, "|"); for (i in a) want[a[i]]=1 }
    /^### TASK-[0-9]+:/ { if (id != "") emit(); match($0, /TASK-[0-9]+/); id=substr($0, RSTART, RLENGTH); delete seen; next }
    id == "" { next }
    { for (w in want) if (index($0, w ":") == 1) seen[w]=1 }
    END { if (id != "") emit() }
    function emit() { m=""; for (w in want) if (!(w in seen)) m=m (m==""?"":", ") w; if (m != "") printf "%s missing: %s\n", id, m }
  ' <<<"$content")
  [[ -z "$missing" ]] ||
    deny plan-schema "plan has TASK block(s) missing Canonical Task Block field(s) — $(printf '%s' "$missing" | tr '\n' '; '): each ### TASK-NNN: block needs all 7 (Depends on / Files / Symbols / Satisfies / Action / Validate / Expected result)."
  return 0
}

# Consolidated PreToolUse entry: one stdin read, debug-gate first (hard gate), then
# plan-schema on Write. No jq → the flag was never set either; nothing to enforce.
pre_tool() {
  command -v jq >/dev/null 2>&1 || exit 0
  local input tool
  input=$(cat)
  debug_gate "$input"
  tool=$(jq -r '.tool_name // ""' <<<"$input" 2>/dev/null)
  [[ "$tool" == "Write" ]] && plan_schema "$input"
  exit 0
}

# ---------- dispatch ----------

case "${1:-}" in
  session-start) session_start ;;
  dispatch-check) dispatch_check ;;
  pre-tool) pre_tool ;;
  *)
    echo "squads: unknown rule '${1:-}'" >&2
    exit 0
    ;;
esac
