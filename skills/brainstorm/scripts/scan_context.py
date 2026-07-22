#!/usr/bin/env python3
"""
Parallel codebase scanner for brainstorm Phase 1.

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
    truncated: dict[str, str] = field(default_factory=dict)


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

# Top-level stdlib module names used later for overlap-scoring filtering.
# Explicit list (no "etc."); filtering is applied at scoring time, not here.
_STDLIB_MODULES = frozenset(
    {
        "os",
        "sys",
        "re",
        "typing",
        "json",
        "pathlib",
        "collections",
        "functools",
        "itertools",
        "subprocess",
        "argparse",
        "dataclasses",
        "concurrent",
        "ast",
        "io",
        "abc",
        "enum",
    }
)


def _stdlib_filter(imports: list[str]) -> list[str]:
    """Drop stdlib top-level module names from a raw imports list."""
    return [m for m in imports if m not in _STDLIB_MODULES]


# Import patterns for non-.py supported languages. Each regex captures the
# top-level module name from ABSOLUTE imports only; relative imports are
# skipped (no match). Compiled once at module load, mirroring _LANG_TYPE_REGEXES.
_LANG_IMPORT_PATTERNS: dict[str, str] = {
    # TS/TSX: import/export ... from "pkg/..." — skip "..." (relative) paths.
    ".ts": r'\b(?:import|export)\b[^;]*?\sfrom\s"([^./][^"]*)"',
    ".tsx": r'\b(?:import|export)\b[^;]*?\sfrom\s"([^./][^"]*)"',
    # Go: import "pkg" (single or grouped). Capture first segment of path.
    ".go": r'\bimport\s+(?:\(\s*)?"([^"]*)"',
    # Rust: use pkg::...; or extern crate pkg; — skip self/crate/super.
    ".rs": r"\b(?:use\s+(?!self::|crate::|super::)([\w]+)|extern\s+crate\s+(\w+))",
    # Top-level package from the dependency statement (first path segment).
    ".java": r"\bimport\s+(?:static\s+)?([\w]+)",
    ".cs": r"\busing\s+([\w]+)",
    ".kt": r"\bimport\s+([\w]+)",
    ".swift": r"\bimport\s+([\w]+)",
}
_LANG_IMPORT_REGEXES: dict[str, re.Pattern[str]] = {
    ext: re.compile(pat) for ext, pat in _LANG_IMPORT_PATTERNS.items()
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
        print(
            f"warning: synonyms.json unreadable ({exc}); synonyms ignored",
            file=sys.stderr,
        )
        return {}
    if not isinstance(raw, dict):
        print(
            "warning: synonyms.json is not a JSON object; synonyms ignored",
            file=sys.stderr,
        )
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
            encoding="utf-8",
            errors="replace",
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
            encoding="utf-8",
            errors="replace",
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
            encoding="utf-8",
            errors="replace",
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
        for dirpath, dirs, filenames in os.walk(test_root):
            dirs[:] = [d for d in dirs if d not in _SKIP_DIRS]
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


def _shapes_from_tree(tree: ast.AST, nouns: set[str]) -> list[str]:
    """Collect noun-matched interface shapes from a parsed Python AST tree.

    Priority-ordered: ClassDef (≤3/file) first, then FunctionDef/AsyncFunctionDef
    (≤2/file combined), then TypeAlias (≤1/file). AnnAssign typed fields are
    dropped (noisy). Per-file terms[:5] cap applied by the caller's sibling
    `_shapes_from_text` is mirrored here.
    """
    terms: list[str] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.ClassDef) and any(
            noun in node.name.lower() for noun in nouns
        ):
            doc = ast.get_docstring(node)
            entry = node.name + (f" — {doc[:80]}" if doc else "")
            terms.append(entry)
    classes = terms[:3]
    funcs: list[str] = []
    aliases: list[str] = []
    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and any(
            noun in node.name.lower() for noun in nouns
        ):
            if len(funcs) < 2:
                funcs.append(node.name)
        elif (
            isinstance(node, ast.TypeAlias)
            and any(noun in node.name.lower() for noun in nouns)
            and len(aliases) < 1
        ):
            aliases.append(node.name)
    terms = classes + funcs + aliases
    return terms[:5]


def _shapes_from_text(text: str, suffix: str, nouns: set[str]) -> list[str]:
    """Regex-based shape extraction for non-.py supported languages."""
    terms: list[str] = []
    compiled = _LANG_TYPE_REGEXES.get(suffix)
    if not compiled:
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


def _imports_from_tree(tree: ast.AST) -> list[str]:
    """Collect top-level module names from a parsed Python AST tree.

    Relative imports (level > 0) are skipped. Returns RAW names (no stdlib
    filtering — that happens at overlap-scoring time).
    """
    names: list[str] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                top = alias.name.split(".")[0]
                if top and top not in names:
                    names.append(top)
        elif isinstance(node, ast.ImportFrom):
            if node.level and node.level > 0:
                continue  # relative import — skip
            if node.module:
                top = node.module.split(".")[0]
                if top and top not in names:
                    names.append(top)
    return names


def _imports_from_text(text: str, suffix: str) -> list[str]:
    """Regex-based top-level import extraction for non-.py supported languages.

    Absolute imports only; relative imports are skipped (no match).
    """
    compiled = _LANG_IMPORT_REGEXES.get(suffix)
    if not compiled:
        return []
    names: list[str] = []
    for match in compiled.finditer(text):
        # Each pattern's first capture group is the top-level module name
        # (Rust has two alternation groups; pick whichever matched).
        top = next((g for g in match.groups() if g), None)
        if not top:
            continue
        # For path-style imports (e.g. TS "pkg/mod"), take the first segment.
        top = top.split("/")[0].split(":")[0]
        if top and top not in names:
            names.append(top)
    return names


def _extract_interface_shapes(file_path: Path, nouns: set[str]) -> list[str]:
    """Extract named types/classes from source files that match domain nouns.

    Uses Python AST for .py files; regex patterns for TypeScript, Go, Rust,
    and others. Thin wrapper over `_shapes_from_tree` / `_shapes_from_text`.
    """
    # Stat-first size guard: skip files >256 KiB without reading. Replaces
    # unimplementable win32 wall-time timeout for in-process AST.
    try:
        if file_path.stat().st_size > 262144:
            return []
    except OSError:
        return []
    suffix = file_path.suffix.lower()

    if suffix == ".py":
        try:
            tree = ast.parse(
                file_path.read_text(encoding="utf-8", errors="ignore")
            )
        except SyntaxError, OSError:
            return []
        return _shapes_from_tree(tree, nouns)

    try:
        text = file_path.read_text(encoding="utf-8-sig", errors="replace")
    except OSError:
        return []
    return _shapes_from_text(text, suffix, nouns)


def _extract_imports(file_path: Path) -> list[str]:
    """Return top-level module names imported by `file_path`.

    For .py: walks ast.Import/ast.ImportFrom; relative imports (level > 0)
    are skipped. For other supported languages: regex over file text, absolute
    imports only. Returns RAW names (no stdlib filtering — that happens at
    overlap-scoring time). Unsupported extensions and parse errors return [].
    Thin wrapper over `_imports_from_tree` / `_imports_from_text`.
    """
    # Stat-first size guard: same 256 KiB ceiling as _extract_interface_shapes.
    try:
        if file_path.stat().st_size > 262144:
            return []
    except OSError:
        return []
    suffix = file_path.suffix.lower()

    if suffix == ".py":
        try:
            tree = ast.parse(
                file_path.read_text(encoding="utf-8", errors="ignore")
            )
        except SyntaxError, OSError:
            return []
        return _imports_from_tree(tree)

    try:
        text = file_path.read_text(encoding="utf-8-sig", errors="replace")
    except OSError:
        return []
    return _imports_from_text(text, suffix)


def _extract_file_signals(
    file_path: Path, nouns: set[str]
) -> tuple[list[str], list[str], str]:
    """Extract (shapes, imports, parse_error) from a single file in ONE read.

    REQ-005: combined extraction in one read per file.
    REQ-006: stat-first 256 KiB guard → ([], [], "size > 256KiB") without
    reading; SyntaxError/OSError → ([], [], str(exc)); success → parse_error == "".
    """
    try:
        if file_path.stat().st_size > 262144:
            return ([], [], "size > 256KiB")
    except OSError as exc:
        return ([], [], str(exc))
    suffix = file_path.suffix.lower()

    if suffix == ".py":
        try:
            text = file_path.read_text(encoding="utf-8", errors="ignore")
            tree = ast.parse(text)
        except (SyntaxError, OSError) as exc:
            return ([], [], str(exc))
        return (
            _shapes_from_tree(tree, nouns),
            _imports_from_tree(tree),
            "",
        )

    try:
        text = file_path.read_text(encoding="utf-8-sig", errors="replace")
    except OSError as exc:
        return ([], [], str(exc))
    return (
        _shapes_from_text(text, suffix, nouns),
        _imports_from_text(text, suffix),
        "",
    )


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
            try:
                paths = fut.result()
            except Exception:
                search_failed.append(noun)
                continue
            if paths is None:
                search_failed.append(noun)
                continue
            match_counts.update(paths)
        seen_paths = set(match_counts)
        ranked = sorted(match_counts, key=lambda p: -match_counts[p])
        result.related_files = [FileSignal(path=p) for p in ranked]

        for noun, fut in adjacent_futures:
            try:
                paths = fut.result()
            except Exception:
                search_failed.append(noun)
                continue
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
        Path(f.path).parts[0] if len(Path(f.path).parts) > 1 else "<root>"
        for f in result.related_files
    }

    # Cap to _MAX_FILES most relevant files
    before_files = len(result.related_files)
    result.related_files = result.related_files[
        :_MAX_FILES
    ]  # keep the highest-ranked files
    after_files = len(result.related_files)
    if before_files > after_files:
        result.truncated["related_files"] = f"{after_files}/{before_files}"

    # Record analogous features (files found only via adjacent synonyms)
    before_analog = len(adjacent_paths)
    result.analogous_features = sorted(adjacent_paths)[:_MAX_ANALOGOUS]
    if before_analog > _MAX_ANALOGOUS:
        result.truncated["analogous_features"] = f"{_MAX_ANALOGOUS}/{before_analog}"

    # ── Phase 2: parallel git log + constraints + shapes+imports + tests ───────
    # shape+import futures run over matched files (≤5) PLUS adjacent files (≤2)
    # = 7 total. Adjacent files get the combined future ONLY (no log/constraint/
    # test futures). Totals: 5 log + 5 constraints + 7 shape+import + 5 tests = 22
    # tasks on 20 workers (2 queue). _phase2_workers stays _MAX_FILES * 4 = 20.
    _phase2_workers = (
        _MAX_FILES * 4
    )  # 20: 5 files x 4 task types (log, constraints, shapes, tests)
    adjacent_files = result.analogous_features  # sorted list, ≤2 posix paths
    file_imports: dict[
        str, list[str]
    ] = {}  # per-file RAW imports for TASK-006
    with ThreadPoolExecutor(max_workers=_phase2_workers) as pool:
        log_futures = {
            pool.submit(_git_log, f.path, cwd): f for f in result.related_files
        }
        constraint_futures = {
            pool.submit(_scan_constraints, cwd / f.path): f.path
            for f in result.related_files
        }
        # Combined shape+import extraction in one read per file (REQ-005).
        # Matched files first, then adjacent — dict-insertion order is the
        # collection order, keeping output deterministic across runs.
        shape_paths = [f.path for f in result.related_files] + list(
            adjacent_files
        )
        shape_futures = {
            pool.submit(_extract_file_signals, cwd / p, noun_set): p
            for p in shape_paths
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
                shapes, imports, parse_error = fut.result()
            except Exception as exc:
                result.unknowns.append(
                    f"Error extracting shapes for {path}: {exc}"
                )
                continue
            if parse_error:
                result.unknowns.append(f"Error parsing {path}: {parse_error}")
                continue
            result.interface_shapes.extend(shapes)
            file_imports[path] = imports

        for fut, file_signal in test_futures.items():
            try:
                test_path = fut.result()
                file_signal.has_tests = bool(test_path)
                file_signal.test_file = test_path
            except Exception as exc:
                result.unknowns.append(
                    f"Error finding test file for {file_signal.path}: {exc}"
                )

    # Expose per-file imports for TASK-006 (not a dataclass field, so asdict
    # JSON output is unaffected). Matched + adjacent files are keyed here.
    result.file_imports = file_imports

    # ── TASK-006: rank synonym-adjacent candidates by import-overlap ───────────
    # Import-overlap is a RANKING signal over the synonym-adjacent pool
    # (adjacent_paths), NOT a separate pool. The x2 synonym weight is dropped
    # (dead logic). Candidates beyond the ≤2 processed in the pool are absent
    # from file_imports → empty imports → overlap 0. The (-overlap, path) key
    # is total-order, so output never depends on PYTHONHASHSEED.
    matched_filtered_imports: set[str] = set()
    for f in result.related_files:
        matched_filtered_imports.update(
            _stdlib_filter(result.file_imports.get(f.path, []))
        )
    ranked = sorted(
        adjacent_paths,
        key=lambda c: (
            -len(
                set(_stdlib_filter(result.file_imports.get(c, [])))
                & matched_filtered_imports
            ),
            c,
        ),
    )
    before_analog_rerank = len(ranked)
    result.analogous_features = ranked[:_MAX_ANALOGOUS]
    if before_analog_rerank > _MAX_ANALOGOUS:
        result.truncated["analogous_features"] = f"{_MAX_ANALOGOUS}/{before_analog_rerank}"

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

    interface_deduped = _dedupe_stable(result.interface_shapes)
    before_shapes = len(interface_deduped)
    result.interface_shapes = interface_deduped[:_MAX_INTERFACE_SHAPES]
    if before_shapes > len(result.interface_shapes):
        result.truncated["interface_shapes"] = f"{len(result.interface_shapes)}/{before_shapes}"

    constraints_deduped = _dedupe_stable(result.constraints)
    before_constraints = len(constraints_deduped)
    result.constraints = constraints_deduped[:_MAX_CONSTRAINTS]
    if before_constraints > len(result.constraints):
        result.truncated["constraints"] = f"{len(result.constraints)}/{before_constraints}"

    unknowns_deduped = _dedupe_stable(result.unknowns)
    before_unknowns = len(unknowns_deduped)
    result.unknowns = unknowns_deduped[:_MAX_UNKNOWNS]
    if before_unknowns > len(result.unknowns):
        result.truncated["unknowns"] = f"{len(result.unknowns)}/{before_unknowns}"

    analogous_deduped = _dedupe_stable(result.analogous_features)
    before_analog_final = len(analogous_deduped)
    result.analogous_features = analogous_deduped[:_MAX_ANALOGOUS]
    if before_analog_final > len(result.analogous_features):
        result.truncated["analogous_features"] = f"{len(result.analogous_features)}/{before_analog_final}"
    result.scope_reasoning = _trim_str(result.scope_reasoning, 150)

    return result


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Parallel codebase scanner for brainstorm Phase 1"
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
