#!/usr/bin/env python3
"""
Parallel codebase scanner for parallel-brainstorming Phase 1.

Replaces sequential Glob/Grep/git-log tool calls with one script invocation.
Returns a JSON Codebase Context Report on stdout.

Usage:
    python scan_context.py NOUN [NOUN ...] [--cwd PATH]

Example:
    python scan_context.py search catalog --cwd /path/to/project
"""

from __future__ import annotations

import argparse
import ast
import json
import os
import re
import subprocess
import sys
from collections import Counter
from collections.abc import Iterable
from concurrent.futures import ThreadPoolExecutor
from dataclasses import asdict, dataclass, field
from pathlib import Path


@dataclass
class FileSignal:
    path: str
    last_commit: str = ""
    has_tests: bool = False
    test_file: str = ""


@dataclass
class ScanResult:
    feature_area: str
    related_files: list[FileSignal] = field(default_factory=list)
    interface_shapes: list[str] = field(default_factory=list)
    constraints: list[str] = field(default_factory=list)
    analogous_features: list[str] = field(default_factory=list)
    scope: str = "M"
    scope_reasoning: str = ""
    unknowns: list[str] = field(default_factory=list)


# Directories that are never useful to scan
_SKIP_DIRS = frozenset(
    {"venv", ".venv", "node_modules", "__pycache__", ".git", "dist", "build"}
)

_MAX_LOG_LINES = 3  # 3: recent commit signals decay fast; more lines add noise
_MAX_CONSTRAINTS_PER_FILE = (
    3  # 3: stop reading a file early; keeps per-file signal tight
)
_MAX_CONSTRAINTS = 5  # 5: global cap across all files (max collectible: _MAX_CONSTRAINTS_PER_FILE x _MAX_FILES)
_MAX_INTERFACE_SHAPES = (
    10  # 10: shapes are cheap tokens and often decisive for design
)
_MAX_UNKNOWNS = 4  # 4: one per batch; clarifications are capped at 4 per batch
_MAX_FILES = 5  # 5: top-N related files kept in the report; higher ranks win
_MAX_ANALOGOUS = (
    2  # 2: only seed the Minimalist lane (sorted for run-to-run determinism)
)

_CONSTRAINT_PATTERNS = [
    "TODO",
    "FIXME",
    "HACK",
    "rate_limit",
    "rate limit",
    "ratelimit",
    "timeout",
    "max_size",
]
# Pre-lowercased once so _scan_constraints avoids pat.lower() inside the hot loop
_CONSTRAINT_PATTERNS_LOWER = [p.lower() for p in _CONSTRAINT_PATTERNS]

# Adjacent synonyms for common domain verbs/nouns used in analogous feature detection
_SYNONYM_MAP: dict[str, list[str]] = {
    "search": ["query", "lookup", "filter", "find"],
    "query": ["search", "filter", "lookup", "fetch"],
    "filter": ["search", "query", "sort", "paginate"],
    "import": ["upload", "ingest", "load", "parse"],
    "export": ["download", "serialize", "dump", "emit"],
    "auth": ["login", "session", "token", "credential", "permission"],
    "user": ["account", "profile", "member", "identity"],
    "notify": ["alert", "email", "webhook", "event", "message"],
    "cache": ["store", "memoize", "persist", "ttl"],
    "log": ["audit", "trace", "event", "record"],
    "report": ["export", "summary", "aggregate", "dashboard"],
    "sync": ["push", "pull", "replicate", "merge"],
    "schedule": ["cron", "job", "task", "queue"],
    "upload": ["import", "ingest", "attach", "store"],
    "download": ["export", "fetch", "stream", "serve"],
}

# Regex patterns for extracting named types from non-Python source files.
# Compiled once at module load to avoid recompilation on every file processed.
_LANG_TYPE_PATTERNS: dict[str, str] = {
    ".ts": r"(?:interface|type|class|enum)\s+(\w+)",
    ".tsx": r"(?:interface|type|class|enum)\s+(\w+)",
    ".go": r"type\s+(\w+)\s+(?:struct|interface)",
    ".rs": r"(?:struct|enum|trait|type)\s+(\w+)",
    ".java": r"(?:class|interface|enum)\s+(\w+)",
    ".cs": r"(?:class|interface|enum|record)\s+(\w+)",
    ".kt": r"(?:class|interface|object|data class)\s+(\w+)",
    ".swift": r"(?:class|struct|enum|protocol)\s+(\w+)",
}
_LANG_TYPE_REGEXES: dict[str, re.Pattern[str]] = {
    ext: re.compile(pat) for ext, pat in _LANG_TYPE_PATTERNS.items()
}

