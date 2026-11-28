#!/usr/bin/env python3
"""PostToolUse hook: remind a subagent to batch reads after three requests in a row that each make one read or search.

Each request re-reads the whole context, so one read per request multiplies the cost of a run.
It only adds context and never blocks a call.
"""

import json
import os
import shlex
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import transcript_tail  # noqa: E402

STREAK = 3
MARKER_DIR = Path(tempfile.gettempdir()) / "claude-batch-reads-reminder"
READ_TOOLS = {"Read", "Grep", "Glob"}
READ_COMMANDS = {"cat", "head", "tail", "sed", "grep", "rg", "find", "ls", "wc", "nl", "awk", "tree", "jq"}
GIT_READS = {"show", "log", "diff", "grep", "blame", "status"}
GIT_OPTIONS_WITH_VALUE = {"-C", "-c"}
STATEMENT_SEPARATORS = {"&&", "||", ";", "&", "(", ")"}
WRITE_FLAGS = {"sed": ("-i", "--in-place"), "find": ("-delete", "-exec", "-execdir", "-ok", "-okdir", "-fprint")}
REMINDER = (
    f"Your last {STREAK} requests each made a single read or search. Send the reads and searches "
    "that do not depend on each other together in one message, and read only the line ranges you need."
)


def tool_calls_per_request(entries):
    # One API response is written as several lines, one per content block, under the same message id.
    requests = {}
    for index, entry in enumerate(entries):
        message = entry.get("message") if entry.get("type") == "assistant" else None
        if not isinstance(message, dict):
            continue
        calls = [b for b in message.get("content") or [] if isinstance(b, dict) and b.get("type") == "tool_use"]
        requests.setdefault(message.get("id") or f"line-{index}", []).extend(calls)
    return list(requests.items())


def shell_tokens(command):
    lexer = shlex.shlex(command.replace("\n", ";"), posix=True, punctuation_chars=True)
    lexer.whitespace_split = True
    return list(lexer)


def split_on(tokens, separators):
    part = []
    for token in tokens + [None]:
        if token is None or token in separators:
            if part:
                yield part
            part = []
        else:
            part.append(token)


def writes_a_file(tokens):
    for token, target in zip(tokens, tokens[1:] + [""], strict=True):
        if ">" in token and target != "/dev/null" and not target.isdigit():
            return True
    return False


def git_subcommand(words):
    rest = words[1:]
    while rest and rest[0].startswith("-"):
        rest = rest[2:] if rest[0] in GIT_OPTIONS_WITH_VALUE else rest[1:]
    return rest[0] if rest else None


def is_read_part(words):
    if words[0] == "git":
        return git_subcommand(words) in GIT_READS
    write_flags = WRITE_FLAGS.get(words[0], ())
    if any(w.startswith(write_flags) for w in words[1:]):
        return False
    return words[0] in READ_COMMANDS


def is_read_statement(tokens):
    return all(is_read_part(part) for part in split_on(tokens, {"|", "|&"}))


def read_statement_count(command):
    """Count the statements of a shell command that read, or return 0 when any statement may write."""
    try:
        tokens = shell_tokens(command)
    except ValueError:
        return 0
    if writes_a_file(tokens):
        return 0
    reads = [s for s in split_on(tokens, STATEMENT_SEPARATORS) if s[0] != "cd"]
    return len(reads) if all(is_read_statement(s) for s in reads) else 0


def is_single_read(calls):
    if len(calls) != 1:
        return False
    call = calls[0]
    if call.get("name") in READ_TOOLS:
        return True
    return call.get("name") == "Bash" and read_statement_count((call.get("input") or {}).get("command", "")) == 1


def trailing_streak(requests):
    streak = []
    for request_id, calls in reversed(requests):
        if not is_single_read(calls):
            break
        streak.append(request_id)
    return streak[::-1]


def run(event):
    if not event.get("transcript_path") or not event.get("agent_id"):
        return
    transcript = transcript_tail.subagent_transcript(event)
    if transcript is None:
        return
    streak = trailing_streak(tool_calls_per_request(transcript_tail.tail_entries(transcript)))
    marker = MARKER_DIR / f"{event.get('session_id', '')}-{event['agent_id']}"
    # The tail can cut a long streak short, so the last reminded request, not a count, decides when to repeat.
    last_reminded = marker.read_text() if marker.exists() else None
    if len(streak) < STREAK or last_reminded in streak[-STREAK:]:
        return
    MARKER_DIR.mkdir(exist_ok=True)
    marker.write_text(streak[-1])
    print(json.dumps({
        "hookSpecificOutput": {"hookEventName": "PostToolUse", "additionalContext": REMINDER}
    }))


if __name__ == "__main__":
    try:
        run(json.load(sys.stdin))
    except Exception:
        # A broken reminder must never block the tool call.
        pass
