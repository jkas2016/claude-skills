import hashlib
import json
from pathlib import Path
import subprocess
import sys
import unittest

import test_memory as fixtures


class Consolidation(unittest.TestCase):
    setUp = fixtures.MemoryCLI.setUp
    run_cli = fixtures.MemoryCLI.run_cli
    note = fixtures.MemoryCLI.note
    def scan(self):
        return json.loads(self.run_cli('consolidate.py').stdout)

    def consolidation_plan(self, actions, snapshot=None):
        p = Path(self.tmp.name) / 'consolidation.json'
        p.write_text(json.dumps({'snapshot': snapshot or self.scan()['snapshot'], 'actions': actions}))
        return str(p)

    def test_keyed_saves_update_one_canonical_file(self):
        for name in ['first', 'second', 'third']:
            self.run_cli('save.py', '--type', 'feedback', '--name', name, '--key', 'answer-format',
                         '--desc', 'format', '--hook', 'Remember output format', body=name)
        files = list((self.vault / 'feedback').glob('*.md'))
        self.assertEqual(len(files), 1)
        self.assertEqual(files[0].stem, 'first')
        self.assertIn('third', files[0].read_text())
        self.assertIn('Remember output format', (self.vault / 'MEMORY.md').read_text())
        self.run_cli('lint.py')

    def test_merge_physically_removes_sources_and_rewrites_links(self):
        a = self.note('feedback/a.md', body='rule A')
        b = self.note('feedback/b.md', body='rule B')
        c = self.note('reference/c.md', body='See [old](../feedback/b.md) and [[b]].')
        before = {str(p.relative_to(self.vault)):p.read_bytes() for p in [a,b,c,self.vault/'MEMORY.md']}
        plan = self.consolidation_plan([
            {'op':'merge','target':'feedback/a.md','sources':['feedback/b.md'],
             'body':'rule A and rule B with both exceptions','description':'combined rule',
             'reason':'same concept; both exceptions retained'},
            {'op':'keep','path':'reference/c.md','reason':'still useful'}])
        self.run_cli('consolidate.py','--plan',plan)
        self.assertTrue(b.exists())
        result=json.loads(self.run_cli('consolidate.py','--plan',plan,'--apply').stdout)
        self.assertFalse(b.exists())
        self.assertNotIn('feedback/b.md',(self.vault/'MEMORY.md').read_text())
        self.assertIn('../feedback/a.md',c.read_text())
        self.assertNotIn('[[b]]',c.read_text())
        self.run_cli('lint.py')
        self.run_cli('maintain.py','--restore',result['backup'],'--apply')
        for rel,data in before.items():self.assertEqual((self.vault/rel).read_bytes(),data)

    def test_merge_encodes_markdown_destination(self):
        self.note('feedback/a b.md')
        self.note('feedback/source.md')
        link=self.note('reference/link.md',body='[source](../feedback/source.md)')
        plan=self.consolidation_plan([
            {'op':'merge','target':'feedback/a b.md','sources':['feedback/source.md'],
             'body':'combined','description':'combined','reason':'same concept'},
            {'op':'keep','path':'reference/link.md','reason':'useful'}])
        self.run_cli('consolidate.py','--plan',plan,'--apply')
        self.assertIn('../feedback/a%20b.md',link.read_text())
        self.assertIn('feedback/a%20b.md', (self.vault/'MEMORY.md').read_text())
        self.run_cli('lint.py')

    def test_drop_removes_index_and_note_but_refuses_incoming_links(self):
        a=self.note()
        b=self.note('reference/link.md',body='[rule](../feedback/rule.md)')
        actions=[{'op':'drop','path':'feedback/rule.md','reason':'obsolete','evidence':'verified replaced upstream'},
                 {'op':'keep','path':'reference/link.md','reason':'useful'}]
        plan=self.consolidation_plan(actions)
        self.run_cli('consolidate.py','--plan',plan,'--apply',ok=False)
        self.assertTrue(a.exists())
        actions[1]={'op':'update','path':'reference/link.md','body':'replacement location',
                    'description':'current reference','reason':'remove obsolete dependency'}
        plan=self.consolidation_plan(actions)
        self.run_cli('consolidate.py','--plan',plan,'--apply')
        self.assertFalse(a.exists())
        self.assertNotIn('feedback/rule.md',(self.vault/'MEMORY.md').read_text())

    def test_stale_and_incomplete_snapshot_cannot_apply(self):
        a=self.note();self.note('feedback/b.md')
        plan=self.consolidation_plan([{'op':'keep','path':'feedback/rule.md','reason':'valid'}])
        self.run_cli('consolidate.py','--plan',plan,'--apply',ok=False)
        actions=[{'op':'keep','path':rel,'reason':'valid'} for rel in self.scan()['notes']]
        plan=self.consolidation_plan(actions)
        a.write_text(a.read_text()+'new evidence')
        self.run_cli('consolidate.py','--plan',plan,'--apply',ok=False)
        self.assertFalse((self.vault/'.memory-state.json').exists())

    def test_due_state_blocks_growth_and_full_review_clears_it(self):
        for i in range(10):
            self.run_cli('save.py','--type','feedback','--name','rule','--key','rule',
                         '--desc','rule','--hook','rule',body=f'version {i}')
        scan=self.scan();self.assertTrue(scan['maintenance']['due'])
        self.run_cli('save.py','--type','reference','--name','unrelated','--key','unrelated',
                     '--desc','other','--hook','other',body='other',ok=False)
        plan=self.consolidation_plan([{'op':'keep','path':'feedback/rule.md','reason':'latest version correct'}])
        self.run_cli('consolidate.py','--plan',plan,'--apply')
        self.assertFalse(self.scan()['maintenance']['due'])
        self.run_cli('save.py','--type','reference','--name','unrelated','--key','unrelated',
                     '--desc','other','--hook','other',body='other')

    def test_related_new_note_requires_explicit_distinction(self):
        self.note()
        self.run_cli('save.py','--type','feedback','--name','another','--desc','git 규칙',
                     '--hook','git','--tags','git',body='another',ok=False)
        self.run_cli('save.py','--type','feedback','--name','another','--desc','git 규칙',
                     '--hook','git','--tags','git','--distinct-reason','applies to a different operation',body='another')

    def test_rebuild_index_is_compact_and_keeps_html_pointer(self):
        for i in range(80):self.note(f'projects/demo/feedback/rule{i}.md',desc='long rule '+str(i))
        (self.vault/'reference').mkdir(exist_ok=True)
        (self.vault/'reference/doc.html').write_text('document')
        with (self.vault/'MEMORY.md').open('a') as f:f.write('- [report](reference/doc.html) — report\n')
        before=(self.vault/'MEMORY.md').stat().st_size
        actions=[{'op':'keep','path':rel,'reason':'reviewed valid'} for rel in self.scan()['notes']]
        plan=self.consolidation_plan(actions)
        self.run_cli('consolidate.py','--plan',plan,'--apply')
        text=(self.vault/'MEMORY.md').read_text()
        self.assertLess(len(text.encode()),before)
        self.assertLessEqual(len(text.encode()),8192)
        self.assertIn('projects/demo/',text)
        self.assertIn('reference/doc.html',text)
        self.run_cli('lint.py')

    def test_committed_backup_retention_is_bounded(self):
        for i in range(24):
            self.run_cli('save.py','--type','feedback','--name','rule','--key','rule',
                         '--desc','rule','--hook','rule',body=f'version {i}')
        self.assertLessEqual(len(list((self.vault/'.memory-backups').glob('*.json'))),20)

    def test_merge_updates_alias_links_and_future_saves_use_original_keys(self):
        self.note('feedback/a.md',body='A',extra='memory_key: first\n')
        b=self.note('feedback/b.md',body='B',extra='memory_key: second\n')
        b.write_text(b.read_text().replace('aliases: [규칙]','aliases: ["Old title"]'))
        c=self.note('reference/c.md',body='[[Old title|display]] and [old](<../feedback/b.md> "title") '
                    '[old](../feedback/b.md "title") <a href="../feedback/b.md">old</a>')
        plan=self.consolidation_plan([
            {'op':'merge','target':'feedback/a.md','sources':['feedback/b.md'],
             'body':'A and B','description':'combined','reason':'same topic'},
            {'op':'keep','path':'reference/c.md','reason':'valid'}])
        self.run_cli('consolidate.py','--plan',plan,'--apply')
        self.assertNotIn('Old title',c.read_text())
        self.assertNotIn('feedback/b.md',c.read_text())
        self.run_cli('save.py','--type','feedback','--name','b','--key','second',
                     '--desc','combined','--hook','combined',body='A and B updated')
        self.assertFalse(b.exists())
        self.assertIn('updated',(self.vault/'feedback/a.md').read_text())

    def test_legacy_maintain_keeps_generated_index_valid(self):
        self.run_cli('save.py','--type','feedback','--name','rule','--desc','old','--hook','old',body='rule')
        a=self.vault/'feedback/rule.md'
        p=Path(self.tmp.name)/'edit.json'
        p.write_text(json.dumps({'changes':[{'path':'feedback/rule.md','sha256':hashlib.sha256(a.read_bytes()).hexdigest(),
                         'description':'new description','reason':'update'}]}))
        self.run_cli('maintain.py',str(p),'--apply')
        self.assertIn('index_hook: "new description"', a.read_text())
        self.assertIn('— new description', (self.vault/'MEMORY.md').read_text())
        self.assertNotIn('— old', (self.vault/'MEMORY.md').read_text())
        self.run_cli('lint.py')

    def test_keep_preserves_crlf_bytes(self):
        a=self.note()
        a.write_bytes(a.read_bytes().replace(b'\\n',b'\\r\\n'))
        before=a.read_bytes()
        p=self.consolidation_plan([{'op':'keep','path':'feedback/rule.md','reason':'valid'}])
        self.run_cli('consolidate.py','--plan',p,'--apply')
        self.assertEqual(a.read_bytes(),before)

    def test_external_nested_readme_prevents_deletion(self):
        self.note('feedback/a.md',body='A')
        b=self.note('feedback/b.md',body='B')
        (self.vault/'feedback/README.md').write_text('[source](b.md)')
        p=self.consolidation_plan([{'op':'merge','target':'feedback/a.md','sources':['feedback/b.md'],
                                   'description':'combined','body':'A and B','reason':'merge'}])
        self.run_cli('consolidate.py','--plan',p,'--apply',ok=False)
        self.assertTrue(b.exists())

    def test_root_html_prevents_merge_and_drop(self):
        self.note('feedback/a.md', body='A')
        b = self.note('feedback/b.md', body='B')
        report = self.vault / 'report.html'
        report.write_text('<a href="feedback/b.md">source</a>')
        before = {p: p.read_bytes() for p in [b, report, self.vault/'MEMORY.md']}
        for action in [
            {'op':'merge','target':'feedback/a.md','sources':['feedback/b.md'],
             'description':'combined','body':'A and B','reason':'merge'},
            {'op':'drop','path':'feedback/b.md','reason':'obsolete','evidence':'reviewed'},
        ]:
            with self.subTest(op=action['op']):
                for path, data in before.items():
                    path.write_bytes(data)
                actions = [action]
                if action['op'] == 'drop':
                    actions.append({'op':'keep','path':'feedback/a.md','reason':'valid'})
                plan = self.consolidation_plan(actions)
                result = self.run_cli('consolidate.py','--plan',plan,'--apply',ok=False)
                self.assertIn('report.html:', result.stderr)
                self.assertIn('incoming link', result.stderr)
                for path, data in before.items():
                    self.assertEqual(path.read_bytes(), data)

    def test_drop_refuses_html_title_and_wiki_filename_references(self):
        for form in ['[source](../feedback/b.md "title")','<a href="../feedback/b.md">source</a>','[[b.md]]']:
            with self.subTest(form=form):
                self.note('feedback/b.md',body='B')
                self.note('reference/c.md',body=form)
                p=self.consolidation_plan([
                    {'op':'drop','path':'feedback/b.md','reason':'obsolete','evidence':'reviewed'},
                    {'op':'keep','path':'reference/c.md','reason':'valid'}])
                self.run_cli('consolidate.py','--plan',p,'--apply',ok=False)
                self.assertTrue((self.vault/'feedback/b.md').exists())


if __name__=='__main__':unittest.main()
