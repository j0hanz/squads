"""Characterization tests for scan_context.py.

Locks the trust-boundary behavior of _sanitize_noun, _load_project_synonyms,
the scope boundary-crossing signal, _find_test_file's vendor-dir prune, and
_grep_files's empty-list-vs-None semantics.

Tests that need git are skipped on git-less machines (do not fail CI).
"""

import subprocess
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import scan_context as sc


def _git_available() -> bool:
    try:
        subprocess.run(
            ["git", "--version"],
            capture_output=True,
            check=False,
            timeout=5,
        )
        return True
    except FileNotFoundError, subprocess.TimeoutExpired:
        return False


_GIT_REQUIRED = pytest.mark.skipif(
    not _git_available(), reason="git not available in this environment"
)


def _init_git_repo(repo_root: Path) -> None:
    """Init a git repo at repo_root and commit a single empty file so git grep
    has indexed content to search. Caller writes real file contents after."""
    subprocess.run(
        ["git", "init", "-q", str(repo_root)],
        check=True,
        capture_output=True,
        timeout=10,
    )
    subprocess.run(
        ["git", "-C", str(repo_root), "config", "user.email", "t@t"],
        check=True,
        capture_output=True,
        timeout=5,
    )
    subprocess.run(
        ["git", "-C", str(repo_root), "config", "user.name", "t"],
        check=True,
        capture_output=True,
        timeout=5,
    )


def _git_commit_all(repo_root: Path, msg: str = "init") -> None:
    subprocess.run(
        ["git", "-C", str(repo_root), "add", "-A"],
        check=True,
        capture_output=True,
        timeout=10,
    )
    subprocess.run(
        ["git", "-C", str(repo_root), "commit", "-q", "-m", msg],
        check=True,
        capture_output=True,
        timeout=10,
    )


# --- Step 1/2: _sanitize_noun trust boundary (already shipped, now locked) ---


def test_sanitize_noun_rejects_empty_and_flags():
    with pytest.raises(ValueError):
        sc._sanitize_noun("")
    with pytest.raises(ValueError):
        sc._sanitize_noun("--flag")
    assert sc._sanitize_noun("search.*") == "search"


def test_sanitize_noun_strips_regex_meta():
    # Parens are regex meta but 'b' is alphanumeric — all three letters kept.
    assert sc._sanitize_noun("a(b)c") == "abc"


# --- Step 1: project synonyms sanitized before reaching grep ---


def test_load_project_synonyms_drops_regex_meta_and_empty(tmp_path, capfd):
    (tmp_path / "synonyms.json").write_text(
        '{"search": [".*", "", "query"]}', encoding="utf-8"
    )
    result = sc._load_project_synonyms(tmp_path)
    assert result == {"search": ["query"]}
    # The dropped synonyms emit warnings on stderr; query is unchanged so no
    # warning for it.
    err = capfd.readouterr().err
    assert "dropped synonym '.*'" in err
    assert "dropped synonym ''" in err


# --- Step 2: malformed synonyms.json warns, returns {} ---


def test_load_project_synonyms_warns_on_bad_json(tmp_path, capfd):
    (tmp_path / "synonyms.json").write_text("{not json", encoding="utf-8")
    assert sc._load_project_synonyms(tmp_path) == {}
    assert "warning: synonyms.json unreadable" in capfd.readouterr().err


def test_load_project_synonyms_warns_on_non_object(tmp_path, capfd):
    (tmp_path / "synonyms.json").write_text("[1, 2, 3]", encoding="utf-8")
    assert sc._load_project_synonyms(tmp_path) == {}
    assert (
        "warning: synonyms.json is not a JSON object" in capfd.readouterr().err
    )


# --- Step 3: root-level files count toward the boundary signal ---


