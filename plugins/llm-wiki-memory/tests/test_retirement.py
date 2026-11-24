from datetime import datetime, timezone
import json
import unittest

import test_consolidation as fixtures


class Retirement(unittest.TestCase):
    setUp = fixtures.Consolidation.setUp
    run_cli = fixtures.Consolidation.run_cli
    note = fixtures.Consolidation.note
    scan = fixtures.Consolidation.scan
    consolidation_plan = fixtures.Consolidation.consolidation_plan

    def test_archive_and_unarchive_preserve_original(self):
        original = self.note()
        actions = [{'op': 'archive', 'path': 'feedback/rule.md', 'reason': 'obsolete'}]
        plan = self.consolidation_plan(actions)
        preview = json.loads(self.run_cli('consolidate.py', '--plan', plan).stdout)
        self.assertEqual(preview['mode'], 'dry-run')
        self.assertTrue(original.exists())
        result = json.loads(self.run_cli('consolidate.py', '--plan', plan, '--apply').stdout)
        archive = self.vault / '_archive/feedback/rule.md'
        self.assertFalse(original.exists())
        self.assertIn('archived_from: "feedback/rule.md"', archive.read_text())
        self.run_cli('maintain.py', '--restore', result['backup'])
        self.run_cli('maintain.py', '--unarchive', '_archive/feedback/rule.md', '--apply')
        self.assertIn('고유한 상세 본문', original.read_text())
        self.assertNotIn('archived_from', original.read_text())
        self.assertFalse(archive.exists())

    def test_compress_preserves_full_text_and_purges_old_copy(self):
        original = self.note()
        actions = [{'op': 'compress', 'path': 'feedback/rule.md', 'reason': 'long',
                    'body': 'summary', 'description': 'shorter'}]
        self.run_cli('consolidate.py', '--plan', self.consolidation_plan(actions), '--apply')
        archive, = (self.vault / '_archive/feedback').glob('*.full-*.md')
        self.assertIn('고유한 상세 본문', archive.read_text())
        self.assertIn('summary', original.read_text())
        rel = archive.relative_to(self.vault).as_posix()
        self.run_cli('maintain.py', '--unarchive', rel, '--apply', ok=False)
        import re
        archive.write_text(re.sub(r'archived_at: .*', 'archived_at: "2020-01-01"', archive.read_text()))
        actions = [{'op': 'keep', 'path': 'feedback/rule.md', 'reason': 'current'}]
        plan = self.consolidation_plan(actions)
        preview = json.loads(self.run_cli('consolidate.py', '--plan', plan).stdout)
        self.assertEqual(preview['purge'], [rel])
        self.assertTrue(archive.exists())
        self.run_cli('consolidate.py', '--plan', plan, '--apply')
        self.assertFalse(archive.exists())
        self.assertNotIn('full_text:', original.read_text())

    def test_retirement_requires_tracking_and_respects_boundaries(self):
        from consolidate import retirement_candidates
        from memory import load_notes
        from usage import NoteUsage, UsageSummary

        self.note('feedback/old.md')
        self.note('feedback/pinned.md', extra='pinned: true\n')
        self.note('feedback/exact.md')
        self.note('feedback/kept.md')
        today = datetime(2026, 11, 24, tzinfo=timezone.utc)
        tracked = datetime(2026, 9, 1, tzinfo=timezone.utc)
        exact = datetime(2026, 10, 25, tzinfo=timezone.utc)
        notes = load_notes(self.vault)
        self.assertEqual(retirement_candidates(notes, UsageSummary(), {}, today), {})
        usage = UsageSummary({'feedback/exact.md': NoteUsage(last_read=exact)}, tracked)
        candidates = retirement_candidates(notes, usage, {'feedback/kept.md': '2026-11-23'}, today)
        self.assertEqual(set(candidates), {'feedback/old.md'})

    def test_report_is_read_only_and_honors_days(self):
        self.note('feedback/read.md')
        self.note('feedback/exposed.md')
        log = self.vault / '.memory-usage' / 'unit.jsonl'
        log.parent.mkdir()
        now = datetime.now(timezone.utc)
        events = [{'ts': now.isoformat(), 'kind': kind, 'rel': f'feedback/{name}.md', 'via': 'recall'}
                  for kind, name in [('read', 'read'), ('exposed', 'exposed')]]
        log.write_text(''.join(json.dumps(e) + '\n' for e in events))
        before = {p: p.read_bytes() for p in self.vault.rglob('*') if p.is_file()}
        report = json.loads(self.run_cli('usage.py', '--report', '--days', '7').stdout)
        self.assertEqual(report['days'], 7)
        self.assertEqual(report['most_read'][0]['rel'], 'feedback/read.md')
        self.assertEqual(report['exposed_unread'][0]['rel'], 'feedback/exposed.md')
        self.assertEqual(report['never_read'], ['feedback/exposed.md'])
        self.assertEqual(before, {p: p.read_bytes() for p in self.vault.rglob('*') if p.is_file()})

    def test_core_index_prefers_pins_recent_reads_and_fallback(self):
        from datetime import timedelta
        from memory import load_notes
        from registry import render_index
        from usage import NoteUsage

        self.note('feedback/pin.md', extra='pinned: true\n')
        self.note('feedback/older.md')
        self.note('feedback/newer.md')
        self.note('feedback/z-most.md')
        self.note('feedback/filler.md')
        self.note('projects/demo/feedback/project.md')
        self.note('feedback/inactive.md', extra='status: archived\n')
        user = self.note('user/fallback.md')
        user.write_text(user.read_text().replace('type: feedback', 'type: user'))
        now = datetime.now(timezone.utc)
        usage = {'feedback/older.md': NoteUsage(reads_30d=1, last_read=now - timedelta(days=1)),
                 'feedback/newer.md': NoteUsage(reads_30d=1, last_read=now),
                 'feedback/z-most.md': NoteUsage(reads_30d=2, last_read=now)}
        index = render_index(load_notes(self.vault), usage=usage)
        core = index.split('## 주제별 탐색', 1)[0]
        expected = ['pin.md', 'z-most.md', 'newer.md', 'older.md', 'fallback.md', 'filler.md']
        self.assertEqual(sorted(expected, key=core.index), expected)
        self.assertNotIn('project.md', core)
        self.assertNotIn('inactive.md', core)

    def test_archive_rejects_incoming_link_and_pinned_note(self):
        self.note('feedback/target.md')
        self.note('feedback/source.md', body='See [[target]].')
        self.note('feedback/pinned.md', extra='pinned: true\n')
        for target, code in [('target', 'incoming'), ('pinned', 'pinned')]:
            actions = [{'op': 'archive' if name == target else 'keep',
                        'path': f'feedback/{name}.md', 'reason': 'reviewed'}
                       for name in ('target', 'source', 'pinned')]
            before = {p: p.read_bytes() for p in self.vault.rglob('*') if p.is_file()}
            result = self.run_cli('consolidate.py', '--plan', self.consolidation_plan(actions),
                                  '--apply', ok=False)
            self.assertIn(code, result.stderr)
            self.assertEqual(before, {p: p.read_bytes() for p in self.vault.rglob('*') if p.is_file()})
