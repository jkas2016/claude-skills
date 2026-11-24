#!/usr/bin/env python3
"""Ranked summaries by default. Explicit original/index reads also have a byte budget."""
import argparse
from memory import budget, cli, emit, inside, load_notes, note_path, positive, resolve_redirect, select, vault
from registry import state
from usage import record, record_exposed


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
        original = note_path(root, args.read)
        rel = args.read if original.is_file() else resolve_redirect(args.read, state(root).get('redirects', {}))
        if rel is None:
            raise ValueError(f'DROPPED_NOTE: {args.read}')
        path = note_path(root, rel)
        if not path.is_file() and not rel.startswith('_archive/'):
            archived = note_path(root, f'_archive/{rel}')
            if archived.is_file():
                path = archived
                rel = f'_archive/{rel}'
        text = f'=== {rel} ===\n'
        if rel.startswith('_archive/'):
            if '.full-' in path.stem:
                text += 'Archived full text of a compressed note.\n'
            else:
                text += f'Restore with maintain.py --unarchive {rel} --apply\n'
        text += path.read_text(encoding='utf-8')
    elif args.index:
        text = inside(root, 'MEMORY.md').read_text(encoding='utf-8')
    else:
        hits = select(load_notes(root), args.keywords, args.project, args.include_inactive)
        text = f'Memory results: {min(len(hits), args.limit)}/{len(hits)}; read with --read PATH\n'
        text += ''.join(n.summary() for n in hits[:args.limit])
        if len(hits) > args.limit:
            text += '[omitted: result limit; narrow search or raise --limit]\n'
    output = emit(text, args.max_bytes, whole_lines=not args.read)
    if args.read:
        record(root, 'read', rel, 'recall')
    elif not args.index:
        record_exposed(root, hits[:args.limit], output, 'recall')


if __name__ == '__main__':
    cli(main)
