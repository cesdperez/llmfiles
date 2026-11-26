import unittest

from transcript_fixtures import user

import transcripts as tr


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

