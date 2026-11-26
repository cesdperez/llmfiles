import importlib.util
import json
import os
import plistlib
import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest import mock

SPEC = importlib.util.spec_from_file_location(
    "routines", Path(__file__).resolve().parent.parent / "routines.py"
)
rt = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(rt)


def git(repo, *args):
    subprocess.run(["git", "-C", str(repo), *args], check=True, capture_output=True)


def facts(**overrides):
    base = {
        "repo": "/r/app",
        "has_origin": True,
        "default": "main",
        "local_exists": True,
        "ahead": 0,
        "behind": 2,
        "checked_out_in": "/r/app",
        "dirty": False,
        "rebasing": False,
    }
    return {**base, **overrides}


class UpdateVerdict(unittest.TestCase):
    def test_clean_checkout_behind_origin_merges(self):
        self.assertEqual(rt.update_verdict(facts())[0], "merge")

    def test_up_to_date_is_current(self):
        self.assertEqual(rt.update_verdict(facts(behind=0))[0], "current")

    def test_ahead_only_is_current(self):
        self.assertEqual(rt.update_verdict(facts(behind=0, ahead=3))[0], "current")

    def test_diverged_is_skipped(self):
        verdict, reason = rt.update_verdict(facts(ahead=1))
        self.assertEqual(verdict, "skip")
        self.assertIn("diverged", reason)

    def test_dirty_checkout_is_skipped(self):
        verdict, reason = rt.update_verdict(facts(dirty=True))
        self.assertEqual(verdict, "skip")
        self.assertIn("uncommitted", reason)

    def test_default_not_checked_out_moves_the_ref(self):
        self.assertEqual(rt.update_verdict(facts(checked_out_in=None))[0], "update-ref")

    def test_default_checked_out_in_another_worktree_is_skipped(self):
        verdict, reason = rt.update_verdict(facts(checked_out_in="/w/other"))
        self.assertEqual(verdict, "skip")
        self.assertIn("/w/other", reason)

    def test_rebase_in_progress_is_skipped(self):
        self.assertEqual(rt.update_verdict(facts(checked_out_in=None, rebasing=True))[0], "skip")

    def test_missing_origin_fetch_or_head_is_skipped(self):
        for case in ({"has_origin": False}, {"fetch_error": "timeout"}, {"default": None},
                     {"local_exists": False}):
            self.assertEqual(rt.update_verdict(facts(**case))[0], "skip", case)


