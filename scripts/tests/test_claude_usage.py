import tempfile
import unittest
from pathlib import Path

from transcript_fixtures import (NOW, StubRevs, assistant, iso, load_script, slash, subagent, tool_result, tool_use, user,
                                 write_jsonl)

usage = load_script("claude-usage.py")
KNOWN = {"fullsend", "fleet"}
PROJECT = "-work-repo"
OPUS_IN, OPUS_OUT = usage.PRICES["claude-opus-5-5"][:2]


def cost_state(total, started_minutes_ago):
    return {"type": "cost-state", "totalCostUSD": total, "startTime": int((NOW - started_minutes_ago * 60) * 1000)}


def analyze(root, days=7, revs=None):
    return usage.analyze(str(root), days, now=NOW, known=KNOWN, revs=revs or StubRevs())


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

    def test_a_token_in_the_first_prompt_is_redacted_from_the_report(self):
        token = "glpat-" + "x" * 200
        write_jsonl(self.root / PROJECT / "s1.jsonl", [user(f"push with {token} please", 30), assistant("m1", 29)])
        top = analyze(self.root)["no_command_sessions"]["top"]
        self.assertEqual(top[0]["first_user"], "push with [gitlab token redacted] please")

    def test_each_session_names_the_setup_it_started_on_even_before_the_window(self):
        write_jsonl(self.root / PROJECT / "s1.jsonl", [slash("fullsend", 30), assistant("m1", 29)])
        write_jsonl(self.root / PROJECT / "s2.jsonl", [user("hi", 60 * 24 * 10), user("again", 20), assistant("m2", 19)])
        out = usage.analyze(str(self.root), 7, now=NOW, known=KNOWN, revs=StubRevs(60))
        self.assertEqual({s["session"]: s["setup_rev"] for s in out["top_sessions"]}, {"s1": "late", "s2": "early"})

    def primary_of(self, *first_rows):
        write_jsonl(self.root / PROJECT / "s1.jsonl", [*first_rows, assistant("m1", 20)])
        return list(analyze(self.root)["commands"])

    def test_conductor_prompt_counts_as_fullconduct(self):
        prompt = [{"type": "text", "text": "Read `~/llmfiles/opencode/fullconduct.md`, then `~/llmfiles/commands/"
                                           "fullsend.md`, and run it with these arguments:\n\nfix x"}]
        self.assertEqual(self.primary_of(user(prompt, 30)), ["fullconduct"])

    def test_branch_name_helper_quoting_the_conductor_prompt_stays_none(self):
        prompt = "Generate a short git branch name.\n\nUser request:\nRead `~/llmfiles/opencode/fullconduct.md`"
        self.assertEqual(self.primary_of(user(prompt, 30)), ["(none)"])

    def test_code_review_started_by_locallensedreview_counts_as_it(self):
        caveat = user("<local-command-caveat>The command below was run directly</local-command-caveat>", 31, isMeta=True)
        self.assertEqual(self.primary_of(caveat, user("/code-review high", 30)), ["locallensedreview"])

    def test_a_reminder_before_the_conductor_prompt_does_not_hide_it(self):
        prompt = [{"type": "text", "text": "<system-reminder>ctx</system-reminder>"},
                  {"type": "text", "text": "Read `~/llmfiles/opencode/fullconduct.md`, then fix x"}]
        self.assertEqual(self.primary_of(user(prompt, 30)), ["fullconduct"])

    def test_a_session_starts_at_its_first_record_of_any_type(self):
        write_jsonl(self.root / PROJECT / "s1.jsonl", [
            {"type": "queue-operation", "timestamp": iso(90)}, slash("fullsend", 30), assistant("m1", 29)])
        self.assertEqual(analyze(self.root, revs=StubRevs(60))["top_sessions"][0]["setup_rev"], "early")

    def test_a_session_resumed_into_the_period_keeps_the_command_its_first_prompt_implies(self):
        self.assertEqual(self.primary_of(user("Read `~/llmfiles/opencode/fullconduct.md`, then fix x", 8 * 24 * 60),
                                         user("go on", 30)), ["fullconduct"])

    def test_dispatched_worker_without_a_command_is_an_orca_worker(self):
        preamble = "You are working inside Orca, a multi-agent IDE. You are a dispatched worker.\nTask: tidy x"
        self.assertEqual(self.primary_of(user(preamble, 30)), ["orca-worker"])

    def test_dispatched_worker_that_loads_a_command_skill_counts_as_that_command(self):
        preamble = "You are working inside Orca, a multi-agent IDE. You are a dispatched worker.\nRun /fullsend"
        skill = assistant("m0", 29, content=[tool_use("t1", "Skill", skill="fullsend")])
        self.assertEqual(self.primary_of(user(preamble, 30), skill), ["fullsend[fleet-worker]"])


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


