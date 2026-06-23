import sys, pathlib, subprocess
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent / "scripts"))
import select_files as sf


def test_total_excludes_tests_and_nonallowed(repo):
    r = sf.select(".", cwd=str(repo))
    files = {f["file"] for f in r["files"]}
    assert files == {"main.go", "internal/foo.go", "src/App.tsx", "lib/util.py"}
    assert r["total"] == 4


def test_excludes_test_files(repo):
    files = {f["file"] for f in sf.select(".", cwd=str(repo))["files"]}
    assert "internal/foo_test.go" not in files     # **/*_test.go
    assert "src/App.test.tsx" not in files          # **/*.test.{...}
    assert "Makefile" not in files                  # not an allowed extension


def test_rule_mapping(repo):
    rule = {f["file"]: f["rule_doc"] for f in sf.select(".", cwd=str(repo))["files"]}
    assert rule["src/App.tsx"] == "ts_js_tsx_jsx.md"
    assert rule["main.go"] == "default.md"           # OCR has no go rule -> default
    assert rule["lib/util.py"] == "default.md"       # OCR has no py rule -> default


def test_not_a_git_repo(tmp_path):
    assert sf.repo_root(cwd=str(tmp_path)) is None


# ── Case-insensitive matching tests (TDD for FIX 1) ───────────────────────────

import pytest

@pytest.fixture
def case_repo(tmp_path):
    """Small git repo with mixed-case filenames to verify case-insensitive matching."""
    def git(*a):
        subprocess.run(["git", *a], cwd=tmp_path, check=True, capture_output=True)
    git("init", "-q")
    git("config", "user.email", "t@t")
    git("config", "user.name", "t")
    # dao/UserDao.xml  → should match **/*{mapper,dao}*.xml → mapper_dao_xml.md
    # Foo.JAVA         → uppercase ext → should match **/*.java → java.md
    # pkg/Foo_Test.go  → uppercase T → should match **/*_test.go (case-insensitive) → excluded
    # main.go          → control: not excluded, maps to default.md
    for rel in ["dao/UserDao.xml", "Foo.JAVA", "pkg/Foo_Test.go", "main.go"]:
        p = tmp_path / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text("x\n")
    git("add", "-A")
    git("commit", "-q", "-m", "init")
    return tmp_path


def test_case_insensitive_rule_dao_xml(case_repo):
    """dao/UserDao.xml must map to mapper_dao_xml.md (case-insensitive rule mapping)."""
    rule = {f["file"]: f["rule_doc"] for f in sf.select(".", cwd=str(case_repo))["files"]}
    assert "dao/UserDao.xml" in rule, "dao/UserDao.xml should be selected"
    assert rule["dao/UserDao.xml"] == "mapper_dao_xml.md"


def test_case_insensitive_rule_java_uppercase_ext(case_repo):
    """Foo.JAVA (uppercase extension) must map to java.md."""
    rule = {f["file"]: f["rule_doc"] for f in sf.select(".", cwd=str(case_repo))["files"]}
    assert "Foo.JAVA" in rule, "Foo.JAVA should be selected (extension allowed case-insensitively)"
    assert rule["Foo.JAVA"] == "java.md"


def test_case_insensitive_exclude_test_go(case_repo):
    """pkg/Foo_Test.go must be excluded (case-insensitive match of **/*_test.go)."""
    files = {f["file"] for f in sf.select(".", cwd=str(case_repo))["files"]}
    assert "pkg/Foo_Test.go" not in files
