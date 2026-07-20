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


@_GIT_REQUIRED
def test_grep_files_returns_empty_on_no_matches(tmp_path):
    _init_git_repo(tmp_path)
    (tmp_path / "a.py").write_text("a = 1\n", encoding="utf-8")
    _git_commit_all(tmp_path)
    assert sc._grep_files("nonexistent", tmp_path) == []
