#!/usr/bin/env python3
"""Save a note and index together; --check shows candidates without writing or reading stdin."""
import argparse
import json
import re
import sys
from memory import cli, edit_note, emit, inside, load_notes, locked, note_path, select, today, vault
from transactions import apply_batch, read_optional

TYPES = ('user', 'feedback', 'project', 'reference')


def identifier(value):
    if not re.fullmatch(r'[\w-]+', value):
        raise argparse.ArgumentTypeError('단일 이름 필요 (문자/숫자/_/-)')
    return value


def index_text(text, rel, alias, hook, section):
    lines = text.splitlines() if text else ['# MEMORY', '']
    lines = [ln for ln in lines if f']({rel})' not in ln]
    pointer = f'- [{alias}]({rel}) — {hook}'
    header = f'## {section}'
    if header in lines:
        i = lines.index(header) + 1
        if i < len(lines) and not lines[i].strip():
            i += 1
        lines.insert(i, pointer)
    else:
        if lines and lines[-1].strip():
            lines.append('')
        lines += [header, '', pointer]
    return '\n'.join(lines).rstrip() + '\n'


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
    alias = aliases[0] if aliases else args.name
    # Escape brackets to avoid introducing extra index links.
    alias = alias.replace('[', '').replace(']', '')
    fields = {'name': args.name, 'description': args.desc, 'type': args.type,
              'tags': [x.strip() for x in args.tags.split(',') if x.strip()],
              'aliases': aliases, 'updated': today()}
    with locked(root):
        before = read_optional(path)
        if before is None:
            fields['created'] = today()
            text = '---\n' + '\n'.join(f'{k}: {json.dumps(v, ensure_ascii=False)}' for k, v in fields.items()) + '\n---\n\n' + body + '\n'
        else:
            text = edit_note(before.decode('utf-8'), fields, body)
        idx = inside(root, 'MEMORY.md')
        old_index = read_optional(idx)
        updated_index = index_text((old_index or b'').decode('utf-8'), rel, alias, args.hook,
                                   f'projects/{args.project}' if args.project else args.type)
        backup = apply_batch(root, [(rel, before, text.encode('utf-8')),
                                   ('MEMORY.md', old_index, updated_index.encode('utf-8'))])
    print(f'wrote {rel}; backup={backup}')


if __name__ == '__main__':
    cli(main)
