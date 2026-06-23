import subprocess, sys, pathlib
import pytest

SCRIPTS = pathlib.Path(__file__).resolve().parent.parent / "scripts"
sys.path.insert(0, str(SCRIPTS))


@pytest.fixture
def repo(tmp_path):
    def git(*a):
        subprocess.run(["git", *a], cwd=tmp_path, check=True, capture_output=True)
    git("init", "-q")
    git("config", "user.email", "t@t")
    git("config", "user.name", "t")
    for rel in ["main.go", "internal/foo.go", "internal/foo_test.go",
                "src/App.tsx", "src/App.test.tsx", "lib/util.py", "Makefile"]:
        p = tmp_path / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text("x\n")
    git("add", "-A")
    git("commit", "-q", "-m", "init")
    return tmp_path
