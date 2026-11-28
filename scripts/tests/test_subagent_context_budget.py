import importlib.util
import io
import json
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path

from transcript_fixtures import assistant, write_jsonl

HOOK = Path(__file__).resolve().parents[2] / "claude-hooks" / "subagent-context-budget.py"
spec = importlib.util.spec_from_file_location("subagent_context_budget", HOOK)
hook = importlib.util.module_from_spec(spec)
spec.loader.exec_module(hook)


class SubagentContextBudget(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.main = Path(self.tmp.name) / "session.jsonl"
        self.main.write_text("")
        hook.MARKER_DIR = Path(self.tmp.name) / "markers"

    def tearDown(self):
        self.tmp.cleanup()

    def run_hook(self, agent_id="a1"):
        event = {"transcript_path": str(self.main), "session_id": "s", "agent_id": agent_id}
        out = io.StringIO()
        with redirect_stdout(out):
            hook.run(event)
        return json.loads(out.getvalue()) if out.getvalue() else None

    def subagent(self, rows, subdir=""):
        write_jsonl(self.main.parent / "session" / "subagents" / subdir / "agent-a1.jsonl", rows)

    def test_a_subagent_over_budget_is_told_once(self):
        self.subagent([assistant("m1", 1, inp=10, cache_read=hook.WARN_TOKENS)])
        self.assertIn("~100k tokens", self.run_hook()["hookSpecificOutput"]["additionalContext"])
        self.assertIsNone(self.run_hook())

    def test_a_subagent_under_budget_is_told_nothing(self):
        self.subagent([assistant("m1", 1, inp=10, cache_read=1000)])
        self.assertIsNone(self.run_hook())

    def test_an_all_zero_usage_entry_falls_back_to_the_turn_before(self):
        self.subagent([assistant("m1", 1, inp=10, cache_read=hook.WARN_TOKENS),
                       assistant("m2", 1, out=0, inp=0)])
        self.assertIsNotNone(self.run_hook())

    def test_workflow_subagent_transcripts_are_found(self):
        self.subagent([assistant("m1", 1, inp=10, cache_read=hook.WARN_TOKENS)], subdir="workflows/wf_1")
        self.assertIsNotNone(self.run_hook())

    def test_main_session_uses_its_own_transcript_and_limit(self):
        write_jsonl(self.main, [assistant("m1", 1, inp=10, cache_read=hook.WARN_TOKENS)])
        self.assertIsNone(self.run_hook(agent_id=None))
        write_jsonl(self.main, [assistant("m1", 1, inp=10, cache_read=hook.MAIN_WARN_TOKENS)])
        self.assertIn("Hand the remaining", self.run_hook(agent_id=None)["hookSpecificOutput"]["additionalContext"])


if __name__ == "__main__":
    unittest.main()
