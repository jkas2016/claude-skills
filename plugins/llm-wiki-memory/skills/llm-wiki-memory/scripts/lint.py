#!/usr/bin/env python3
"""Lint the vault like a formatter: every note carries the 7 frontmatter fields, and
MEMORY.md pointers and note files stay in sync. Run after any edit/delete.
Exits non-zero when there are problems so it can gate a commit.
"""
import os
import pathlib
import re
import sys

sys.stdout.reconfigure(encoding="utf-8")  # Windows 콘솔(cp949)에서도 한글·em-dash 출력
sys.stderr.reconfigure(encoding="utf-8")

FIELDS = ("name", "description", "type", "tags", "aliases", "created", "updated")
ROOTS = ("user", "feedback", "project", "reference", "projects")
SKIP = {"README.md", "MEMORY.md"}  # 노트가 아닌 문서는 검사 대상에서 제외


def vault() -> pathlib.Path:
    v = os.environ.get("LLM_WIKI_PATH")
    if not v or not os.path.isdir(v):
        sys.exit(f"LLM_WIKI_PATH 미설정/없음: {v!r}")
    return pathlib.Path(v)


def main() -> None:
    vp = vault()
    problems: list[str] = []
    notes: list[pathlib.Path] = []

    for r in ROOTS:
        for p in (vp / r).rglob("*.md"):
            if p.name in SKIP:
                continue
            notes.append(p)
            rel = p.relative_to(vp).as_posix()
            text = p.read_text(encoding="utf-8", errors="ignore")
            fm = re.match(r"^---\n(.*?)\n---", text, re.S)
            if not fm:
                problems.append(f"{rel}: frontmatter(--- 블록) 없음")
                continue
            for f in FIELDS:
                if not re.search(rf"^{f}:", fm.group(1), re.M):
                    problems.append(f"{rel}: frontmatter 필드 누락 '{f}'")

    idx = vp / "MEMORY.md"
    idx_text = idx.read_text(encoding="utf-8") if idx.exists() else ""
    linked = set(re.findall(r"\]\(([^)]+\.md)\)", idx_text))
    for rel in sorted(linked):
        if not (vp / rel).exists():
            problems.append(f"MEMORY.md: dead link -> {rel}")

    note_rels = {p.relative_to(vp).as_posix() for p in notes}
    for rel in sorted(note_rels - linked):
        problems.append(f"{rel}: MEMORY.md 인덱스에 포인터 없음")

    if problems:
        print(f"LINT 문제 {len(problems)}건:")
        for x in problems:
            print("  -", x)
        sys.exit(1)
    print(f"OK — 노트 {len(notes)}개, 인덱스 링크 {len(linked)}개, 문제 0")


if __name__ == "__main__":
    main()
