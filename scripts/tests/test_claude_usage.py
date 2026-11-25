import tempfile
import unittest
from pathlib import Path

from transcript_fixtures import NOW, assistant, iso, load_script, slash, subagent, tool_result, tool_use, user, write_jsonl

usage = load_script("claude-usage.py")
KNOWN = {"fullsend", "fleet"}
PROJECT = "-work-repo"
OPUS_IN, OPUS_OUT = usage.PRICES["claude-opus-5-5"][:2]


def cost_state(total, started_minutes_ago):
    return {"type": "cost-state", "totalCostUSD": total, "startTime": int((NOW - started_minutes_ago * 60) * 1000)}


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
        self.assertAlmostEqual(out["total_cost"], OPUS_OUT + 10 * OPUS_IN / 1e6)

    def test_resumed_session_copy_is_owned_by_the_earliest_file(self):
        write_jsonl(self.root / PROJECT / "first.jsonl", [user("hi", 60), assistant("m1", 59, out=1_000_000)])
        write_jsonl(self.root / PROJECT / "resumed.jsonl", [
            user("again", 20), assistant("m1", 59, out=1_000_000), assistant("m2", 19, out=0, inp=0),
        ])
        out = analyze(self.root)
        self.assertEqual(out["cross_file_duplicate_message_ids"], 1)
        self.assertAlmostEqual(out["total_cost"], OPUS_OUT + 10 * OPUS_IN / 1e6)
        costs = {s["session"]: s["cost"] for s in out["top_sessions"]}
        self.assertGreater(costs["first"], OPUS_OUT)
        self.assertLess(costs["resumed"], 0.01)

    def test_records_before_the_window_are_ignored(self):
        write_jsonl(self.root / PROJECT / "s1.jsonl", [
            assistant("old", 8 * 24 * 60, out=1_000_000), user("hi", 10), assistant("new", 9, out=0, inp=0),
        ])
        self.assertEqual(analyze(self.root)["by_model"]["claude-opus-5-5"]["requests"], 1)

    def test_first_request_cache_write_is_not_a_cache_miss(self):
        write_jsonl(self.root / PROJECT / "s1.jsonl", [user("hi", 10), assistant("m1", 9, cache_write=50_000)])
        out = analyze(self.root)
        self.assertEqual(out["cache_misses"]["first_request"]["n"], 1)
        self.assertEqual(out["headline"]["cache_miss_cost"], 0)

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


class Subagents(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)

    def tearDown(self):
        self.tmp.cleanup()

    def test_subagent_without_a_main_file_counts_as_orphan_but_its_cost_stays(self):
        subagent(self.root, PROJECT, "gone", "a1", "worker", [user("go", 20), assistant("m1", 19, out=1_000_000)])
        out = analyze(self.root)
        self.assertEqual(out["orphan_subagent_files"], 1)
        self.assertAlmostEqual(out["sub_cost"], OPUS_OUT + 10 * OPUS_IN / 1e6)

    def test_subagent_without_meta_is_typed_unknown(self):
        write_jsonl(self.root / PROJECT / "s1.jsonl", [user("hi", 30), assistant("m1", 29)])
        write_jsonl(self.root / PROJECT / "s1" / "subagents" / "agent-a1.jsonl", [user("go", 20), assistant("m2", 19)])
        self.assertIn("unknown", analyze(self.root)["agents"])


class CostStateCheck(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)

    def tearDown(self):
        self.tmp.cleanup()

    def check(self):
        return analyze(self.root)["cost_state_check"]

    def test_session_started_in_the_window_with_a_final_cost_state_is_compared(self):
        write_jsonl(self.root / PROJECT / "s1.jsonl", [
            user("hi", 3 * 24 * 60), assistant("m1", 3 * 24 * 60 - 1, out=1_000_000),
            cost_state(OPUS_OUT, 3 * 24 * 60 + 1),
        ])
        check = self.check()
        self.assertEqual(check["sessions"], 1)
        self.assertAlmostEqual(check["claude_code"], OPUS_OUT)

    def test_usage_after_the_last_cost_state_excludes_the_session(self):
        write_jsonl(self.root / PROJECT / "s1.jsonl", [
            user("hi", 3 * 24 * 60), cost_state(0.01, 3 * 24 * 60 + 1),
            assistant("m1", 3 * 24 * 60 - 1, out=1_000_000),
        ])
        self.assertEqual(self.check()["sessions"], 0)

    def test_cost_state_started_after_the_first_record_excludes_the_session(self):
        write_jsonl(self.root / PROJECT / "s1.jsonl", [
            user("copied history", 3 * 24 * 60), user("continued", 60), assistant("m1", 59),
            cost_state(OPUS_OUT, 61),
        ])
        self.assertEqual(self.check()["sessions"], 0)

    def test_cost_state_started_before_the_window_excludes_the_session(self):
        write_jsonl(self.root / PROJECT / "s1.jsonl", [
            user("old", 8 * 24 * 60), user("hi", 60), assistant("m1", 59), cost_state(1.0, 8 * 24 * 60 + 1),
        ])
        self.assertEqual(self.check()["sessions"], 0)

    def test_compacted_session_is_excluded(self):
        write_jsonl(self.root / PROJECT / "s1.jsonl", [
            {"type": "system", "subtype": "compact_boundary", "timestamp": iso(60)},
            user("summary of the earlier conversation", 60, isCompactSummary=True), assistant("m1", 59),
            cost_state(30.0, 24 * 60),
        ])
        self.assertEqual(self.check()["sessions"], 0)

    def test_session_with_a_compacted_subagent_is_excluded(self):
        write_jsonl(self.root / PROJECT / "s1.jsonl", [user("hi", 60), assistant("m1", 59), cost_state(30.0, 61)])
        subagent(self.root, PROJECT, "s1", "a1", "worker", [
            {"type": "system", "subtype": "compact_boundary", "timestamp": iso(50)}, assistant("m2", 49),
        ])
        self.assertEqual(self.check()["sessions"], 0)


class Helpers(unittest.TestCase):
    def test_bash_head_skips_setup_and_keeps_subcommand(self):
        head = usage.tr.bash_head
        self.assertEqual(head("cd /x && git status --short"), "git status")
        self.assertEqual(head("FOO=1 pytest -q"), "pytest")
        self.assertEqual(head("S=/home/me/x; f=$(ls a b); git -C /repo log"), "git")
        self.assertEqual(usage.tool_key("Bash", {"command": "TILE=3x2 pnpm exec vitest"}), "Bash: pnpm exec vitest")

    def test_uncovered_len_subtracts_busy_time(self):
        self.assertEqual(usage.uncovered_len([(0, 10)], [(2, 4), (6, 7)]), 7)

    def test_haiku_long_prompt_uses_long_context_price(self):
        req = {"model": "claude-haiku-5-5", "ctx": 200_000, "inp": 1_000_000, "out": 0, "cr": 0, "cw5": 0, "cw1": 0}
        self.assertAlmostEqual(usage.cost_of(req), usage.HAIKU_LONG[0])


if __name__ == "__main__":
    unittest.main()