# Regex for exported function names in TypeScript/TSX files.
# Matches: export function foo, export async function foo,
#          export const foo = (, export const foo: Type = (
_TS_EXPORT_FN_PATTERN: re.Pattern[str] = re.compile(
    r"^export\s+(?:async\s+)?(?:function\s+(\w+)|const\s+(\w+)\s*(?::[^=]+)?\s*=\s*(?:async\s+)?\()",
    re.MULTILINE,
)


def _dedupe_stable(items: Iterable[str]) -> list[str]:
    """Deduplicate preserving first-occurrence order."""
    seen: set[str] = set()
    result: list[str] = []
    for item in items:
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
    return body + suffix if body else "no history"


def _trim_str(value: str, max_chars: int = 200) -> str:
    return value[:max_chars] + "…" if len(value) > max_chars else value


def _sanitize_noun(raw: str) -> str:
    """Strip to alphanumeric/hyphen only; reject empty or flag-like results.

    The script must not trust argv unconditionally before it reaches git
    grep / rg as a regex pattern, regardless of what the caller passed.
    """
    cleaned = re.sub(r"[^A-Za-z0-9-]", "", raw)
    if not cleaned or cleaned.startswith("-"):
        raise ValueError(f"invalid domain noun after sanitization: {raw!r}")
    if cleaned != raw:
        print(
            f"warning: sanitized noun {raw!r} → {cleaned!r} (non-alphanumeric chars stripped)",
            file=sys.stderr,
        )
    return cleaned


def _load_project_synonyms(cwd: Path) -> dict[str, list[str]]:
    """Load project-specific synonyms from `<cwd>/synonyms.json` if present.

    The file must be a JSON object mapping lowercase noun strings to lists of
    lowercase synonym strings. Extra keys are merged with `_SYNONYM_MAP`;
    conflicting keys extend (not replace) the built-in synonym list.
    Missing file or any parse error returns an empty dict (silent degradation).
    """
    path = cwd / "synonyms.json"
    if not path.exists():
        return {}
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        print(f"warning: synonyms.json unreadable ({exc}); synonyms ignored", file=sys.stderr)
        return {}
    if not isinstance(raw, dict):
        print("warning: synonyms.json is not a JSON object; synonyms ignored", file=sys.stderr)
        return {}
    result: dict[str, list[str]] = {}
    for key, value in raw.items():
        if isinstance(key, str) and isinstance(value, list):
            clean_syns = []
            for s in value:
                if not isinstance(s, str):
                    continue
                cleaned = re.sub(r"[^A-Za-z0-9-]", "", s)
                if not cleaned or cleaned.startswith("-"):
                    print(
                        f"warning: dropped synonym {s!r} (empty or flag-like after sanitization)",
                        file=sys.stderr,
                    )
                    continue
                if cleaned != s:
                    print(
                        f"warning: sanitized synonym {s!r} → {cleaned!r} (non-alphanumeric chars stripped)",
                        file=sys.stderr,
                    )
                clean_syns.append(cleaned)
            if clean_syns:
                result[key.lower()] = clean_syns
    return result


def _expand_synonyms(
    nouns: list[str],
    synonym_map: dict[str, list[str]] | None = None,
) -> list[str]:
    """Return adjacent synonyms for domain terms (deduped, originals first).

    Uses `synonym_map` if provided, falling back to the built-in `_SYNONYM_MAP`.
    """
    if synonym_map is None:
        synonym_map = _SYNONYM_MAP
    expanded = list(nouns)
    seen = {n.lower() for n in nouns}
    for noun in nouns:
        for synonym in synonym_map.get(noun.lower(), []):
            if synonym not in seen:
                seen.add(synonym)
                expanded.append(synonym)
    return expanded


_SUBPROCESS_TIMEOUT = 15  # 15s: git grep/rg over a mid-size repo returns well within this; bounds a hung tool


def _git_log(path: str, cwd: Path) -> str:
    try:
        result = subprocess.run(
            ["git", "log", "--oneline", f"-{_MAX_LOG_LINES}", "--", path],
            capture_output=True,
            text=True,
            cwd=str(cwd),
            timeout=_SUBPROCESS_TIMEOUT,
        )
    except FileNotFoundError, subprocess.TimeoutExpired:
        return "no history"
    if result.returncode != 0:
        return "no history"
    return result.stdout.strip() or "no history"


