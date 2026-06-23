#!/usr/bin/env python3
"""Recall: print the vault index, and (with keywords) the bodies of matching notes.
Run this BEFORE producing or recommending anything — that's the step that gets skipped.

Usage:
  python recall.py                 # just the MEMORY.md index
  python recall.py html pr serif   # index + every note whose text contains any keyword
"""
import os
import pathlib
import sys

sys.stdout.reconfigure(encoding="utf-8")  # Windows 콘솔(cp949)에서도 한글·em-dash 출력
sys.stderr.reconfigure(encoding="utf-8")

ROOTS = ("user", "feedback", "project", "reference", "projects")


def vault() -> pathlib.Path:
    v = os.environ.get("LLM_WIKI_PATH")
    if not v or not os.path.isdir(v):
        sys.exit(f"LLM_WIKI_PATH 미설정/없음: {v!r}")
    return pathlib.Path(v)


def main() -> None:
    vp = vault()
    idx = vp / "MEMORY.md"
    print("=== MEMORY.md ===")
    print(idx.read_text(encoding="utf-8") if idx.exists() else "(없음)")

    kws = [k.lower() for k in sys.argv[1:]]
    if not kws:
        return

    print(f"\n=== 매칭 노트 (키워드: {' '.join(kws)}) ===")
    hits = []
    for r in ROOTS:
        for p in (vp / r).rglob("*.md"):
            text = p.read_text(encoding="utf-8", errors="ignore")
            if any(k in text.lower() for k in kws):
                hits.append((p, text))
    if not hits:
        print("(매칭 없음)")
    for p, text in hits:
        print(f"\n--- {p.relative_to(vp).as_posix()} ---")
        print(text.strip())


if __name__ == "__main__":
    main()
