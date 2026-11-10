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

WARN_TOKENS = int(os.environ.get("SUBAGENT_CONTEXT_WARN_TOKENS", "300000"))
# Lower than the subagent limit: the main session may run in a 200k window and still has later steps to coordinate.
MAIN_WARN_TOKENS = int(os.environ.get("MAIN_CONTEXT_WARN_TOKENS", "120000"))
TAIL_BYTES = 512 * 1024
MARKER_DIR = Path(tempfile.gettempdir()) / "claude-subagent-context-budget"


SUBAGENT_ADVICE = (
    "Finish the step you are on, then report what is done, what remains, "
    "and the file:line pointers a fresh agent needs to continue."
)
MAIN_ADVICE = (
    "Hand the remaining reading, exploring and editing to agents, and keep only their "
    "conclusions in this session."
)


def transcript_path(event):
    main = Path(event["transcript_path"]).expanduser()
    agent_id = event.get("agent_id")
    if not agent_id:
        return main
    return main.parent / main.stem / "subagents" / f"agent-{agent_id}.jsonl"


def context_tokens(transcript):
    with transcript.open("rb") as f:
        f.seek(max(0, transcript.stat().st_size - TAIL_BYTES))
        lines = f.read().decode("utf-8", "replace").splitlines()
    for line in reversed(lines):
        try:
            usage = json.loads(line).get("message", {}).get("usage")
        except (json.JSONDecodeError, AttributeError):
            continue
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


def main():
    event = json.load(sys.stdin)
    if not event.get("transcript_path"):
        return
    agent_id = event.get("agent_id")

    marker = MARKER_DIR / f"{event.get('session_id', '')}-{agent_id or 'main'}"
    if marker.exists():
        return

    transcript = transcript_path(event)
    if not transcript.exists():
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
        main()
    except Exception:
        # A broken budget check must never block the tool call.
        pass
