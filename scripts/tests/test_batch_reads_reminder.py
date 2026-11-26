import importlib.util
import io
import json
import shutil
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path

from transcript_fixtures import assistant, tool_use, write_jsonl

HOOK = Path(__file__).resolve().parents[2] / "claude-hooks" / "batch-reads-reminder.py"
spec = importlib.util.spec_from_file_location("batch_reads_reminder", HOOK)
hook = importlib.util.module_from_spec(spec)
spec.loader.exec_module(hook)


def request(msg_id, *calls):
    return assistant(msg_id, 1, content=list(calls))


def read(path):
    return tool_use("t-" + path, "Read", file_path=path)


def bash(command):
    return tool_use("t-" + command, "Bash", command=command)


class BatchReadsReminder(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.main = Path(self.tmp.name) / "session.jsonl"
        self.main.write_text("")
        hook.MARKER_DIR = Path(self.tmp.name) / "markers"

    def tearDown(self):
        self.tmp.cleanup()

    def run_hook(self, rows, agent_id="a1", subdir=""):
        if agent_id:
            write_jsonl(self.main.parent / "session" / "subagents" / subdir / f"agent-{agent_id}.jsonl", rows)
        event = {"transcript_path": str(self.main), "session_id": "s", "agent_id": agent_id, "tool_name": "Read"}
        out = io.StringIO()
        with redirect_stdout(out):
            hook.run(event)
        return json.loads(out.getvalue()) if out.getvalue() else None

    def test_three_single_reads_in_a_row_add_a_reminder(self):
        out = self.run_hook([request("m1", read("a")), request("m2", bash("cd x && sed -n 1,20p b")),
                             request("m3", tool_use("g", "Grep", pattern="x"))])
        self.assertEqual(out["hookSpecificOutput"]["hookEventName"], "PostToolUse")
        self.assertIn("one message", out["hookSpecificOutput"]["additionalContext"])

    def test_two_single_reads_add_nothing(self):
        self.assertIsNone(self.run_hook([request("m1", read("a")), request("m2", read("b"))]))

    def test_a_batched_request_breaks_the_streak(self):
        rows = [request("m1", read("a")), request("m2", read("b"), read("c")),
                request("m3", read("d")), request("m4", read("e"))]
        self.assertIsNone(self.run_hook(rows))

    def test_blocks_of_one_request_split_over_lines_count_once(self):
        rows = [request("m1", read("a")), request("m2", read("b")), request("m2", read("c")), request("m3", read("d"))]
        self.assertIsNone(self.run_hook(rows))

    def test_an_edit_or_a_write_command_breaks_the_streak(self):
        self.assertIsNone(self.run_hook([request("m1", read("a")), request("m2", bash("sed -i s/a/b/ f")),
                                         request("m3", read("b"))]))
        self.assertIsNone(self.run_hook([request("m1", read("a")), request("m2", tool_use("e", "Edit")),
                                         request("m3", read("b"))]))

    def test_reminds_again_only_after_three_more(self):
        rows = [request(f"m{i}", read(str(i))) for i in range(3)]
        self.assertIsNotNone(self.run_hook(rows))
        for i in range(3, 5):
            rows.append(request(f"m{i}", read(str(i))))
            self.assertIsNone(self.run_hook(rows), f"streak {i + 1}")
        rows.append(request("m5", read("5")))
        self.assertIsNotNone(self.run_hook(rows))

    def test_a_streak_cut_short_by_the_tail_still_reminds_once(self):
        rows = [request(f"m{i}", read(str(i))) for i in range(3)]
        self.assertIsNotNone(self.run_hook(rows))
        rows = rows[1:] + [request("m3", read("3"))]
        self.assertIsNone(self.run_hook(rows))

    def test_a_new_streak_after_a_break_reminds_again(self):
        rows = [request(f"m{i}", read(str(i))) for i in range(3)]
        self.assertIsNotNone(self.run_hook(rows))
        rows.append(request("m3", tool_use("e", "Edit")))
        rows.extend(request(f"m{i}", read(str(i))) for i in range(4, 7))
        self.assertIsNotNone(self.run_hook(rows))

    def test_main_session_gets_no_reminder(self):
        write_jsonl(self.main, [request(f"m{i}", read(str(i))) for i in range(3)])
        self.assertIsNone(self.run_hook([], agent_id=None))

    def test_workflow_subagent_transcripts_are_found(self):
        rows = [request(f"m{i}", read(str(i))) for i in range(3)]
        self.assertIsNotNone(self.run_hook(rows, subdir="workflows/wf_1"))

    def test_requests_without_a_message_id_count_separately(self):
        rows = [request(None, read(str(i))) for i in range(3)]
        self.assertIsNotNone(self.run_hook(rows))

    def assert_single_read(self, command, expected):
        shutil.rmtree(hook.MARKER_DIR, ignore_errors=True)
        out = self.run_hook([request("m1", read("a")), request("m2", bash(command)), request("m3", read("b"))])
        self.assertEqual(out is not None, expected, command)

    def test_reading_commands_keep_the_streak(self):
        for command in ["cd x && sed -n 1,20p b", "cat a 2>/dev/null | head -5", "git -C dir log -3",
                        "git --no-pager diff", "git -c core.pager=cat show HEAD", "grep 'a;b' f"]:
            self.assert_single_read(command, True)

    def test_writing_commands_break_the_streak(self):
        for command in ["cat a > b", "cat a || rm b", "cat a\nrm b", "grep x f | xargs rm", "sed --in-place s/a/b/ f",
                        "find . -delete", "find . -exec rm {} \\;", "cat a; touch b", "cat 'unbalanced"]:
            self.assert_single_read(command, False)

    def test_a_shell_call_with_several_reads_is_a_batched_read(self):
        self.assert_single_read("cat a && sed -n 1,5p b", False)
        self.assert_single_read("cat a\nhead b", False)


if __name__ == "__main__":
    unittest.main()
