#!/usr/bin/env python3
"""Save a note and index together; --check shows candidates without writing or reading stdin."""
import argparse
import json
import re
import sys
from memory import Note, cli, edit_note, emit, inside, load_notes, locked, note_path, select, split_note, today, vault
from registry import STATE, due, next_state, render_index
from transactions import apply_batch, read_optional

TYPES = ('user', 'feedback', 'project', 'reference')


def identifier(value):
    if not re.fullmatch(r'[\w-]+', value):
        raise argparse.ArgumentTypeError('단일 이름 필요 (문자/숫자/_/-)')
    return value


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--type', required=True, choices=TYPES)
    ap.add_argument('--name', required=True, type=identifier)
    ap.add_argument('--desc', required=True)
    ap.add_argument('--tags', default='')
    ap.add_argument('--alias', default='')
    ap.add_argument('--hook', required=True)
    ap.add_argument('--project', type=identifier)
    ap.add_argument('--check', action='store_true')
    ap.add_argument('--key', type=identifier, help='stable concept key; update its existing canonical file')
    ap.add_argument('--distinct-reason', help='why a new note differs from related candidates')
    args = ap.parse_args()
    root = vault()
    rel = f'projects/{args.project}/{args.type}/{args.name}.md' if args.project else f'{args.type}/{args.name}.md'
    path = note_path(root, rel)
    if args.check:
        hits = select(load_notes(root), [args.name, args.desc, args.tags.replace(',', ' ')],
                      args.project or '', include_inactive=True)
        emit('Candidates (inspect before creating; inactive notes may need reactivation):\n' +
             ''.join(n.summary() for n in hits[:8]), 8192)
        return
    body = sys.stdin.read().strip()
    if not body:
        raise ValueError('빈 본문 거부')
    for value in (args.desc, args.hook, args.alias):
        if '\n' in value or '\r' in value:
            raise ValueError('description/hook/alias는 한 줄')
    aliases = [x.strip() for x in args.alias.split(',') if x.strip()]
    fields = {'name': args.name, 'description': args.desc, 'type': args.type,
              'tags': [x.strip() for x in args.tags.split(',') if x.strip()],
              'aliases': aliases, 'index_hook': args.hook, 'updated': today()}
    with locked(root):
        notes = load_notes(root)
        matches = [n for n in notes if args.key and n.project == (args.project or '') and
                   n.meta.get('type') == args.type and
                   (n.meta.get('memory_key') == args.key or args.key in n.meta.get('memory_keys', []))]
        if len(matches) > 1:
            raise ValueError('duplicate concept key; consolidate first')
        if matches:
            rel = matches[0].rel
            path = note_path(root, rel)
            fields['name'] = path.stem
        before = read_optional(path)
        maintenance = due(root, notes)
        if before is None:
            if maintenance['due']:
                raise ValueError('CONSOLIDATION_REQUIRED: run consolidate.py and finish host review before creating another note')
            hits = [n for n in select(notes, [args.name, args.desc, args.tags.replace(',', ' ')],
                                     args.project or '', include_inactive=True)
                    if n.project == (args.project or '') and n.meta.get('type') == args.type]
            if hits and not (args.distinct_reason or '').strip():
                raise ValueError('RELATED_MEMORY_EXISTS: update the canonical note/key, or supply --distinct-reason after reading candidates')
        if args.key and (before is None or not split_note(before.decode())[1].get('memory_key')):
            fields['memory_key'] = args.key
        if before is None:
            fields['created'] = today()
            text = '---\n' + '\n'.join(f'{k}: {json.dumps(v, ensure_ascii=False)}' for k, v in fields.items()) + '\n---\n\n' + body + '\n'
        else:
            text = edit_note(before.decode('utf-8'), fields, body)
        idx = inside(root, 'MEMORY.md')
        old_index = read_optional(idx)
        parsed = split_note(text)
        updated_notes = [n for n in notes if n.rel != rel] + [Note(rel, text, parsed[1], parsed[2])]
        updated_index = render_index(updated_notes, (old_index or b'').decode('utf-8'))
        backup = apply_batch(root, [(rel, before, text.encode('utf-8')),
                                   ('MEMORY.md', old_index, updated_index.encode('utf-8')),
                                   (STATE, read_optional(inside(root, STATE)), next_state(root, updated_notes))])
    status = due(root, updated_notes)
    print(f'wrote {rel}; backup={backup}; consolidation_due={status["due"]}')
    if status['due']:
        print('NEXT: run consolidate.py; review all scope groups and apply the consolidation plan.')


if __name__ == '__main__':
    cli(main)
