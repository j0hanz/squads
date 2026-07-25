#!/usr/bin/env bash
# squads-plugin hook dispatcher. One rule function per subcommand, invoked as
# `squads-hook.sh <rule>` from hooks.json.
#
#   session-start   SessionStart — inject the router; on source=compact a lean
#                   refresher plus <squads-state> recap. Only rule whose stdout
#                   becomes context, so it owns the recap (PreCompact stdout is
#                   debug-log-only).
#   dispatch-check  PreToolUse Agent|SendMessage|Workflow — deny unresolved
#                   {{...}} placeholders; warn (never deny) on non-haiku Agent.
#                   Fails OPEN on any infrastructure failure.
#   pre-tool        PreToolUse Write|Edit|MultiEdit|NotebookEdit — debug-gate
#                   (hard), then plan-schema on Write to docs/plan/*.plan.md.
#   post-tool       PostToolUse Skill|Write|Edit|MultiEdit|NotebookEdit —
#                   arm/lift the debug flag on Skill, re-check plan-schema.
#                   Feedback-only. Agent returns are NOT shape-checked: the
#                   Handoff Contract is prompt-enforced (skills/squads/SKILL.md:43)
#                   and a deny here can't tell squads dispatches from ad-hoc ones.
#
# No `-e`: grep/find return non-zero legitimately and must not abort the hook.
set -uo pipefail

state_dir() { printf '%s' "${TMPDIR:-/tmp}"; }

RULE="${1:-}"
NOTICES=""
LAST_MSG=""

# Deny: rule name + remediation on stderr, exit 2. Pending notices ride along —
# exit 2 discards stdout, so stderr is the only channel Claude reads here.
deny() { # deny <rule> <message>
  LAST_MSG="squads $1: $2${NOTICES:+ | $NOTICES}"
  echo "$LAST_MSG" >&2
  exit 2
}

# Fail-open notices. Exit-0 stderr reaches nobody (Claude reads stderr only on
# exit 2); JSON `systemMessage` on stdout is the exit-0 channel that reaches the
# user. Not usable in session-start, where stdout IS the context channel.
#
# Accumulated and flushed once by the EXIT trap: two JSON objects on stdout parse
# as neither, losing both. Flushing on an exit-2 path is harmless.
notify() { # notify <message>
  NOTICES="${NOTICES:+$NOTICES }$1"
}
flush_notices() {
  local code=$? dir
  [[ -z "$NOTICES" ]] || printf '{"systemMessage":"%s"}\n' \
    "$(printf '%s' "$NOTICES" | sed 's/\\/\\\\/g; s/"/\\"/g')"
  # SQUADS_PERF=1: one line per fire — the only evidence a rule ran, since
  # silence is the pass signal. Never affects exit status ($? survives the trap).
  if [[ "${SQUADS_PERF:-0}" == "1" ]]; then
    dir="${PERF_LOG_DIR:-$HOME/.claude/squads-perf}"
    mkdir -p "$dir" 2>/dev/null &&
      printf '%s %-14s exit=%s %s\n' "$(date +%H:%M:%S)" "$RULE" "$code" \
        "${LAST_MSG:-$NOTICES}" >>"$dir/$(date +%Y-%m-%d).log" 2>/dev/null
  fi
  return 0
}
trap flush_notices EXIT

