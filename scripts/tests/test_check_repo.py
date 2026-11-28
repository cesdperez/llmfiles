import importlib.util
import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

CHECK = Path(__file__).resolve().parents[2] / "hooks" / "check-repo.py"
spec = importlib.util.spec_from_file_location("check_repo", CHECK)
repo = importlib.util.module_from_spec(spec)
spec.loader.exec_module(repo)


class DisallowedTools(unittest.TestCase):
    def check(self, field):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "reviewer.md"
            path.write_text("---\nname: reviewer\ndescription: Reviews code\nmodel: opus\neffort: high\n"
                            + field + "\n---\n")
            with patch.object(repo, "ROOT", path.parent), patch.object(repo, "tracked", return_value=[path]), \
                    patch.object(repo, "errors", []):
                repo.check_agents()
                return repo.errors

    def test_valid_formats(self):
        for field in ("disallowedTools: Edit, Workflow, mcp__*",
                      'disallowedTools: [Read, "Bash(git push *)"]',
                      "disallowedTools:\n  - Agent\n  - Write  # protects files"):
            with self.subTest(field=field):
                self.assertEqual(self.check(field), [])

    def test_reports_each_unknown_name(self):
        for field in ("disallowedTools: Reaad, Edit, Writ",
                      "disallowedTools:\n  - Reaad\n  - Edit\n  - Writ"):
            with self.subTest(field=field):
                errors = self.check(field)
                self.assertEqual(len(errors), 2)
                self.assertIn("`Reaad`", errors[0])
                self.assertIn("`Writ`", errors[1])

    def test_skips_empty_names_and_null(self):
        for field in ("disallowedTools: Edit, Write,", "disallowedTools:"):
            with self.subTest(field=field):
                self.assertEqual(self.check(field), [])


class AgentFrontmatter(unittest.TestCase):
    def check(self, field):
        return DisallowedTools.check(self, field)

    def test_reports_ruby_parse_error(self):
        errors = self.check("extra: &a x\nother: *a")
        self.assertEqual(len(errors), 1)
        self.assertIn("alias", errors[0])
        self.assertNotIn("from ", errors[0])

    def test_reports_non_mapping(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "reviewer.md"
            path.write_text("---\n- a\n- b\n---\n")
            with patch.object(repo, "ROOT", path.parent), patch.object(repo, "errors", []):
                self.assertIsNone(repo.frontmatter(path, agent=True))
                self.assertIn("must be a YAML mapping", repo.errors[0])

    def test_missing_ruby_fails_instead_of_crashing(self):
        run = subprocess.run

        def no_ruby(args, **kwargs):
            if args[0] == "ruby":
                raise FileNotFoundError(args[0])
            return run(args, **kwargs)

        with patch.object(repo.subprocess, "run", side_effect=no_ruby):
            errors = self.check("disallowedTools: Edit")
        self.assertEqual(len(errors), 1)
        self.assertIn("ruby", errors[0])
