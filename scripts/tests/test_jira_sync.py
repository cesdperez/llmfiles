import importlib.util
import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

SCRIPTS = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(SCRIPTS))
CONFIG = tempfile.NamedTemporaryFile("w", suffix=".json", delete=False)
json.dump({"gitlab_group": "acme", "git_author": "me@acme.com",
           "jira_base_url": "https://acme.atlassian.net/browse/"}, CONFIG)
CONFIG.close()
with mock.patch.dict(os.environ, {"LLMFILES_WORK_CONFIG": CONFIG.name}):
    SPEC = importlib.util.spec_from_file_location("jira_sync", SCRIPTS / "jira-sync.py")
    js = importlib.util.module_from_spec(SPEC)
    SPEC.loader.exec_module(js)
os.unlink(CONFIG.name)

ME = {"gitlab_username": "me", "email": "me@acme.com", "account_id": "acc-me"}
MINE = [{"author_username": "me", "matched_in": ["title"]}]
THEIRS = [{"author_username": "ann", "matched_in": ["title"]}]


def done(proc_stdout, stderr="", code=0):
    return subprocess.CompletedProcess([], code, stdout=proc_stdout, stderr=stderr)


def mr(title, author="me", target="main", branch="feature", description=""):
    return {"references": {"full": "acme/app!1"}, "title": title, "web_url": "https://gl/1",
            "author": {"name": author.title(), "username": author}, "merged_at": "2026-11-01",
            "target_branch": target, "source_branch": branch, "description": description}


def issue(key, status="In Progress", category="indeterminate", email="me@acme.com", account=None,
          assigned=True, kind="Story"):
    assignee = {"displayName": "Someone", "emailAddress": email, "accountId": account}
    return {"key": key, "summary": f"{key} summary", "issuetype": {"name": kind},
            "status": {"name": status, "statusCategory": {"key": category}},
            "assignee": assignee if assigned and (email or account) else None}


class RunJson(unittest.TestCase):
    def test_parses_stdout_and_ignores_stderr_noise(self):
        with mock.patch.object(js.subprocess, "run",
                               return_value=done('{"ok": 1}', stderr="Update available\n")):
            self.assertEqual(js.run_json(["glab", "api", "user"]), {"ok": 1})

    def test_failure_surfaces_stderr(self):
        with mock.patch.object(js.subprocess, "run", return_value=done("", "401 Unauthorized", 1)):
            with self.assertRaisesRegex(js.CommandError, "401 Unauthorized"):
                js.run_json(["glab", "api", "user"])

    def test_non_json_stdout_surfaces_stderr(self):
        with mock.patch.object(js.subprocess, "run", return_value=done("key: value", "warn")):
            with self.assertRaisesRegex(js.CommandError, "no JSON.*warn"):
                js.run_json(["twg", "jira"])


class TwgQuery(unittest.TestCase):
    def test_follows_pages_and_drops_the_yaml_switch(self):
        pages = [
            {"data": {"issues": [issue("ABC-1")]}, "pageInfo": {"hasNextPage": True, "nextCursor": "c1"}},
            {"data": {"issues": [issue("ABC-2")]}, "pageInfo": {"hasNextPage": False}},
        ]
        calls = []

        def fake(cmd, **kwargs):
            calls.append((cmd, kwargs["env"]))
            return done(json.dumps(pages[len(calls) - 1]))

        with mock.patch.dict(os.environ, {"TWG_AGENT_DEFAULTS": "1"}), \
                mock.patch.object(js.subprocess, "run", side_effect=fake):
            issues = js.twg_query("parent = ABC-0")
        self.assertEqual([i["key"] for i in issues], ["ABC-1", "ABC-2"])
        self.assertIn("--after", calls[1][0])
        self.assertNotIn("TWG_AGENT_DEFAULTS", calls[0][1])