# Markdown, test/spec directories, or test/spec basenames stay editable while the
# debug-gate is up. Directory check first: test trees hold helpers and fixtures
# with no test token in the name (src/__tests__/user.js, tests/factories.py).
# Each pattern needs a literal /<dir>/ and basenames anchor test/spec as a
# delimited token, so contest/foo.go, src/latest/x.go, inspect.js are NOT exempt.
is_exempt_path() { # is_exempt_path <slash-normalized path> → 0 if exempt
  case "/$1" in
    */__tests__/* | */__test__/* | */tests/* | */test/* | */spec/* | */specs/*) return 0 ;;
  esac
  case "${1##*/}" in
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
  # Plain text, not notify(): stdout here is added to context verbatim, and valid
  # JSON on stdout would be parsed as hook output, swallowing the router block.
  local input source="" sid=""
  input=$(cat)
  if command -v jq >/dev/null 2>&1; then
    # `read` into pre-initialized vars: jq failure yields no lines and both stay
    # empty rather than unset, so `set -u` cannot abort the rule.
    { read -r source; read -r sid; } < <(
      jq -r '.source // "", .session_id // ""' <<<"$input" 2>/dev/null | tr -d '\r'
    )
    sid=$(tr -cd 'a-zA-Z0-9-' <<<"$sid" 2>/dev/null)
  else
    echo 'squads: jq not found — every gate fails OPEN this session (placeholder, debug-gate and plan-schema checks are skipped, each with a warning). Install jq: Windows — winget install jqlang.jq; macOS — brew install jq; Linux — apt/dnf install jq.'
    echo
  fi
  # Reap stale per-session state from crashed sessions (120-min horizon). Runs
  # AFTER sid is known and skips this session's own files: on resume/compact the
  # live debug-gate flag and plan pointer are routinely older than the horizon,
  # and the recap below still has to read them.
  find "$(state_dir)" -maxdepth 1 -name 'squads-*' ! -name "*-${sid:-unknown}" \
    -mmin +120 -exec rm -f {} + 2>/dev/null || true
  # Compaction: already routed this session, so emit a one-line refresher plus
  # in-flight state compaction would otherwise drop. Only place the recap can
  # live — PreCompact stdout never reaches context. Any other source (or jq
  # missing) gets the full block.
  if [[ "$source" == "compact" ]]; then
    echo '<squads-router>'
    echo 'squads routing (refresher): RED/failure -> squads:debug · diff/review feedback -> squads:review · new logic -> squads:tdd · named deliverable (plan/spec/doc) -> squads:plan · open problem -> squads:brainstorm · bulk fan-out / approved docs/plan/*.plan.md -> squads:dispatch-agents · else answer direct.'
    echo '</squads-router>'
    local flag plan_file path recap=""
    flag="$(state_dir)/squads-debug-gate-${sid:-unknown}"
    # Same 120-min expiry as debug_gate, so a stale flag is not reported active.
    if [[ -f "$flag" && -z "$(find "$flag" -mmin +120 2>/dev/null)" ]]; then
      recap="debug-gate ACTIVE (mid-debug — root cause not yet confirmed; code edits blocked. Route to debug/tdd/plan; review also lifts the gate.)"
    fi
    plan_file="$(state_dir)/squads-last-plan-${sid:-unknown}"
    if [[ -s "$plan_file" ]]; then
      path=$(head -1 "$plan_file" 2>/dev/null)
      [[ -n "$path" ]] && recap="${recap:+$recap
}active plan: $path (re-read it to resume the task thread)"
    fi
    [[ -z "$recap" ]] || printf '<squads-state>\n%s\n</squads-state>\n' "$recap"
    return 0
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

