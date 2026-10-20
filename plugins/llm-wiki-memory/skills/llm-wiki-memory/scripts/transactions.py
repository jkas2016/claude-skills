"""Recoverable multi-file writes. Local lock; hashes detect, but cannot lock, iCloud peers."""
import json
import uuid
from memory import atomic_write, digest, inside


def read_optional(path):
    return path.read_bytes() if path.exists() else None


def apply_batch(root, changes):
    # Caller holds the local vault lock. None means a new file.
    for rel, before, after in changes:
        if read_optional(inside(root, rel)) != before:
            raise ValueError(f'동시 변경: {rel}')
    entries = [{'path': rel,
                'before': before.decode('utf-8') if before is not None else None,
                'after': after.decode('utf-8'), 'after_sha256': digest(after)}
               for rel, before, after in changes]
    backup = '.memory-backups/' + uuid.uuid4().hex + '.json'
    atomic_write(inside(root, backup), json.dumps({'version': 1, 'entries': entries},
                 ensure_ascii=False, indent=2).encode('utf-8'))
    written = []
    try:
        for rel, before, after in changes:
            path = inside(root, rel)
            if read_optional(path) != before:
                raise ValueError(f'동시 변경: {rel}')
            atomic_write(path, after)
            written.append((path, before, after))
    except BaseException:
        for path, before, after in reversed(written):
            if read_optional(path) == after:
                if before is None:
                    path.unlink()
                else:
                    atomic_write(path, before)
        raise
    return backup


def restore_batch(root, backup, apply=False):
    if not backup.startswith('.memory-backups/') or not backup.endswith('.json'):
        raise ValueError('vault 내 .memory-backups/*.json 경로 필요')
    manifest = json.loads(inside(root, backup).read_text(encoding='utf-8'))
    entries = manifest['entries']
    validated = []
    seen = set()
    for entry in entries:
        rel = entry['path']
        if rel in seen or (rel != 'MEMORY.md' and rel.split('/')[0] not in
                           ('user', 'feedback', 'project', 'reference', 'projects')):
            raise ValueError(f'잘못된 백업 경로: {rel}')
        seen.add(rel)
        path = inside(root, rel)
        after = entry['after'].encode('utf-8')
        before = entry['before'].encode('utf-8') if entry['before'] is not None else None
        if digest(after) != entry['after_sha256']:
            raise ValueError('백업 무결성 오류')
        current = read_optional(path)
        # Accept before too: a killed process may have applied only part of the batch.
        if current not in (before, after):
            raise ValueError(f'복구 충돌: {rel}')
        validated.append((path, before, current))
    if apply:
        for path, before, expected in validated:
            if read_optional(path) != expected:
                raise ValueError(f'복구 중 동시 변경: {path.name}')
            if before is None:
                if path.exists():
                    path.unlink()
            else:
                atomic_write(path, before)
    return {'mode': 'restored' if apply else 'restore-dry-run', 'files': len(entries), 'backup': backup}