def _grep_files(pattern: str, cwd: Path) -> list[str] | None:
    """Return file paths matching pattern, or None if no grep tool is available."""
    try:
        git_result = subprocess.run(
            ["git", "grep", "-ril", "-e", pattern],
            capture_output=True,
            text=True,
            cwd=str(cwd),
            timeout=_SUBPROCESS_TIMEOUT,
        )
        if git_result.returncode == 0:
            return [p for p in git_result.stdout.splitlines() if p]
        if git_result.returncode == 1:
            # healthy git, zero matches — do not fall through to rg
            return []
        if git_result.returncode > 1:
            print(
                f"warning: git grep failed for {pattern!r}: {git_result.stderr.strip()}",
                file=sys.stderr,
            )
    except FileNotFoundError:
        pass
    except subprocess.TimeoutExpired:
        print(
            f"warning: git grep timed out for {pattern!r}; falling back to rg",
            file=sys.stderr,
        )

    # Fallback to rg
    try:
        rg_result = subprocess.run(
            [
                "rg",
                "--files-with-matches",
                "-i",
                "--glob",
                "!*.lock",
                "--glob",
                "!*.sum",
                "--sort=path",
                "--",
                pattern,
                ".",
            ],
            capture_output=True,
            text=True,
            cwd=str(cwd),
            timeout=_SUBPROCESS_TIMEOUT,
        )
    except FileNotFoundError:
        return None
    except subprocess.TimeoutExpired:
        print(f"warning: search timed out for {pattern!r}", file=sys.stderr)
        return None

    if rg_result.returncode > 1:
        print(
            f"warning: rg failed for {pattern!r}: {rg_result.stderr.strip()}",
            file=sys.stderr,
        )
        return None
    paths = [p for p in rg_result.stdout.splitlines() if p]
    normalized: list[str] = []
    for p in paths:
        p_path = Path(p)
        if p_path.is_absolute():
            try:
                rel = p_path.relative_to(cwd)
            except ValueError:
                continue  # outside cwd — not a match we should report
            normalized.append(rel.as_posix())
        else:
            normalized.append(p_path.as_posix())
    return normalized


def _find_test_file(file_path: Path, cwd: Path) -> str:
    """Return the relative path of a test file for the given source file, or ''."""
    stem = file_path.stem
    suffix = file_path.suffix
    parent = file_path.parent

    # Check fixed sibling candidates first (fastest, no walk needed)
    candidates = [
        parent / f"test_{stem}{suffix}",
        parent / f"{stem}_test{suffix}",
        parent / f"{stem}.test{suffix}",
        parent / f"{stem}.spec{suffix}",
    ]
    for candidate in candidates:
        if candidate.exists():
            try:
                return candidate.relative_to(cwd).as_posix()
            except ValueError:
                return candidate.as_posix()

    # Walk known test roots for nested layouts (e.g. tests/unit/test_foo.py)
    _test_root_names = ("tests", "test", "__tests__", "spec")
    _test_name_patterns = (
        f"test_{stem}{suffix}",
        f"{stem}_test{suffix}",
        f"{stem}.test{suffix}",
        f"{stem}.spec{suffix}",
        f"{stem}_spec{suffix}",
    )
    for root_name in _test_root_names:
        test_root = cwd / root_name
        if not test_root.is_dir():
            continue
        for dirpath, _, filenames in os.walk(test_root):
            for pattern in _test_name_patterns:
                if pattern in filenames:
                    found = Path(dirpath) / pattern
                    try:
                        return found.relative_to(cwd).as_posix()
                    except ValueError:
                        return found.as_posix()
    return ""


def _scan_constraints(file_path: Path) -> list[str]:
    """Scan a file for constraint signals (TODOs, rate limits, timeouts)."""
    hits: list[str] = []
    try:
        with file_path.open(encoding="utf-8-sig", errors="replace") as fh:
            for line_no, line in enumerate(fh, 1):
                ll = line.lower()
                if any(pat in ll for pat in _CONSTRAINT_PATTERNS_LOWER):
                    hits.append(f"{file_path}:{line_no}: {line.strip()[:120]}")
                    if (
                        len(hits) == _MAX_CONSTRAINTS_PER_FILE
                    ):  # stop reading early
                        break
    except OSError:
        return []
    return hits


