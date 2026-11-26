import json
import os
import tempfile
import unittest
from pathlib import Path

from transcript_fixtures import (NOW, StubRevs, assistant, load_script, slash, subagent, tool_result, tool_use, user,
                                 write_jsonl)

friction = load_script("session-friction.py")
KNOWN = {"fullsend", "locallensedreview", "fleet"}
PROJECT = "-work-repo"
FAKE_TOKEN = "glpat-" + "x" * 24
FAKE_KEY_BODY = "Q" * 64
FAKE_PRIVATE_KEY = ("-----BEGIN RSA PRIVATE KEY-----\n" + FAKE_KEY_BODY + "\n-----END RSA PRIVATE KEY-----")
FAKE_SECRETS = {
    "github token": "github_pat_" + "a" * 30,
    "openai key": "sk-svcacct-" + "b" * 30,
    "google key": "AIza" + "c" * 35,
    "jwt": "eyJ" + "d" * 12 + ".eyJ" + "e" * 12 + "." + "f" * 10,
    "bearer token": "Bearer " + "g" * 28 + "42",
}


def text(msg_id, minutes_ago, body):
    return assistant(msg_id, minutes_ago, content=[{"type": "text", "text": body}])


class Extracts(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)

    def tearDown(self):
        self.tmp.cleanup()

    def analyze(self, **kw):
        kw.setdefault("revs", StubRevs())
        return friction.analyze(str(self.root), 7, now=NOW, known=KNOWN, **kw)

    def only_session(self, **kw):
        sessions = self.analyze(**kw)["sessions"]
        self.assertEqual(len(sessions), 1)
        return sessions[0]

    def test_human_messages_after_the_first_skip_system_and_agent_text(self):
        write_jsonl(self.root / PROJECT / "s1.jsonl", [
            slash("fullsend", 60),
            user("<task-notification><result>done</result></task-notification>", 55),
            user("Another Claude session sent a message: hi", 54),
            user("skill body", 53, isMeta=True),
            user("\u2500\u2500\u2500\u2500 From: worker-2 \u2500\u2500\u2500\u2500\nstage 3 done", 52),
            user("<command-message>fleet</command-message>\n<command-name>/fleet</command-name>", 51),
            user("no, keep the old name", 50),
            user("[Request interrupted by user]", 40),
        ])
        s = self.only_session()
        self.assertEqual([h["text"] for h in s["humans"]], ["no, keep the old name", "[interrupted]"])
        self.assertEqual(s["interrupts"], 1)
        self.assertEqual(s["command"], "fullsend")

    def test_tool_errors_are_counted_by_kind_across_main_and_subagents(self):
        failing = [
            assistant("m1", 50, content=[tool_use("t1", "Bash", command="cd /x && pnpm test --run")]),
            tool_result("t1", "Exit code 1\nFAIL 3 tests", 49, is_error=True),
        ]
        write_jsonl(self.root / PROJECT / "s1.jsonl", [slash("fullsend", 60)] + failing)
        subagent(self.root, PROJECT, "s1", "a1", "worker", [user("brief", 48)] + [
            assistant("m2", 47, content=[tool_use("t2", "Bash", command="pnpm test")]),
            tool_result("t2", "Exit code 2", 46, is_error=True),
        ])
        out = self.analyze()
        self.assertEqual(out["tool_errors"][0]["kind"], "Bash: exit nonzero [pnpm test]")
        self.assertEqual(out["tool_errors"][0]["count"], 2)
        self.assertEqual(out["tool_errors"][0]["sessions"], 1)
        self.assertEqual(out["sessions"][0]["tool_errors"], 2)

    def analyze_errors(self, commands):
        rows = [slash("fullsend", 60)]
        for i, cmd in enumerate(commands):
            rows += [assistant(f"m{i}", 50, content=[tool_use(f"t{i}", "Bash", command=cmd)]),
                     tool_result(f"t{i}", "Exit code 1", 49, is_error=True)]
        write_jsonl(self.root / PROJECT / "s1.jsonl", rows)
        return self.analyze()

    def test_error_kind_names_the_command_after_a_cd(self):
        out = self.analyze_errors(["cd /x; glab mr view 1", "TILE=3x2 S=/home/me/x; f=$(ls a b); grep -r foo",
                                   "playwright-cli -s=abc click e1", "S=(playwright-cli -s=feat-1 open x) && -s=feat-1 click",
                                   "A=(a b); echo ok"])
        self.assertEqual(sorted(e["kind"] for e in out["tool_errors"]),
                         sorted(["Bash: exit nonzero [glab mr view]", "Bash: exit nonzero [grep]",
                          "Bash: exit nonzero [playwright-cli click]", "Bash: exit nonzero [(unparsed)]",
                          "Bash: exit nonzero [echo]"]))
        self.assertNotIn("/home/me", str(out["tool_errors_by_command"]))

    def test_subagent_brief_and_report_are_cut_short_and_findings_counted(self):
        write_jsonl(self.root / PROJECT / "s1.jsonl", [slash("locallensedreview", 60)])
        report = "Findings:\n- [8/10] null deref\n- [5/10] naming " + "x" * 500
        subagent(self.root, PROJECT, "s1", "a1", "reviewer", [
            user("Review the diff " + "y" * 500, 58),
            assistant("m1", 50, content=[tool_use("h1", "SubagentHandback", message=report)]),
        ], description="correctness lens")
        agent = self.only_session(clip_n=100)["agents"][0]
        self.assertEqual(agent["type"], "reviewer")
        self.assertEqual(agent["findings"], 2)
        self.assertEqual(agent["report_chars"], len(report))
        self.assertLessEqual(len(agent["brief"]), 103)

    def test_review_table_keeps_the_findings_that_survived(self):
        table = "| # | Score | Lens | Finding |\n|---|---|---|---|\n| 1 | 8/10 | correctness | x |\n| 2 | 7/10 | test-health | y |"
        write_jsonl(self.root / PROJECT / "s1.jsonl", [slash("locallensedreview", 60), text("m1", 50, table)])
        tables = self.only_session()["review_tables"]
        self.assertEqual(tables[0]["kept"], [{"score": 8.0, "lens": "correctness"}, {"score": 7.0, "lens": "test-health"}])

    def test_secret_is_reported_by_session_and_kind_and_redacted_from_extracts(self):
        write_jsonl(self.root / PROJECT / "s1.jsonl", [
            slash("fullsend", 60), user(f"use token {FAKE_TOKEN} please", 50),
        ])
        out = self.analyze()
        self.assertEqual(out["secrets"], [{"session": "s1", "date": "2026-06-15", "kind": "gitlab token", "count": 1}])
        self.assertNotIn(FAKE_TOKEN, str(out))

    def test_pushback_and_rework_come_only_from_what_the_human_typed(self):
        reminder = [{"type": "text", "text": "that finding is a false positive"},
                    {"type": "text", "text": "<system-reminder>the pipeline failed on main</system-reminder>"}]
        write_jsonl(self.root / PROJECT / "s1.jsonl", [
            slash("fullsend", 60),
            text("m1", 59, "Declined finding 2: false positive. The pipeline failed once, verify failed too."),
            user("Base directory for this skill: x\nreview missed things are noise", 58),
            assistant("m2", 57, content=[tool_use("t1", "Bash", command="glab ci status")]),
            tool_result("t1", "job lint failed; pipeline failed", 56),
            user(reminder, 55),
            user("the pipeline failed again, look", 54),
        ])
        s = self.only_session()
        self.assertEqual(len(s["review_pushback"]), 1)
        self.assertIn("false positive", s["review_pushback"][0])
        self.assertEqual(len(s["rework"]), 1)
        self.assertIn("failed again", s["rework"][0])

    def test_dispatched_preamble_is_the_first_message_but_not_human_text(self):
        write_jsonl(self.root / PROJECT / "s1.jsonl", [
            user("You are working inside Orca. You are a dispatched worker. Declined findings are noise.", 60),
            slash("fullsend", 59),
            user("not that branch", 50),
        ])
        s = self.only_session()
        self.assertEqual([h["text"] for h in s["humans"]], ["not that branch"])
        self.assertEqual(s["review_pushback"], [])

    def test_command_filter_keeps_sessions_whose_first_command_matches(self):
        write_jsonl(self.root / PROJECT / "s1.jsonl", [slash("fleet", 60), slash("fullsend", 59)])
        write_jsonl(self.root / PROJECT / "s2.jsonl", [slash("fullsend", 60)])
        self.assertEqual([s["session"] for s in self.analyze(wanted=["fullsend"])["sessions"]], ["s2"])

    def test_code_review_started_by_locallensedreview_counts_as_it(self):
        write_jsonl(self.root / PROJECT / "s1.jsonl", [user("/code-review high", 60), user("thanks", 50)])
        self.assertEqual(self.only_session()["command"], "locallensedreview")

    def test_implied_commands_and_orca_workers_are_in_scope_by_default(self):
        write_jsonl(self.root / PROJECT / "s1.jsonl", [user("Read `~/llmfiles/opencode/fullconduct.md`, then fix x", 60)])
        write_jsonl(self.root / PROJECT / "s2.jsonl", [user("You are a dispatched worker. Task ID: 1\ntidy x", 60)])
        out = self.analyze()
        self.assertEqual(out["sessions_by_command"], {"fullconduct": 1, "orca-worker": 1})

    def test_a_session_resumed_into_the_period_keeps_the_command_its_first_prompt_implies(self):
        old = 8 * 24 * 60
        write_jsonl(self.root / PROJECT / "s1.jsonl", [
            user("Read `~/llmfiles/opencode/fullconduct.md`, then fix x", old), user("go on", 30)])
        self.assertEqual(self.only_session()["command"], "fullconduct")

    def test_a_session_names_the_setup_it_started_on(self):
        write_jsonl(self.root / PROJECT / "s1.jsonl", [slash("fullsend", 90), user("go on", 30)])
        s = friction.analyze(str(self.root), 7, now=NOW, known=KNOWN, revs=StubRevs(60))["sessions"][0]
        self.assertEqual(s["setup_rev"], "early")

    def test_session_without_a_known_command_is_out_of_scope(self):
        write_jsonl(self.root / PROJECT / "s1.jsonl", [user("hi", 60), user("again", 50)])
        self.assertEqual(self.analyze()["sessions"], [])

    def test_sessions_outside_any_command_are_listed_by_first_prompt(self):
        write_jsonl(self.root / PROJECT / "s1.jsonl", [
            user("recap what landed in tosti this week", 60), user("no, only the merged ones", 50),
        ])
        write_jsonl(self.root / PROJECT / "s2.jsonl", [user("Name this chat", 60, entrypoint="sdk-cli")])
        out = self.analyze()
        self.assertEqual(out["sessions"], [])
        outside = out["outside_commands"]
        self.assertEqual(outside["programmatic"], 1)
        self.assertEqual([(r["session"], r["first"], r["follow_ups"], r["redirects"]) for r in outside["sessions"]],
                         [("s1", "recap what landed in tosti this week", 1, 1)])
        self.assertEqual(outside["redirects"]["negation"], 1)

    def test_prompts_a_program_wrote_are_not_a_person_working(self):
        write_jsonl(self.root / PROJECT / "s1.jsonl", [
            user("You are a subagent spawned by another session. Fix x", 60),
            user('<subagent sessionID="ses_1" state="completed" description="d">PASSED</subagent>', 50),
        ])
        write_jsonl(self.root / PROJECT / "s2.jsonl", [
            user("tidy the readme", 60),
            user('<subagent sessionID="ses_2" state="completed" description="d">PASSED</subagent>', 50),
        ])
        write_jsonl(self.root / "-claude-runtime-x-scratchpad" / "s3.jsonl", [user("reply with the single word ok", 60)])
        outside = self.analyze()["outside_commands"]
        self.assertEqual(outside["programmatic"], 2)
        self.assertEqual([(r["session"], r["follow_ups"]) for r in outside["sessions"]], [("s2", 0)])

    def test_phrases_typed_in_four_sessions_are_counted_once_per_session(self):
        for n in range(4):
            write_jsonl(self.root / PROJECT / f"s{n}.jsonl", [
                slash("fullsend", 60), user(f"fix bug {n}, then ship to main", 50), user("ship to main", 40),
            ])
        write_jsonl(self.root / PROJECT / "s9.jsonl", [user("make it super short", 60, entrypoint="cli")])
        phrases = {p["phrase"]: p["sessions"] for p in self.analyze()["retyped_phrases"]}
        self.assertEqual(phrases.get("ship to main"), 4)
        self.assertNotIn("to main", phrases)
        self.assertNotIn("super short", phrases)

    def test_a_token_typed_in_four_sessions_is_not_a_retyped_phrase(self):
        bearer = FAKE_SECRETS["bearer token"]
        for n in range(4):
            write_jsonl(self.root / PROJECT / f"s{n}.jsonl", [
                user(f"<command-name>/fullsend</command-name>\n<command-args>use {FAKE_TOKEN} now</command-args>", 60),
                user(f"call the api with {bearer} then retry", 50),
            ])
        phrases = " | ".join(p["phrase"] for p in self.analyze()["retyped_phrases"])
        self.assertIn("call the api", phrases)
        for leak in ("redacted", "glpat", "ggg", "bearer"):
            self.assertNotIn(leak, phrases)

    def test_waiting_or_checking_is_not_a_redirect(self):
        for n, follow_up in enumerate(["waiting for CI", "just checking", "nope, use the other file",
                                       "just use the other file"]):
            write_jsonl(self.root / PROJECT / f"s{n}.jsonl", [
                user(f"recap what landed in repo {n}", 60), user(follow_up, 50),
            ])
        redirects = self.analyze()["outside_commands"]["redirects"]
        self.assertEqual(redirects, {"negation": 1, "scope": 1})

    def test_timeline_orders_human_assistant_and_error_events(self):
        write_jsonl(self.root / PROJECT / "abc123.jsonl", [
            user("fix the bug", 60),
            assistant("m1", 59, content=[{"type": "text", "text": "looking"}, tool_use("t1", "Read", file_path="/x")]),
            tool_result("t1", "File does not exist", 58, is_error=True),
            user("try again", 50),
        ])
        events = friction.timeline(str(self.root), "abc")["events"]
        self.assertEqual([e["kind"] for e in events], ["human", "error [Read]", "assistant", "human"])



