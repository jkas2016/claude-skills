import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

SCRIPTS = Path(__file__).resolve().parents[1] / "skills/llm-wiki-memory/scripts"
sys.path.insert(0, str(SCRIPTS))


class MemoryCLI(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.vault = Path(self.tmp.name) / "vault"
        self.vault.mkdir()
        (self.vault / "MEMORY.md").write_text("# MEMORY\n", encoding="utf-8")
        self.env = {**os.environ, "LLM_WIKI_PATH": str(self.vault)}

    def run_cli(self, script, *args, body="", ok=True):
        result = subprocess.run(
            [sys.executable, str(SCRIPTS / script), *args], input=body,
            encoding="utf-8", capture_output=True, env=self.env,
        )
        if ok:
            self.assertEqual(result.returncode, 0, result.stderr + result.stdout)
        else:
            self.assertNotEqual(result.returncode, 0)
        return result

    def note(self, rel="feedback/rule.md", desc="git 규칙", body="고유한 상세 본문", extra=""):
        path = self.vault / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        text = (
            f"---\nname: {path.stem}\ndescription: {desc}\ntype: feedback\n"
            f"tags: [git]\naliases: [규칙]\ncreated: 2020-01-01\nupdated: 2020-01-01\n"
            f"{extra}---\n\n{body}\n"
        )
        path.write_text(text, encoding="utf-8")
        with (self.vault / "MEMORY.md").open("a", encoding="utf-8") as f:
            f.write(f"- [규칙]({rel}) — {desc}\n")
        return path

    def plan(self, changes):
        path = Path(self.tmp.name) / "plan.json"
        path.write_text(json.dumps({"changes": changes}, ensure_ascii=False), encoding="utf-8")
        return str(path)

    def change(self, path, **fields):
        return {"path": path.relative_to(self.vault).as_posix(),
                "sha256": hashlib.sha256(path.read_bytes()).hexdigest(), **fields}

    def test_search_defaults_to_summaries_and_excludes_inactive(self):
        self.note()
        self.note("feedback/old.md", extra="status: archived\n")
        text = self.run_cli("recall.py", "git").stdout
        self.assertIn("feedback/rule.md", text)
        self.assertNotIn("고유한 상세 본문", text)
        self.assertNotIn("feedback/old.md", text)
        self.assertIn("feedback/old.md", self.run_cli("recall.py", "git", "--include-inactive").stdout)

    def test_search_ranks_metadata_and_scopes_projects(self):
        self.note("feedback/body.md", desc="other", body="needle")
        self.note("feedback/title.md", desc="needle")
        self.note("projects/a/feedback/yes.md", desc="needle")
        self.note("projects/b/feedback/no.md", desc="needle")
        text = self.run_cli("recall.py", "needle", "--project", "a").stdout
        self.assertLess(text.index("feedback/title.md"), text.index("feedback/body.md"))
        self.assertIn("projects/a/", text)
        self.assertNotIn("projects/b/", text)

    def test_budget_utf8_and_explicit_read(self):
        self.note(body="한글" * 2000)
        text = self.run_cli("recall.py", "--read", "feedback/rule.md", "--max-bytes", "400").stdout
        self.assertLessEqual(len(text.encode()), 400)
        self.assertIn("omitted", text)
        self.assertIn("한글", text)
        self.assertNotIn("\ufffd", text)

    def test_reject_read_outside_vault(self):
        self.run_cli("recall.py", "--read", "../secret.md", ok=False)

    def test_context_only_pinned_and_mapped_project(self):
        self.note(extra="pinned: true\n")
        self.note("feedback/no.md")
        self.note("projects/a/feedback/yes.md")
        self.note("projects/b/feedback/no.md")
        cfg = Path(self.tmp.name) / "config.json"
        cfg.write_text(json.dumps({"projects": {"/work/a": "a"}}))
        text = self.run_cli("context.py", "--config", str(cfg), "--cwd", "/work/a/sub").stdout
        self.assertIn("feedback/rule.md", text)
        self.assertIn("projects/a/", text)
        self.assertNotIn("feedback/no.md", text)
        self.assertNotIn("projects/b/", text)
        self.assertLessEqual(len(text.encode()), 4096)

    def test_context_hook_reads_cwd_and_handles_missing_vault(self):
        self.note("projects/a/feedback/yes.md")
        cfg = Path(self.tmp.name) / "config.json"
        cfg.write_text(json.dumps({"projects": {"/work/a": "a"}}))
        text = self.run_cli("context.py", "--hook", "--config", str(cfg),
                            body='{"cwd":"/work/a"}').stdout
        self.assertIn("projects/a/", text)
        self.env.pop("LLM_WIKI_PATH")
        self.assertEqual(self.run_cli("context.py", "--hook", body="{}").stdout, "")

    def test_audit_is_read_only_and_candidates_are_not_verdicts(self):
        self.note(body="duplicate body")
        self.note("feedback/copy.md", body="duplicate body")
        before = {str(p): p.read_bytes() for p in self.vault.rglob("*.md")}
        report = json.loads(self.run_cli("audit.py").stdout)
        self.assertTrue(report["candidates"])
        self.assertIn("duplicate", json.dumps(report))
        self.assertEqual(before, {str(p): p.read_bytes() for p in self.vault.rglob("*.md")})

    def test_maintenance_dry_run_apply_and_restore(self):
        old = self.note()
        original = old.read_bytes()
        plan = self.plan([self.change(old, status="archived", reason="completed")])
        self.run_cli("maintain.py", plan)
        self.assertEqual(original, old.read_bytes())
        output = json.loads(self.run_cli("maintain.py", plan, "--apply").stdout)
        self.assertRegex(old.read_text(), 'status: "?archived')
        self.assertNotIn("feedback/rule.md", self.run_cli("recall.py", "git").stdout)
        self.run_cli("maintain.py", "--restore", output["backup"], "--apply")
        self.assertEqual(original, old.read_bytes())

    def test_maintenance_validates_entire_batch_before_writes(self):
        a = self.note()
        b = self.note("feedback/b.md")
        original = a.read_bytes()
        bad = self.change(b, status="archived", reason="old")
        bad["sha256"] = "wrong"
        plan = self.plan([self.change(a, status="archived", reason="old"), bad])
        self.run_cli("maintain.py", plan, "--apply", ok=False)
        self.assertEqual(original, a.read_bytes())

    def test_superseded_requires_active_target_and_restore_checks_conflict(self):
        a = self.note()
        plan = self.plan([self.change(a, status="superseded", superseded_by="feedback/missing.md",
                                     reason="merged")])
        self.run_cli("maintain.py", plan, "--apply", ok=False)
        b = self.note("feedback/b.md")
        plan = self.plan([self.change(a, status="superseded", superseded_by="feedback/b.md",
                                     reason="merged"), self.change(b, body="통합 규칙", reason="merge")])
        output = json.loads(self.run_cli("maintain.py", plan, "--apply").stdout)
        self.run_cli("lint.py")
        b.write_text(b.read_text() + "\nconcurrent change")
        self.run_cli("maintain.py", "--restore", output["backup"], "--apply", ok=False)
        self.assertRegex(a.read_text(), 'status: "?superseded')

    def test_save_preserves_metadata_and_checks_candidates_without_writing(self):
        path = self.note(extra="originSessionId: abc\npinned: true\nstatus: archived\n")
        args = ("--type", "feedback", "--name", "rule", "--desc", "git 규칙",
                "--hook", "git 규칙", "--tags", "git")
        original = path.read_bytes()
        self.run_cli("save.py", *args, "--check", body="new")
        self.assertEqual(original, path.read_bytes())
        self.run_cli("save.py", *args, body="new")
        text = path.read_text()
        for value in ["created: 2020-01-01", "originSessionId: abc", "pinned: true", "status: archived"]:
            self.assertIn(value, text)
        self.run_cli("lint.py")
        self.run_cli("save.py", "--type", "feedback", "--name", "../escape",
                     "--desc", "bad", "--hook", "bad", body="bad", ok=False)

    def test_hook_install_preserves_other_hooks_and_is_idempotent(self):
        settings = Path(self.tmp.name) / "settings.json"
        old = 'if [ -f "$LLM_WIKI_PATH/MEMORY.md" ]; then printf \'## Auto-memory index (from $LLM_WIKI_PATH/MEMORY.md)\\n\\n\'; cat "$LLM_WIKI_PATH/MEMORY.md"; fi'
        other = {"type": "command", "command": "echo other"}
        data = {"env": {"TEST": "keep"}, "hooks": {"SessionStart": [
            {"hooks": [{"type": "command", "command": old}, other]}],
            "Stop": [{"hooks": [other]}]}}
        settings.write_text(json.dumps(data))
        self.run_cli("install_hook.py", "--settings", str(settings))
        self.assertEqual(json.loads(settings.read_text()), data)
        self.run_cli("install_hook.py", "--settings", str(settings), "--apply")
        changed = json.loads(settings.read_text())
        hooks = [h for g in changed["hooks"]["SessionStart"] for h in g["hooks"]]
        self.assertIn(other, hooks)
        self.assertEqual(changed["hooks"]["Stop"], data["hooks"]["Stop"])
        self.assertEqual(changed["env"], data["env"])
        self.assertTrue(any("context.py" in h["command"] for h in hooks))
        before = settings.read_bytes()
        self.run_cli("install_hook.py", "--settings", str(settings), "--apply")
        self.assertEqual(before, settings.read_bytes())

    def test_unknown_compound_hook_is_not_removed(self):
        settings = Path(self.tmp.name) / "settings.json"
        text = json.dumps({"hooks": {"SessionStart": [{"hooks": [{
            "type": "command", "command": 'cat "$LLM_WIKI_PATH/MEMORY.md"; echo keep-me'}]}]}})
        settings.write_text(text)
        self.run_cli("install_hook.py", "--settings", str(settings), "--apply", ok=False)
        self.assertEqual(settings.read_text(), text)

    def test_symlink_read_and_write_escape_are_rejected(self):
        target = Path(self.tmp.name) / "outside"
        target.mkdir()
        (target / "secret.md").write_text("secret")
        (self.vault / "feedback").symlink_to(target, target_is_directory=True)
        self.run_cli("recall.py", "--read", "feedback/secret.md", ok=False)
        self.run_cli("save.py", "--type", "feedback", "--name", "secret",
                     "--desc", "x", "--hook", "x", body="bad", ok=False)
        self.assertEqual((target / "secret.md").read_text(), "secret")

    def test_apply_failure_rolls_back_prior_writes(self):
        import transactions
        a = self.note()
        b = self.note("feedback/b.md")
        before_a, before_b = a.read_bytes(), b.read_bytes()
        real_write = transactions.atomic_write

        def fail_second(path, data):
            if path == b and data == b"new b":
                raise OSError("simulated disk failure")
            return real_write(path, data)

        with patch.object(transactions, "atomic_write", side_effect=fail_second):
            with self.assertRaises(OSError):
                transactions.apply_batch(self.vault, [
                    ("feedback/rule.md", before_a, b"new a"),
                    ("feedback/b.md", before_b, b"new b")])
        self.assertEqual(a.read_bytes(), before_a)
        self.assertEqual(b.read_bytes(), before_b)
        self.assertEqual(len(list((self.vault / ".memory-backups").glob("*.json"))), 1)

    def test_cycles_and_retiring_a_referenced_target_are_rejected(self):
        a = self.note()
        b = self.note("feedback/b.md")
        plan = self.plan([
            self.change(a, status="superseded", superseded_by="feedback/b.md", reason="merge"),
            self.change(b, status="superseded", superseded_by="feedback/rule.md", reason="merge")])
        self.run_cli("maintain.py", plan, "--apply", ok=False)
        self.assertNotIn("status:", a.read_text())

    def test_audit_hash_matches_crlf_file(self):
        path = self.note()
        path.write_bytes(path.read_bytes().replace(b"\n", b"\r\n"))
        report = json.loads(self.run_cli("audit.py").stdout)
        self.assertEqual(report["sha256"]["feedback/rule.md"], hashlib.sha256(path.read_bytes()).hexdigest())
        plan = self.plan([self.change(path, status="archived", reason="completed")])
        self.run_cli("maintain.py", plan, "--apply")

    def test_body_summary_update_and_index_restore(self):
        path = self.note()
        original_index = (self.vault / "MEMORY.md").read_bytes()
        plan = self.plan([self.change(path, body="new body", description="new summary", reason="compact")])
        output = json.loads(self.run_cli("maintain.py", plan, "--apply").stdout)
        self.assertIn("new summary", self.run_cli("recall.py", "new").stdout)
        self.run_cli("maintain.py", "--restore", output["backup"], "--apply")
        self.assertEqual(original_index, (self.vault / "MEMORY.md").read_bytes())

    def test_context_overflow_keeps_complete_rules_and_notice(self):
        for i in range(20):
            self.note(f"feedback/rule{i}.md", desc="중요한 규칙" * 30, extra="pinned: true\n")
        text = self.run_cli("context.py", "--max-bytes", "1500").stdout
        self.assertLessEqual(len(text.encode()), 1500)
        self.assertIn("omitted", text)
        for line in text.splitlines():
            if line.startswith("- ["):
                self.assertTrue(line.endswith("(status=active)"), line)

    def test_null_description_cannot_delete_required_metadata(self):
        path = self.note()
        before = path.read_bytes()
        plan = self.plan([self.change(path, description=None, reason="bad")])
        self.run_cli("maintain.py", plan, "--apply", ok=False)
        self.assertEqual(path.read_bytes(), before)
        path = self.note(extra="status: archived\n")
        before = path.read_bytes()
        plan = self.plan([self.change(path, status=None, reason="bad")])
        self.run_cli("maintain.py", plan, "--apply", ok=False)
        self.assertEqual(path.read_bytes(), before)

    def test_frontmatter_inline_comments_and_quoted_hash(self):
        self.note(desc='"title # literal"', extra="status: active # default\npinned: true # core\n")
        text = self.run_cli("context.py").stdout
        self.assertIn("feedback/rule.md", text)
        self.assertIn("title # literal", text)
        self.run_cli("lint.py")


if __name__ == "__main__":
    unittest.main()
