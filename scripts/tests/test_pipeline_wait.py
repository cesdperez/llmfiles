import unittest

from transcript_fixtures import load_script

pw = load_script("pipeline-wait.py")
SHA = "abc123"


class FakeForge:
    """Answers `api(path)` from a list of snapshots, one per poll."""

    def __init__(self, polls, jobs=None):
        self.polls, self.jobs, self.calls = list(polls), jobs or {}, []

    def api(self, path):
        self.calls.append(path)
        if "/jobs" in path:
            return self.jobs
        snapshot = self.polls.pop(0) if len(self.polls) > 1 else self.polls[0]
        if isinstance(snapshot, Exception):
            raise snapshot
        return snapshot


class Clock:
    def __init__(self):
        self.now = 0.0

    def __call__(self):
        return self.now

    def sleep(self, seconds):
        self.now += seconds


def gitlab(status, pid=7):
    return [{"id": pid, "status": status, "web_url": f"https://gitlab.example/p/{pid}"}]


def wait_gitlab(forge, appear_timeout=600, timeout=6600):
    clock = Clock()
    return pw.wait(lambda s: pw.gitlab_status(forge.api, s), pw.gitlab_code, SHA,
                   30, appear_timeout, timeout, sleep=clock.sleep, clock=clock)


class GitLab(unittest.TestCase):
    def test_waits_for_the_pipeline_to_appear_then_to_finish(self):
        forge = FakeForge([[], [], gitlab("pending"), gitlab("running"), gitlab("success")])
        code, result = wait_gitlab(forge)
        self.assertEqual(code, 0)
        self.assertEqual(result["sha"], SHA)
        self.assertEqual(len(forge.calls), 5)

    def test_failure_names_the_failed_jobs_but_not_those_allowed_to_fail(self):
        jobs = [{"name": "unit", "status": "failed"},
                {"name": "lint", "status": "failed", "allow_failure": True},
                {"name": "build", "status": "success"}]
        code, result = wait_gitlab(FakeForge([gitlab("failed")], jobs))
        self.assertEqual(code, 1)
        self.assertEqual(result["failed_jobs"], ["unit"])
        self.assertEqual(result["url"], "https://gitlab.example/p/7")

    def test_canceled_is_a_failure(self):
        self.assertEqual(wait_gitlab(FakeForge([gitlab("canceled")], []))[0], 1)

    def test_skipped_is_not_green(self):
        self.assertEqual(wait_gitlab(FakeForge([gitlab("skipped")]))[0], 3)

    def test_ref_keeps_only_that_branch(self):
        forge = FakeForge([gitlab("success")])
        pw.gitlab_status(forge.api, SHA, ref="main")
        self.assertIn("&ref=main&", forge.calls[0])

    def test_jobs_are_read_across_pages(self):
        pages = {1: [{"name": f"j{i}", "status": "failed"} for i in range(100)], 2: [{"name": "last", "status": "failed"}]}

        def api(path):
            if "/jobs" in path:
                return pages[int(path.rsplit("page=", 1)[1])]
            return gitlab("failed")
        self.assertEqual(len(pw.gitlab_status(api, SHA)["failed_jobs"]), 101)

    def test_blocking_manual_job_waits_on_a_person(self):
        jobs = [{"name": "deploy", "status": "manual"}, {"name": "optional", "status": "manual", "allow_failure": True}]
        code, result = wait_gitlab(FakeForge([gitlab("manual")], jobs))
        self.assertEqual(code, 4)
        self.assertEqual(result["manual_jobs"], ["deploy"])

    def test_scheduled_keeps_waiting(self):
        self.assertEqual(wait_gitlab(FakeForge([gitlab("scheduled"), gitlab("success")]))[0], 0)

    def test_no_pipeline_within_the_appear_timeout(self):
        code, result = wait_gitlab(FakeForge([[]]), appear_timeout=90)
        self.assertEqual((code, result["state"]), (3, "none"))

    def test_still_running_at_the_timeout(self):
        self.assertEqual(wait_gitlab(FakeForge([gitlab("running")]), timeout=300)[0], 5)

    def test_a_passing_cli_error_is_retried(self):
        forge = FakeForge([gitlab("running"), pw.CliError("502"), gitlab("success")])
        self.assertEqual(wait_gitlab(forge)[0], 0)

    def test_repeated_cli_errors_give_up(self):
        code, result = wait_gitlab(FakeForge([pw.CliError("401 unauthorized")]))
        self.assertEqual(code, 2)
        self.assertIn("401", result["error"])

    def test_an_unreadable_answer_is_a_cli_error_not_a_failed_pipeline(self):
        api = pw.api_for("glab", None, runner=lambda cmd, cwd: "<html>502 Bad Gateway</html>")
        clock = Clock()
        code, _ = pw.wait(lambda s: pw.gitlab_status(api, s), pw.gitlab_code, SHA,
                          30, 600, 6600, sleep=clock.sleep, clock=clock)
        self.assertEqual(code, 2)

    def test_a_malformed_answer_is_retried_like_a_cli_error(self):
        forge = FakeForge([[{"id": 1}], gitlab("success")])
        self.assertEqual(wait_gitlab(forge)[0], 0)


