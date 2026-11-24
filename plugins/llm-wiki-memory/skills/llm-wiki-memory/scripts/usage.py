#!/usr/bin/env python3
"""Per-device memory usage, independent of vault write transactions."""
from collections import Counter
from contextlib import contextmanager, nullcontext
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
import base64
import fcntl
import json
import os
from pathlib import Path
import sys
from tempfile import NamedTemporaryFile
from uuid import UUID, uuid4

from memory import atomic_write, inside, resolve_redirect
from registry import state

USAGE_DIR = '.memory-usage'


def device_id():
    base = Path(os.environ.get('XDG_STATE_HOME') or Path.home() / '.local/state')
    path = base / 'llm-wiki-memory/device-id'
    path.parent.mkdir(parents=True, exist_ok=True)
    if not path.exists():
        with NamedTemporaryFile(dir=path.parent) as temporary:
            temporary.write(str(uuid4()).encode('ascii'))
            temporary.flush()
            try:
                os.link(temporary.name, path)
            except FileExistsError:
                pass
    return str(UUID(path.read_text(encoding='ascii').strip(), version=4))


@contextmanager
def device_lock(directory, device):
    # Local advisory lock shared by append and compaction, separate from vault writes.
    with (directory / f'{device}.lock').open('ab') as lock:
        fcntl.flock(lock, fcntl.LOCK_EX)
        yield


def record(root, kind, rel, via):
    try:
        directory = inside(root, USAGE_DIR)
        directory.mkdir(exist_ok=True)
        device = device_id()
        event = {'ts': datetime.now(timezone.utc).isoformat(), 'kind': kind,
                 'rel': rel, 'via': via}
        with device_lock(directory, device):
            finish_compaction(directory, device)
            path = inside(root, f'{USAGE_DIR}/{device}.jsonl')
            with path.open('a', encoding='utf-8') as stream:
                stream.write(json.dumps(event, ensure_ascii=False) + '\n')
    except (OSError, ValueError) as exc:
        print(f'usage recording failed: {exc}', file=sys.stderr)


def record_exposed(root, notes, output, via):
    lines = set(output.splitlines(keepends=True))
    for note in notes:
        if note.summary() in lines:
            record(root, 'exposed', note.rel, via)


@dataclass
class NoteUsage:
    reads_30d: int = 0
    exposed_30d: int = 0
    reads_total: int = 0
    last_read: datetime | None = None
    reads_period: int = 0
    exposed_period: int = 0


@dataclass
class UsageSummary:
    notes: dict[str, NoteUsage] = field(default_factory=dict)
    tracking_since: datetime | None = None
    malformed: int = 0


def timestamp(value):
    time = datetime.fromisoformat(value.replace('Z', '+00:00'))
    if time.tzinfo is None:
        raise ValueError('usage timestamp must include a timezone')
    return time.astimezone(timezone.utc)


def summary(root, now, *, days=30):
    result = UsageSummary()
    redirects = state(root).get('redirects', {})
    recent = now - timedelta(days=30)
    period = now - timedelta(days=days)

    def add(event, count=1):
        time = timestamp(event['ts'])
        kind = event['kind']
        rel = event['rel']
        if kind not in ('read', 'exposed') or not isinstance(rel, str) or not rel:
            raise ValueError('invalid usage event')
        inside(root, rel)
        if result.tracking_since is None or time < result.tracking_since:
            result.tracking_since = time
        if rel.startswith('_archive/') and '.full-' not in Path(rel).stem:
            rel = rel.removeprefix('_archive/')
        rel = resolve_redirect(rel, redirects)
        if rel is None:
            return
        archive_rel = f'_archive/{rel}'
        if not rel.startswith('_archive/') and inside(root, archive_rel).is_file():
            rel = archive_rel
        stats = result.notes.setdefault(rel, NoteUsage())
        if kind == 'read':
            stats.reads_total += count
            if stats.last_read is None or time > stats.last_read:
                stats.last_read = time
            stats.reads_30d += count if recent <= time <= now else 0
            stats.reads_period += count if period <= time <= now else 0
        else:
            stats.exposed_30d += count if recent <= time <= now else 0
            stats.exposed_period += count if period <= time <= now else 0

    directory = inside(root, USAGE_DIR)
    suffixes = ('.jsonl', '.rollup.json', '.pending.json')
    devices = {path.name.removesuffix(suffix) for suffix in suffixes
               for path in directory.glob(f'*{suffix}') if not path.is_symlink()}
    for device in sorted(devices):
        try:
            raw, counts = device_data(directory, device)
        except (ValueError, TypeError, KeyError):
            result.malformed += 1
            continue
        for line in raw.splitlines():
            try:
                add(json.loads(line))
            except (ValueError, TypeError, KeyError, AttributeError):
                result.malformed += 1
        for events in counts.values():
            for ts, kind, rel, count in events:
                try:
                    add({'ts': ts, 'kind': kind, 'rel': rel}, count)
                except (ValueError, TypeError, KeyError, AttributeError):
                    result.malformed += 1
    return result


