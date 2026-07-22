#!/usr/bin/env python3
"""squads perf wrapper: time squads-hook.sh, log one JSONL line per fire.

hooks.json routes every entry through `perf-hook.py <rule>` (falling back to
the bare dispatcher when python is absent). The wrapper reads the hook payload
from stdin, runs the real `squads-hook.sh <rule>` on it, and re-emits the
child's stdout/stderr and exit code unchanged — transparent to Claude Code's
hook result handling. One token-cheap record per fire is appended to
<log-dir>/YYYY-MM-DD.jsonl (date in the filename, time in the record).
Logging can never block the hook chain: failures are swallowed and the
child's outcome still passes through; a wrapper crash exits 0 (fail-open,
same as a Claude Code command-hook error).

Log dir:   $PERF_LOG_DIR or ~/.claude/squads-perf
Report:    perf-hook.py report
Self-test: perf-hook.py --self-check

Record shape (fields omitted when absent; exit omitted when 0):

    {"ts":"14:03:22","rule":"pre-tool","ms":41,"exit":2,"tool":"Write",
     "skill":"","session":"abc12345",
     "err":"squads debug-gate: ..."}

exit 2 + the "squads <gate>:" err prefix names the guard that fired
(debug-gate, dispatch-check, plan-schema); post-tool exit 2
with no prefix is plan-schema feedback, not a deny. "timeout":1 marks a rule
killed at CHILD_TIMEOUT. Every rule fails open on timeout, emitting a [WARN]
line to stderr naming the guard that did not run. Only Claude Code's own outer
kill (10s, which the wrapper cannot intercept) stays an unfixable fail-open —
the R2 residual hooks.json documents.
"""

import json
import os
import subprocess
import sys
import time
from contextlib import suppress
from datetime import datetime
from pathlib import Path
from typing import Any

ERR_MAX = 160
# Child timeout sits below its hooks.json entry so a hung rule is logged as a
# fail-open timeout instead of vanishing when Claude Code kills the wrapper:
# 8s < the 10s pre/post/dispatch entries, 4s < the 5s session-start entry.
CHILD_TIMEOUT = 8
SESSION_START_TIMEOUT = 4
SELF_CHECK_TIMEOUT = 1
GATES = ("debug-gate", "dispatch-check", "plan-schema")


def log_dir() -> Path:
    return Path(
        os.environ.get("PERF_LOG_DIR")
        or Path.home() / ".claude" / "squads-perf"
    )


def first_line(value: Any) -> str:
    """First non-blank line of a string, clipped; '' for anything else."""
    if isinstance(value, str) and value.strip():
        return next(ln.strip() for ln in value.splitlines() if ln.strip())[
            :ERR_MAX
        ]
    return ""


def find_bash() -> str:
    """First bash.exe on PATH that is not WSL's System32 stub (which is slow
    to start and cannot read C:/ script paths); plain 'bash' elsewhere."""
    for entry in os.get_exec_path():
        candidate = Path(entry) / "bash.exe"
        lowered = entry.lower()
        if (
            candidate.is_file()
            and "system32" not in lowered
            and "windowsapps" not in lowered
        ):
            return str(candidate)
    return "bash"


def run_rule(
    rule: str, payload: bytes, script: Path | None = None, timeout: int | None = None
) -> dict[str, Any]:
    """Run squads-hook.sh <rule> with the payload on stdin, wall-clocked."""
    script = script or Path(__file__).with_name("squads-hook.sh")
    cmd = [find_bash(), str(script).replace("\\", "/"), rule]
    if timeout is None:
        timeout = (
            SESSION_START_TIMEOUT if rule == "session-start" else CHILD_TIMEOUT
        )
    t0 = time.perf_counter()
    try:
        proc = subprocess.run(
            cmd, input=payload, capture_output=True, timeout=timeout
        )
        out, err, code, timed_out = (
            proc.stdout,
            proc.stderr,
            proc.returncode,
            False,
        )
    except subprocess.TimeoutExpired:
        # Every rule fails open on timeout, announcing to stderr which gate was not applied.
        out, err, code, timed_out = (
            b"",
            f"[WARN] squads {rule}: guard timed out after {timeout}s, gate not applied.\n".encode(),
            0,
            True,
        )
    ms = max(0, round((time.perf_counter() - t0) * 1000))
    return {
        "code": code,
        "out": out,
        "err": err,
        "ms": ms,
        "timeout": timed_out,
    }


