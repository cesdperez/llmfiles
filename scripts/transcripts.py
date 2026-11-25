"""Streaming reads of Claude Code transcripts, shared by the /tunesetup scripts.

A projects root holds `<project>/<session>.jsonl` for main sessions and
`<project>/<session>/subagents/agent-*.jsonl` for their subagents, with the agent type in
the sibling `.meta.json`. Transcripts run to gigabytes a week, so they are read line by line.
"""

import glob
import json
import os
import re
import time
from datetime import datetime
from pathlib import Path

DEFAULT_ROOT = os.path.expanduser("~/.claude/projects")
REPO = Path(__file__).resolve().parent.parent
COMMAND_RE = re.compile(r"<command-name>/?([\w:-]+)</command-name>")
DISPATCH_MARKERS = ("You are a dispatched worker", "Dispatch ID", "Dispatch id")


def repo_commands():
    return {p.stem for p in (REPO / "commands").glob("*.md")}


def cutoff_for(days, now=None):
    return (now or time.time()) - days * 86400


def parse_ts(value):
    if not value:
        return None
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00")).timestamp()
    except ValueError:
        return None


def text_of(content):
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        return "\n".join(b.get("text", "") for b in content if isinstance(b, dict) and b.get("type") == "text")
    return ""


def records(path):
    with open(path, "rb") as fh:
        for raw in fh:
            try:
                yield json.loads(raw)
            except ValueError:
                continue


def transcript_files(root, cutoff):
    """Main and subagent transcripts touched since the cutoff, as (path, kind)."""
    for path in glob.glob(os.path.join(root, "**", "*.jsonl"), recursive=True):
        if os.path.getmtime(path) < cutoff:
            continue
        depth = len(os.path.relpath(path, root).split(os.sep))
        yield path, "main" if depth == 2 else "sub"


def main_path_of(sub_path, root):
    project, session = os.path.relpath(sub_path, root).split(os.sep)[:2]
    return os.path.join(root, project, session + ".jsonl")


def subagent_meta(sub_path):
    try:
        with open(sub_path[:-len(".jsonl")] + ".meta.json") as fh:
            return json.load(fh)
    except (OSError, ValueError):
        return {}


def subagent_type(sub_path, meta):
    if meta.get("agentType"):
        return meta["agentType"]
    return "workflow-agent" if f"{os.sep}workflows{os.sep}" in sub_path else "unknown"


def project_label(project_dir):
    """Project directory name without the encoded home prefix, so output holds no user name."""
    home = "-" + os.path.expanduser("~").strip("/").replace("/", "-").replace(".", "-") + "-"
    return project_dir[len(home):] if project_dir.startswith(home) else project_dir


def commands_in(record, known):
    """Command names a record invokes: a typed slash command or a Skill call naming one."""
    message = record.get("message") or {}
    content = message.get("content")
    if record.get("type") == "user" and not record.get("isMeta"):
        return [n.split(":")[-1] for n in COMMAND_RE.findall(text_of(content)) if n.split(":")[-1] in known]
    if record.get("type") == "assistant" and isinstance(content, list):
        return [
            b["input"]["skill"]
            for b in content
            if isinstance(b, dict) and b.get("type") == "tool_use" and b.get("name") == "Skill"
            and isinstance(b.get("input"), dict) and b["input"].get("skill") in known
        ]
    return []


def is_dispatched(text):
    return any(m in text[:2000] for m in DISPATCH_MARKERS)