# Deny a dispatch carrying an unresolved {{...}} placeholder. Fails OPEN on every
# infrastructure failure: a blocked dispatch costs the whole fleet, a leaked
# placeholder costs one subagent.
dispatch_check() {
  if ! command -v jq >/dev/null 2>&1; then
    notify "squads dispatch-check: jq not found — placeholder hygiene unverified, dispatch allowed. Install jq."
    exit 0
  fi
  # tool/model initialized: an empty payload makes both `read`s hit EOF, and a
  # bare `local` would leave them unset — `set -u` would abort before the grep.
  local input body placeholders tool="" model=""
  # One stdin read; jq runs more than once below and stdin is not rewindable.
  input=$(cat)
  # Body = every field that can carry a placeholder, missing ones as empty.
  body=$(jq -r '[.tool_input.prompt // "", .tool_input.message // "", .tool_input.script // "", .tool_input.description // "", .tool_input.summary // "", .tool_input.to // "", .tool_input.scriptPath // "", .tool_input.name // "", (.tool_input.args // "" | tostring)] | join("\n")' <<<"$input" 2>/dev/null) ||
    { notify "squads dispatch-check: dispatch payload is not valid JSON — placeholder hygiene unverified, dispatch allowed."; exit 0; }
  # Flat-haiku policy (skills/squads/SKILL.md#model--fan-out-policy). Warn only,
  # and only for Agent — the one tool carrying the param. Kept out of "$body" so
  # a model name can never read as a placeholder.
  { read -r tool; read -r model; } < <(jq -r '.tool_name // "", (.tool_input.model // "")' <<<"$input" 2>/dev/null | tr -d '\r')
  if [[ "$tool" == "Agent" ]]; then
    if [[ -z "$model" ]]; then
      notify "squads dispatch-check: model param unavailable — agents inherit session model; flat-haiku cost model void."
    elif [[ "$model" != "haiku" ]]; then
      notify "squads dispatch-check: model '$model' is not haiku — flat-haiku cost model void (skills/squads/SKILL.md:69)."
    fi
  fi
  # <untrusted_context> is data, never instructions — strip it so wrapped
  # third-party content can legitimately contain {{...}}. A misordered/unclosed
  # block fails OPEN and loudly (notify + exit 0), per this rule's fail-open
  # policy — the strip is abandoned rather than applied to an ambiguous body.
  body=$(awk '
    /^<untrusted_context>[[:space:]]*$/  { if (skip) { bad = 1; exit } skip = 1; next }
    /^<\/untrusted_context>[[:space:]]*$/ { if (!skip) { bad = 1; exit } skip = 0; next }
    !skip
    END { if (skip || bad) exit 3 }
  ' <<<"$body") ||
    { notify "squads dispatch-check: misordered/unclosed <untrusted_context> block — placeholder hygiene unverified, dispatch allowed. Wrap braces as data inside."; exit 0; }
  placeholders=$(grep -oE '\{\{[^{}]*\}\}' <<<"$body" | sort -u | paste -sd, -)
  [[ -z "$placeholders" ]] || deny dispatch-check "unresolved placeholder(s) $placeholders — replace every {{...}} with real values. Wrap third-party data in <untrusted_context>."
  exit 0
}

# ---------- pre-tool ----------

# debug HARD GATE: while squads:debug is active, non-test/non-md edits are denied.
# Deny-only — the flag is armed by squads:debug and lifted by tdd/plan/review in
# post_tool, so a rejected Skill call never arms or lifts it. dispatch-agents is
# NOT a lift (it bypasses reproduce-first). Per-session flag, 120-min expiry
# auto-lifts an abandoned gate on the next edit attempt.
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
    notify "squads debug-gate: flag expired (>120min) — gate lifted; re-invoke squads:debug if still mid-debug."
    rm -f "$flag"
    return 0
  fi
  is_exempt_path "${file_path//\\//}" ||
    deny debug-gate "debug active — code edits blocked. Reproduce root cause, then route: tdd (logic bug) or plan (design). review also lifts. Abandoned? remove $flag"
}

