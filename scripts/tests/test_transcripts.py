import tempfile
import unittest
from pathlib import Path

from transcript_fixtures import NOW, git_repo, iso, user

import transcripts as tr

DAY = 86400


def blocks(*texts):
    return [{"type": "text", "text": t} for t in texts]


class HumanText(unittest.TestCase):
    def test_a_reminder_leading_a_block_is_dropped_and_the_typing_after_it_kept(self):
        self.assertEqual(tr.human_text(user(blocks("<system-reminder>ctx</system-reminder>\nfix the bug"), 1)), "fix the bug")
        self.assertEqual(tr.human_text(user("<system-reminder>ctx</system-reminder>\nfix the bug", 1)), "fix the bug")

    def test_a_conversation_checkpoint_is_history_not_typing(self):
        record = user(blocks("<conversation-checkpoint>\nhistory from OpenCode", "<tool>", "that is a false positive",
                             "</tool>", "</conversation-checkpoint>", "explain why"), 1)
        self.assertEqual(tr.human_text(record), "explain why")

    def test_a_restart_notice_or_system_update_after_a_checkpoint_is_not_typing(self):
        record = user(blocks("<conversation-checkpoint>\nx", "</conversation-checkpoint>",
                             "<system-update>\nThe tool catalog has changed.", "Read `~/llmfiles/opencode/fullconduct.md`"), 1)
        self.assertEqual(tr.human_text(record), "Read `~/llmfiles/opencode/fullconduct.md`")
        restart = user(blocks("The server restarted while you were working. Continue from where you left off"), 1)
        self.assertEqual(tr.human_text(restart), "")

    def test_a_forwarded_command_body_is_not_typing(self):
        body = "# /curatemds\n\nRead ~/llmfiles/shared/agent-docs-bar.md first. No, the bar is strict."
        self.assertEqual(tr.human_text(user(body, 1)), "")
        self.assertEqual(tr.human_text(user(blocks(body, "tidy the readme"), 1)), "tidy the readme")


class SessionHead(unittest.TestCase):
    def test_the_first_prompt_is_what_a_person_first_typed(self):
        head = tr.SessionHead()
        for record in (user("<local-command-caveat>x</local-command-caveat>", 3, isMeta=True),
                       user(blocks("<system-reminder>ctx</system-reminder>", "/code-review high"), 2), user("thanks", 1)):
            head.feed(record)
        self.assertEqual((head.first_prompt, head.command()), ("/code-review high", "locallensedreview"))

    def test_the_start_is_the_first_timestamp_of_any_record(self):
        head = tr.SessionHead()
        for record in ({"type": "mode"}, {"type": "queue-operation", "timestamp": "nope"},
                       {"type": "queue-operation", "timestamp": iso(90)}, user("hi", 30)):
            head.feed(record)
        self.assertEqual(head.start, NOW - 90 * 60)


class SetupRevs(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.repo = Path(self.tmp.name) / "llmfiles"
        (self.a, self.b, self.c), self.git = git_repo(self.repo, [10, 5, 2])

    def tearDown(self):
        self.tmp.cleanup()

    def test_a_session_gets_the_commit_main_pointed_at_when_it_started(self):
        revs = tr.SetupRevs(str(self.repo))
        self.assertIsNone(revs.at(NOW - 11 * DAY))
        self.assertEqual(revs.at(NOW - 7 * DAY), self.a)
        self.assertEqual(revs.at(NOW - 3 * DAY), self.b)
        self.assertEqual(revs.at(NOW), self.c)

    def test_a_reset_moves_main_back_from_that_moment(self):
        self.git("reset", "-q", "--hard", self.a, when=NOW - DAY)
        self.assertEqual(tr.SetupRevs(str(self.repo)).at(NOW), self.a)

    def test_moves_in_the_same_second_keep_their_order(self):
        low, high = sorted([self.a, self.b])
        self.git("reset", "-q", "--hard", high, when=NOW - DAY)
        self.git("reset", "-q", "--hard", low, when=NOW - DAY)
        self.assertEqual(tr.SetupRevs(str(self.repo)).at(NOW), low)

    def test_times_older_than_the_reflog_fall_back_to_commit_dates(self):
        self.git("reflog", "expire", "--expire=all", "--all")
        revs = tr.SetupRevs(str(self.repo))
        self.assertEqual(revs.at(NOW - 7 * DAY), self.a)
        self.assertEqual(revs.at(NOW), self.c)

    def test_a_rev_contains_its_ancestors_only(self):
        revs = tr.SetupRevs(str(self.repo))
        self.assertTrue(revs.contains(self.c, self.b))
        self.assertTrue(revs.contains(self.b, self.b))
        self.assertFalse(revs.contains(self.a, self.b))

    def test_first_time_main_held_all_commits(self):
        revs = tr.SetupRevs(str(self.repo))
        self.assertEqual(revs.first_containing([self.a, self.b]), NOW - 5 * DAY)
        self.assertIsNone(revs.first_containing(["f" * 40]))

    def test_resolve_gives_the_full_sha_of_a_commit_or_none(self):
        revs = tr.SetupRevs(str(self.repo))
        self.assertEqual(revs.resolve(self.b[:7]), self.b)
        self.assertIsNone(revs.resolve("~/.claude/settings.json:effortLevel"))
        self.assertIsNone(revs.resolve("deadbee"))

    def test_a_missing_repo_names_no_rev(self):
        revs = tr.SetupRevs(str(Path(self.tmp.name) / "nope"))
        self.assertIsNone(revs.at(NOW))
        self.assertIsNone(revs.resolve("main"))


if __name__ == "__main__":
    unittest.main()
