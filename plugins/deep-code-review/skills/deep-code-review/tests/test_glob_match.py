import sys, pathlib
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent / "scripts"))
from glob_match import match_glob, expand_braces

def test_brace_expand():
    assert sorted(expand_braces("a.{ts,js}")) == ["a.js", "a.ts"]
    assert expand_braces("a.{kt}") == ["a.kt"]

def test_star_does_not_cross_slash():
    assert match_glob("**/*.java", "Foo.java")
    assert match_glob("**/*.java", "src/main/Foo.java")
    assert not match_glob("**/*.java", "src/main/Foo.kt")

def test_brace_in_glob():
    assert match_glob("**/*.{ts,js,tsx,jsx}", "a/b/c.tsx")
    assert not match_glob("**/*.{ts,js,tsx,jsx}", "a/b/c.py")
    assert match_glob("**/*.{kt}", "x/Main.kt")

def test_literal_filenames():
    assert match_glob("**/pom.xml", "mod/pom.xml")
    assert not match_glob("**/pom.xml", "mod/pom.xml.bak")

def test_doublestar_dir():
    assert match_glob("**/__tests__/**", "src/__tests__/a.js")
    assert not match_glob("**/__tests__/**", "src/app.js")
    assert match_glob("**/src/test/java/**/*.java", "a/src/test/java/x/y/T.java")

def test_case_sensitive_glob():
    assert match_glob("**/*{mapper,dao}*.xml", "m/userdao.xml")
    assert not match_glob("**/*{mapper,dao}*.xml", "m/UserDao.xml")
