import tempfile
import unittest
from pathlib import Path

from transcript_fixtures import NOW, assistant, load_script, slash, subagent, tool_result, tool_use, user, write_jsonl

usage = load_script("claude-usage.py")
KNOWN = {"fullsend", "fleet"}
PROJECT = "-work-repo"


def analyze(root, days=7):
    return usage.analyze(str(root), days, now=NOW, known=KNOWN)


class Deduplication(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)

    def tearDown(self):
        self.tmp.cleanup()

    def test_streamed_repeats_of_one_message_count_once_with_the_final_usage(self):
        write_jsonl(self.root / PROJECT / "s1.jsonl", [
            user("hi", 30),
            assistant("m1", 29, out=5),
            assistant("m1", 29, out=1_000_000),
        ])
        out = analyze(self.root)
        self.assertEqual(out["by_model"]["claude-opus-5-5"]["requests"], 1)
        self.assertEqual(out["by_model"]["claude-opus-5-5"]["out"], 1_000_000)
        self.assertAlmostEqual(out["total_cost"], 20.0 + 10 * 4.0 / 1e6)

    def test_resumed_session_copy_is_owned_by_the_earliest_file(self):
        write_jsonl(self.root / PROJECT / "first.jsonl", [user("hi", 60), assistant("m1", 59, out=1_000_000)])
        write_jsonl(self.root / PROJECT / "resumed.jsonl", [
            user("again", 20), assistant("m1", 59, out=1_000_000), assistant("m2", 19, out=0, inp=0),
        ])
        out = analyze(self.root)
        self.assertEqual(out["cross_file_duplicate_message_ids"], 1)
        self.assertAlmostEqual(out["total_cost"], 20.0 + 10 * 4.0 / 1e6)
        costs = {s["session"]: s["cost"] for s in out["top_sessions"]}
        self.assertGreater(costs["first"], 20)
        self.assertLess(costs["resumed"], 0.01)

    def test_records_before_the_window_are_ignored(self):
        write_jsonl(self.root / PROJECT / "s1.jsonl", [
            assistant("old", 8 * 24 * 60, out=1_000_000), user("hi", 10), assistant("new", 9, out=0, inp=0),
        ])
        self.assertEqual(analyze(self.root)["by_model"]["claude-opus-5-5"]["requests"], 1)

    def test_unknown_model_is_reported_not_priced(self):
        write_jsonl(self.root / PROJECT / "s1.jsonl", [user("hi", 10), assistant("m1", 9, model="claude-new-9")])
        out = analyze(self.root)
        self.assertEqual(out["unpriced_requests"], {"claude-new-9": 1})
        self.assertEqual(out["total_cost"], 0)


class SessionAttribution(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)

    def tearDown(self):
        self.tmp.cleanup()

    def test_session_and_its_subagents_belong_to_the_first_slash_command(self):
        write_jsonl(self.root / PROJECT / "s1.jsonl", [
            slash("fullsend", 60),
            assistant("m1", 59, content=[tool_use("t1", "Agent", subagent_type="worker", prompt="do it")]),
            tool_result("t1", "done", 40),
            assistant("m2", 39, content=[tool_use("t2", "Skill", skill="fleet")]),
        ])
        subagent(self.root, PROJECT, "s1", "a1", "worker", [user("do it", 58), assistant("m3", 50, out=1_000_000)])
        out = analyze(self.root)
        self.assertEqual(list(out["commands"]), ["fullsend"])
        self.assertEqual(out["command_invocations_all"], {"fullsend": 1, "fleet": 1})
        self.assertAlmostEqual(out["commands"]["fullsend"]["total_cost"], out["total_cost"])
        self.assertGreater(out["commands"]["fullsend"]["sub_share"], 0.99)
        self.assertEqual(out["agents"]["worker"]["runs"], 1)

    def test_dispatched_worker_is_tagged(self):
        write_jsonl(self.root / PROJECT / "s1.jsonl", [
            user("You are a dispatched worker. Task ID: 1", 30), slash("fullsend", 29), assistant("m1", 28),
        ])
        self.assertIn("fullsend[fleet-worker]", analyze(self.root)["commands"])

    def test_session_without_a_command_is_grouped_as_none(self):
        write_jsonl(self.root / PROJECT / "s1.jsonl", [user("hi", 30), assistant("m1", 29)])
        self.assertIn("(none)", analyze(self.root)["commands"])


class Helpers(unittest.TestCase):
    def test_bash_key_drops_cd_prefix_and_keeps_subcommand(self):
        self.assertEqual(usage.bash_key("cd /x && git status --short"), "git status")
        self.assertEqual(usage.bash_key("FOO=1 pytest -q"), "pytest")

    def test_uncovered_len_subtracts_busy_time(self):
        self.assertEqual(usage.uncovered_len([(0, 10)], [(2, 4), (6, 7)]), 7)

    def test_haiku_long_prompt_uses_long_context_price(self):
        req = {"model": "claude-haiku-5-5", "ctx": 200_000, "inp": 1_000_000, "out": 0, "cr": 0, "cw5": 0, "cw1": 0}
        self.assertAlmostEqual(usage.cost_of(req), 0.50)


if __name__ == "__main__":
    unittest.main()