def _extract_interface_shapes(file_path: Path, nouns: set[str]) -> list[str]:
    """Extract named types/classes from source files that match domain nouns.

    Uses Python AST for .py files; regex patterns for TypeScript, Go, Rust, and others.
    """
    suffix = file_path.suffix.lower()
    terms: list[str] = []

    if suffix == ".py":
        try:
            tree = ast.parse(
                file_path.read_text(encoding="utf-8", errors="ignore")
            )
        except SyntaxError, OSError:
            return []
        for node in ast.walk(tree):
            if isinstance(node, ast.ClassDef) and any(
                noun in node.name.lower() for noun in nouns
            ):
                doc = ast.get_docstring(node)
                entry = node.name + (f" — {doc[:80]}" if doc else "")
                terms.append(entry)
        return terms[:5]

    compiled = _LANG_TYPE_REGEXES.get(suffix)
    if not compiled:
        return []
    try:
        text = file_path.read_text(encoding="utf-8-sig", errors="replace")
    except OSError:
        return []
    for match in compiled.finditer(text):
        name = match.group(1)
        if any(noun in name.lower() for noun in nouns):
            terms.append(name)

    # Additional pass: exported function names for TypeScript/TSX
    if suffix in {".ts", ".tsx"}:
        for match in _TS_EXPORT_FN_PATTERN.finditer(text):
            # group(1) = function keyword name, group(2) = const arrow name
            name = match.group(1) or match.group(2) or ""
            if name and any(noun in name.lower() for noun in nouns):
                terms.append(name)

    return terms[:5]


def _estimate_scope(
    file_count: int, crosses_boundary: bool
) -> tuple[str, str]:
    if file_count <= 2 and not crosses_boundary:
        return "S", f"{file_count} file(s), isolated change"
    if file_count <= 5:
        label = "M"
    elif file_count <= 10:
        label = "L"
    else:
        label = "XL"
    if crosses_boundary:
        label = {"S": "M", "M": "L"}.get(label, label)
    return (
        label,
        f"{file_count} file(s) matched; boundary crossing: {crosses_boundary}",
    )