def optional_read(path):
    try:
        if not path.is_symlink():
            return path.read_bytes()
    except FileNotFoundError:
        pass
    return b''


def device_data(directory, device):
    # A reader doesn't create lock files. A pending journal represents both outputs.
    lock_path = directory / f'{device}.lock'
    try:
        lock = lock_path.open('rb') if not lock_path.is_symlink() else nullcontext()
    except FileNotFoundError:
        lock = nullcontext()
    with lock as handle:
        if handle is not None:
            fcntl.flock(handle, fcntl.LOCK_SH)
        pending = optional_read(directory / f'{device}.pending.json')
        if pending:
            data = json.loads(pending)
            return base64.b64decode(data['remaining']), data['months']
        raw = optional_read(directory / f'{device}.jsonl')
        counts = json.loads(optional_read(directory / f'{device}.rollup.json') or b'{}')
        return raw, counts


def finish_compaction(directory, device):
    pending = directory / f'{device}.pending.json'
    if not pending.exists():
        return
    data = json.loads(pending.read_bytes())
    atomic_write(directory / f'{device}.rollup.json', json.dumps(data['months']).encode())
    atomic_write(directory / f'{device}.jsonl', base64.b64decode(data['remaining']))
    pending.unlink()


def compact(root, now):
    directory = inside(root, USAGE_DIR)
    if not directory.is_dir():
        return
    device = device_id()
    with device_lock(directory, device):
        finish_compaction(directory, device)
        raw = optional_read(directory / f'{device}.jsonl')
        if not raw:
            return
        old_rollup = optional_read(directory / f'{device}.rollup.json')
        counts = Counter({(ts, kind, rel): n for events in json.loads(old_rollup or b'{}').values()
                          for ts, kind, rel, n in events})
        remaining = []
        moved = False
        cutoff = now - timedelta(days=90)
        for line in raw.splitlines(keepends=True):
            try:
                event = json.loads(line)
                time = timestamp(event['ts'])
                kind, rel = event['kind'], event['rel']
                if time < cutoff and kind in ('read', 'exposed') and isinstance(rel, str) and rel:
                    counts[time.isoformat(), kind, rel] += 1
                    moved = True
                    continue
            except (ValueError, TypeError, KeyError, AttributeError):
                pass
            remaining.append(line)
        if not moved:
            return
        months = {}
        for (ts, kind, rel), count in sorted(counts.items()):
            months.setdefault(ts[:7], []).append((ts, kind, rel, count))
        pending = {'remaining': base64.b64encode(b''.join(remaining)).decode(), 'months': months}
        atomic_write(directory / f'{device}.pending.json', json.dumps(pending).encode())
        finish_compaction(directory, device)


def main():
    import argparse
    from consolidate import purge_schedule, retirement_candidates
    from memory import load_archives, load_notes, positive, vault

    parser = argparse.ArgumentParser(description='Report memory usage without writing to the vault.')
    parser.add_argument('--report', action='store_true', required=True)
    parser.add_argument('--days', type=positive, default=30)
    args = parser.parse_args()
    root = vault()
    now = datetime.now(timezone.utc)
    usage = summary(root, now, days=args.days)
    notes = load_notes(root)
    current = {n.rel: usage.notes.get(n.rel, NoteUsage()) for n in notes if n.status == 'active'}
    reads = sorted(current, key=lambda rel: (-current[rel].reads_period, rel))
    exposures = sorted(current, key=lambda rel: (-current[rel].exposed_period, rel))
    schedule = purge_schedule(load_archives(root), usage)
    report = {
        'days': args.days,
        'tracking_since': usage.tracking_since.isoformat() if usage.tracking_since else None,
        'malformed': usage.malformed,
        'most_read': [{'rel': rel, 'reads': current[rel].reads_period}
                      for rel in reads if current[rel].reads_period],
        'exposed_unread': [{'rel': rel, 'exposed': current[rel].exposed_period}
                           for rel in exposures if current[rel].exposed_period and not current[rel].reads_period],
        'never_read': sorted(rel for rel, stats in current.items()
                             if usage.tracking_since is not None and not stats.reads_total),
        'retirement_candidates': retirement_candidates(notes, usage, state(root).get('retention_kept', {}), now),
        'archive_purge_schedule': {rel: deadline.isoformat() for rel, deadline in sorted(schedule.items())},
    }
    print(json.dumps(report, ensure_ascii=False, indent=2))


if __name__ == '__main__':
    from memory import cli
    cli(main)