class Secrets(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)

    def tearDown(self):
        self.tmp.cleanup()

    def analyze(self, **kw):
        kw.setdefault("revs", StubRevs())
        return friction.analyze(str(self.root), 7, now=NOW, known=KNOWN, **kw)

    def kinds(self, out):
        return {s["kind"]: s["count"] for s in out["secrets"]}

    def test_secret_in_an_error_message_or_command_stays_out_of_error_output(self):
        write_jsonl(self.root / PROJECT / "s1.jsonl", [
            slash("fullsend", 60),
            assistant("m1", 50, content=[tool_use("t1", "Bash", command=f"GITLAB_TOKEN={FAKE_TOKEN} glab mr list")]),
            tool_result("t1", f"Exit code 1\n401 for token {FAKE_TOKEN}", 49, is_error=True),
            assistant("m2", 48, content=[tool_use("t2", "Bash", command="glab api")]),
            tool_result("t2", f"Reason: [{FAKE_TOKEN}] blocked", 47, is_error=True),
        ])
        out = self.analyze()
        self.assertEqual(self.kinds(out), {"gitlab token": 3})
        self.assertNotIn("glpat-", json.dumps(out))

    def test_private_key_body_is_redacted_with_its_header(self):
        write_jsonl(self.root / PROJECT / "s1.jsonl", [
            slash("fullsend", 60), user("deploy key: " + FAKE_PRIVATE_KEY + " thanks", 50),
            user("half a key: -----BEGIN PRIVATE KEY-----\n" + FAKE_KEY_BODY, 40),
        ])
        out = self.analyze()
        self.assertEqual(self.kinds(out), {"private key": 2})
        self.assertNotIn(FAKE_KEY_BODY[:20], json.dumps(out))

    def test_secret_cut_at_a_snippet_edge_does_not_leak_its_tail(self):
        body = "w" * 150 + FAKE_TOKEN + " " + "z" * 140 + " is a false positive"
        write_jsonl(self.root / PROJECT / "s1.jsonl", [slash("fullsend", 60), user(body, 50)])
        out = self.analyze()
        self.assertTrue(out["sessions"][0]["review_pushback"])
        self.assertNotIn("x" * 12, json.dumps(out["sessions"][0]["review_pushback"]))

    def test_every_secret_kind_is_detected_and_redacted(self):
        write_jsonl(self.root / PROJECT / "s1.jsonl", [slash("fullsend", 60)] + [
            user(f"value {value} here", 50 - i) for i, value in enumerate(FAKE_SECRETS.values())
        ])
        out = self.analyze()
        self.assertEqual(self.kinds(out), {k: 1 for k in FAKE_SECRETS})
        for value in FAKE_SECRETS.values():
            self.assertNotIn(value, json.dumps(out))

    def test_prose_that_looks_like_a_key_prefix_is_not_a_secret(self):
        write_jsonl(self.root / PROJECT / "s1.jsonl", [
            slash("fullsend", 60), user("see task-notification-handler-for-the-queue and disk-usage-report-weekly-x", 50),
            user("send Authorization: Bearer token-from-the-environment", 49),
        ])
        self.assertEqual(self.analyze()["secrets"], [])

    def test_home_directory_is_shortened_in_extracts(self):
        home = os.path.expanduser("~")
        write_jsonl(self.root / PROJECT / "s1.jsonl", [
            slash("fullsend", 60), user(f"open {home}/notes.md", 50),
        ])
        self.assertEqual(self.analyze()["sessions"][0]["humans"][0]["text"], "open ~/notes.md")

    def test_secrets_in_subagent_brief_report_and_timeline_are_counted_never_shown(self):
        write_jsonl(self.root / PROJECT / "s1.jsonl", [
            slash("fullsend", 60),
            assistant("m1", 55, content=[tool_use("t1", "Agent", subagent_type="worker", description="go",
                                                  prompt=f"use {FAKE_TOKEN}")]),
            tool_result("t1", f"done with {FAKE_TOKEN}", 40),
        ])
        subagent(self.root, PROJECT, "s1", "a1", "worker", [
            user(f"use {FAKE_TOKEN}", 54),
            assistant("m2", 45, content=[tool_use("h1", "SubagentHandback", message=f"done with {FAKE_TOKEN}")]),
        ])
        out = self.analyze()
        self.assertEqual(self.kinds(out), {"gitlab token": 4})
        timeline = friction.timeline(str(self.root), "s1")
        self.assertNotIn("glpat-", json.dumps(out) + json.dumps(timeline))
        self.assertIn("agent report", [e["kind"] for e in timeline["events"]])

    def test_errors_and_secrets_before_the_window_are_not_reported_again(self):
        old = 8 * 24 * 60
        write_jsonl(self.root / PROJECT / "s1.jsonl", [
            slash("fullsend", old), user(f"token {FAKE_TOKEN}", old - 1),
            assistant("m1", old - 2, content=[tool_use("t1", "Bash", command="pnpm test")]),
            tool_result("t1", "Exit code 1", old - 3, is_error=True),
            user("still here", 10),
        ])
        out = self.analyze()
        self.assertEqual(out["secrets"], [])
        self.assertEqual(out["tool_errors"], [])
        self.assertEqual(len(out["sessions"]), 1)


if __name__ == "__main__":
    unittest.main()
