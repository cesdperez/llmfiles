import unittest
from datetime import datetime, timezone

from transcript_fixtures import load_script

bw = load_script("review-bot-wait.py")
SINCE = datetime(2026, 6, 15, 12, 0, tzinfo=timezone.utc)
BOT = "acme-review-bot"
MARKER = "review-bot: running"


def note(author, minute, body="looks fine"):
    return {"author": {"username": author}, "body": body, "created_at": f"2026-06-15T12:{minute:02d}:00Z"}


def old_note(author, body=f"earlier pass <!-- {MARKER} -->"):
    return {"author": {"username": author}, "body": body, "created_at": "2026-06-15T11:59:00Z"}


class Finished(unittest.TestCase):
    def test_a_bot_note_since_the_request_finishes_the_pass(self):
        self.assertTrue(bw.finished([note(BOT, 5)], BOT, SINCE, ""))

    def test_a_note_created_at_the_request_counts(self):
        self.assertTrue(bw.finished([note(BOT, 0)], BOT, SINCE, ""))

    def test_notes_from_before_the_request_do_not_count(self):
        self.assertFalse(bw.finished([old_note(BOT, "No findings")], BOT, SINCE, ""))

    def test_a_busy_marker_from_before_the_request_is_ignored(self):
        self.assertTrue(bw.finished([note(BOT, 5), old_note(BOT)], BOT, SINCE, MARKER))

    def test_other_authors_do_not_count(self):
        self.assertFalse(bw.finished([note("someone", 5)], BOT, SINCE, ""))

    def test_busy_marker_keeps_the_pass_open(self):
        notes = [note(BOT, 5, f"Review running <!-- {MARKER} sha=abc -->"), note(BOT, 6)]
        self.assertFalse(bw.finished(notes, BOT, SINCE, MARKER))

    def test_marker_from_another_author_is_ignored(self):
        notes = [note("someone", 5, MARKER), note(BOT, 6)]
        self.assertTrue(bw.finished(notes, BOT, SINCE, MARKER))


class NotesSince(unittest.TestCase):
    def test_pages_until_a_note_older_than_since(self):
        pages = {1: [note(BOT, 9)] * bw.PER_PAGE, 2: [note(BOT, 1), old_note(BOT)], 3: [note(BOT, 2)]}
        calls = []

        def api(path):
            calls.append(path)
            return pages[int(path.rsplit("page=", 1)[1])]

        notes = bw.notes_since(api, "12", SINCE)
        self.assertEqual(len(notes), bw.PER_PAGE + 2)
        self.assertEqual(len(calls), 2)
        self.assertIn("order_by=created_at&sort=desc", calls[0])

    def test_a_short_page_is_the_last(self):
        calls = []

        def api(path):
            calls.append(path)
            return [note(BOT, 3)]

        self.assertEqual(len(bw.notes_since(api, "12", SINCE)), 1)
        self.assertEqual(len(calls), 1)


class Api(unittest.TestCase):
    def test_an_unreadable_answer_is_a_cli_error(self):
        api = bw.api_for(None, runner=lambda cmd, cwd: "<html>502</html>")
        with self.assertRaises(bw.CliError):
            api("projects/:id/merge_requests/12/notes")


class Clock:
    def __init__(self):
        self.now = 0.0

    def __call__(self):
        return self.now

    def sleep(self, seconds):
        self.now += seconds


def run_wait(polls, timeout=2700):
    polls, clock = list(polls), Clock()

    def fetch():
        snapshot = polls.pop(0) if len(polls) > 1 else polls[0]
        if isinstance(snapshot, Exception):
            raise snapshot
        return snapshot

    return bw.wait(fetch, BOT, MARKER, SINCE, 30, timeout, sleep=clock.sleep, clock=clock)


class Wait(unittest.TestCase):
    def test_waits_through_the_running_note_until_it_is_edited(self):
        running = [note(BOT, 1, f"<!-- {MARKER} -->")]
        self.assertEqual(run_wait([[], running, running, [note(BOT, 1, "No findings")]]), (0, "finished"))

    def test_gives_up_at_the_timeout(self):
        self.assertEqual(run_wait([[]], timeout=120), (3, "timeout"))

    def test_repeated_cli_errors_give_up(self):
        self.assertEqual(run_wait([bw.CliError("401")]), (2, "error"))

    def test_retries_after_one_cli_error(self):
        self.assertEqual(run_wait([bw.CliError("502"), [note(BOT, 4)]]), (0, "finished"))

    def test_an_unexpected_answer_counts_as_a_cli_failure(self):
        self.assertEqual(run_wait([[{"body": "no author"}]]), (2, "error"))


if __name__ == "__main__":
    unittest.main()