def attachment(kind, minutes_ago, **fields):
    return {"type": "attachment", "timestamp": iso(minutes_ago), "attachment": {"type": kind, **fields}}


class BaseContext(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)

    def tearDown(self):
        self.tmp.cleanup()

    def test_first_request_context_is_reported_per_agent_type(self):
        write_jsonl(self.root / PROJECT / "s1.jsonl", [
            user("hi", 60), assistant("m1", 59, cache_write=30_000), assistant("m2", 58, cache_read=90_000),
        ])
        subagent(self.root, PROJECT, "s1", "a1", "worker", [user("go", 50), assistant("m3", 49, inp=0, cache_write=40_000)])
        first = analyze(self.root)["base_context"]["first_request_ctx"]
        self.assertEqual(first["main"]["median"], 30_010)
        self.assertEqual(first["worker"], {"runs": 1, "median": 40_000, "p90": 40_000})

    def test_a_session_with_usage_before_the_window_has_no_first_request(self):
        write_jsonl(self.root / PROJECT / "s1.jsonl", [user("hi", 60), assistant("m1", 59, inp=0, cache_write=30_000)])
        write_jsonl(self.root / PROJECT / "s2.jsonl", [
            assistant("old", 8 * 24 * 60, inp=0, cache_write=20_000), user("again", 10),
            assistant("m2", 9, inp=0, cache_read=150_000),
        ])
        self.assertEqual(analyze(self.root)["base_context"]["first_request_ctx"]["main"]["runs"], 1)

    def test_skills_listed_are_compared_with_skills_invoked(self):
        listing = "- fleet: run items\n- glab-cli: GitLab CLI\n- figma:figma-use: Figma"
        write_jsonl(self.root / PROJECT / "s1.jsonl", [
            attachment("skill_listing", 60, content=listing),
            user("hi", 59),
            assistant("m1", 58, content=[tool_use("t1", "Skill", skill="glab-cli"), tool_use("t2", "Skill", skill="figma:figma-use")]),
        ])
        skills = analyze(self.root)["base_context"]["skills"]
        self.assertEqual(skills["listed"], 3)
        self.assertEqual(skills["invoked"], {"glab-cli": 1, "figma:figma-use": 1})
        self.assertEqual(skills["listed_never_invoked"], ["fleet"])
        self.assertEqual(analyze(self.root)["base_context"]["plugin_calls"], {"figma": 1})

    def test_mcp_calls_are_counted_by_server_and_sessions_by_project(self):
        write_jsonl(self.root / PROJECT / "s1.jsonl", [
            user("hi", 60),
            assistant("m1", 59, content=[tool_use("t1", "mcp__claude_ai_Slack__slack_send_message", text="x")]),
        ])
        write_jsonl(self.root / "-other" / "s2.jsonl", [user("hi", 60), assistant("m2", 59)])
        base = analyze(self.root)["base_context"]
        self.assertEqual(base["mcp_calls_by_server"], {"claude_ai_Slack": 1})
        self.assertEqual({k: v["sessions"] for k, v in base["sessions_by_project"].items()}, {"-work-repo": 1, "-other": 1})


