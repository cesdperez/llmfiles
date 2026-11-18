import importlib.util
import os
import subprocess
import tempfile
import time
import unittest
from pathlib import Path

SPEC = importlib.util.spec_from_file_location(
    "orca_cleanup", Path(__file__).resolve().parent.parent / "orca-cleanup.py"
)
oc = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(oc)

HOUR = 3600


def worktree(**overrides):
    facts = {
        "path": "/w/feature",
        "is_main": False,
        "exists": True,
        "pinned": False,
        "kept_path": False,
        "dirty": False,
        "merged": "ancestor of origin/main",
        "temp_root": False,
        "idle_s": 10 * HOUR,
        "agent_busy": False,
        "worker_live": False,
    }
    return {**facts, **overrides}


class WorktreeVerdict(unittest.TestCase):
    def test_merged_clean_idle_worktree_is_removed(self):
        self.assertEqual(oc.worktree_verdict(worktree())[0], "remove")

    def test_main_checkout_is_never_removed(self):
        self.assertIsNone(oc.worktree_verdict(worktree(is_main=True))[0])

    def test_unmerged_worktree_is_kept_silently(self):
        self.assertIsNone(oc.worktree_verdict(worktree(merged=None))[0])

    def test_merged_but_dirty_worktree_is_kept_and_reported(self):
        verdict, reason = oc.worktree_verdict(worktree(dirty=True))
        self.assertEqual(verdict, "keep")
        self.assertIn("uncommitted", reason)

    def test_busy_agent_keeps_worktree(self):
        self.assertEqual(oc.worktree_verdict(worktree(agent_busy=True))[0], "keep")

    def test_live_worker_keeps_worktree(self):
        self.assertEqual(oc.worktree_verdict(worktree(worker_live=True))[0], "keep")

    def test_recent_activity_keeps_worktree(self):
        self.assertEqual(oc.worktree_verdict(worktree(idle_s=HOUR))[0], "keep")

    def test_pinned_or_kept_path_keeps_worktree(self):
        self.assertEqual(oc.worktree_verdict(worktree(pinned=True))[0], "keep")
        self.assertEqual(oc.worktree_verdict(worktree(kept_path=True))[0], "keep")

    def test_stale_temp_worktree_is_removed_even_when_dirty_and_unmerged(self):
        facts = worktree(temp_root=True, dirty=True, merged=None, idle_s=30 * HOUR)
        self.assertEqual(oc.worktree_verdict(facts)[0], "force-remove")

    def test_never_committed_worktree_waits_three_days(self):
        self.assertIsNone(oc.worktree_verdict(worktree(empty=True, idle_s=30 * HOUR))[0])
        self.assertEqual(oc.worktree_verdict(worktree(empty=True, idle_s=80 * HOUR))[0], "remove")

    def test_fresh_temp_worktree_is_kept(self):
        facts = worktree(temp_root=True, dirty=True, merged=None, idle_s=2 * HOUR)
        self.assertIsNone(oc.worktree_verdict(facts)[0])


class HubLeads(unittest.TestCase):
    def test_lead_is_kept_while_a_child_is_kept(self):
        tree = {"lead": ["a", "b"], "a": [], "b": []}
        self.assertEqual(oc.prune_leads({"lead", "a"}, tree), {"a"})

    def test_lead_goes_when_every_child_goes(self):
        tree = {"lead": ["a"], "a": []}
        self.assertEqual(oc.prune_leads({"lead", "a"}, tree), {"lead", "a"})


class ComposeVerdict(unittest.TestCase):
    def test_project_of_missing_checkout_goes_down(self):
        project = {"name": "app", "working_dir": "/gone", "config_files": []}
        self.assertEqual(oc.compose_verdict(project, set(), set(), set().__contains__), "down")

    def test_project_of_removed_worktree_goes_down(self):
        project = {"name": "app", "working_dir": "/w/feature/api", "config_files": []}
        self.assertEqual(oc.compose_verdict(project, set(), {"/w/feature"}, {"/w/feature/api"}.__contains__), "down")

    def test_kept_project_never_goes_down(self):
        project = {"name": "stack", "working_dir": "/gone", "config_files": []}
        self.assertIsNone(oc.compose_verdict(project, {"stack"}, set(), set().__contains__))

    def test_kept_project_serving_a_missing_override_is_repaired(self):
        project = {"name": "stack", "working_dir": "/s", "config_files": ["/s/compose.yaml", "/gone/override.yaml"]}
        self.assertEqual(oc.compose_verdict(project, {"stack"}, set(), {"/s", "/s/compose.yaml"}.__contains__), "repair")

    def test_project_of_live_checkout_is_left_alone(self):
        project = {"name": "app", "working_dir": "/repo", "config_files": ["/repo/compose.yaml"]}
        self.assertIsNone(oc.compose_verdict(project, set(), set(), {"/repo", "/repo/compose.yaml"}.__contains__))


