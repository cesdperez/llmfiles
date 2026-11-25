import tempfile
import unittest
from pathlib import Path

from transcript_fixtures import (NOW, assistant, load_script, slash, subagent, tool_result, tool_use, user,
                                 write_jsonl)

friction = load_script("session-friction.py")
KNOWN = {"fullsend", "locallensedreview", "fleet"}
PROJECT = "-work-repo"
FAKE_TOKEN = "glpat-" + "x" * 24


def text(msg_id, minutes_ago, body):
    return assistant(msg_id, minutes_ago, content=[{"type": "text", "text": body}])


class Extracts(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)

    def tearDown(self):
        self.tmp.cleanup()

    def analyze(self, **kw):
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

    def test_error_kind_names_the_command_after_a_cd(self):
        self.assertEqual(friction.command_head("cd /x; glab mr view 1"), "glab mr")
        self.assertEqual(friction.command_head("cd /x\ngrep -r foo"), "grep")

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

    def test_command_filter_keeps_sessions_whose_first_command_matches(self):
        write_jsonl(self.root / PROJECT / "s1.jsonl", [slash("fleet", 60), slash("fullsend", 59)])
        write_jsonl(self.root / PROJECT / "s2.jsonl", [slash("fullsend", 60)])
        self.assertEqual([s["session"] for s in self.analyze(wanted=["fullsend"])["sessions"]], ["s2"])

    def test_session_without_a_known_command_is_out_of_scope(self):
        write_jsonl(self.root / PROJECT / "s1.jsonl", [user("hi", 60), user("again", 50)])
        self.assertEqual(self.analyze()["sessions"], [])

    def test_timeline_orders_human_assistant_and_error_events(self):
        write_jsonl(self.root / PROJECT / "abc123.jsonl", [
            user("fix the bug", 60),
            assistant("m1", 59, content=[{"type": "text", "text": "looking"}, tool_use("t1", "Read", file_path="/x")]),
            tool_result("t1", "File does not exist", 58, is_error=True),
            user("try again", 50),
        ])
        events = friction.timeline(str(self.root), "abc")["events"]
        self.assertEqual([e["kind"] for e in events], ["human", "error [Read]", "assistant", "human"])


if __name__ == "__main__":
    unittest.main()