@_GIT_REQUIRED
def test_scope_boundary_with_root_file(tmp_path):
    _init_git_repo(tmp_path)
    (tmp_path / "src").mkdir()
    (tmp_path / "src" / "foo.py").write_text("search = 1\n", encoding="utf-8")
    (tmp_path / "config.py").write_text("search = 2\n", encoding="utf-8")
    _git_commit_all(tmp_path)
    result = sc.scan(["search"], tmp_path)
    # src/foo.py (module 'src') + root config.py (sentinel '<root>') => 2 modules
    assert "boundary crossing: True" in result.scope_reasoning


# --- Step 4: _find_test_file prunes _SKIP_DIRS during os.walk ---


def test_find_test_file_skips_vendor_dirs(tmp_path):
    (tmp_path / "foo.py").write_text("# source\n", encoding="utf-8")
    (tmp_path / "tests").mkdir()
    (tmp_path / "tests" / "test_foo.py").write_text(
        "# real test\n", encoding="utf-8"
    )
    vendored = tmp_path / "tests" / "node_modules" / "pkg"
    vendored.mkdir(parents=True)
    (vendored / "test_foo.py").write_text(
        "# vendored trap\n", encoding="utf-8"
    )
    found = sc._find_test_file(tmp_path / "foo.py", tmp_path)
    assert found == "tests/test_foo.py"


# --- Step 6: _grep_files semantics: [] on zero matches, None on no tool ---


def test_interface_extraction_surfaces_functions():
    # Path resolution matches the convention used by the other tests.
    target = Path(__file__).resolve().parent.parent / "scan_context.py"
    shapes = sc._extract_interface_shapes(target, {"scan"})
    # ClassDef ScanResult must still be present (existing behavior).
    assert any(s.startswith("ScanResult") for s in shapes)
    # FunctionDef scan must now also be surfaced (new behavior).
    assert any(s == "scan" or s.startswith("scan") for s in shapes)


def test_size_guard_skips_oversize_file(tmp_path, monkeypatch):
    # >256 KiB file must be rejected by stat-before-read; never read.
    big = tmp_path / "big.py"
    big.write_text("x = 1\n" * 60000, encoding="utf-8")  # ~300 KiB
    assert big.stat().st_size > 262144

    read_calls = 0

    def _count_read(self, *args, **kwargs):
        nonlocal read_calls
        read_calls += 1
        return original_read(self, *args, **kwargs)

    original_read = Path.read_text
    monkeypatch.setattr(Path, "read_text", _count_read)

    assert sc._extract_interface_shapes(big, {"x"}) == []
    assert read_calls == 0


@_GIT_REQUIRED
def test_grep_files_returns_empty_on_no_matches(tmp_path):
    _init_git_repo(tmp_path)
    (tmp_path / "a.py").write_text("a = 1\n", encoding="utf-8")
    _git_commit_all(tmp_path)
    assert sc._grep_files("nonexistent", tmp_path) == []


# --- TASK-003: _extract_imports ---


def test_extract_imports_py(tmp_path):
    f = tmp_path / "m.py"
    f.write_text(
        "import os.path\n"
        "from collections import defaultdict\n"
        "from . import x\n",
        encoding="utf-8",
    )
    assert sc._extract_imports(f) == ["os", "collections"]


def test_extract_imports_skips_py_relative(tmp_path):
    f = tmp_path / "m.py"
    f.write_text(
        "from .sub import y\nfrom ..pkg import z\n",
        encoding="utf-8",
    )
    assert sc._extract_imports(f) == []


def test_extract_imports_ts_absolute_and_relative(tmp_path):
    f = tmp_path / "m.ts"
    f.write_text(
        'import {x} from "pkg/mod"\nimport {y} from "./rel"\n',
        encoding="utf-8",
    )
    assert sc._extract_imports(f) == ["pkg"]


def test_extract_imports_unsupported_ext(tmp_path):
    f = tmp_path / "m.txt"
    f.write_text('import {x} from "pkg"\n', encoding="utf-8")
    assert sc._extract_imports(f) == []


# --- TASK-004: _extract_file_signals ---