class GitLabMergeRequest(unittest.TestCase):
    def status(self, head, parents=()):
        def api(path):
            if "repository/commits/" in path:
                return {"parent_ids": list(parents)}
            return {"head_pipeline": head}
        return pw.gitlab_status(api, SHA, mr="12")

    def test_head_pipeline_on_this_commit(self):
        self.assertEqual(self.status({"id": 1, "sha": SHA, "status": "success"})["state"], "success")

    def test_merged_results_pipeline_whose_parent_is_this_commit(self):
        head = {"id": 2, "sha": "merge1", "status": "running"}
        self.assertEqual(self.status(head, parents=["base1", SHA])["state"], "running")

    def test_head_pipeline_of_an_earlier_push_is_not_this_one(self):
        self.assertIsNone(self.status({"id": 1, "sha": "older", "status": "success"}, parents=["base1"]))

    def test_no_head_pipeline_yet(self):
        self.assertIsNone(self.status(None))


def run(rid, workflow, status="completed", conclusion="success"):
    return {"id": rid, "workflow_id": workflow, "name": f"wf{workflow}", "status": status,
            "conclusion": conclusion, "html_url": f"https://github.example/runs/{rid}"}


def wait_github(forge):
    clock = Clock()
    return pw.wait(lambda s: pw.github_status(forge.api, s), pw.github_code, SHA,
                   30, 600, 6600, sleep=clock.sleep, clock=clock)


class GitHub(unittest.TestCase):
    def test_settles_once_every_workflow_completed(self):
        forge = FakeForge([{"workflow_runs": [run(1, 1), run(2, 2, "in_progress", None)]},
                           {"workflow_runs": [run(1, 1), run(2, 2, conclusion="skipped")]}])
        self.assertEqual(wait_github(forge)[0], 0)
        self.assertEqual(len(forge.calls), 2)

    def test_newest_run_of_a_workflow_replaces_the_old_one(self):
        forge = FakeForge([{"workflow_runs": [run(1, 1, conclusion="failure"), run(5, 1)]}])
        self.assertEqual(wait_github(forge)[0], 0)

    def test_a_workflow_run_per_event_is_followed_separately(self):
        push, pr = run(1, 1, conclusion="failure"), run(2, 1)
        push["event"], pr["event"] = "push", "pull_request"
        self.assertEqual(wait_github(FakeForge([{"workflow_runs": [push, pr]}], {"jobs": []}))[0], 1)

    def test_every_run_skipped_is_not_green(self):
        forge = FakeForge([{"workflow_runs": [run(1, 1, conclusion="skipped")]}])
        self.assertEqual(wait_github(forge)[0], 3)

    def test_failure_names_the_run_and_its_failed_jobs(self):
        jobs = {"jobs": [{"name": "test", "conclusion": "failure"}, {"name": "lint", "conclusion": "success"}]}
        code, result = wait_github(FakeForge([{"workflow_runs": [run(3, 1, conclusion="timed_out")]}], jobs))
        self.assertEqual(code, 1)
        self.assertEqual(result["failed_jobs"], ["wf1 / test"])
        self.assertEqual(result["url"], "https://github.example/runs/3")

    def test_a_run_held_for_approval_waits_on_a_person(self):
        forge = FakeForge([{"workflow_runs": [run(1, 1), run(2, 2, "waiting", None)]}])
        code, result = wait_github(forge)
        self.assertEqual(code, 4)
        self.assertEqual(result["manual_jobs"], ["wf2"])


class Forge(unittest.TestCase):
    def test_github_remote_uses_gh_and_any_other_uses_glab(self):
        self.assertEqual(pw.forge_of("git@github.com:me/repo.git"), "github")
        self.assertEqual(pw.forge_of("git@gitlab.com:acme/web.git"), "gitlab")


if __name__ == "__main__":
    unittest.main()