class MergedMrs(unittest.TestCase):
    def search(self, mrs):
        with mock.patch.object(js, "glab_api", return_value=mrs):
            return js.merged_mrs("ABC-38")

    def test_keeps_exact_key_merged_to_main(self):
        found = self.search([mr("ABC-38: add login"), mr("chore", branch="feat/ABC-38-x"),
                             mr("fix", description="Closes ABC-38.")])
        self.assertEqual([m["matched_in"] for m in found], [["title"], ["source_branch"], ["description"]])

    def test_drops_longer_keys_and_other_targets(self):
        self.assertEqual(self.search([mr("ABC-381 other"), mr("XABC-38"), mr("ABC-38", target="develop")]), [])

    def test_matches_lowercase_branch_but_not_a_longer_prefix(self):
        found = self.search([mr("chore", branch="feat/abc-38-x"), mr("chore", branch="feat/xabc-38")])
        self.assertEqual([m["matched_in"] for m in found], [["source_branch"]])

    def test_reads_every_page_and_skips_archived_filter(self):
        noise = [mr(f"ABC-{n} other") for n in range(380, 480)]
        paths = []

        def fake(path):
            paths.append(path)
            return noise if path.endswith("&page=1") else [mr("ABC-38: the real one")]

        with mock.patch.object(js, "glab_api", side_effect=fake):
            found = js.merged_mrs("ABC-38")
        self.assertEqual([m["title"] for m in found], ["ABC-38: the real one"])
        self.assertEqual(len(paths), 2)
        self.assertTrue(all("non_archived=false" in p for p in paths))

    def test_glab_timeout_body_is_retried_then_raised(self):
        body = done(json.dumps({"message": {"error": "Request timed out"}}))
        with mock.patch.object(js.subprocess, "run", return_value=body) as run:
            with self.assertRaisesRegex(js.CommandError, "timed out"):
                js.glab_api("groups/acme/merge_requests")
        self.assertEqual(run.call_count, js.GLAB_ATTEMPTS)


class Diff(unittest.TestCase):
    def tickets(self):
        return [
            js.ticket(issue("ABC-1"), MINE, ME),
            js.ticket(issue("ABC-2", "Done", "done"), [], ME),
            js.ticket(issue("ABC-3", "Done", "done", email=None), THEIRS, ME),
            js.ticket(issue("ABC-4", email="ann@acme.com"), MINE, ME),
            js.ticket(issue("ABC-5", "Done", "done"), [], ME),
        ]

    def test_buckets(self):
        result = js.diff(self.tickets(), ME, failed=set())
        self.assertEqual(result["merged_not_done"], ["ABC-1", "ABC-4"])
        self.assertEqual(result["done_nothing_merged"], ["ABC-2", "ABC-5"])
        self.assertEqual(result["missing_assignee"], ["ABC-3"])
        self.assertEqual(result["assign_to_me"], ["ABC-4"])

    def test_failed_lookup_is_never_reported_as_nothing_merged(self):
        result = js.diff(self.tickets(), ME, failed={"ABC-2"})
        self.assertEqual(result["done_nothing_merged"], ["ABC-5"])

    def test_ticket_links_jira_and_flags_my_work(self):
        t = js.ticket(issue("ABC-1"), MINE, ME)
        self.assertEqual(t["url"], "https://acme.atlassian.net/browse/ABC-1")
        self.assertTrue(t["merged_by_me"])
        self.assertFalse(t["done"])

    def test_description_mention_is_not_my_work(self):
        mention = [{"author_username": "me", "matched_in": ["description"]}]
        t = js.ticket(issue("ABC-6", email="ann@acme.com"), mention, ME)
        self.assertFalse(t["merged_by_me"])
        self.assertEqual(js.diff([t], ME, failed=set())["assign_to_me"], [])

    def test_assignee_matches_on_account_when_email_is_hidden(self):
        t = js.ticket(issue("ABC-7", email=None, account="acc-me"), MINE, ME)
        self.assertEqual(t["assignee"]["account_id"], "acc-me")
        self.assertEqual(js.diff([t], ME, failed=set())["assign_to_me"], [])

    def test_account_beats_a_matching_email(self):
        t = js.ticket(issue("ABC-8", email="me@acme.com", account="acc-ann"), MINE, ME)
        self.assertEqual(js.diff([t], ME, failed=set())["assign_to_me"], ["ABC-8"])

    def test_falls_back_to_email_without_my_account(self):
        me = {**ME, "account_id": None}
        t = js.ticket(issue("ABC-9", account="acc-x"), MINE, me)
        self.assertEqual(js.diff([t], me, failed=set())["assign_to_me"], [])


class Whoami(unittest.TestCase):
    def test_reads_account_id_from_stdout_without_yaml_switch(self):
        out = json.dumps({"data": {"accountId": "acc-me", "email": "me@acme.com"}})
        with mock.patch.dict(os.environ, {"TWG_AGENT_DEFAULTS": "1"}), \
                mock.patch.object(js.subprocess, "run",
                                  return_value=done(out, stderr="twg: update available\n")) as run:
            self.assertEqual(js.my_account_id(), "acc-me")
        self.assertNotIn("TWG_AGENT_DEFAULTS", run.call_args.kwargs["env"])


class Main(unittest.TestCase):
    def test_refuses_a_parent_that_is_not_an_epic(self):
        with mock.patch.object(sys, "argv", ["jira-sync.py", "ABC-1"]), \
                mock.patch.object(js, "twg_query", return_value=[issue("ABC-1", kind="Story")]):
            with self.assertRaisesRegex(SystemExit, "ABC-1 is a Story, not an Epic"):
                js.main()


if __name__ == "__main__":
    unittest.main()
