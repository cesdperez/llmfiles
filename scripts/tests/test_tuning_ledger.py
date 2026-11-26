import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from transcript_fixtures import NOW, assistant, git_repo, load_script, slash, tool_use, write_jsonl

import transcripts as tr

ledger = load_script("tuning-ledger.py")
SCRIPT = Path(__file__).resolve().parent.parent / "tuning-ledger.py"
DAY_MIN = 24 * 60


def entry(**overrides):
    e = {
        "id": "2026-11-25-1", "date": "2026-11-25", "source": "tunesetup",
        "change": "agents batch independent reads", "files": ["agents/worker.md"], "where": ["4243c67"],
        "why": "one tool call per request", "metric": "usage:tools/calls_per_request",
        "baseline": 1.05, "expected": "up", "status": "applied",
    }
    e.update(overrides)
    return e


class Validation(unittest.TestCase):
    def test_a_complete_entry_is_valid(self):
        self.assertEqual(ledger.validate_entry(entry()), [])

    def test_unknown_enum_values_and_fields_are_errors(self):
        errors = ledger.validate_entry(entry(status="done", source="me", expected="sideways", colour="red"))
        self.assertEqual(len(errors), 4)

    def test_a_metric_needs_a_baseline_and_a_direction(self):
        self.assertTrue(ledger.validate_entry(entry(baseline=None)))
        self.assertTrue(ledger.validate_entry(entry(expected=None)))
        self.assertEqual(ledger.validate_entry(entry(metric=None, baseline=None, expected=None)), [])

    def test_a_script_metric_names_one_of_the_three_outputs(self):
        self.assertTrue(ledger.validate_entry(entry(metric="cost/total")))
        self.assertEqual(ledger.validate_entry(entry(metric="review reports flagging a decision", hand_counted=True)), [])

    def test_a_proposal_names_what_it_would_touch(self):
        self.assertTrue(ledger.validate_entry(entry(status="proposed", files=[], where=[])))
        self.assertEqual(ledger.validate_entry(entry(status="proposed", files=[], where=["settings.json:effortLevel"])), [])

    def test_an_applied_entry_points_to_its_change(self):
        self.assertTrue(ledger.validate_entry(entry(where=[])))

    def test_a_file_with_a_bad_line_or_a_repeated_id_fails(self):
        with tempfile.TemporaryDirectory() as d:
            path = Path(d) / "ledger.jsonl"
            path.write_text(json.dumps(entry()) + "\n" + json.dumps(entry()) + "\nnot json\n")
            errors = ledger.validate_file(path)
        self.assertEqual(len(errors), 2)
        self.assertTrue(all(e.startswith("line ") for e in errors))


