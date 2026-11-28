#!/usr/bin/env python3
"""PostToolUse hook: tell a subagent or the main session once when its context passes the budget.

Neither can see its own token count, so the delegation rule in shared/CLAUDE.md
only holds if something measures it from outside.
"""

import json
import os
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import transcript_tail  # noqa: E402

WARN_TOKENS = int(os.environ.get("SUBAGENT_CONTEXT_WARN_TOKENS", "100000"))
# Higher than the subagent limit: the main session cannot restart from a notes file, so it hands off later, still short of a 200k window.
MAIN_WARN_TOKENS = int(os.environ.get("MAIN_CONTEXT_WARN_TOKENS", "120000"))
MARKER_DIR = Path(tempfile.gettempdir()) / "claude-subagent-context-budget"


SUBAGENT_ADVICE = (
    "Finish the step you are on, then write what is done, what remains, and the file:line "
    "pointers a fresh agent needs to continue to the notes file your brief names, or to your report."
)
MAIN_ADVICE = (
    "Hand the remaining reading, exploring and editing to agents, and keep only their "
    "conclusions in this session."
)


def transcript_path(event):
    if not event.get("agent_id"):
        return Path(event["transcript_path"]).expanduser()
    return transcript_tail.subagent_transcript(event)


def context_tokens(transcript):
    for entry in reversed(list(transcript_tail.tail_entries(transcript))):
        message = entry.get("message")
        usage = message.get("usage") if isinstance(message, dict) else None
        if not usage:
            continue
        tokens = (
            usage.get("input_tokens", 0)
            + usage.get("cache_read_input_tokens", 0)
            + usage.get("cache_creation_input_tokens", 0)
        )
        # An API error entry carries all-zero usage; the real count is on the turn before.
        if tokens:
            return tokens
    return 0


def run(event):
    if not event.get("transcript_path"):
        return
    agent_id = event.get("agent_id")

    marker = MARKER_DIR / f"{event.get('session_id', '')}-{agent_id or 'main'}"
    if marker.exists():
        return

    transcript = transcript_path(event)
    if transcript is None or not transcript.exists():
        return
    tokens = context_tokens(transcript)
    if tokens < (WARN_TOKENS if agent_id else MAIN_WARN_TOKENS):
        return

    MARKER_DIR.mkdir(exist_ok=True)
    marker.touch()
    print(json.dumps({
        "hookSpecificOutput": {
            "hookEventName": "PostToolUse",
            "additionalContext": (
                f"Your context is at ~{tokens // 1000}k tokens and output quality drops from here. "
                + (SUBAGENT_ADVICE if agent_id else MAIN_ADVICE)
            ),
        }
    }))


if __name__ == "__main__":
    try:
        run(json.load(sys.stdin))
    except Exception:
        # A broken budget check must never block the tool call.
        pass