class CommandEconomics(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)

    def tearDown(self):
        self.tmp.cleanup()

    def test_the_command_with_the_largest_spend_is_broken_down(self):
        write_jsonl(self.root / PROJECT / "s1.jsonl", [
            slash("fullsend", 120),
            assistant("m1", 119, content=[tool_use("t1", "Bash", command="git diff --shortstat origin/main...")]),
            tool_result("t1", " 3 files changed, 40 insertions(+), 20 deletions(-)", 118),
            assistant("m2", 100, content=[tool_use("t2", "Bash", command="cd /repo && glab mr create --draft")]),
            tool_result("t2", "https://gitlab.example.com/g/r/-/merge_requests/7", 99),
            assistant("m3", 98, out=10),
            user("now rebase it", 68),
            assistant("m4", 67, out=10),
        ])
        subagent(self.root, PROJECT, "s1", "a1", "reviewer", [user("review", 110), assistant("m5", 109, out=1_000_000)])
        write_jsonl(self.root / PROJECT / "s2.jsonl", [
            user("You are a dispatched worker. Task ID: 2", 60), slash("fullsend", 59),
            assistant("m6", 58, content=[tool_use("t3", "Bash", command="git push -u origin HEAD")]),
            tool_result("t3", "ok", 57),
        ])
        write_jsonl(self.root / PROJECT / "s3.jsonl", [slash("fleet", 30), assistant("m7", 29)])
        econ = analyze(self.root)["command_economics"]
        self.assertEqual(econ["command"], "fullsend")
        self.assertEqual(econ["sessions"], 2)
        self.assertGreater(econ["cost_by_role"]["reviewer"], econ["cost_by_role"]["main"])
        self.assertEqual({k: v["sessions"] for k, v in econ["by_change_size"].items()}, {"51-200": 1, "unknown": 1})
        self.assertAlmostEqual(econ["wait_min"], 30)
        self.assertEqual(econ["human_turns"], 1)
        self.assertEqual(econ["outcomes"], {"mr_created": 1, "pushed": 1, "neither": 0})

    def test_consecutive_human_messages_wait_only_on_the_assistant_turn_before_them(self):
        write_jsonl(self.root / PROJECT / "s1.jsonl", [
            slash("fullsend", 120), assistant("m1", 119), user("are you there", 89), user("hello?", 79),
            assistant("m2", 78),
        ])
        econ = analyze(self.root)["command_economics"]
        self.assertAlmostEqual(econ["wait_min"], 30)
        self.assertAlmostEqual(econ["work_min"], 42 - 30)

    def test_a_failed_or_unanswered_mr_create_or_push_is_no_outcome(self):
        write_jsonl(self.root / PROJECT / "s1.jsonl", [
            slash("fullsend", 60),
            assistant("m1", 59, content=[tool_use("t1", "Bash", command="glab mr create --draft")]),
            tool_result("t1", "error: no remote", 58, is_error=True),
            assistant("m2", 57, content=[tool_use("t2", "Bash", command="git push -u origin HEAD")]),
        ])
        econ = analyze(self.root)["command_economics"]
        self.assertEqual(econ["outcomes"], {"mr_created": 0, "pushed": 0, "neither": 1})

    def test_change_size_is_the_last_git_diff_stat_across_main_and_subagents(self):
        write_jsonl(self.root / PROJECT / "s1.jsonl", [
            slash("fullsend", 120),
            assistant("m1", 119, content=[tool_use("t1", "Bash", command="git diff --shortstat origin/main...")]),
            tool_result("t1", " 9 files changed, 400 insertions(+), 100 deletions(-)", 118),
            assistant("m2", 90, content=[tool_use("t2", "Bash", command="git log --stat -5")]),
            tool_result("t2", " 90 files changed, 4000 insertions(+)", 89),
        ])
        subagent(self.root, PROJECT, "s1", "a1", "worker", [
            user("go", 110),
            assistant("m3", 100, content=[tool_use("t3", "Bash", command="git -C /repo diff --stat main")]),
            tool_result("t3", " 2 files changed, 40 insertions(+), 20 deletions(-)", 99),
        ])
        sizes = analyze(self.root)["command_economics"]["by_change_size"]
        self.assertEqual({k: v["sessions"] for k, v in sizes.items()}, {"51-200": 1})


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