class UpdateRepo(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        root = Path(os.path.realpath(self.tmp.name))
        self.origin, self.repo, self.other = root / "origin.git", root / "repo", root / "other"
        git(root, "init", "-q", "--bare", "-b", "main", str(self.origin))
        for clone in (self.repo, self.other):
            git(root, "clone", "-q", str(self.origin), str(clone))
            git(clone, "config", "user.email", "t@example.com")
            git(clone, "config", "user.name", "t")
        self.commit(self.repo, "base")
        git(self.repo, "push", "-q", "origin", "main")
        git(self.repo, "remote", "set-head", "origin", "main")
        git(self.other, "pull", "-q", "origin", "main")

    def tearDown(self):
        self.tmp.cleanup()

    def commit(self, repo, name):
        (repo / f"{name}.txt").write_text(name)
        git(repo, "add", ".")
        git(repo, "commit", "-qm", name)

    def push_upstream(self):
        self.commit(self.other, "upstream")
        git(self.other, "push", "-q", "origin", "main")

    def head(self, ref="main"):
        return subprocess.run(["git", "-C", str(self.repo), "rev-parse", ref],
                              capture_output=True, text=True, check=True).stdout.strip()

    def test_fast_forwards_a_clean_checkout(self):
        self.push_upstream()
        self.assertEqual(rt.update_repo(str(self.repo))[0], "updated")
        self.assertEqual(self.head(), self.head("origin/main"))

    def test_moves_the_ref_when_on_another_branch(self):
        git(self.repo, "checkout", "-qb", "feature")
        self.push_upstream()
        self.assertEqual(rt.update_repo(str(self.repo))[0], "updated")
        self.assertEqual(self.head("main"), self.head("origin/main"))
        self.assertEqual(self.head("HEAD"), self.head("feature"))

    def test_skips_a_dirty_checkout(self):
        self.push_upstream()
        (self.repo / "base.txt").write_text("edited")
        verdict, reason = rt.update_repo(str(self.repo))
        self.assertEqual(verdict, "skip")
        self.assertIn("uncommitted", reason)

    def test_skips_a_diverged_branch(self):
        self.push_upstream()
        self.commit(self.repo, "local")
        before = self.head()
        self.assertEqual(rt.update_repo(str(self.repo))[0], "skip")
        self.assertEqual(self.head(), before)

    def test_skips_when_origin_head_dangles_after_a_default_branch_rename(self):
        git(self.origin, "branch", "-m", "main", "trunk")
        git(self.origin, "symbolic-ref", "HEAD", "refs/heads/trunk")
        verdict, reason = rt.update_repo(str(self.repo))
        self.assertEqual(verdict, "skip")
        self.assertTrue(reason)

    def test_skips_when_the_branch_holder_changes_before_applying(self):
        git(self.repo, "checkout", "-qb", "feature")
        self.push_upstream()
        before = self.head("main")
        moved = [{"worktree": "/elsewhere", "branch": "refs/heads/main"}]
        real = rt.worktrees(str(self.repo))
        with mock.patch.object(rt, "worktrees", side_effect=[real, moved]):
            verdict, reason = rt.update_repo(str(self.repo))
        self.assertEqual(verdict, "skip")
        self.assertIn("changed", reason)
        self.assertEqual(self.head("main"), before)

    def test_any_exception_becomes_a_skip(self):
        with mock.patch.object(rt, "repo_facts", side_effect=ValueError("boom")):
            self.assertEqual(rt.update_repo(str(self.repo)), ("skip", "boom"))

    def test_failed_worktree_query_is_a_skip(self):
        self.push_upstream()
        with mock.patch.object(rt, "worktrees", return_value=None):
            self.assertEqual(rt.update_repo(str(self.repo))[0], "skip")

    def test_worktrees_of_a_non_repo_is_none(self):
        with tempfile.TemporaryDirectory() as tmp:
            self.assertIsNone(rt.worktrees(tmp))


class DiscoverRepos(unittest.TestCase):
    def test_merges_orca_and_root_repos_without_duplicates(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(os.path.realpath(tmp))
            for name in ("a", "group/b"):
                (root / name / ".git").mkdir(parents=True)
            (root / "plain").mkdir()
            found = rt.discover_repos([str(root / "a"), str(root / "gone")], rt.root_repos(str(root)))
            self.assertEqual(found, [str(root / "a"), str(root / "group/b")])

    def test_failed_orca_listing_keeps_root_repos(self):
        with tempfile.TemporaryDirectory() as tmp:
            (Path(tmp) / "a" / ".git").mkdir(parents=True)
            self.assertEqual(len(rt.discover_repos(None, rt.root_repos(tmp))), 1)


    def test_accepts_a_separate_git_dir_and_skips_linked_worktrees(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(os.path.realpath(tmp))
            (root / "store").mkdir()
            git(root, "init", "-q", "--separate-git-dir", str(root / "store" / "sep.git"),
                str(root / "work" / "sep"))
            main = root / "work" / "main"
            git(root, "init", "-q", str(main))
            subprocess.run(["git", "-C", str(main), "-c", "user.name=t", "-c",
                            "user.email=t@example.com", "commit", "-q", "--allow-empty",
                            "-m", "base"], check=True)
            git(main, "worktree", "add", "-q", str(root / "work" / "linked"))
            found = rt.discover_repos([str(root / "work" / "linked")],
                                      rt.root_repos(str(root / "work")))
            self.assertEqual(found, [str(main), str(root / "work" / "sep")])


class Launchctl(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        root = Path(self.tmp.name)
        (root / "llmfiles" / "scripts").mkdir(parents=True)
        (root / "llmfiles" / "scripts" / "routines.py").write_text("")
        for name, value in (("INSTALLED_REPO", root / "llmfiles"), ("AGENTS_DIR", root / "agents"),
                            ("LOG_DIR", root / "logs")):
            patcher = mock.patch.object(rt, name, value)
            patcher.start()
            self.addCleanup(patcher.stop)
        sleep = mock.patch.object(rt.time, "sleep")
        sleep.start()
        self.addCleanup(sleep.stop)
        self.addCleanup(self.tmp.cleanup)

    def fake(self, still_loaded=False, bootstrap=None):
        bootstrap = list(bootstrap or [])

        def launchctl(*args):
            if args[0] == "print":
                return (0, "", "") if still_loaded else (113, "", "not found")
            if args[0] == "bootstrap":
                return bootstrap.pop(0) if bootstrap else (0, "", "")
            return 0, "", ""
        return mock.patch.object(rt, "launchctl", side_effect=launchctl)

    def test_install_succeeds_when_every_job_loads(self):
        with self.fake(), mock.patch("builtins.print"):
            self.assertTrue(rt.install(["nightly"]))

    def test_install_retries_bootstrap_on_eio(self):
        eio = (5, "", "Bootstrap failed: 5: Input/output error")
        with self.fake(bootstrap=[eio, eio]), mock.patch("builtins.print"):
            self.assertTrue(rt.install(["nightly"]))

    def test_install_fails_when_bootstrap_keeps_failing(self):
        with self.fake(bootstrap=[(1, "", "nope")] * 9), mock.patch("builtins.print"):
            self.assertFalse(rt.install(["nightly"]))

    def test_uninstall_fails_when_a_job_stays_loaded(self):
        with self.fake(still_loaded=True), mock.patch("builtins.print"):
            self.assertFalse(rt.uninstall())

    def test_uninstall_treats_not_loaded_as_done(self):
        with self.fake(), mock.patch("builtins.print"):
            self.assertTrue(rt.uninstall())


class RunJob(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        patcher = mock.patch.object(rt, "LOG_DIR", Path(self.tmp.name))
        patcher.start()
        self.addCleanup(patcher.stop)

    def test_morning_denies_every_write_tool_without_prompts(self):
        with mock.patch.object(rt, "run", return_value=(0, "draft", "")) as run, \
                mock.patch("builtins.print"):
            rt.run_job("morning")
        cmd = run.call_args.args[0]
        self.assertEqual(cmd[cmd.index("--permission-prompts") + 1], "none")
        denied = cmd[cmd.index("--disallowedTools") + 1].split(",")
        self.assertEqual(set(denied), set(rt.MORNING_DENY))
        self.assertIn("Bash(glab:*)", denied)

    def test_glabsummary_denies_approve_and_merge(self):
        with mock.patch.object(rt, "run", return_value=(0, "", "")) as run, \
                mock.patch("builtins.print"):
            rt.run_job("glabsummary")
        cmd = run.call_args.args[0]
        self.assertIn("Bash(glab mr merge:*)", cmd[cmd.index("--disallowedTools") + 1])

    def test_zero_budget_cap_is_passed(self):
        with mock.patch.object(rt, "run", return_value=(0, "", "")) as run:
            rt.claude("/x", {"max_budget_usd": 0})
        cmd = run.call_args.args[0]
        self.assertEqual(cmd[cmd.index("--max-budget-usd") + 1], "0")

    def test_failed_run_keeps_the_existing_draft(self):
        draft = Path(self.tmp.name) / "draft.md"
        draft.write_text("earlier\n")
        for result in ((1, "partial", "boom"), (0, "  ", "")):
            with mock.patch.object(rt, "claude", return_value=result), \
                    mock.patch("builtins.print"):
                rt.run_command("morning", "/x", {}, out_file=draft)
            self.assertEqual(draft.read_text(), "earlier\n")

    def test_successful_run_writes_the_draft(self):
        draft = Path(self.tmp.name) / "draft.md"
        with mock.patch.object(rt, "claude", return_value=(0, "notes", "")), \
                mock.patch("builtins.print"):
            rt.run_command("morning", "/x", {}, out_file=draft)
        self.assertEqual(draft.read_text(), "notes\n")


class RenderPlist(unittest.TestCase):
    def render(self, job, settings=None):
        settings = settings or rt.JOBS[job]
        plist = rt.render_plist(job, settings, Path("/h/llmfiles"), "/usr/bin/python3",
                                "/bin", home=Path("/h"), log_dir=Path("/h/logs"))
        return plistlib.loads(plistlib.dumps(plist))

    def test_nightly_runs_daily_from_the_installed_repo(self):
        plist = self.render("nightly")
        self.assertEqual(plist["Label"], "com.llmfiles.routines.nightly")
        self.assertEqual(plist["ProgramArguments"],
                         ["/usr/bin/python3", "/h/llmfiles/scripts/routines.py", "run", "nightly"])
        self.assertEqual(plist["StartCalendarInterval"], {"Hour": 3, "Minute": 0})
        self.assertEqual(plist["EnvironmentVariables"], {"PATH": "/bin", "HOME": "/h"})
        self.assertEqual(plist["StandardOutPath"], "/h/logs/nightly.log")

    def test_weekday_job_gets_one_interval_per_day(self):
        intervals = self.render("morning")["StartCalendarInterval"]
        self.assertEqual([i["Weekday"] for i in intervals], [1, 2, 3, 4, 5])
        self.assertTrue(all(i["Hour"] == 8 and i["Minute"] == 30 for i in intervals))

    def test_local_file_overrides_the_schedule(self):
        with tempfile.NamedTemporaryFile("w", suffix=".json") as f:
            json.dump({"morning": {"hour": 7, "minute": 15}}, f)
            f.flush()
            with mock.patch.dict(os.environ, {"LLMFILES_ROUTINES_CONFIG": f.name}):
                settings = rt.load_settings()
        self.assertEqual((settings["morning"]["hour"], settings["morning"]["minute"]), (7, 15))
        self.assertEqual(settings["morning"]["weekdays"], [1, 2, 3, 4, 5])
        self.assertEqual(settings["nightly"]["hour"], 3)

    def test_install_reads_the_installed_repo_config(self):
        with tempfile.TemporaryDirectory() as tmp:
            (Path(tmp) / "local").mkdir()
            (Path(tmp) / "local" / "routines.json").write_text('{"nightly": {"hour": 1}}')
            env = {k: v for k, v in os.environ.items() if k != "LLMFILES_ROUTINES_CONFIG"}
            with mock.patch.object(rt, "INSTALLED_REPO", Path(tmp)), \
                    mock.patch.dict(os.environ, env, clear=True):
                self.assertEqual(rt.installed_settings()["nightly"]["hour"], 1)

    def test_config_override_is_persisted_into_the_plist(self):
        with tempfile.TemporaryDirectory() as tmp, \
                mock.patch.dict(os.environ, {"LLMFILES_ROUTINES_CONFIG": "/c/routines.json"}):
            path = rt.write_plist("nightly", rt.load_settings(), tmp)
            plist = plistlib.loads(path.read_bytes())
        self.assertEqual(plist["EnvironmentVariables"]["LLMFILES_ROUTINES_CONFIG"],
                         "/c/routines.json")


if __name__ == "__main__":
    unittest.main()
