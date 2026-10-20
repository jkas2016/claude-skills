#!/usr/bin/env python3
"""Ranked summaries by default. Explicit original/index reads also have a byte budget."""
import argparse
from memory import budget, cli, emit, inside, load_notes, note_path, positive, select, vault


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('keywords', nargs='*')
    ap.add_argument('--project', help='프로젝트 + 전역 노트로 범위 제한')
    ap.add_argument('--include-inactive', action='store_true')
    modes = ap.add_mutually_exclusive_group()
    modes.add_argument('--read', metavar='RELATIVE_PATH', help='상태와 무관하게 선택 원문 읽기')
    modes.add_argument('--index', action='store_true', help='전체 인덱스 읽기')
    ap.add_argument('--limit', type=positive, default=8)
    ap.add_argument('--max-bytes', type=budget, default=8192)
    args = ap.parse_args()
    root = vault()
    if args.read:
        text = f'=== {args.read} ===\n' + note_path(root, args.read).read_text(encoding='utf-8')
    elif args.index:
        text = inside(root, 'MEMORY.md').read_text(encoding='utf-8')
    else:
        hits = select(load_notes(root), args.keywords, args.project, args.include_inactive)
        text = f'Memory results: {min(len(hits), args.limit)}/{len(hits)}; read with --read PATH\n'
        text += ''.join(n.summary() for n in hits[:args.limit])
        if len(hits) > args.limit:
            text += '[omitted: result limit; narrow search or raise --limit]\n'
    emit(text, args.max_bytes, whole_lines=not args.read)


if __name__ == '__main__':
    cli(main)
