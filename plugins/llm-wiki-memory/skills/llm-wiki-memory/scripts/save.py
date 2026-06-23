#!/usr/bin/env python3
"""Write a vault note with valid frontmatter (7 fields, auto dates) and update the
MEMORY.md index pointer. Mechanizes the deterministic parts so SKILL.md stays lean —
the LLM cannot reliably know today's date; this script fills it from the system clock.

Body is read from stdin. On re-save of an existing note, `created` is preserved and
`updated` bumped to today.

Example:
  python save.py --type feedback --name no_dark_html \\
    --desc "정보 문서 HTML은 화이트·단일 컬럼" --tags "html,doc" \\
    --alias "정보 우선 HTML" --hook "화이트 단일 컬럼, 다크/hero 금지" < body.md
"""
import argparse
import datetime
import os
import pathlib
import re
import sys

sys.stdout.reconfigure(encoding="utf-8")  # Windows 콘솔(cp949)에서도 한글·em-dash 출력
sys.stderr.reconfigure(encoding="utf-8")
sys.stdin.reconfigure(encoding="utf-8")  # 본문(stdin)을 UTF-8로 읽는다(cp949 → surrogate 깨짐 방지)

TYPES = ("user", "feedback", "project", "reference")


def vault() -> pathlib.Path:
    v = os.environ.get("LLM_WIKI_PATH")
    if not v or not os.path.isdir(v):
        sys.exit(f"LLM_WIKI_PATH 미설정/없음: {v!r}")
    return pathlib.Path(v)


def fmt_list(s: str) -> str:
    return "[" + ", ".join(x.strip() for x in s.split(",") if x.strip()) + "]"


def update_index(vp: pathlib.Path, rel: str, alias: str, hook: str, section: str) -> None:
    idx = vp / "MEMORY.md"
    lines = idx.read_text(encoding="utf-8").splitlines() if idx.exists() else ["# MEMORY", ""]
    lines = [ln for ln in lines if f"]({rel})" not in ln]  # drop any stale pointer to this file
    pointer = f"- [{alias}]({rel}) — {hook}"
    header = f"## {section}"
    if header in lines:
        i = lines.index(header) + 1
        if i < len(lines) and lines[i].strip() == "":  # keep the blank line after the header
            i += 1
        lines.insert(i, pointer)
    else:
        if lines and lines[-1].strip():
            lines.append("")
        lines += [header, "", pointer]
    idx.write_text("\n".join(lines).rstrip() + "\n", encoding="utf-8")


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--type", required=True, choices=TYPES)
    ap.add_argument("--name", required=True, help="영문 snake_case 1-3 단어")
    ap.add_argument("--desc", required=True, help="80자 이내 한 줄 요약")
    ap.add_argument("--tags", default="", help="콤마 구분, 2-4개")
    ap.add_argument("--alias", default="", help="콤마 구분, 보통 한국어 1개")
    ap.add_argument("--hook", required=True, help="MEMORY.md 인덱스 한 줄 요약")
    ap.add_argument("--project", default="", help="projects/<name> 하위에 둘 때")
    args = ap.parse_args()

    vp = vault()
    today = datetime.date.today().isoformat()
    sub = pathlib.Path("projects", args.project, args.type) if args.project else pathlib.Path(args.type)
    path = vp / sub / f"{args.name}.md"
    rel = (sub / f"{args.name}.md").as_posix()

    created = today
    if path.exists():
        m = re.search(r"^created:\s*(.+)$", path.read_text(encoding="utf-8"), re.M)
        if m:
            created = m.group(1).strip()

    body = sys.stdin.read().strip()
    if not body:
        print("경고: 본문(stdin)이 비었습니다.", file=sys.stderr)
    alias0 = args.alias.split(",")[0].strip() if args.alias.strip() else args.name

    frontmatter = (
        f"---\nname: {args.name}\ndescription: {args.desc}\ntype: {args.type}\n"
        f"tags: {fmt_list(args.tags)}\naliases: {fmt_list(args.alias)}\n"
        f"created: {created}\nupdated: {today}\n---\n\n"
    )
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(frontmatter + body + "\n", encoding="utf-8")

    section = f"projects/{args.project}" if args.project else args.type
    update_index(vp, rel, alias0, args.hook, section)
    print(f"wrote {rel}  (created={created}, updated={today}); MEMORY.md '## {section}' 갱신")


if __name__ == "__main__":
    main()