def scan(nouns: list[str], cwd: Path) -> ScanResult:
    """Scan the codebase for context relevant to the given domain nouns.

    Returns a ScanResult with related files, terminology, constraints,
    analogous features, test coverage, scope estimate, and unknowns.
    """
    if not nouns:
        raise ValueError("scan() requires at least one domain noun")
    nouns = [_sanitize_noun(n) for n in nouns]

    noun_set = {n.lower() for n in nouns}
    project_synonyms = _load_project_synonyms(cwd)
    effective_map = (
        {k: list(v) for k, v in _SYNONYM_MAP.items()}
        if not project_synonyms
        else {
            k: list(
                dict.fromkeys(
                    _SYNONYM_MAP.get(k, []) + project_synonyms.get(k, [])
                )
            )
            for k in {**_SYNONYM_MAP, **project_synonyms}
        }
    )
    all_terms = _expand_synonyms(nouns, effective_map)
    adjacent_nouns = all_terms[len(nouns) :]

    result = ScanResult(feature_area=" | ".join(nouns))

    # ── Phase 1: parallel grep ──────────────────────────────────────────────
    adjacent_paths: set[str] = set()
    search_failed: list[str] = []

    # Cap workers: phase 1 has len(all_terms) grep tasks
    _phase1_workers = min(32, len(all_terms))
    with ThreadPoolExecutor(max_workers=_phase1_workers) as pool:
        # Submit in noun order; iterate results in the same order (not
        # completion order) so related_files is deterministic across runs.
        grep_futures = [
            (noun, pool.submit(_grep_files, noun, cwd)) for noun in nouns
        ]
        adjacent_futures = [
            (noun, pool.submit(_grep_files, noun, cwd))
            for noun in adjacent_nouns
        ]

        match_counts: Counter[str] = Counter()
        for noun, fut in grep_futures:
            paths = fut.result()
            if paths is None:
                search_failed.append(noun)
                continue
            match_counts.update(paths)
        seen_paths = set(match_counts)
        ranked = sorted(match_counts, key=lambda p: -match_counts[p])
        result.related_files = [FileSignal(path=p) for p in ranked]

        for noun, fut in adjacent_futures:
            paths = fut.result()
            if paths is None:
                search_failed.append(noun)
                continue
            for path_str in paths:
                if (
                    path_str not in seen_paths
                    and path_str not in adjacent_paths
                ):
                    adjacent_paths.add(path_str)

    if search_failed:
        result.unknowns.append(
            "search unavailable or timed out for: "
            + ", ".join(search_failed)
            + " — file coverage incomplete"
        )

    # Scope must reflect everything that matched, not the capped report list
    total_matched = len(result.related_files)
    matched_modules = {
        Path(f.path).parts[0]
        if len(Path(f.path).parts) > 1
        else "<root>"
        for f in result.related_files
    }

    # Cap to _MAX_FILES most relevant files
    result.related_files = result.related_files[
        :_MAX_FILES
    ]  # keep the highest-ranked files

    # Record analogous features (files found only via adjacent synonyms)
    result.analogous_features = sorted(adjacent_paths)[:_MAX_ANALOGOUS]

    # ── Phase 2: parallel git log + constraints + term extraction + test files ──
    # Cap workers: phase 2 tasks are bounded by _MAX_FILES (5 files x 4 task types)
    _phase2_workers = (
        _MAX_FILES * 4
    )  # 20: 5 files x 4 task types (log, constraints, shapes, tests)
    with ThreadPoolExecutor(max_workers=_phase2_workers) as pool:
        log_futures = {
            pool.submit(_git_log, f.path, cwd): f for f in result.related_files
        }
        constraint_futures = {
            pool.submit(_scan_constraints, cwd / f.path): f.path
            for f in result.related_files
        }
        shape_futures = {
            pool.submit(
                _extract_interface_shapes, cwd / f.path, noun_set
            ): f.path
            for f in result.related_files
        }
        test_futures = {
            pool.submit(_find_test_file, cwd / f.path, cwd): f
            for f in result.related_files
        }

        # Collect in submission (dict-insertion) order, not completion order,
        # so constraints / interface_shapes / unknowns stay deterministic
        # across runs — the futures still execute concurrently in the pool.
        for fut, file_signal in log_futures.items():
            try:
                file_signal.last_commit = fut.result()
            except Exception:
                file_signal.last_commit = "no history"

        for fut, path in constraint_futures.items():
            try:
                result.constraints.extend(fut.result())
            except Exception as exc:
                result.unknowns.append(
                    f"Error scanning constraints for {path}: {exc}"
                )

        for fut, path in shape_futures.items():
            try:
                result.interface_shapes.extend(fut.result())
            except Exception as exc:
                result.unknowns.append(
                    f"Error extracting shapes for {path}: {exc}"
                )

        for fut, file_signal in test_futures.items():
            try:
                test_path = fut.result()
                file_signal.has_tests = bool(test_path)
                file_signal.test_file = test_path
            except Exception as exc:
                result.unknowns.append(
                    f"Error finding test file for {file_signal.path}: {exc}"
                )

    # ── Scope signal ─────────────────────────────────────────────────────────
    crosses_boundary = len(matched_modules) > 1
    result.scope, result.scope_reasoning = _estimate_scope(
        total_matched, crosses_boundary
    )

    # ── Unknowns ──────────────────────────────────────────────────────────────
    if not result.interface_shapes:
        result.unknowns.append("No typed definitions found for domain nouns")
    if not any(
        f.last_commit and f.last_commit != "no history"
        for f in result.related_files
    ):
        result.unknowns.append("No git history found for matched files")
    if result.related_files and not any(
        f.has_tests for f in result.related_files
    ):
        result.unknowns.append(
            "No test files found for matched files — test coverage unknown"
        )

    # ── Compress: dedupe + cap low-signal fields for Phase 3 ideation ──────────
    for f in result.related_files:
        f.last_commit = _truncate_git_log(f.last_commit, _MAX_LOG_LINES)
    result.interface_shapes = _dedupe_stable(result.interface_shapes)[
        :_MAX_INTERFACE_SHAPES
    ]
    result.constraints = _dedupe_stable(result.constraints)[:_MAX_CONSTRAINTS]
    result.unknowns = _dedupe_stable(result.unknowns)[:_MAX_UNKNOWNS]
    result.analogous_features = _dedupe_stable(result.analogous_features)[
        :_MAX_ANALOGOUS
    ]
    result.scope_reasoning = _trim_str(result.scope_reasoning, 150)

    return result


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Parallel codebase scanner for parallel-brainstorming Phase 1"
    )
    parser.add_argument(
        "nouns", nargs="+", help="Domain nouns from the feature description"
    )
    parser.add_argument(
        "--cwd",
        default=".",
        type=Path,
        help="Project root (default: current directory)",
    )
    args = parser.parse_args()

    try:
        args.nouns = [_sanitize_noun(n) for n in args.nouns]
    except ValueError as exc:
        parser.error(str(exc))

    cwd = args.cwd.resolve()
    if not cwd.is_dir():
        parser.error(f"--cwd path does not exist or is not a directory: {cwd}")
    result = scan(args.nouns, cwd)
    print(json.dumps(asdict(result), separators=(",", ":")))


if __name__ == "__main__":
    main()
