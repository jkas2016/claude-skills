#!/usr/bin/env python3
"""Validate required fields, index links, dates and lifecycle targets without changing files."""
import datetime as dt
import re
from memory import FIELDS, cli, inside, load_notes, vault
from maintain import validate_lifecycle


def main():
    root = vault()
    notes = load_notes(root)
    problems = []
    for n in notes:
        for field in FIELDS:
            if field not in n.meta:
                problems.append(f'{n.rel}: missing {field}')
        for field in ('created', 'updated'):
            try:
                dt.date.fromisoformat(str(n.meta.get(field, '')))
            except ValueError:
                problems.append(f'{n.rel}: invalid {field}')
        if n.meta.get('type') not in ('user', 'feedback', 'project', 'reference'):
            problems.append(f'{n.rel}: invalid type')
        if 'pinned' in n.meta and n.meta['pinned'] not in ('true', 'false'):
            problems.append(f'{n.rel}: invalid pinned')
    try:
        validate_lifecycle(notes)
    except ValueError as exc:
        problems.append(str(exc))
    idx = inside(root, 'MEMORY.md')
    text = idx.read_text(encoding='utf-8') if idx.exists() else ''
    linked = re.findall(r'\]\(([^)]+\.(?:md|html))\)', text)
    for rel in sorted(set(linked)):
        if not inside(root, rel).is_file():
            problems.append(f'MEMORY.md: dead link -> {rel}')
        if linked.count(rel) > 1:
            problems.append(f'MEMORY.md: duplicate pointer -> {rel}')
    for rel in sorted({n.rel for n in notes} - set(linked)):
        problems.append(f'{rel}: MEMORY.md 인덱스에 포인터 없음')
    if problems:
        raise ValueError('\n'.join(problems))
    print(f'OK — 노트 {len(notes)}개, 인덱스 링크 {len(linked)}개, 문제 0')


if __name__ == '__main__':
    cli(main)