def build_record(
    rule: str, payload: dict[str, Any], result: dict[str, Any], now: datetime
) -> dict[str, Any]:
    record: dict[str, Any] = {
        "ts": f"{now:%H:%M:%S}",
        "rule": rule,
        "ms": result["ms"],
    }
    if result["timeout"]:
        record["timeout"] = 1
    if result["code"]:
        record["exit"] = result["code"]
    if payload.get("tool_name"):
        record["tool"] = str(payload["tool_name"])[:ERR_MAX]
    tool_input = payload.get("tool_input")
    if isinstance(tool_input, dict) and isinstance(
        tool_input.get("skill"), str
    ):
        record["skill"] = tool_input["skill"][:ERR_MAX]
    if payload.get("session_id"):
        record["session"] = str(payload["session_id"])[:8]
    if line := first_line(result["err"].decode("utf-8", "replace")):
        record["err"] = line
    return record


def to_line(record: dict[str, Any]) -> str:
    """Serialize a record compactly: no separator spaces, raw unicode."""
    return json.dumps(record, separators=(",", ":"), ensure_ascii=False)


def append_line(path: Path, line: str) -> bool:
    """Append one full line atomically (single O_APPEND write), retrying on
    transient OSError — concurrent hook fires write the same file, and a
    buffered open()+write() silently drops events under exactly that load."""
    data = line.encode("utf-8")
    for attempt in range(3):
        try:
            fd = os.open(path, os.O_APPEND | os.O_CREAT | os.O_WRONLY)
            try:
                os.write(fd, data)
            finally:
                os.close(fd)
            return True
        except OSError:
            time.sleep(0.05 * (attempt + 1))
    return False


def main(rule: str) -> int:
    payload_raw = sys.stdin.buffer.read()
    result = run_rule(rule, payload_raw)
    try:
        try:
            payload = json.loads(
                payload_raw.decode("utf-8", "replace") or "{}"
            )
        except json.JSONDecodeError:
            payload = {}
        if not isinstance(payload, dict):
            payload = {}
        now = datetime.now()
        directory = log_dir()
        directory.mkdir(parents=True, exist_ok=True)
        append_line(
            directory / f"{now:%Y-%m-%d}.jsonl",
            to_line(build_record(rule, payload, result, now)) + "\n",
        )
    except Exception:
        sys.stderr.buffer.write(
            b"[DEBUG] perf-hook logging failed; passthrough unaffected.\n"
        )
    sys.stdout.buffer.write(result["out"])
    sys.stderr.buffer.write(result["err"])
    return result["code"]


# ---------- self-check ----------


