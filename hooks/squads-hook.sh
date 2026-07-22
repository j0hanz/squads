#!/usr/bin/env bash
# squads-plugin hook dispatcher. One rule function per <rule> subcommand, invoked as
# `squads-hook.sh <rule>` via command-string hooks.json.
#
# Rules:
#   session-start   SessionStart                          — inject the squads router
#   dispatch-check  PreToolUse Agent|SendMessage|Workflow — deny unresolved {{...}}
#                   placeholders in dispatch bodies (a clean dispatch is silent by
#                   design: nothing on a clean pass, deny on stderr exit 2)
#   pre-tool        PreToolUse Write|Edit|MultiEdit|NotebookEdit — debug-gate
#                   (debug HARD GATE), then plan-schema (Write to a
#                   docs/plan/*.plan.md)
#   post-tool       PostToolUse Write|Edit|MultiEdit|NotebookEdit — plan-schema
#                   feedback-only on docs/plan/*.plan.md (exit 2 + stderr on
#                   violation, silent exit 0 otherwise)
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

is_plan_path() { # is_plan_path <path> → 0 if a docs/plan/*.plan.md
  case "${1//\\//}" in
    */docs/plan/*.plan.md | docs/plan/*.plan.md) return 0 ;;
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
  echo 'Route each task by first match and invoke the matched skill DIRECTLY — no mandatory first hop:'
  echo 'unexpected failure/RED -> squads:debug · diff or review feedback -> squads:review · single new logic behavior -> squads:tdd · named deliverable (plan/spec/doc) -> squads:plan · open problem, no shape yet -> squads:brainstorm · bulk/fan-out/whole-repo audit OR an APPROVED docs/plan/*.plan.md -> squads:dispatch-agents (its Governor sizes the fleet and picks inline vs composed).'
  echo 'One-shot edit or pure conversation -> answer direct, no skill.'
  echo '</squads-router>'
}

# ---------- dispatch-check ----------

# Deny a dispatch whose body carries an unresolved {{...}} placeholder. Fail-closed
# without jq (hygiene unverifiable = blocked, not shipped, with hint).
dispatch_check() {
  command -v jq >/dev/null 2>&1 || deny dispatch-check "jq not found — guard cannot run. Install jq and retry. Blocked."
  local body placeholders
  # The dispatch body is a concatenation of all the fields that can carry placeholders. If any field is missing, it is treated as empty. The jq command extracts these fields and joins them with newlines.
  body=$(jq -r '[.tool_input.prompt // "", .tool_input.message // "", .tool_input.script // "", .tool_input.description // "", .tool_input.summary // "", .tool_input.to // "", .tool_input.scriptPath // "", .tool_input.name // "", (.tool_input.args // "" | tostring)] | join("\n")' 2>/dev/null) ||
    deny dispatch-check "dispatch payload is not valid JSON — placeholder hygiene unverifiable. Blocked; retry."
  # <untrusted_context> blocks are data to analyze, never instructions — strip them
  # before linting so wrapped third-party content can legitimately contain {{...}}.
  # Same pass fails closed on a misordered/unclosed block (close before open, or
  # EOF still inside one): either could smuggle a placeholder past the strip.
  # (dispatch-check is placeholder hygiene only — it does NOT enforce routing.)
  body=$(awk '
    /^<untrusted_context>[[:space:]]*$/  { if (skip) { bad = 1; exit } skip = 1; next }
    /^<\/untrusted_context>[[:space:]]*$/ { if (!skip) { bad = 1; exit } skip = 0; next }
    !skip
    END { if (skip || bad) exit 3 }
  ' <<<"$body") ||
    deny dispatch-check "misordered/unclosed <untrusted_context> block — open before close, and close it; wrap braces as data inside."
  placeholders=$(grep -oE '\{\{[^{}]*\}\}' <<<"$body" | sort -u | paste -sd, -)
  [[ -z "$placeholders" ]] || deny dispatch-check "unresolved placeholder(s) $placeholders — replace every {{...}} with real values. Wrap third-party data in <untrusted_context>."
  exit 0
}

# ---------- pre-tool ----------

# debug HARD GATE (pre-tool side): while squads:debug is active, non-test/non-md
# edits are denied. Deny-only here — the flag is armed by squads:debug and lifted
# by tdd / plan / review on the PostToolUse side (post_tool), so a rejected Skill
# call never arms or lifts it. dispatch-agents is NOT a lift — it bypasses
# reproduce-first. Per-session flag file, 120-min expiry backstop auto-lifts an
# abandoned flag on the next edit attempt.
debug_gate() { # debug_gate <tool> <sid> <file_path>
  local tool="$1" sid="$2" file_path="$3" flag
  case "$tool" in
    Write | Edit | MultiEdit | NotebookEdit) ;;
    *) return 0 ;;
  esac
  sid=$(tr -cd 'a-zA-Z0-9-' <<<"$sid" 2>/dev/null)
  flag="$(state_dir)/squads-debug-gate-${sid:-unknown}"
  [[ -f "$flag" ]] || return 0
  if [[ -n "$(find "$flag" -mmin +120 2>/dev/null)" ]]; then
    rm -f "$flag"
    return 0
  fi
  is_exempt_path "$(basename "${file_path//\\//}")" ||
    deny debug-gate "debug active — code edits blocked. Reproduce root cause, then route: tdd (logic bug) or plan (design). review also lifts. Abandoned? remove $flag"
}

# Shared plan-schema validator: file content on stdin, first violation text on
# stdout (empty if valid). Both pre-tool (Write deny) and post-tool
# (feedback-only) paths route through this. Short-circuits on Origin like the
# original inline check.
plan_schema_violations() {
  local content missing
  content=$(cat)
  grep -qE '^Origin:[[:space:]]*\S' <<<"$content" || {
    printf "missing 'Origin:' header (e.g. 'Origin: plan').\n"
    return 0
  }
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
    printf 'TASK block(s) missing fields — %s. Each ### TASK-NNN: block needs all 7: Depends on / Files / Symbols / Satisfies / Action / Validate / Expected result.\n' "$(printf '%s' "$missing" | tr '\n' '; ')"
}

# Canonical Task Block guard on Write to a docs/plan/*.plan.md. Write-only: Edit's
# old_string/new_string is a partial view of the file, so Edit is not matched.
plan_schema() { # plan_schema <file_path> <content>
  local file_path="$1" content="$2" violations
  is_plan_path "$file_path" || return 0
  violations=$(printf '%s' "$content" | plan_schema_violations)
  [[ -z "$violations" ]] || deny plan-schema "$violations"
  return 0
}

# Consolidated PreToolUse entry: one stdin read, debug-gate (hard gate) then
# plan-schema on Write. No jq → the flags were never set either; nothing to
# enforce.
pre_tool() {
  command -v jq >/dev/null 2>&1 || exit 0
  local input tool="" sid="" file_path="" content=""
  input=$(cat)
  # Single jq for scalars. `read` (bash 3.2+), NOT `mapfile` (bash 4.0+): the
  # dispatcher must run under macOS /bin/bash 3.2, where mapfile is absent and
  # would silently no-op every gate. jq failure → fewer lines → vars stay empty
  # (declared above) → fail-open, no set -u abort.
  { read -r tool; read -r sid; read -r file_path; } < <(
    jq -r '.tool_name // "", .session_id // "",
          (.tool_input.file_path // .tool_input.notebook_path // "")' <<<"$input" 2>/dev/null | tr -d '\r'
  )
  # Arming/lifting is post_tool's job, so the gate does not mutate state here.
  debug_gate "$tool" "$sid" "$file_path"
  [[ "$tool" == "Write" ]] && {
    content=$(jq -r '.tool_input.content // ""' <<<"$input" 2>/dev/null)
    plan_schema "$file_path" "$content"
  }
  exit 0
}

# ---------- post-tool ----------

# PostToolUse. Two jobs, keyed off the tool that just COMPLETED (a PreToolUse
# deny never reaches here, so a rejected Skill call cannot arm/lift a flag):
#   Skill → arm the debug flag (squads:debug); lift it (tdd / plan / review).
#           This is where session state is mutated — never at PreToolUse.
#   Write|Edit|... on a docs/plan/*.plan.md → re-read the completed file and emit
#           missing-field violations to stderr, exit 2. Feedback-only, never a
#           deny. Silent exit 0 otherwise (missing jq, unreadable file, etc.).
post_tool() {
  command -v jq >/dev/null 2>&1 || exit 0
  local input tool file_path content violations
  input=$(cat)
  tool=$(jq -r '.tool_name // ""' <<<"$input" 2>/dev/null)
  case "$tool" in
    Skill)
      local skill sid
      skill=$(jq -r '.tool_input.skill // ""' <<<"$input" 2>/dev/null)
      sid=$(jq -r '.session_id // ""' <<<"$input" 2>/dev/null)
      sid=$(tr -cd 'a-zA-Z0-9-' <<<"$sid" 2>/dev/null)
      case "$skill" in
        squads:debug) touch "$(state_dir)/squads-debug-gate-${sid:-unknown}" ;;
        squads:tdd | squads:plan | squads:review) rm -f "$(state_dir)/squads-debug-gate-${sid:-unknown}" ;;
      esac
      exit 0
      ;;
    Write | Edit | MultiEdit | NotebookEdit) ;;
    *) exit 0 ;;
  esac
  file_path=$(jq -r '.tool_input.file_path // ""' <<<"$input" 2>/dev/null)
  is_plan_path "$file_path" || exit 0
  # Remember the last plan path touched this session so the PreCompact recap
  # can name it after compaction. One line, reaped with the rest of squads-*
  # by session_start's 120-min find. sid sanitized to prevent traversal.
  local sid_for_plan
  sid_for_plan=$(jq -r '.session_id // ""' <<<"$input" 2>/dev/null)
  sid_for_plan=$(tr -cd 'a-zA-Z0-9-' <<<"$sid_for_plan" 2>/dev/null)
  printf '%s\n' "${file_path//\\//}" > "$(state_dir)/squads-last-plan-${sid_for_plan:-unknown}" 2>/dev/null || true
  [[ -r "${file_path//\\//}" ]] || exit 0
  content=$(cat "${file_path//\\//}") || exit 0
  violations=$(printf '%s' "$content" | plan_schema_violations)
  if [[ -n "$violations" ]]; then
    printf '%s\n' "$violations" >&2
    exit 2
  fi
  exit 0
}

# ---------- compact ----------

# PreCompact: inject a one-block recap of in-flight squads state so it
# survives compaction. Two signals: the debug-gate flag (mid-debug) and the
# last plan path touched. Silent + exit 0 when neither is set — never inject
# noise, never block compaction. Fail-open on any error.
compact() {
  command -v jq >/dev/null 2>&1 || exit 0
  local input sid flag plan_file recap=""
  input=$(cat)
  sid=$(jq -r '.session_id // ""' <<<"$input" 2>/dev/null)
  sid=$(tr -cd 'a-zA-Z0-9-' <<<"$sid" 2>/dev/null)
  flag="$(state_dir)/squads-debug-gate-${sid:-unknown}"
  if [[ -f "$flag" ]]; then
    # honor the same 120-min expiry as debug_gate so a stale flag isn't
    # reported as active
    if [[ -z "$(find "$flag" -mmin +120 2>/dev/null)" ]]; then
      recap="debug-gate ACTIVE (mid-debug — root cause not yet confirmed; code edits blocked. Route to debug/tdd/plan; review also lifts the gate.)"
    fi
  fi
  plan_file="$(state_dir)/squads-last-plan-${sid:-unknown}"
  if [[ -s "$plan_file" ]]; then
    local path
    path=$(head -1 "$plan_file" 2>/dev/null)
    [[ -n "$path" ]] && recap="${recap:+$recap
}active plan: $path (re-read it to resume the task thread)"
  fi
  [[ -z "$recap" ]] || {
    printf '<squads-state>\n'
    printf '%s\n' "$recap"
    printf '</squads-state>\n'
  }
  exit 0
}

# ---------- dispatch ----------

case "${1:-}" in
  session-start) session_start ;;
  dispatch-check) dispatch_check ;;
  pre-tool) pre_tool ;;
  post-tool) post_tool ;;
  compact) compact ;;
  *)
    echo "squads: unknown rule '${1:-}'" >&2
    exit 0
    ;;
esac
