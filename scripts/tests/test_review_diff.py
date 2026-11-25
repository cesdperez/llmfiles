import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

SCRIPT = Path(__file__).resolve().parent.parent / "review-diff.py"


def git(repo, *args):
    subprocess.run(["git", "-C", str(repo), *args], check=True, capture_output=True)


class ReviewDiff(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.repo = Path(self.tmp.name) / "repo"
        self.out = Path(self.tmp.name) / "out"
        self.repo.mkdir()
        git(self.repo, "init", "-q", "-b", "main")
        git(self.repo, "config", "user.email", "t@example.com")
        git(self.repo, "config", "user.name", "t")
        (self.repo / "a.txt").write_text("one\ntwo\nthree\n")
        git(self.repo, "add", ".")
        git(self.repo, "commit", "-qm", "base")

    def tearDown(self):
        self.tmp.cleanup()

    def run_script(self):
        done = subprocess.run(
            [sys.executable, str(SCRIPT), "--base", "main", "--out", str(self.out)],
            cwd=self.repo, check=True, capture_output=True, text=True,
        )
        return json.loads(done.stdout)

    def test_anchors_cover_committed_uncommitted_and_untracked_lines(self):
        git(self.repo, "checkout", "-qb", "feature")
        (self.repo / "a.txt").write_text("one\nTWO\nthree\n")
        git(self.repo, "commit", "-qam", "change")
        (self.repo / "a.txt").write_text("one\nTWO\nthree\nfour\n")
        (self.repo / "new file.txt").write_text("fresh\n")

        summary = self.run_script()

        anchors = (self.out / "anchors.tsv").read_text().splitlines()
        self.assertEqual(anchors, ["a.txt:2\tTWO", "a.txt:4\tfour", "new file.txt:1\tfresh"])
        self.assertIn("+fresh", (self.out / "diff.patch").read_text())
        self.assertEqual(summary["added_lines"], 3)
        self.assertFalse(summary["empty"])

    def test_an_unchanged_branch_reports_empty(self):
        self.assertTrue(self.run_script()["empty"])


if __name__ == "__main__":
    unittest.main()
