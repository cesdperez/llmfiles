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
# Text Claude Code or another agent puts in a user turn; a human message never starts with these.
NOT_HUMAN = ("<task-notification", "<system-reminder", "Another Claude session", "<agent-message",
             "──── From: ", "Base directory", "**Role:**", "<local-command", "Caveat",
             "This session is being continued", "<bash-", "[Request interrupted by user for tool use]",
             "<system-update>", "The server restarted while you were working")
SYSTEM_REMINDER_RE = re.compile(r"<system-reminder>.*?(</system-reminder>|$)", re.S)
# OpenCode replays earlier history between these, one text block per message.
CHECKPOINT_OPEN, CHECKPOINT_CLOSE = "<conversation-checkpoint>", "</conversation-checkpoint>"
# OpenCode forwards a command's body as a user turn headed by its name.
FORWARDED_COMMAND_RE = re.compile(r"# /[\w:-]+[ \t]*\n[ \t]*\n")
# Prompts that start a session for a command without typing it, as (pattern, command).
IMPLIED_COMMANDS = [
    (re.compile(r"\s*Read `?" + re.escape("~/llmfiles/opencode/fullconduct.md")), "fullconduct"),
    # /locallensedreview runs `claude -p "/code-review high"`, which records the prompt as plain text.
    (re.compile(r"\s*/code-review\b"), "locallensedreview"),
]
ORCA_WORKER = "orca-worker"
AGENT_TOOLS = ("Agent", "Task")
# CLIs whose first word alone says too little, so a command is keyed by its subcommand too.
MULTIWORD = {"glab", "gh", "git", "npm", "pnpm", "npx", "yarn", "orca", "gcx", "twg", "aws", "docker", "dotnet",
             "kubectl", "playwright-cli", "cf", "uv", "python3", "bun", "make", "helm", "sp", "claude", "codex"}
SETUP_STATEMENT_RE = re.compile(r"""^(cd|source|export|set)\b|^\w+=(\$?\(.*\)|"[^"]*"|'[^']*')$|^(\w+=\S*\s*)+$""")
ENV_PREFIX_RE = re.compile(r"^(\w+=\S*\s+)+")
SUBCOMMAND_RE = re.compile(r"^[a-z][\w:.-]*$")
PROGRAM_RE = re.compile(r"^[\w.+][\w.+-]*$")


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


def tool_result_text(block):
    content = block.get("content")
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        return " ".join(b.get("text", "") for b in content if isinstance(b, dict))
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


def session_of(path, root):
    """(project directory, session id) of a main or subagent transcript."""
    project, session = os.path.relpath(path, root).split(os.sep)[:2]
    return project, session.removesuffix(".jsonl")


def main_path_of(sub_path, root):
    project, session = session_of(sub_path, root)
    return os.path.join(root, project, session + ".jsonl")


def subagent_paths(root, project, session):
    return sorted(glob.glob(os.path.join(root, project, session, "subagents", "agent-*.jsonl")))


def subagent_meta(sub_path):
    try:
        with open(sub_path.removesuffix(".jsonl") + ".meta.json") as fh:
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


def bash_head(cmd):
    """The program a shell command runs, plus its subcommand for MULTIWORD CLIs.

    Setup statements (cd, source, export, assignments) are skipped, so one-off values and
    paths never become part of the key."""
    statements = [s.strip() for s in re.split(r"&&|;|\n", cmd) if s.strip()]
    rest = [s for s in statements if not SETUP_STATEMENT_RE.match(s)]
    words = ENV_PREFIX_RE.sub("", rest[0]).split() if rest else []
    if not words:
        return "(setup only)" if statements else "(empty)"
    head = os.path.basename(words[0])
    if not PROGRAM_RE.match(head):
        return "(unparsed)"
    if head in MULTIWORD:
        return " ".join([head] + [w for w in words[1:3] if SUBCOMMAND_RE.match(w)][:2])
    return head


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


def implied_command(first_prompt):
    """The command a session ran without a slash command or Skill call, from its first prompt."""
    for pattern, command in IMPLIED_COMMANDS:
        if pattern.match(first_prompt or ""):
            return command
    return None


def primary_command(commands, first_prompt, dispatched):
    """The command a session belongs to, tagged when an Orca coordinator dispatched it."""
    primary = commands[0] if commands else implied_command(first_prompt)
    if primary is None:
        return ORCA_WORKER if dispatched else "(none)"
    return primary + ("[fleet-worker]" if dispatched else "")


def human_text(record):
    """What a person typed in a user turn, or "" for a turn no person wrote.

    Tool results, meta turns, compaction summaries, injected skill bodies, notifications and
    system reminders attached to the turn are left out."""
    if record.get("type") != "user" or record.get("isMeta") or record.get("isCompactSummary"):
        return ""
    content = (record.get("message") or {}).get("content")
    blocks = [content] if isinstance(content, str) else [
        b.get("text", "") for b in content or [] if isinstance(b, dict) and b.get("type") == "text"]
    kept = [b for b in (SYSTEM_REMINDER_RE.sub("", b).strip() for b in outside_checkpoints(blocks))
            if b and not b.startswith(NOT_HUMAN) and not FORWARDED_COMMAND_RE.match(b)]
    return "\n".join(kept)


def outside_checkpoints(blocks):
    inside = False
    for b in blocks:
        if b.lstrip().startswith(CHECKPOINT_OPEN):
            inside = True
        if not inside:
            yield b
        elif CHECKPOINT_CLOSE in b:
            inside = False
            yield b.split(CHECKPOINT_CLOSE, 1)[1]


class SessionHead:
    """How a session began, read from every record of its file, so a session resumed into the
    period keeps its command: the commands it ran, what a person first typed, and whether an Orca
    coordinator dispatched it."""

    def __init__(self, known=frozenset()):
        self.known, self.commands, self.first_prompt, self.dispatched = known, [], None, False

    def feed(self, record):
        self.commands += commands_in(record, self.known)
        if record.get("type") == "user":
            self.dispatched = self.dispatched or is_dispatched(text_of((record.get("message") or {}).get("content")))
            self.first_prompt = self.first_prompt or human_text(record) or None

    def command(self):
        return primary_command(self.commands, self.first_prompt, self.dispatched)

