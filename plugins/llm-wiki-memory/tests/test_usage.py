import json
from pathlib import Path
import unittest

import test_memory as fixtures


class Usage(unittest.TestCase):
    setUp = fixtures.MemoryCLI.setUp
    run_cli = fixtures.MemoryCLI.run_cli
    note = fixtures.MemoryCLI.note

    def events(self):
        return [json.loads(line) for path in (self.vault / '.memory-usage').glob('*.jsonl')
                for line in path.read_text().splitlines()]

    def test_read_logs_canonical_path_and_index_does_not_log(self):
        self.note()
        (self.vault / '.memory-state.json').write_text(json.dumps({
            'redirects': {'feedback/old.md': 'feedback/rule.md'},
        }))
        self.run_cli('recall.py', '--index')
        self.assertEqual(self.events(), [])
        output = self.run_cli('recall.py', '--read', 'feedback/old.md')
        self.assertIn('고유한 상세 본문', output.stdout)
        event, = self.events()
        self.assertEqual((event['kind'], event['rel'], event['via']),
                         ('read', 'feedback/rule.md', 'recall'))

    def test_lint_checks_the_usage_ranked_index_written_by_save(self):
        self.note('feedback/a.md')
        self.note('feedback/z.md')
        self.run_cli('recall.py', '--read', 'feedback/z.md')
        self.run_cli('save.py', '--project', 'serverb4', '--type', 'feedback',
                     '--name', 'fixture', '--desc', 'local fixture baseline',
                     '--hook', 'Check local fixture IDs', body='fixture baseline')

        index = self.vault / 'MEMORY.md'
        text = index.read_text()
        self.assertLess(text.index('(feedback/z.md)'), text.index('(feedback/a.md)'))
        self.run_cli('lint.py')
        self.assertEqual(index.read_text(), text)

        index.write_text(text.replace('(feedback/z.md) — git 규칙',
                                      '(feedback/z.md) — outdated summary'))
        result = self.run_cli('lint.py', ok=False)
        self.assertIn('MEMORY.md: generated index is stale', result.stderr)

    def test_usage_failure_preserves_read(self):
        self.note()
        bad = Path(self.tmp.name) / 'bad-state'
        bad.touch()
        self.env['XDG_STATE_HOME'] = str(bad)
        result = self.run_cli('recall.py', '--read', 'feedback/rule.md')
        self.assertIn('고유한 상세 본문', result.stdout)
        self.assertIn('usage', result.stderr)
        self.assertEqual(self.events(), [])

    def test_only_emitted_rows_are_counted(self):
        self.note('feedback/a.md', desc='a' * 150, extra='pinned: true\n')
        self.note('feedback/b.md', desc='b' * 150, extra='pinned: true\n')
        for script, via in [('recall.py', 'recall'), ('context.py', 'context')]:
            full = self.run_cli(script).stdout
            limit = len(full[:full.index('- [feedback/b.md]')].encode()) + 80
            result = self.run_cli(script, '--max-bytes', str(limit))
            self.assertIn('[feedback/a.md]', result.stdout)
            self.assertNotIn('[feedback/b.md]', result.stdout)
            self.assertEqual([event['rel'] for event in self.events() if event['via'] == via],
                             ['feedback/a.md', 'feedback/b.md', 'feedback/a.md'])

    def test_summary_combines_devices_and_redirects(self):
        from datetime import datetime, timezone
        from usage import summary

        self.note('feedback/rule.md')
        (self.vault / '.memory-state.json').write_text(json.dumps({
            'redirects': {'feedback/old.md': 'feedback/rule.md'},
        }))
        usage = self.vault / '.memory-usage'
        usage.mkdir()
        for device, dates in [('a', ['2026-10-25T00:00:00+00:00', '2026-10-24T00:00:00+00:00']),
                              ('b', ['2026-11-23T23:00:00+09:00'])]:
            rows = [json.dumps({'ts': ts, 'kind': 'read', 'rel': 'feedback/old.md',
                                'via': 'recall'}) for ts in dates]
            (usage / f'{device}.jsonl').write_text('\n'.join(rows + ['bad', '']))
        now = datetime(2026, 11, 24, tzinfo=timezone.utc)
        result = summary(self.vault, now)
        stats = result.notes['feedback/rule.md']
        self.assertEqual((stats.reads_30d, stats.reads_total, stats.exposed_30d), (2, 3, 0))
        self.assertEqual(stats.last_read.isoformat(), '2026-11-23T14:00:00+00:00')
        self.assertEqual(result.tracking_since.isoformat(), '2026-10-24T00:00:00+00:00')
        self.assertEqual(result.malformed, 2)

    def test_compaction_preserves_totals_and_other_devices(self):
        from datetime import datetime, timezone
        from unittest.mock import patch
        from usage import compact, device_id, summary

        now = datetime(2026, 11, 24, tzinfo=timezone.utc)
        with patch.dict('os.environ', self.env):
            device = device_id()
            directory = self.vault / '.memory-usage'
            directory.mkdir()
            old = json.dumps({'ts': '2026-07-01T00:00:00Z', 'kind': 'read',
                              'rel': 'feedback/old.md', 'via': 'recall'}) + '\n'
            recent = old.replace('2026-07-01', '2026-11-20')
            path = directory / f'{device}.jsonl'
            other = directory / 'other.jsonl'
            path.write_text(old + recent)
            other.write_text(old)
            before = summary(self.vault, now, days=365)
            compact(self.vault, now)
            compact(self.vault, now)
            self.assertEqual(path.read_text(), recent)
            self.assertEqual(other.read_text(), old)
            self.assertEqual(summary(self.vault, now, days=365), before)

    def test_interrupted_compaction_is_counted_once_and_recovered_before_append(self):
        from datetime import datetime, timezone
        from unittest.mock import patch
        import usage

        now = datetime(2026, 11, 24, tzinfo=timezone.utc)
        with patch.dict('os.environ', self.env):
            device = usage.device_id()
            directory = self.vault / '.memory-usage'
            directory.mkdir()
            log = directory / f'{device}.jsonl'
            log.write_text(json.dumps({'ts': '2026-07-01T00:00:00Z', 'kind': 'read',
                                       'rel': 'feedback/rule.md', 'via': 'recall'}) + '\n')
            expected = usage.summary(self.vault, now)
            original_write = usage.atomic_write

            def fail_at_log(path, data):
                if path == log:
                    raise OSError('interrupted')
                return original_write(path, data)

            with patch.object(usage, 'atomic_write', side_effect=fail_at_log):
                with self.assertRaisesRegex(OSError, 'interrupted'):
                    usage.compact(self.vault, now)
            self.assertEqual(usage.summary(self.vault, now), expected)
            usage.record(self.vault, 'read', 'feedback/rule.md', 'recall')
            self.assertEqual(usage.summary(self.vault, now).notes['feedback/rule.md'].reads_total, 2)
            self.assertFalse((directory / f'{device}.pending.json').exists())