class ProcessVerdict(unittest.TestCase):
    def test_server_in_missing_dir_is_killed(self):
        self.assertTrue(oc.should_kill({"command": "node", "cwd": "/gone"}, set(), set().__contains__))

    def test_server_in_removed_worktree_is_killed(self):
        proc = {"command": "node", "cwd": "/w/feature/web"}
        self.assertTrue(oc.should_kill(proc, {"/w/feature"}, {"/w/feature/web"}.__contains__))

    def test_shell_is_never_killed(self):
        self.assertFalse(oc.should_kill({"command": "zsh", "cwd": "/gone"}, set(), set().__contains__))

    def test_process_in_live_dir_is_left_alone(self):
        self.assertFalse(oc.should_kill({"command": "node", "cwd": "/repo"}, set(), {"/repo"}.__contains__))

    def test_sibling_path_with_shared_prefix_is_not_inside(self):
        proc = {"command": "node", "cwd": "/w/feature-2"}
        self.assertFalse(oc.should_kill(proc, {"/w/feature"}, {"/w/feature-2"}.__contains__))


class BranchVerdict(unittest.TestCase):
    def branch(self, **overrides):
        facts = {"name": "feat/x", "checked_out": False, "is_base": False, "kept": False,
                 "merged": "ancestor of origin/main", "age_s": HOUR}
        return {**facts, **overrides}

    def test_merged_branch_is_deleted(self):
        self.assertEqual(oc.branch_verdict(self.branch()), "delete")

    def test_checked_out_base_or_kept_branch_stays(self):
        for facts in (self.branch(checked_out=True), self.branch(is_base=True), self.branch(kept=True)):
            self.assertIsNone(oc.branch_verdict(facts))

    def test_unmerged_branch_stays(self):
        self.assertIsNone(oc.branch_verdict(self.branch(merged=None)))

    def test_old_agent_scratch_branch_is_deleted_unmerged(self):
        facts = self.branch(name="worktree-agent-abc", merged=None, age_s=20 * 24 * HOUR)
        self.assertEqual(oc.branch_verdict(facts), "delete")

    def test_recent_agent_scratch_branch_stays(self):
        facts = self.branch(name="worktree-opencode-x", merged=None, age_s=2 * 24 * HOUR)
        self.assertIsNone(oc.branch_verdict(facts))


def git(cwd, *args):
    return subprocess.run(["git", "-C", str(cwd), *args], check=True, capture_output=True, text=True).stdout.strip()


class MergedEvidence(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.repo = Path(self.tmp.name)
        git(self.repo, "init", "-q", "-b", "main")
        git(self.repo, "config", "user.email", "t@t")
        git(self.repo, "config", "user.name", "t")
        self.commit("base.txt", "base")

    def tearDown(self):
        self.tmp.cleanup()

    def commit(self, name, text):
        (self.repo / name).write_text(text)
        git(self.repo, "add", name)
        git(self.repo, "commit", "-q", "-m", name)
        return git(self.repo, "rev-parse", "HEAD")

    def test_ancestor_of_base_is_merged(self):
        git(self.repo, "switch", "-q", "-c", "feat")
        tip = self.commit("a.txt", "a")
        git(self.repo, "switch", "-q", "main")
        git(self.repo, "merge", "-q", "--ff-only", "feat")
        self.assertIn("ancestor", oc.merged_evidence(self.repo, "feat", tip, "main", lookup_mr=False))

    def test_cherry_picked_commits_are_merged(self):
        git(self.repo, "switch", "-q", "-c", "feat")
        tip = self.commit("a.txt", "a")
        git(self.repo, "switch", "-q", "main")
        self.commit("other.txt", "other")
        git(self.repo, "cherry-pick", tip)
        self.assertIn("patch", oc.merged_evidence(self.repo, "feat", tip, "main", lookup_mr=False))

    def test_unmerged_branch_has_no_evidence(self):
        git(self.repo, "switch", "-q", "-c", "feat")
        tip = self.commit("a.txt", "a")
        self.assertIsNone(oc.merged_evidence(self.repo, "feat", tip, "main", lookup_mr=False))


class TempRoots(unittest.TestCase):
    def test_claude_scratchpad_is_a_temp_root(self):
        path = str(Path.home() / ".claude/runtime/claude-502/x/scratchpad/eval/repo")
        self.assertTrue(oc.under_temp_root(path))

    def test_orca_workspace_is_not(self):
        self.assertFalse(oc.under_temp_root(str(Path.home() / "orca/workspaces/repo/feat")))


class StaleLock(unittest.TestCase):
    def test_owner_untouched_for_over_an_hour_is_stale(self):
        with tempfile.TemporaryDirectory() as tmp:
            owner = Path(tmp) / "owner"
            owner.write_text("feat")
            old = time.time() - 2 * HOUR
            os.utime(owner, (old, old))
            self.assertTrue(oc.lock_is_stale(Path(tmp)))

    def test_fresh_owner_is_held(self):
        with tempfile.TemporaryDirectory() as tmp:
            (Path(tmp) / "owner").write_text("feat")
            self.assertFalse(oc.lock_is_stale(Path(tmp)))


if __name__ == "__main__":
    unittest.main()