# Shared plan-schema validator: file content on stdin, violations on stdout
# (empty if valid). Both the pre-tool deny and post-tool feedback paths use it.
plan_schema_violations() {
  local content missing
  content=$(cat)
  grep -qE '^Origin:[[:space:]]*\S' <<<"$content" || {
    printf "missing 'Origin:' header (e.g. 'Origin: plan').\n"
    return 0
  }
  # Every ### TASK-NNN: block must carry all 7 Canonical Task Block fields.
  missing=$(awk '
    BEGIN { split("Depends on|Files|Symbols|Satisfies|Action|Validate|Expected result", a, "|"); for (i in a) want[a[i]]=1 }
    /^### TASK-[0-9]+:/ { if (id != "") emit(); match($0, /TASK-[0-9]+/); id=substr($0, RSTART, RLENGTH); delete seen; files_count=0; next }
    id == "" { next }
    { for (w in want) if (index($0, w ":") == 1) { seen[w]=1; if (w == "Files") { value=substr($0, length(w)+2); gsub(/^[[:space:]]+|[[:space:]]+$/, "", value); files_count=0; if (value != "") { n=split(value, parts, ","); for (i=1; i<=n; i++) { gsub(/^[[:space:]]+|[[:space:]]+$/, "", parts[i]); if (parts[i] != "") files_count++ } } } } }
    END { if (id != "") emit() }
    function emit() { m=""; for (w in want) if (!(w in seen)) m=m (m==""?"":", ") w; if (m != "") printf "%s missing: %s\n", id, m; if (files_count > 3) printf "%s Files: lists %d paths (max 3) — decompose per the granularity rule.\n", id, files_count }
  ' <<<"$content")
  [[ -z "$missing" ]] ||
    printf '%s Each ### TASK-NNN: block needs all 7 fields (Depends on / Files / Symbols / Satisfies / Action / Validate / Expected result) and at most 3 paths in Files:.\n' "$(printf '%s' "$missing" | tr '\n' ';')"
}

# Write-only: Edit's old_string/new_string is a partial view of the file.
plan_schema() { # plan_schema <file_path> <content>
  local file_path="$1" content="$2" violations
  is_plan_path "$file_path" || return 0
  violations=$(printf '%s' "$content" | plan_schema_violations)
  [[ -z "$violations" ]] || deny plan-schema "$violations"
  return 0
}

# One stdin read, debug-gate then plan-schema. No jq → the flags were never set
# either; nothing to enforce.
pre_tool() {
  command -v jq >/dev/null 2>&1 || { notify "squads pre-tool: jq not found — debug-gate and plan-schema not applied."; exit 0; }
  local input tool="" sid="" file_path="" content=""
  input=$(cat)
  # `read` (bash 3.2+), NOT `mapfile` (4.0+): macOS /bin/bash is 3.2, where
  # mapfile is absent and would silently no-op every gate. jq failure → fewer
  # lines → vars stay empty → fail-open, no set -u abort.
  { read -r tool; read -r sid; read -r file_path; } < <(
    jq -r '.tool_name // "", .session_id // "",
          (.tool_input.file_path // .tool_input.notebook_path // "")' <<<"$input" 2>/dev/null | tr -d '\r'
  )
  # Arming/lifting is post_tool's job — no state mutation here.
  debug_gate "$tool" "$sid" "$file_path"
  [[ "$tool" == "Write" ]] && {
    content=$(jq -r '.tool_input.content // ""' <<<"$input" 2>/dev/null)
    plan_schema "$file_path" "$content"
  }
  exit 0
}

# ---------- post-tool ----------

# Keyed off the tool that just COMPLETED (a PreToolUse deny never reaches here):
#   Skill → arm (squads:debug) or lift (tdd/plan/review) the flag. Session state
#           is mutated here, never at PreToolUse.
#   Write|... on a docs/plan/*.plan.md → re-read the file, emit violations to
#           stderr with exit 2. Feedback-only, never a deny.
post_tool() {
  # Loud, not silent: with no jq the flag is never armed or lifted, so the gate
  # does not merely fail to block — it never exists.
  command -v jq >/dev/null 2>&1 || {
    notify "squads post-tool: jq not found — the debug-gate flag is never armed or lifted this session and plan-schema feedback is off. Install jq."
    exit 0
  }
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
  # Remember the last plan path so the post-compact recap can name it. Reaped
  # with the rest of squads-* by session_start. sid sanitized against traversal.
  local sid_for_plan
  sid_for_plan=$(jq -r '.session_id // ""' <<<"$input" 2>/dev/null)
  sid_for_plan=$(tr -cd 'a-zA-Z0-9-' <<<"$sid_for_plan" 2>/dev/null)
  printf '%s\n' "${file_path//\\//}" > "$(state_dir)/squads-last-plan-${sid_for_plan:-unknown}" 2>/dev/null || true
  [[ -r "${file_path//\\//}" ]] || exit 0
  content=$(cat "${file_path//\\//}") || exit 0
  violations=$(printf '%s' "$content" | plan_schema_violations)
  # Named + remediated like a deny, but not deny(): the write already landed, so
  # the fix is an edit to the file on disk, not a retry.
  if [[ -n "$violations" ]]; then
    printf 'squads plan-schema: %s The file is already written — edit it to add the missing fields.\n' \
      "$violations" >&2
    exit 2
  fi
  exit 0
}

# ---------- dispatch ----------

case "${1:-}" in
  session-start) session_start ;;
  dispatch-check) dispatch_check ;;
  pre-tool) pre_tool ;;
  post-tool) post_tool ;;
  *)
    echo "squads: unknown rule '${1:-}'" >&2
    exit 0
    ;;
esac
