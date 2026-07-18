#!/usr/bin/env python3
"""
Compresses a Codebase Context Report JSON to minimal token form.

Deduplicates and truncates low-signal fields before the report feeds
Phase 3 ideation. Reads from a file or stdin.

Usage:
    python compress_report.py report.json
    cat report.json | python compress_report.py
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

_MAX_FILES = 5  # 5: matches the related_files cap in scan_context.py
_MAX_LOG_LINES = 3  # 3: recent commit signals decay fast; more lines add noise
_MAX_CONSTRAINTS = 5  # 5: enough to surface limits without flooding the brief
_MAX_INTERFACE_SHAPES = (
    10  # 10: shapes are cheap tokens and often decisive for design
)
_MAX_UNKNOWNS = 4  # 4: one per batch; clarifications are capped at 4 per batch
_MAX_DESIGN_DOCS = 3  # 3: docs rarely add signal beyond the top 3
_MAX_ANALOGOUS = (
    2  # 2: analogous features seed the Minimalist lane; 2 keep it focused
)


def _dedupe_stable(items: list[Any]) -> list[str]:
    """Deduplicate preserving first-occurrence order."""
    seen: set[str] = set()
    result: list[str] = []
    for item in items:
        item = item if isinstance(item, str) else str(item)
        key = item.strip().lower()
        if key not in seen:
            seen.add(key)
            result.append(item)
    return result


def _truncate_git_log(log: str, max_lines: int) -> str:
    if not log or not log.strip() or log == "no history":
        return "no history"
    lines = [line for line in log.splitlines() if line.strip()]
    truncated = lines[:max_lines]
    omitted = len(lines) - len(truncated)
    suffix = f" … +{omitted} more" if omitted > 0 else ""
    body = "\n".join(truncated)
    return body + suffix if body else (suffix.strip() or "no history")


def _trim_str(value: str, max_chars: int = 200) -> str:
    return value[:max_chars] + "…" if len(value) > max_chars else value


def compress(report: dict[str, Any]) -> dict[str, Any]:
    """Compress a Codebase Context Report to minimal token form.

    Deduplicates and truncates each field to module-level limits.
    """
    if not isinstance(report, dict):
        raise TypeError(
            f"expected a JSON object (dict), got {type(report).__name__}"
        )
    out: dict[str, Any] = {}

    # Always keep — zero token cost to preserve
    out["feature_area"] = report.get("feature_area", "")
    out["scope"] = report.get("scope", "M")
    out["scope_reasoning"] = _trim_str(report.get("scope_reasoning", ""), 150)

    # Related files — cap count, truncate git log, preserve test coverage signals
    raw_files: list[Any] = report.get("related_files", [])
    out["related_files"] = []
    for f in raw_files[:_MAX_FILES]:
        if not isinstance(f, dict):
            raise TypeError(
                f"expected related_files entries to be objects, got {type(f).__name__}"
            )
        out["related_files"].append(
            {
                "path": f.get("path", ""),
                "last_commit": _truncate_git_log(
                    f.get("last_commit", ""), _MAX_LOG_LINES
                ),
                "has_tests": f.get("has_tests", False),
                "test_file": f.get("test_file", ""),
            }
        )

    # Deduplicate and cap list fields
    out["interface_shapes"] = _dedupe_stable(
        report.get("interface_shapes", [])
    )[:_MAX_INTERFACE_SHAPES]
    out["constraints"] = _dedupe_stable(report.get("constraints", []))[
        :_MAX_CONSTRAINTS
    ]
    out["design_docs"] = _dedupe_stable(report.get("design_docs", []))[
        :_MAX_DESIGN_DOCS
    ]
    out["unknowns"] = _dedupe_stable(report.get("unknowns", []))[
        :_MAX_UNKNOWNS
    ]

    # Analogous features — key for the Creative Checkpoint and the Minimalist lane
    out["analogous_features"] = _dedupe_stable(
        report.get("analogous_features", [])
    )[:_MAX_ANALOGOUS]

    return out


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Compress a Codebase Context Report for Phase 3 ideation"
    )
    parser.add_argument(
        "report",
        nargs="?",
        help="Path to report JSON (omit to read from stdin)",
    )
    args = parser.parse_args()

    try:
        if args.report:
            raw = json.loads(Path(args.report).read_text(encoding="utf-8"))
        else:
            raw = json.loads(sys.stdin.read())
    except FileNotFoundError as exc:
        sys.exit(f"error: report file not found — {exc}")
    except PermissionError as exc:
        sys.exit(f"error: cannot read report file — {exc}")
    except json.JSONDecodeError as exc:
        sys.exit(f"error: invalid JSON — {exc}")
    except (OSError, EOFError) as exc:
        sys.exit(f"error: failed to read input — {exc}")

    try:
        compressed = compress(raw)
    except TypeError as exc:
        sys.exit(f"error: {exc}")
    print(json.dumps(compressed, separators=(",", ":")))


if __name__ == "__main__":
    main()
