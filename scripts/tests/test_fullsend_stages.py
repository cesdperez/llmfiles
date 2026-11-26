import tempfile
import unittest
from pathlib import Path

from transcript_fixtures import NOW, StubRevs, assistant, load_script, slash, tool_use, user, write_jsonl

stages = load_script("fullsend-stages.py")
PROJECT = "-work-repo"


def mark(msg_id, minutes_ago, n, stage):
    cmd = f'orca worktree set --worktree current --comment "{n}/7 {stage}" --json'
    return assistant(msg_id, minutes_ago, content=[tool_use(msg_id + "t", "Bash", command=cmd)])


class StageTimings(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)

    def tearDown(self):
        self.tmp.cleanup()

    def run_stages(self):
        return stages.analyze(str(self.root), 7, now=NOW, revs=StubRevs())

    def test_minutes_per_stage_run_from_its_mark_to_the_next(self):
        write_jsonl(self.root / PROJECT / "s1.jsonl", [
            slash("fullsend", 100),
            mark("a", 100, 0, "intake"),
            mark("b", 90, 1, "setup"),
            mark("c", 80, 2, "implement"),
            mark("d", 50, 2, "implement"),
            mark("e", 40, 3, "review"),
            user("end", 30),
        ])
        out = self.run_stages()
        self.assertEqual(out["runs"][0]["stages"], {"0 intake": 10, "1 setup": 10, "2 implement": 40, "3 review": 10})
        self.assertEqual(out["runs"][0]["total_min"], 70)
        self.assertEqual(out["stages"]["2 implement"]["median"], 40)

    def test_a_run_names_the_setup_it_started_on(self):
        write_jsonl(self.root / PROJECT / "s1.jsonl", [slash("fullsend", 100)] + [
            mark(f"m{n}", 100 - 10 * n, n, f"stage{n}") for n in range(4)])
        self.assertEqual(stages.analyze(str(self.root), 7, now=NOW, revs=StubRevs(80))["runs"][0]["setup_rev"], "early")

    def test_session_that_never_ran_fullsend_is_skipped(self):
        write_jsonl(self.root / PROJECT / "s1.jsonl", [
            slash("fleet", 100), mark("a", 100, 0, "intake"), mark("b", 90, 1, "setup"),
            mark("c", 80, 2, "hunt"), mark("d", 70, 3, "fix"),
        ])
        self.assertEqual(self.run_stages()["runs"], [])

    def test_stage_names_are_lowercased_and_merged_by_number(self):
        for session, name in (("s1", "Review"), ("s2", "review")):
            write_jsonl(self.root / PROJECT / f"{session}.jsonl", [
                slash("fullsend", 100), mark("a", 100, 0, "intake"), mark("b", 90, 1, "setup"),
                mark("c", 80, 2, "implement"), mark("d", 70, 3, name), user("end", 60),
            ])
        self.assertEqual(self.run_stages()["stages"]["3 review"]["n"], 2)

    def test_run_with_fewer_than_four_stages_is_skipped(self):
        write_jsonl(self.root / PROJECT / "s1.jsonl", [
            slash("fullsend", 100), mark("a", 100, 0, "intake"), mark("b", 90, 1, "setup"), user("end", 80),
        ])
        self.assertEqual(self.run_stages()["runs"], [])

    def test_stage_left_open_past_the_limit_is_not_counted(self):
        write_jsonl(self.root / PROJECT / "s1.jsonl", [
            slash("fullsend", 2000), mark("a", 2000, 0, "intake"), mark("b", 1990, 1, "setup"), mark("c", 1980, 2, "implement"),
            mark("d", 10, 3, "review"), user("end", 0),
        ])
        out = self.run_stages()
        self.assertNotIn("2 implement", out["runs"][0]["stages"])
        self.assertEqual(out["runs"][0]["stages"]["3 review"], 10)


if __name__ == "__main__":
    unittest.main()
