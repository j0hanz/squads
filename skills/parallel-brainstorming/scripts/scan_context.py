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
import fnmatch
import json
import os
import re
import subprocess
import sys
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
    design_docs: list[str] = field(default_factory=list)
    analogous_features: list[str] = field(default_factory=list)
    scope: str = "M"
    scope_reasoning: str = ""
    unknowns: list[str] = field(default_factory=list)


# Directories that are never useful to scan
_SKIP_DIRS = frozenset(
    {"venv", ".venv", "node_modules", "__pycache__", ".git", "dist", "build"}
)

_DOC_GLOBS = [
    "glossary.md",
    "CONTEXT.md",
    "ARCHITECTURE.md",
    "docs/adr/*.md",
    "decisions/*.md",
    "docs/design/*.md",
]
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

# Regex patterns for extracting named types from non-Python source files
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


def _sanitize_noun(raw: str) -> str:
    """Strip to alphanumeric/hyphen only; reject empty or flag-like results.

    The script must not trust argv unconditionally before it reaches git
    grep / rg as a regex pattern, regardless of what the caller passed.
    """
    cleaned = re.sub(r"[^A-Za-z0-9-]", "", raw)
    if not cleaned or cleaned.startswith("-"):
        raise ValueError(f"invalid domain noun after sanitization: {raw!r}")
    return cleaned


def _expand_synonyms(nouns: list[str]) -> list[str]:
    """Return adjacent synonyms for well-known domain terms (deduped, originals first)."""
    expanded = list(nouns)
    seen = {n.lower() for n in nouns}
    for noun in nouns:
        for synonym in _SYNONYM_MAP.get(noun.lower(), []):
            if synonym not in seen:
                seen.add(synonym)
                expanded.append(synonym)
    return expanded


_SUBPROCESS_TIMEOUT = 15  # 15s: git grep/rg over a mid-size repo returns well within this; bounds a hung tool


def _git_log(path: str, cwd: Path) -> str:
    try:
        result = subprocess.run(
            ["git", "log", "--oneline", "-5", "--", path],
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


def _find_doc_files(cwd: Path) -> list[str]:
    buckets: list[list[str]] = [[] for _ in _DOC_GLOBS]
    for root, dirnames, filenames in os.walk(cwd):
        # prune skip-dirs in place; sorted for run-to-run determinism
        dirnames[:] = sorted(d for d in dirnames if d not in _SKIP_DIRS)
        rel_root = Path(root).relative_to(cwd)
        for name in sorted(filenames):
            rel = (rel_root / name).as_posix()
            for i, g in enumerate(_DOC_GLOBS):
                if fnmatch.fnmatch(rel, g) or fnmatch.fnmatch(rel, "*/" + g):
                    buckets[i].append((rel_root / name).as_posix())
                    break
    found = [p for bucket in buckets for p in bucket]
    return found[:5]  # 5: matches the original cap


def _find_test_file(file_path: Path, cwd: Path) -> str:
    """Return the relative path of a test file for the given source file, or ''."""
    stem = file_path.stem
    suffix = file_path.suffix
    parent = file_path.parent

    candidates = [
        parent / f"test_{stem}{suffix}",
        parent / f"{stem}_test{suffix}",
        parent / f"{stem}.test{suffix}",
        parent / f"{stem}.spec{suffix}",
        cwd / "tests" / f"test_{stem}{suffix}",
        cwd / "test" / f"test_{stem}{suffix}",
        cwd / "__tests__" / f"{stem}.test{suffix}",
        cwd / "__tests__" / f"{stem}.spec{suffix}",
        cwd / "spec" / f"{stem}_spec{suffix}",
        cwd / "spec" / f"{stem}.spec{suffix}",
    ]
    for candidate in candidates:
        if candidate.exists():
            try:
                return candidate.relative_to(cwd).as_posix()
            except ValueError:
                return candidate.as_posix()
    return ""


def _scan_constraints(file_path: Path) -> list[str]:
    """Scan a file for constraint signals (TODOs, rate limits, timeouts)."""
    try:
        text = file_path.read_text(encoding="utf-8-sig", errors="replace")
    except OSError:
        return []
    hits: list[str] = []
    for line_no, line in enumerate(text.splitlines(), 1):
        if any(pat.lower() in line.lower() for pat in _CONSTRAINT_PATTERNS):
            hits.append(f"{file_path.name}:{line_no}: {line.strip()[:120]}")
    return hits[:3]


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

    pattern = _LANG_TYPE_PATTERNS.get(suffix)
    if not pattern:
        return []
    try:
        text = file_path.read_text(encoding="utf-8-sig", errors="replace")
    except OSError:
        return []
    for match in re.finditer(pattern, text):
        name = match.group(1)
        if any(noun in name.lower() for noun in nouns):
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
        label = {"S": "M", "M": "L", "L": "XL"}.get(label, label)
    return (
        label,
        f"{file_count} file(s) matched; boundary crossing: {crosses_boundary}",
    )


def scan(nouns: list[str], cwd: Path) -> ScanResult:
    """Scan the codebase for context relevant to the given domain nouns.

    Returns a ScanResult with related files, terminology, constraints, design
    docs, analogous features, test coverage, scope estimate, and unknowns.
    """
    if not nouns:
        raise ValueError("scan() requires at least one domain noun")

    noun_set = {n.lower() for n in nouns}
    all_terms = _expand_synonyms(nouns)
    adjacent_nouns = all_terms[len(nouns) :]

    result = ScanResult(feature_area=" | ".join(nouns))

    # ── Phase 1: parallel grep + doc discovery ──────────────────────────────
    seen_paths: set[str] = set()
    adjacent_paths: set[str] = set()
    search_failed: list[str] = []

    with ThreadPoolExecutor(max_workers=8) as pool:
        # Submit in noun order; iterate results in the same order (not
        # completion order) so related_files is deterministic across runs.
        grep_futures = [
            (noun, pool.submit(_grep_files, noun, cwd)) for noun in nouns
        ]
        adjacent_futures = [
            (noun, pool.submit(_grep_files, noun, cwd))
            for noun in adjacent_nouns
        ]
        doc_future = pool.submit(_find_doc_files, cwd)

        for noun, fut in grep_futures:
            paths = fut.result()
            if paths is None:
                search_failed.append(noun)
                continue
            for path_str in paths:
                if path_str not in seen_paths:
                    seen_paths.add(path_str)
                    result.related_files.append(FileSignal(path=path_str))

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

        result.design_docs = doc_future.result()
        if not result.design_docs:
            result.unknowns.append(
                "No glossary, ADR, or architecture docs found"
            )

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
        for f in result.related_files
        if len(Path(f.path).parts) > 1
    }

    # Cap to 5 most relevant files
    result.related_files = result.related_files[
        :5
    ]  # 5: matches _MAX_FILES in compress_report.py

    # Record analogous features (files found only via adjacent synonyms)
    result.analogous_features = sorted(adjacent_paths)[
        :2
    ]  # 2: only seed the Minimalist lane (sorted for run-to-run determinism)

    # ── Phase 2: parallel git log + constraints + term extraction + test files ──
    with ThreadPoolExecutor(max_workers=8) as pool:
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
    print(json.dumps(asdict(result), indent=2))


if __name__ == "__main__":
    main()
