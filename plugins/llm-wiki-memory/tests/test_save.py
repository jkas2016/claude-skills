import json
import subprocess
import sys
import unittest

import test_memory as fixtures


class Save(unittest.TestCase):
    setUp = fixtures.MemoryCLI.setUp
    run_cli = fixtures.MemoryCLI.run_cli
    note = fixtures.MemoryCLI.note

    def save(self, name, *args, **kwargs):
        return self.run_cli('save.py', '--type', 'feedback', '--name', name,
                            '--desc', 'output format', '--hook', 'output rules', *args, **kwargs)

    def test_key_wins_over_name_and_check_leaves_stdin_unread(self):
        canonical = self.note('feedback/canonical.md', extra='memory_key: canonical\n')
        other = self.note('feedback/other.md', extra='memory_key: other\n')
        original = {p: p.read_bytes() for p in (canonical, other)}
        command = [sys.executable, str(fixtures.SCRIPTS / 'save.py'), '--type', 'feedback',
                   '--name', 'other', '--key', 'canonical', '--desc', 'output format',
                   '--hook', 'output rules', '--check']
        with subprocess.Popen(command, stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                              stderr=subprocess.PIPE, env=self.env) as process:
            try:
                self.assertEqual(process.wait(timeout=5), 0)
                preview = process.stdout.read().decode()
            finally:
                if process.poll() is None:
                    process.kill()
        self.assertIn('target=feedback/canonical.md via=key', preview)
        self.assertEqual(original, {p: p.read_bytes() for p in original})
        result = self.save('other', '--key', 'canonical', body='replacement')
        self.assertIn('target=feedback/canonical.md via=key', result.stdout)
        self.assertIn('replacement', canonical.read_text())
        self.assertEqual(other.read_bytes(), original[other])

    def test_name_key_conflict_leaves_note_unchanged(self):
        path = self.note(extra='memory_key: original\n')
        before = path.read_bytes()
        for key in ((), ('--key', 'different')):
            for mode in (('--check',), ()):
                with self.subTest(key=key, mode=mode):
                    result = self.save('rule', *key, *mode, body='replacement', ok=False)
                    self.assertIn('KEY_NAME_CONFLICT', result.stderr)
        self.assertEqual(path.read_bytes(), before)

    def test_redirect_updates_terminal_target(self):
        canonical = self.note('feedback/canonical.md')
        state = self.vault / '.memory-state.json'
        state.write_text(json.dumps({'redirects': {'feedback/old.md': 'feedback/middle.md',
                                                   'feedback/middle.md': 'feedback/canonical.md'}}))
        self.assertIn('target=feedback/canonical.md via=redirect', self.save('old', '--check').stdout)
        self.save('old', body='replacement')
        self.assertIn('replacement', canonical.read_text())
        self.assertFalse((self.vault / 'feedback/old.md').exists())

    def test_dropped_or_archived_name_refuses_creation(self):
        state = self.vault / '.memory-state.json'
        state.write_text(json.dumps({'redirects': {'feedback/dropped.md': None}}))
        archive = self.note('_archive/feedback/archived.md', extra='status: archived\n')
        before = archive.read_bytes()
        for name, code in [('dropped', 'DROPPED_NOTE'), ('archived', 'ARCHIVED_EXISTS')]:
            for mode in (('--check',), ()):
                with self.subTest(name=name, mode=mode):
                    result = self.save(name, *mode, body='replacement', ok=False)
                    self.assertIn(code, result.stderr)
                    if name == 'archived':
                        self.assertIn('--unarchive _archive/feedback/archived.md', result.stderr)
            self.assertFalse((self.vault / f'feedback/{name}.md').exists())
        self.assertEqual(archive.read_bytes(), before)

    def test_cross_type_candidate_blocks_both_modes_and_records_override(self):
        candidate = self.note('user/answer_format.md', desc='답변 형식 선호')
        candidate.write_text(candidate.read_text().replace('type: feedback', 'type: user'))
        options = ('--desc', '답변 형식 선호', '--hook', 'h')
        for reason in ((), ('--distinct-reason', '  ')):
            check = self.save('answer_format', *options, *reason, '--check', ok=False)
            save = self.save('answer_format', *options, *reason, body='new rule', ok=False)
            self.assertEqual((check.stdout, check.stderr), (save.stdout, save.stderr))
            self.assertIn('block user/answer_format.md score=1.000', check.stdout)
            self.assertIn('RELATED_MEMORY_EXISTS', check.stderr)
        target = self.vault / 'feedback/answer_format.md'
        self.assertFalse(target.exists())
        reason = ('--distinct-reason', '  적용 대상이 다르다  ')
        check = self.save('answer_format', *options, *reason, '--check')
        self.assertFalse(target.exists())
        save = self.save('answer_format', *options, *reason, body='separate rule')
        self.assertTrue(save.stdout.startswith(check.stdout))
        from memory import split_note
        _, metadata, _ = split_note(target.read_text())
        self.assertEqual(metadata['distinct_from'], ['user/answer_format.md'])
        self.assertEqual(metadata['distinct_reason'], '적용 대상이 다르다')

    def test_korean_inflection_warns_but_s1_common_word_does_not_block(self):
        self.note('feedback/answer_format.md', desc='응답 형식은 요청을 따른다')
        self.note('feedback/git_merge.md', desc='git merge over rebase',
                  body='Use merge to resolve conflicts once.')
        options = ('--desc', '응답의 형식을 지킨다', '--hook', 'h')
        check = self.save('reply_shape', *options, '--check')
        save = self.save('reply_shape', *options, body='new rule')
        self.assertIn('warn feedback/answer_format.md score=0.125', check.stdout)
        self.assertTrue(save.stdout.startswith(check.stdout))
        self.save('stock_terms', '--desc', 'explain finance terms to the user',
                  '--hook', 'h', body='unrelated note')