def self_check() -> None:
    import tempfile

    now = datetime(2026, 1, 1, 14, 3, 22)
    ok = {"code": 0, "out": b"", "err": b"", "ms": 41, "timeout": False}
    bare = build_record("session-start", {}, ok, now)
    assert bare == {"ts": "14:03:22", "rule": "session-start", "ms": 41}, bare
    denied = build_record(
        "pre-tool",
        {
            "tool_name": "Write",
            "tool_input": {"file_path": "src/x.go"},
            "session_id": "abcdef123456",
        },
        {
            "code": 2,
            "out": b"",
            "err": b"squads debug-gate: debug is active\nmore",
            "ms": 7,
            "timeout": False,
        },
        now,
    )
    assert denied == {
        "ts": "14:03:22",
        "rule": "pre-tool",
        "ms": 7,
        "exit": 2,
        "tool": "Write",
        "session": "abcdef12",
        "err": "squads debug-gate: debug is active",
    }, denied
    assert to_line(bare) == '{"ts":"14:03:22","rule":"session-start","ms":41}'
    assert to_line({"err": "naïve"}) == '{"err":"naïve"}'

    with tempfile.TemporaryDirectory() as td:
        path = Path(td) / "t.jsonl"
        line = to_line(bare) + "\n"
        assert append_line(path, line) and append_line(path, line)
        assert path.read_text(encoding="utf-8") == line * 2

        # exit-code passthrough + stream capture + non-negative timing, via stub
        stub = Path(td) / "stub.sh"
        stub.write_text(
            'cat >/dev/null; printf out; printf "e1\\ne2" >&2; exit 2\n',
            encoding="utf-8",
        )
        r = run_rule("x", b"{}", script=stub)
        assert r["code"] == 2 and r["out"] == b"out", r
        assert (
            r["err"].startswith(b"e1") and r["ms"] >= 0 and not r["timeout"]
        ), r

    # end-to-end against the real dispatcher: placeholder → deny, clean → silent
    dirty = json.dumps(
        {"tool_name": "Agent", "tool_input": {"prompt": "do {{task}}"}}
    ).encode()
    r = run_rule("dispatch-check", dirty)
    assert r["code"] == 2 and b"unresolved placeholder" in r["err"], r
    # model field handling: haiku is silent, others warn, absent warns
    with_haiku = json.dumps(
        {"tool_name": "Agent", "tool_input": {"prompt": "do it", "model": "haiku"}}
    ).encode()
    r = run_rule("dispatch-check", with_haiku)
    assert r["code"] == 0 and r["err"] == b"" and r["out"] == b"", r
    with_opus = json.dumps(
        {"tool_name": "Agent", "tool_input": {"prompt": "do it", "model": "opus"}}
    ).encode()
    r = run_rule("dispatch-check", with_opus)
    assert r["code"] == 0 and b"is not haiku" in r["err"], r
    no_model = json.dumps(
        {"tool_name": "Agent", "tool_input": {"prompt": "do it"}}
    ).encode()
    r = run_rule("dispatch-check", no_model)
    assert r["code"] == 0 and b"model param unavailable" in r["err"], r

    # --- pre-tool path assertions (TASK-005) ---
    # Flag files live in the hook's bash state_dir (${TMPDIR:-/tmp}). On
    # Windows, Python's /tmp ≠ git-bash's /tmp, so every create/test/remove
    # of a flag file is routed through bash to share the hook's view.
    _state_expr = "${TMPDIR:-/tmp}"

    def _bash(script: str) -> bytes:
        with suppress(Exception):
            return subprocess.run(
                [find_bash(), "-c", script],
                capture_output=True,
                timeout=2,
            ).stdout
        return b""

    def _flag(pattern: str) -> bool:
        return (
            _bash(f'test -f "{_state_expr}/{pattern}" && echo y').strip()
            == b"y"
        )

    def _clean(sid: str) -> None:
        _bash(f'rm -f "{_state_expr}/squads-debug-gate-{sid}"')

    # (1) lifecycle skills route directly now — a Skill call with no flag set
    # passes at pre-tool (governor-gate removed; debug-gate matches edits, not
    # Skill). pre-tool arms nothing (arming is post-tool).
    sid = "schk-route"
    _clean(sid)
    r = run_rule(
        "pre-tool",
        json.dumps(
            {
                "tool_name": "Skill",
                "tool_input": {"skill": "squads:debug"},
                "session_id": sid,
            }
        ).encode(),
    )
    assert r["code"] == 0 and r["err"] == b"", r
    assert not _flag(f"squads-debug-gate-{sid}"), "pre-tool must not arm debug"
    _clean(sid)

    # (2) post-tool arms/lifts the debug gate; pre-tool denies edits while it is
    # up. post-tool squads:debug arms it; a non-exempt Write denies, an exempt
    # *.md passes; post-tool squads:tdd lifts it. Flags live in the hook's bash
    # state_dir, so every touch/lift is routed through the real dispatcher, not
    # fabricated in Python.
    sid = "schk-dbg"
    _clean(sid)
    r = run_rule(
        "post-tool",
        json.dumps(
            {
                "tool_name": "Skill",
                "tool_input": {"skill": "squads:debug"},
                "session_id": sid,
            }
        ).encode(),
    )
    assert r["code"] == 0 and _flag(f"squads-debug-gate-{sid}"), r
    r = run_rule(
        "pre-tool",
        json.dumps(
            {
                "tool_name": "Write",
                "tool_input": {"file_path": "src/x.go"},
                "session_id": sid,
            }
        ).encode(),
    )
    assert r["code"] == 2 and r["err"].startswith(b"squads debug-gate:"), r
    r = run_rule(
        "pre-tool",
        json.dumps(
            {
                "tool_name": "Write",
                "tool_input": {"file_path": "notes.md"},
                "session_id": sid,
            }
        ).encode(),
    )
    assert r["code"] == 0, r
    r = run_rule(
        "post-tool",
        json.dumps(
            {
                "tool_name": "Skill",
                "tool_input": {"skill": "squads:tdd"},
                "session_id": sid,
            }
        ).encode(),
    )
    assert r["code"] == 0 and not _flag(f"squads-debug-gate-{sid}"), r
    _clean(sid)

    # (3) plan-schema: Write to docs/plan/x.plan.md missing Origin → deny
    sid = "schk-plan"
    _clean(sid)
    r = run_rule(
        "pre-tool",
        json.dumps(
            {
                "tool_name": "Write",
                "tool_input": {
                    "file_path": "docs/plan/x.plan.md",
                    "content": "no Origin header here",
                },
                "session_id": sid,
            }
        ).encode(),
    )
    assert r["code"] == 2 and r["err"].startswith(b"squads plan-schema:"), r
    _clean(sid)

    # (4) clean pre-tool: a non-Skill non-Write tool passes silent
    sid = "schk-clean"
    _clean(sid)
    r = run_rule(
        "pre-tool",
        json.dumps(
            {
                "tool_name": "Read",
                "tool_input": {"file_path": "README.md"},
                "session_id": sid,
            }
        ).encode(),
    )
    assert r["code"] == 0 and r["err"] == b"" and r["out"] == b"", r
    _clean(sid)

    # (9) compact recap: armed debug-gate → ACTIVE in recap; clean → silent.
    # last-plan tracking: a plan-path Write post-tool records the path, and
    # the compact recap names it. Routes through the real dispatcher.
    sid = "schk-compact"
    _clean(sid)
    # also remove the last-plan file for this sid
    _bash(f'rm -f "{_state_expr}/squads-last-plan-{sid}"')

    # clean: no flag, no plan → compact is silent
    r = run_rule(
        "compact",
        json.dumps({"session_id": sid}).encode(),
    )
    assert r["code"] == 0 and r["out"] == b"", r

    # arm the debug-gate via post-tool squads:debug → compact reports ACTIVE
    r = run_rule(
        "post-tool",
        json.dumps(
            {
                "tool_name": "Skill",
                "tool_input": {"skill": "squads:debug"},
                "session_id": sid,
            }
        ).encode(),
    )
    assert r["code"] == 0 and _flag(f"squads-debug-gate-{sid}"), r
    r = run_rule(
        "compact",
        json.dumps({"session_id": sid}).encode(),
    )
    assert r["code"] == 0 and b"<squads-state>" in r["out"], r
    assert b"debug-gate ACTIVE" in r["out"], r

    # record a plan path via a plan-path Write post-tool → recap names it
    td_plan = _bash(f'mktemp -d "{_state_expr}/squadsplan.XXXXXX"').strip()
    plan_path = f"{td_plan.decode()}/docs/plan/x.plan.md"
    _bash(f'mkdir -p "{td_plan.decode()}/docs/plan" && printf "Origin: plan\\n" > "{plan_path}"')
    r = run_rule(
        "post-tool",
        json.dumps(
            {
                "tool_name": "Write",
                "tool_input": {"file_path": plan_path, "content": "Origin: plan\n"},
                "session_id": sid,
            }
        ).encode(),
    )
    assert r["code"] == 0, r
    r = run_rule(
        "compact",
        json.dumps({"session_id": sid}).encode(),
    )
    assert r["code"] == 0 and b"active plan:" in r["out"], r
    assert plan_path.encode() in r["out"] or b"x.plan.md" in r["out"], r

    # lift the gate via post-tool squads:tdd → recap no longer reports ACTIVE
    r = run_rule(
        "post-tool",
        json.dumps(
            {
                "tool_name": "Skill",
                "tool_input": {"skill": "squads:tdd"},
                "session_id": sid,
            }
        ).encode(),
    )
    assert r["code"] == 0 and not _flag(f"squads-debug-gate-{sid}"), r
    r = run_rule(
        "compact",
        json.dumps({"session_id": sid}).encode(),
    )
    assert r["code"] == 0 and b"debug-gate ACTIVE" not in r["out"], r
    assert b"active plan:" in r["out"], r  # plan file still recorded

    _bash(f'rm -f "{_state_expr}/squads-last-plan-{sid}"')
    _bash(f'rm -rf "{td_plan.decode()}"')
    _clean(sid)

    # (5) plan-schema: a full Canonical Task Block passes; dropping one field
    # denies and names it — exercises the 7-field awk, not just the Origin
    # short-circuit that test (3) covers.
    full_plan = (
        "Origin: plan\n\n"
        "### TASK-001: Do the thing\n\n"
        "Depends on: none\n"
        "Files: src/x.go\n"
        "Symbols: foo\n"
        "Satisfies: REQ-001\n"
        "Action: Do it.\n"
        "Validate: `go test`\n"
        "Expected result: passes\n"
    )
    sid = "schk-plan2"
    _clean(sid)
    r = run_rule(
        "pre-tool",
        json.dumps(
            {
                "tool_name": "Write",
                "tool_input": {
                    "file_path": "docs/plan/x.plan.md",
                    "content": full_plan,
                },
                "session_id": sid,
            }
        ).encode(),
    )
    assert r["code"] == 0 and r["err"] == b"", r
    r = run_rule(
        "pre-tool",
        json.dumps(
            {
                "tool_name": "Write",
                "tool_input": {
                    "file_path": "docs/plan/x.plan.md",
                    "content": full_plan.replace("Symbols: foo\n", ""),
                },
                "session_id": sid,
            }
        ).encode(),
    )
    assert r["code"] == 2 and b"Symbols" in r["err"], r
    _clean(sid)

    # (6) dispatch-check untrusted_context: a balanced block hides its {{...}}
    # from the linter; a close-before-open block now fails open with [WARN].
    balanced = json.dumps(
        {
            "tool_name": "Agent",
            "tool_input": {
                "prompt": "analyze:\n<untrusted_context>\n"
                "user: {{foo}}\n</untrusted_context>\ndone",
                "model": "haiku"
            },
        }
    ).encode()
    r = run_rule("dispatch-check", balanced)
    assert r["code"] == 0 and r["err"] == b"", r
    misordered = json.dumps(
        {
            "tool_name": "Agent",
            "tool_input": {
                "prompt": "</untrusted_context>\n{{x}}\n<untrusted_context>",
                "model": "haiku"
            },
        }
    ).encode()
    r = run_rule("dispatch-check", misordered)
    assert r["code"] == 0 and b"untrusted_context" in r["err"], r

    # (7) dispatch-check lints SendMessage to/summary and Workflow scriptPath/name
    # — a {{...}} in any of those metadata fields is caught, not just in prompt.
    for field in ("to", "summary", "scriptPath", "name"):
        dirty_meta = json.dumps(
            {"tool_name": "SendMessage", "tool_input": {field: "do {{x}}"}}
        ).encode()
        r = run_rule("dispatch-check", dirty_meta)
        assert r["code"] == 2 and b"unresolved placeholder" in r["err"], (field, r)

    # (8) dispatch-check fails open on a child timeout (exit 0 + [WARN] err);
    # every rule fails open. Stub sleeps past SELF_CHECK_TIMEOUT; quick assertion.
    with tempfile.TemporaryDirectory() as td:
        slow = Path(td) / "slow.sh"
        slow.write_text("sleep 2\n", encoding="utf-8")
        r = run_rule("dispatch-check", b"{}", script=slow, timeout=SELF_CHECK_TIMEOUT)
        assert (
            r["code"] == 0
            and r["timeout"]
            and r["err"].startswith(b"[WARN] squads dispatch-check:")
        ), r

    print("self-check OK")


if __name__ == "__main__":
    argv = sys.argv[1:]
    if argv == ["--self-check"]:
        self_check()  # assertion failures stay loud on purpose
    else:
        rule = argv[0] if argv else ""
        try:
            code = main(rule)
        except Exception:
            # Fail-open: every rule announces to stderr when it does not run,
            # whether due to timeout or wrapper crash.
            sys.stderr.write(
                f"[WARN] squads {rule}: guard wrapper failed, gate not applied.\n"
            )
            code = 0
        sys.exit(code)