class Writing(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.path = Path(self.tmp.name) / "tunesetup" / "ledger.jsonl"

    def tearDown(self):
        self.tmp.cleanup()

    def test_add_numbers_entries_per_date_and_fills_defaults(self):
        first = entry()
        del first["id"]
        self.assertEqual(ledger.add(self.path, first), "2026-11-25-1")
        self.assertEqual(ledger.add(self.path, dict(first)), "2026-11-25-2")
        saved = ledger.load(self.path)
        self.assertEqual([e["id"] for e in saved], ["2026-11-25-1", "2026-11-25-2"])
        self.assertIsNone(saved[0]["verdict"])
        self.assertFalse(saved[0]["hand_counted"])

    def test_add_refuses_an_invalid_entry(self):
        with self.assertRaises(ValueError):
            ledger.add(self.path, entry(status="done"))
        self.assertFalse(self.path.exists())

    def test_update_changes_fields_in_place_and_validates(self):
        ledger.add(self.path, entry(status="proposed", where=[]))
        ledger.update(self.path, "2026-11-25-1", {"status": "applied", "where": ["abc1234"]})
        self.assertEqual(ledger.load(self.path)[0]["where"], ["abc1234"])
        with self.assertRaises(ValueError):
            ledger.update(self.path, "2026-11-25-1", {"verdict": "great"})
        with self.assertRaises(KeyError):
            ledger.update(self.path, "nope", {"status": "applied"})


class OpenEntries(unittest.TestCase):
    def test_applied_measurable_entries_a_week_old_without_verdict(self):
        entries = [
            entry(id="a"),
            entry(id="young", date="2026-11-30"),
            entry(id="settled", verdict="kept"),
            entry(id="proposed", status="proposed"),
            entry(id="no-metric", metric=None, baseline=None, expected=None),
        ]
        self.assertEqual([e["id"] for e in ledger.open_entries(entries, "2026-12-02")], ["a"])


class Measuring(unittest.TestCase):
    outputs = {
        "usage": {"days": 14, "tools": {"calls_per_request": 1.4},
                  "headline": {"agents.worker.runs": 700}},
        "stages": {"days": 14, "stages": {"3 review": {"median": 8.0}}},
        "friction": {"days": 14, "tool_errors": [{"kind": "Bash: permission denied", "count": 30}]},
    }

    def test_a_metric_reads_a_path_through_dicts_and_kind_lists(self):
        self.assertEqual(ledger.metric_value("usage:tools/calls_per_request", self.outputs), (1.4, 14))
        self.assertEqual(ledger.metric_value("usage:headline/agents.worker.runs", self.outputs), (700, 14))
        self.assertEqual(ledger.metric_value("stages:stages/3 review/median", self.outputs), (8.0, 14))
        self.assertEqual(ledger.metric_value("friction:tool_errors/Bash: permission denied/count", self.outputs), (30, 14))

    def test_a_tool_error_kind_that_did_not_occur_counts_zero(self):
        self.assertEqual(ledger.metric_value("friction:tool_errors/Bash: blocked command/count", self.outputs), (0, 14))
        self.assertIsNone(ledger.metric_value("friction:tool_errors/Bash: blocked command/sessions", self.outputs))

    def test_a_missing_metric_or_output_reads_as_none(self):
        self.assertIsNone(ledger.metric_value("usage:tools/nope", self.outputs))
        self.assertIsNone(ledger.metric_value("usage:tools/calls_per_request", {}))

    def test_a_period_total_is_scaled_to_the_baseline_period(self):
        e = entry(metric="usage:headline/agents.worker.runs", baseline=319, baseline_days=7, expected="down")
        self.assertEqual(ledger.measured_value(e, self.outputs), 350)

    def test_judge_needs_a_five_percent_move(self):
        self.assertEqual(ledger.judge(entry(), 1.4), ("as_expected", "kept"))
        self.assertEqual(ledger.judge(entry(), 1.07), ("flat", "inconclusive"))
        self.assertEqual(ledger.judge(entry(), 0.9), ("against", None))
        self.assertEqual(ledger.judge(entry(baseline=0, expected="down"), 0), ("flat", "inconclusive"))


class MeasuringBySetup(unittest.TestCase):
    """Sessions that started on a setup holding the change against those that started before it."""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        d = Path(self.tmp.name)
        self.path, self.root = d / "ledger.jsonl", d / "projects"
        (_, self.change), _ = git_repo(d / "llmfiles", [40, 10])
        self.revs = tr.SetupRevs(str(d / "llmfiles"))
        write_jsonl(self.root / "-p" / "before.jsonl", [
            slash("fullsend", 15 * DAY_MIN), assistant("m1", 15 * DAY_MIN - 1, content=[tool_use("t1", "Read")])])
        write_jsonl(self.root / "-p" / "after.jsonl", [
            slash("fullsend", 2 * DAY_MIN),
            assistant("m2", 2 * DAY_MIN - 1, content=[tool_use("t2", "Read"), tool_use("t3", "Read")])])

    def tearDown(self):
        self.tmp.cleanup()

    def measure(self, *entries):
        for e in entries:
            ledger.add(self.path, e)
        results = ledger.measure(self.path, "2026-06-15", 28, str(self.root), self.revs, now=NOW)
        return {r["id"]: r for r in results}, {e["id"]: e for e in ledger.load(self.path)}

    def test_sessions_on_a_setup_with_the_commit_are_compared_with_those_before_it(self):
        results, saved = self.measure(entry(id="a", date="2026-06-05", where=[self.change[:7]], baseline=9))
        self.assertEqual({k: results["a"][k] for k in ("split", "before", "measured", "moved")},
                         {"split": "commit", "before": 1.0, "measured": 2.0, "moved": "as_expected"})
        self.assertEqual((saved["a"]["measured_before"], saved["a"]["measured"], saved["a"]["verdict"]), (1.0, 2.0, "kept"))

    def test_a_where_that_is_no_commit_splits_by_the_entry_date(self):
        results, _ = self.measure(entry(id="a", date="2026-06-05", where=["~/.claude/settings.json:effortLevel"]))
        self.assertEqual((results["a"]["split"], results["a"]["before"], results["a"]["measured"]), ("date", 1.0, 2.0))

    def test_a_change_older_than_the_period_is_compared_with_its_baseline(self):
        (old, _), _ = git_repo(Path(self.tmp.name) / "old", [40, 30])
        self.revs = tr.SetupRevs(str(Path(self.tmp.name) / "old"))
        results, _ = self.measure(entry(id="a", date="2026-05-16", where=[old], baseline=2.5))
        self.assertEqual((results["a"]["before"], results["a"]["measured"], results["a"]["moved"]), (None, 1.5, "against"))

    def test_a_period_total_is_scaled_to_the_days_main_held_each_side_setup(self):
        d = Path(self.tmp.name)
        (_, c1, c2), _ = git_repo(d / "three", [40, 20, 10])
        self.revs = tr.SetupRevs(str(d / "three"))
        write_jsonl(self.root / "-p" / "middle.jsonl", [slash("fullsend", 25 * DAY_MIN), assistant("m0", 25 * DAY_MIN - 1)])
        e = entry(id="a", date="2026-06-05", where=[c1, c2], metric="usage:headline/main_sessions",
                  baseline=1, baseline_days=7, expected="down")
        results, _ = self.measure(e)
        self.assertEqual((results["a"]["before"], results["a"]["measured"]), (0.875, 0.7))

    def test_a_side_with_no_sessions_has_no_value(self):
        (self.root / "-p" / "before.jsonl").unlink()
        results, saved = self.measure(entry(id="a", date="2026-06-05", where=[self.change], baseline=9))
        self.assertEqual((results["a"]["before"], results["a"]["measured"], saved["a"]["measured_before"]), (None, 2.0, None))
        (self.root / "-p" / "after.jsonl").unlink()
        results, _ = self.measure(entry(id="b", date="2026-06-05", where=[self.change], baseline=9))
        self.assertEqual(results["b"]["moved"], "no_value")

    def test_the_shas_in_where_split_by_commit_beside_a_settings_key(self):
        results, _ = self.measure(entry(id="a", date="2026-06-05", where=[self.change, "~/.claude/settings.json:effortLevel"]))
        self.assertEqual((results["a"]["split"], results["a"]["before"], results["a"]["measured"]), ("commit", 1.0, 2.0))

    def test_hand_counts_and_missing_metrics_are_left_open(self):
        results, saved = self.measure(
            entry(id="hand", date="2026-06-05", metric="decisions flagged", hand_counted=True, baseline=4, expected="down"),
            entry(id="gone", date="2026-06-05", metric="usage:tools/nope"))
        self.assertEqual({k: r["moved"] for k, r in results.items()}, {"hand": "hand_count", "gone": "no_value"})
        self.assertIsNone(saved["gone"]["verdict"])


class Pending(unittest.TestCase):
    def test_lists_commits_on_the_branch_since_the_date_touching_the_files(self):
        with tempfile.TemporaryDirectory() as d:
            def git(*args, date="2026-11-20T12:00:00"):
                env = {"GIT_AUTHOR_DATE": date, "GIT_COMMITTER_DATE": date, "HOME": d, "PATH": "/usr/bin:/bin:/usr/local/bin:/opt/homebrew/bin"}
                return subprocess.run(["git", "-C", d, *args], check=True, capture_output=True, text=True, env=env).stdout

            git("init", "-q", "-b", "main")
            git("config", "user.email", "t@example.com")
            git("config", "user.name", "t")
            (Path(d) / "a.md").write_text("1")
            git("add", "a.md")
            git("commit", "-q", "-m", "before")
            (Path(d) / "a.md").write_text("2")
            git("commit", "-q", "-am", "a: the change", date="2026-11-27T12:00:00")
            (Path(d) / "b.md").write_text("1")
            git("add", "b.md")
            git("commit", "-q", "-m", "b: unrelated", date="2026-11-27T13:00:00")
            proposals = [entry(id="p", status="proposed", where=[], files=["a.md"]), entry(id="x"),
                         entry(id="s", status="proposed", files=[], where=["settings.json:effortLevel"])]
            out = ledger.pending(proposals, d, "main")
        self.assertEqual(list(out), ["p", "s"])
        self.assertEqual([c.split(" ", 1)[1] for c in out["p"]["commits"]], ["2026-11-27 a: the change"])
        self.assertEqual(out["s"], {"commits": [], "check_by_hand": ["settings.json:effortLevel"]})


class Fields(unittest.TestCase):
    def test_values_parse_as_json_when_they_parse_and_as_text_otherwise(self):
        self.assertEqual(ledger.parse_value('["abc"]'), ["abc"])
        self.assertIsNone(ledger.parse_value("null"))
        self.assertEqual(ledger.parse_value("2026-11-27"), "2026-11-27")
        self.assertEqual(ledger.parse_value("my reason"), "my reason")

    def test_plus_equals_appends_to_a_list_field(self):
        self.assertEqual(ledger.parse_fields(["status=applied", "where+=abc1234"]),
                         ({"status": "applied"}, {"where": "abc1234"}))

    def test_set_appends_a_sha_and_keeps_the_settings_key(self):
        with tempfile.TemporaryDirectory() as d:
            path = Path(d) / "ledger.jsonl"
            ledger.add(path, entry(status="proposed", where=["settings.json:effortLevel"]))
            subprocess.run([sys.executable, str(SCRIPT), "--ledger", str(path), "set", "2026-11-25-1",
                            "status=applied", "where+=abc1234", "note=my reason"], check=True, capture_output=True)
            saved = ledger.load(path)[0]
        self.assertEqual((saved["status"], saved["where"], saved["note"]),
                         ("applied", ["settings.json:effortLevel", "abc1234"], "my reason"))


if __name__ == "__main__":
    unittest.main()