def test_file_signals_success():
    target = Path(__file__).resolve().parent.parent / "scan_context.py"
    shapes, imports, parse_error = sc._extract_file_signals(target, {"scan"})
    assert parse_error == ""
    assert shapes
    assert any(s.startswith("ScanResult") for s in shapes)
    assert any(s == "scan" or s.startswith("scan") for s in shapes)
    assert imports
    assert any(
        top in {"ast", "pathlib", "subprocess", "os", "re", "json", "sys"}
        for top in imports
    )


def test_file_signals_parse_failure(tmp_path):
    f = tmp_path / "broken.py"
    f.write_text("def (\n", encoding="utf-8")
    shapes, imports, parse_error = sc._extract_file_signals(f, {"x"})
    assert shapes == []
    assert imports == []
    assert parse_error  # truthy exception string


def test_file_signals_oversize(tmp_path):
    big = tmp_path / "big.py"
    big.write_text("x = 1\n" * 60000, encoding="utf-8")  # ~300 KiB
    assert big.stat().st_size > 262144
    shapes, imports, parse_error = sc._extract_file_signals(big, {"x"})
    assert shapes == []
    assert imports == []
    assert parse_error == "size > 256KiB"


# --- TASK-005: Phase-2 pool over 7 files + unknowns ---


@_GIT_REQUIRED
def test_phase2_adjacent_gets_signals_only(tmp_path):
    """Adjacent files get the combined shape+import future only — no
    log/constraint/test futures. Proven via imports dict + absence from
    related_files/constraints."""
    _init_git_repo(tmp_path)
    (tmp_path / "src").mkdir()
    # Matched file: contains noun "search"
    (tmp_path / "src" / "foo.py").write_text(
        "class SearchEngine:\n    pass\n", encoding="utf-8"
    )
    # Adjacent file: contains synonym "query", NOT "search"; has an import.
    (tmp_path / "src" / "bar.py").write_text(
        "import foo\n\ndef query_handler():\n    pass\n", encoding="utf-8"
    )
    _git_commit_all(tmp_path)
    result = sc.scan(["search"], tmp_path)
    # Adjacent is NOT a related_file
    assert [f.path for f in result.related_files] == ["src/foo.py"]
    # No constraint line references the adjacent path
    assert not any("src/bar.py" in c for c in result.constraints)
    # Adjacent file was processed by _extract_file_signals: imports recorded
    assert "src/bar.py" in result.file_imports
    assert "foo" in result.file_imports["src/bar.py"]
    # Matched file imports also recorded
    assert "src/foo.py" in result.file_imports
    # No parse error for adjacent
    assert not any("src/bar.py" in u for u in result.unknowns)
    # Matched file shape present in interface_shapes
    assert any(s.startswith("SearchEngine") for s in result.interface_shapes)


@_GIT_REQUIRED
def test_phase2_adjacent_parse_failure_unknowns(tmp_path):
    """Adjacent file with a syntax error lands an Error parsing line in
    unknowns."""
    _init_git_repo(tmp_path)
    (tmp_path / "src").mkdir()
    (tmp_path / "src" / "foo.py").write_text("search = 1\n", encoding="utf-8")
    # Adjacent: contains synonym "query" but has a syntax error.
    (tmp_path / "src" / "bar.py").write_text(
        "def (\nimport query\n", encoding="utf-8"
    )
    _git_commit_all(tmp_path)
    result = sc.scan(["search"], tmp_path)
    assert any("Error parsing src/bar.py" in u for u in result.unknowns)


@_GIT_REQUIRED
def test_phase2_matched_parse_failure_unknowns(tmp_path):
    """A matched file with a syntax error lands an Error parsing line in
    unknowns and contributes no shapes."""
    _init_git_repo(tmp_path)
    (tmp_path / "src").mkdir()
    # Matched file: contains noun "search" but has a syntax error.
    (tmp_path / "src" / "foo.py").write_text(
        "def (\nsearch = 1\n", encoding="utf-8"
    )
    _git_commit_all(tmp_path)
    result = sc.scan(["search"], tmp_path)
    assert any("Error parsing src/foo.py" in u for u in result.unknowns)
    assert not any("Search" in s for s in result.interface_shapes)


