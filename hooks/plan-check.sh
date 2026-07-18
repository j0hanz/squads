#!/usr/bin/env bash
# Guard for docs/plan/*.plan.md writes.
# PreToolUse: deny a plan born APPROVED (receive-plan: NO Self-Verify) and
# deny APPROVED on a sketch-depth plan (receive-plan: NO Sketch Plans).
# PostToolUse: mirror receive-plan Step 2's traceability check — schema
# fields, Depends-on resolution + acyclicity, Satisfies -> REQ-NNN in the
# sibling specs.md. Failures exit 2 so they feed straight back to Claude.
set -uo pipefail

if ! command -v jq >/dev/null 2>&1; then
  echo 'squads plan-check: jq not found — plan guard skipped' >&2
  exit 0
fi

deny() {
  echo "squads plan-check: $1" >&2
  exit 2
}

input=$(cat)
event=$(jq -r '.hook_event_name // empty' <<<"$input" 2>/dev/null) || exit 0
file_path=$(jq -r '.tool_input.file_path // empty' <<<"$input")

# Normalize to forward slashes; only docs/plan/*.plan.md is in scope.
file_path=${file_path//\\//}
[[ "$file_path" =~ (^|/)docs/plan/[^/]+\.plan\.md$ ]] || exit 0

pre_check() {
  local written
  written=$(jq -r '.tool_input.content // .tool_input.new_string // ""' <<<"$input")

  if [[ ! -f "$file_path" ]] && grep -qE '^Status:[[:space:]]*APPROVED' <<<"$written"; then
    deny 'plans are born `Status: DRAFT` — only receive-plan flips DRAFT to APPROVED after verification (NO Self-Verify). Write the plan with `Status: DRAFT`.'
  fi

  if grep -qF 'APPROVED' <<<"$written"; then
    if grep -qE '^Depth:[[:space:]]*sketch' <<<"$written" ||
      { [[ -f "$file_path" ]] && grep -qE '^Depth:[[:space:]]*sketch' "$file_path"; }; then
      deny 'sketch-depth plans are never APPROVED — receive-plan rejects sketch by design (NO Sketch Plans). Implement a sketch directly; it stays DRAFT.'
    fi
  fi
}

post_check() {
  [[ -f "$file_path" ]] || exit 0 # file gone or unreadable — nothing to validate

  local specs_path specs_name specs_exists=0 declared='' failures count
  specs_path="${file_path%.plan.md}.specs.md"
  specs_name=$(basename "$specs_path")

  # Satisfies cross-check runs only when the sibling specs.md exists;
  # specs may legitimately be written after the plan, so absence is a note.
  if [[ -f "$specs_path" ]]; then
    specs_exists=1
    declared=$(grep -oE '^#### REQ-[0-9]+:' "$specs_path" | grep -oE 'REQ-[0-9]+' | sort -u | tr '\n' ' ')
  else
    echo "squads plan-check: $specs_name not found yet — REQ traceability unchecked this pass"
  fi

  failures=$(awk -v declared="$declared" -v specs_exists="$specs_exists" -v specs_name="$specs_name" '
    function trim(s) { gsub(/^[ \t]+|[ \t]+$/, "", s); return s }

    BEGIN {
      nfields = split("Depends on:|Files:|Symbols:|Satisfies:|Action:|Validate:|Expected result:", fields, "|")
      nreq = split(declared, reqs, " ")
      for (i = 1; i <= nreq; i++) if (reqs[i] != "") declared_req[reqs[i]] = 1
    }

    { sub(/\r$/, "") }

    /^Status:[ \t]*(DRAFT|APPROVED)/ { has_status = 1 }
    /^Status:[ \t]*APPROVED/ { approved = 1 }
    /^Depth:[ \t]*(sketch|contract|blueprint)/ { has_depth = 1 }
    /^Depth:[ \t]*sketch/ { sketch = 1 }

    /^### TASK-[0-9]+:/ {
      id = $0; sub(/^### /, "", id); sub(/:.*/, "", id)
      ntasks++; order[ntasks] = id; ids[id] = 1; cur = id
      next
    }

    cur != "" {
      for (i = 1; i <= nfields; i++)
        if (index($0, fields[i]) == 1) seen[cur, fields[i]] = 1
      if ($0 ~ /^Depends on:/) { v = $0; sub(/^Depends on:[ \t]*/, "", v); dep_line[cur] = v }
      if ($0 ~ /^Satisfies:/) { v = $0; sub(/^Satisfies:[ \t]*/, "", v); sat_line[cur] = v }
    }

    END {
      if (!has_status) print "missing `Status: DRAFT|APPROVED` header"
      if (!has_depth) print "missing `Depth: sketch|contract|blueprint` header"
      if (sketch && approved) print "`Depth: sketch` plan marked APPROVED — sketch plans stay DRAFT by design (receive-plan: NO Sketch Plans)"

      if (ntasks == 0) {
        print "no `### TASK-NNN:` blocks found — plan tasks must use the Canonical Task Block Schema"
        exit
      }

      for (t = 1; t <= ntasks; t++) {
        id = order[t]

        for (i = 1; i <= nfields; i++)
          if (!seen[id, fields[i]]) printf "%s: missing required field `%s`\n", id, fields[i]

        if ((id in dep_line) && dep_line[id] !~ /^[Nn]one/) {
          n = split(dep_line[id], toks, ",")
          for (i = 1; i <= n; i++) {
            tok = trim(toks[i])
            if (tok == "") continue
            if (tok !~ /^TASK-[0-9]+$/) printf "%s: `Depends on:` token \"%s\" is not TASK-NNN or none\n", id, tok
            else if (!(tok in ids)) printf "%s: depends on undefined %s\n", id, tok
            else deps[id] = deps[id] " " tok
          }
        }

        if (id in sat_line) {
          n = split(sat_line[id], toks, ",")
          for (i = 1; i <= n; i++) {
            tok = trim(toks[i])
            if (tok == "") continue
            if (tok !~ /^REQ-[0-9]+$/) printf "%s: `Satisfies:` token \"%s\" is not a REQ-NNN ID\n", id, tok
            else if (specs_exists && !(tok in declared_req)) printf "%s: Satisfies %s not declared in %s\n", id, tok, specs_name
          }
        }
      }

      # Kahn-style cycle check: peel tasks whose deps are all resolved;
      # anything left over sits on a cycle.
      changed = 1
      while (changed) {
        changed = 0
        for (t = 1; t <= ntasks; t++) {
          id = order[t]
          if (done[id]) continue
          unresolved = 0
          n = split(deps[id], toks, " ")
          for (i = 1; i <= n; i++) if (toks[i] != "" && !done[toks[i]]) unresolved = 1
          if (!unresolved) { done[id] = 1; changed = 1 }
        }
      }
      cycle = ""
      for (t = 1; t <= ntasks; t++)
        if (!done[order[t]]) cycle = cycle (cycle == "" ? "" : ", ") order[t]
      if (cycle != "") printf "dependency cycle among: %s\n", cycle
    }
  ' "$file_path")

  if [[ -n "$failures" ]]; then
    count=$(wc -l <<<"$failures" | tr -d ' ')
    {
      echo "squads plan-check: $count traceability failure(s) in $file_path (Canonical Task Block Schema, request-plan):"
      sed 's/^/- /' <<<"$failures"
    } >&2
    exit 2
  fi
  echo 'squads plan-check: schema and traceability OK'
}

case "$event" in
  PreToolUse) pre_check ;;
  PostToolUse) post_check ;;
esac

exit 0
