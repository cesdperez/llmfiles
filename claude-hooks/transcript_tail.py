"""Transcript lookup and tail reading shared by the hooks in this directory."""

import json
from pathlib import Path

# A long session's transcript runs to many megabytes, and the hooks only need its last turns.
TAIL_BYTES = 512 * 1024


def subagent_transcript(event):
    """Return the transcript of the subagent in a hook event, or None when it is not on disk."""
    main = Path(event["transcript_path"]).expanduser()
    subagents = main.parent / main.stem / "subagents"
    name = f"agent-{event['agent_id']}.jsonl"
    direct = subagents / name
    if direct.exists():
        return direct
    return next(subagents.glob(f"workflows/*/{name}"), None)


def tail_entries(transcript):
    """Yield the JSON objects in the last TAIL_BYTES of a transcript, oldest first."""
    with transcript.open("rb") as f:
        f.seek(max(0, transcript.stat().st_size - TAIL_BYTES))
        lines = f.read().decode("utf-8", "replace").splitlines()
    for line in lines:
        try:
            entry = json.loads(line)
        except json.JSONDecodeError:
            continue
        if isinstance(entry, dict):
            yield entry