# --- TASK-006: ranked analog detection by import-overlap ---


@_GIT_REQUIRED
def test_analog_rank_prefers_import_overlap(tmp_path):
    """Among synonym-adjacent candidates, the one sharing a project (non-stdlib)
    import with the matched file ranks first."""
    _init_git_repo(tmp_path)
    (tmp_path / "src").mkdir()
    # Matched file: contains noun "search"; imports a project module sharedlib.
    (tmp_path / "src" / "foo.py").write_text(
        "import sharedlib\nsearch = 1\n", encoding="utf-8"
    )
    # High-overlap adjacent: contains synonym "query", imports the same
    # project module sharedlib → overlap_count = 1. Named to sort AFTER the
    # low-overlap file so the old sorted() behavior would put it second.
    (tmp_path / "src" / "a_z_high.py").write_text(
        "import sharedlib\nquery = 1\n", encoding="utf-8"
    )
    # Low-overlap adjacent: contains synonym "query", imports only stdlib os
    # → filtered out → overlap_count = 0. Sorts BEFORE the high file.
    (tmp_path / "src" / "a_a_low.py").write_text(
        "import os\nquery = 1\n", encoding="utf-8"
    )
    _git_commit_all(tmp_path)
    result = sc.scan(["search"], tmp_path)
    # Both adjacent files are in the pool, both in adjacent_paths.
    assert {f.path for f in result.related_files} == {"src/foo.py"}
    assert len(result.analogous_features) >= 1
    # High-overlap candidate ranks first despite sorting after the low one.
    assert result.analogous_features[0].endswith("a_z_high.py")
    # Low-overlap is present and not first.
    analog_names = [p.rsplit("/", 1)[-1] for p in result.analogous_features]
    assert "a_z_high.py" in analog_names
    if "a_a_low.py" in analog_names:
        assert analog_names.index("a_z_high.py") < analog_names.index(
            "a_a_low.py"
        )


@_GIT_REQUIRED
def test_analog_rank_deterministic_across_seeds(tmp_path):
    """analogous_features output is identical under PYTHONHASHSEED=0 and =1."""
    import os

    _init_git_repo(tmp_path)
    (tmp_path / "src").mkdir()
    # Matched file contains the noun "search".
    (tmp_path / "src" / "foo.py").write_text(
        "import sharedlib\nsearch = 1\n", encoding="utf-8"
    )
    # Three synonym-adjacent files (all contain "query", not "search") so
    # ordering is non-trivial.
    for name in ("a_one.py", "a_two.py", "a_three.py"):
        (tmp_path / "src" / name).write_text(
            "import sharedlib\nquery = 1\n", encoding="utf-8"
        )
    _git_commit_all(tmp_path)

    script = (
        "import sys, json; sys.path.insert(0, "
        f"{str(Path(__file__).resolve().parent.parent)!r}); "
        "from pathlib import Path; "
        "import scan_context as sc; "
        f"r = sc.scan(['search'], Path({str(tmp_path)!r})); "
        "print(json.dumps(r.analogous_features))"
    )

    out0 = subprocess.run(
        [sys.executable, "-c", script],
        capture_output=True,
        text=True,
        env={**os.environ, "PYTHONHASHSEED": "0"},
        timeout=30,
    )
    out1 = subprocess.run(
        [sys.executable, "-c", script],
        capture_output=True,
        text=True,
        env={**os.environ, "PYTHONHASHSEED": "1"},
        timeout=30,
    )
    assert out0.returncode == 0, out0.stderr
    assert out1.returncode == 0, out1.stderr
    assert out0.stdout.strip(), "empty stdout under PYTHONHASHSEED=0"
    assert out0.stdout.strip() == out1.stdout.strip(), (
        f"analogous_features differs across seeds:\n"
        f"  seed=0: {out0.stdout.strip()}\n"
        f"  seed=1: {out1.stdout.strip()}"
    )
