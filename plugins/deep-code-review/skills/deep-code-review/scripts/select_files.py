#!/usr/bin/env python3
"""Deterministic reviewable-file selection ported from OpenCodeReview.
Outputs JSON: {scope, repo_root, total, by_rule, files:[{file, rule_doc}]}.
Exit 2 if not inside a git repository."""
import json, subprocess, sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from glob_match import match_glob

REFS = Path(__file__).resolve().parent.parent / "references"


def repo_root(cwd=None):
    r = subprocess.run(["git", "rev-parse", "--show-toplevel"],
                       capture_output=True, text=True, cwd=cwd)
    return r.stdout.strip() if r.returncode == 0 else None


def list_files(scope, cwd=None):
    r = subprocess.run(["git", "ls-files", "--full-name", "--", scope],
                       capture_output=True, text=True, cwd=cwd)
    return [ln for ln in r.stdout.splitlines() if ln] if r.returncode == 0 else []


def load_refs():
    exts = {e.lower() for e in json.loads((REFS / "supported_file_types.json").read_text())}
    excludes = json.loads((REFS / "default_exclude_patterns.json").read_text())
    rules = json.loads((REFS / "system_rules.json").read_text())
    return exts, excludes, rules["path_rule_map"], rules["default_rule"]


def is_allowed(path, exts):
    return ("." in path) and ("." + path.rsplit(".", 1)[-1]).lower() in exts


def is_excluded(path, excludes):
    lpath = path.lower()
    return any(match_glob(p.lower(), lpath) for p in excludes)


def rule_for(path, path_rule_map, default_rule):
    lpath = path.lower()
    for pat, doc in path_rule_map.items():
        if match_glob(pat.lower(), lpath):
            return doc
    return default_rule


def select(scope=".", cwd=None):
    root = repo_root(cwd)
    if root is None:
        raise SystemExit(2)
    exts, excludes, prm, default_rule = load_refs()
    files = []
    for p in list_files(scope, cwd):
        if not is_allowed(p, exts) or is_excluded(p, excludes):
            continue
        files.append({"file": p, "rule_doc": rule_for(p, prm, default_rule)})
    by_rule = {}
    for f in files:
        by_rule.setdefault(f["rule_doc"], []).append(f["file"])
    return {"scope": scope, "repo_root": root, "total": len(files),
            "by_rule": by_rule, "files": files}


def main(argv):
    scope = argv[1] if len(argv) > 1 else "."
    if repo_root() is None:
        print("error: not inside a git repository", file=sys.stderr)
        return 2
    print(json.dumps(select(scope), ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
