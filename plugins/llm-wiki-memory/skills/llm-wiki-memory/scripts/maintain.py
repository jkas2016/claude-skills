#!/usr/bin/env python3
"""Validate a reviewable JSON plan; --apply backs up and applies it, --restore reverses it."""
import argparse
from contextlib import nullcontext
import json
from pathlib import Path
from memory import STATUSES, cli, digest, edit_note, load_notes, locked, note_path, split_note, today, vault
from transactions import apply_batch, restore_batch
from registry import MARKER, STATE, next_state, render_index


def validate_lifecycle(notes):
    by_path = {n.rel: n for n in notes}
    for n in notes:
        if n.status not in STATUSES:
            raise ValueError(f'{n.rel}: invalid status')
        target = n.meta.get('superseded_by')
        if n.status == 'superseded':
            if target == n.rel or target not in by_path or by_path[target].status != 'active':
                raise ValueError(f'{n.rel}: superseded_by must point directly to another active note')
        elif target:
            raise ValueError(f'{n.rel}: superseded_by requires status=superseded')


def prepare(root, plan):
    changes = plan.get('changes')
    if not isinstance(changes, list) or not changes:
        raise ValueError('non-empty changes 목록 필요')
    notes = load_notes(root)
    by_path = {n.rel: n for n in notes}
    batch, seen, preview = [], set(), []
    for change in changes:
        if set(change) - {'path', 'sha256', 'reason', 'status', 'superseded_by', 'body', 'description', 'pinned'}:
            raise ValueError('지원하지 않는 변경 필드')
        rel = change['path']
        path = note_path(root, rel)
        if rel in seen or rel not in by_path:
            raise ValueError(f'중복/없는 노트: {rel}')
        seen.add(rel)
        if not isinstance(change.get('reason'), str) or not change['reason'].strip():
            raise ValueError('변경 reason 필요')
        before = path.read_bytes()
        if digest(before) != change['sha256']:
            raise ValueError(f'원본 해시 불일치: {rel}')
        fields = {k: change[k] for k in ('status', 'superseded_by', 'description', 'pinned') if k in change}
        if 'status' in fields and fields['status'] not in STATUSES:
            raise ValueError('status는 active/archived/superseded')
        if 'description' in fields and (not isinstance(fields['description'], str) or
                not fields['description'].strip() or '\n' in fields['description'] or '\r' in fields['description']):
            raise ValueError('description은 비어 있지 않은 한 줄')
        if 'superseded_by' in fields and (not isinstance(fields['superseded_by'], str) or
                                         not fields['superseded_by'].strip()):
            raise ValueError('superseded_by는 정본 경로')
        if 'pinned' in fields and not isinstance(fields['pinned'], bool):
            raise ValueError('pinned는 boolean')
        if 'body' in change and (not isinstance(change['body'], str) or not change['body'].strip()):
            raise ValueError('비어 있지 않은 body 필요')
        if not fields and 'body' not in change:
            raise ValueError('변경 내용 없음')
        if fields.get('status') in ('active', 'archived'):
            fields['superseded_by'] = None
        if 'description' in fields:
            fields['index_hook'] = fields['description']
        fields['updated'] = today()
        text = edit_note(before.decode('utf-8'), fields, change.get('body'))
        n = by_path[rel]
        _, n.meta, n.body = split_note(text)
        n.text = text
        batch.append((rel, before, text.encode('utf-8')))
        preview.append({'path': rel, 'reason': change['reason'], 'fields': fields,
                        'before_bytes': len(before), 'after_bytes': len(text.encode('utf-8'))})
    validate_lifecycle(notes)
    # Summaries must reflect changed descriptions rather than retain stale index hooks.
    from memory import inside
    index = inside(root, 'MEMORY.md')
    if index.exists():
        import re
        old_index = index.read_bytes()
        index_text = old_index.decode('utf-8')
        for change in changes:
            if 'description' in change:
                desc = ' '.join(str(change['description']).split())
                pattern = r'^(.*\]\(' + re.escape(change['path']) + r'\))[^\n]*$'
                index_text = re.sub(pattern, lambda m: m[1] + ' — ' + desc, index_text, flags=re.M)
        if MARKER in index_text:
            index_text = render_index(notes, index_text)
        if index_text.encode('utf-8') != old_index:
            batch.append(('MEMORY.md', old_index, index_text.encode('utf-8')))
    from transactions import read_optional
    batch.append((STATE, read_optional(inside(root, STATE)), next_state(root, notes)))
    return batch, preview


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('plan', nargs='?')
    ap.add_argument('--apply', action='store_true')
    ap.add_argument('--restore', metavar='BACKUP_RELATIVE_PATH')
    args = ap.parse_args()
    if bool(args.plan) == bool(args.restore):
        ap.error('plan 또는 --restore 하나 필요')
    root = vault()
    with locked(root) if args.apply else nullcontext():
        if args.restore:
            result = restore_batch(root, args.restore, args.apply)
        else:
            batch, preview = prepare(root, json.loads(Path(args.plan).read_text(encoding='utf-8')))
            result = {'mode': 'apply' if args.apply else 'dry-run', 'changes': preview}
            if args.apply:
                result['backup'] = apply_batch(root, batch)
        print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == '__main__':
    cli(main)
