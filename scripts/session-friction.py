#!/usr/bin/env python3
"""Compact extracts of the sessions that ran a command, for reading friction without the transcripts.

Usage: session-friction.py [--days 14] [--root ~/.claude/projects] [--command NAME ...] [--clip 300]
       session-friction.py --session <id prefix> [--root ...]

Emits JSON on stdout. Per session: the human messages after the first (corrections, nudges,
interrupts), each subagent's brief and report cut short with its review findings, review tables
with the findings that survived, review pushback, rework signals and tool errors. Across
sessions: tool errors by category with counts and an example, and secrets found, named by session,
date and kind, never by value. Secrets are redacted from every extract. `--session` gives one
session's timeline instead.
"""

import argparse
import glob
import json
import os
import re
import sys
from collections import Counter, defaultdict
from datetime import datetime, timezone

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import transcripts as tr  # noqa: E402

MAX_HUMANS = 40
MAX_SNIPPETS = 5
NOT_HUMAN = ("<task-notification", "<system-reminder", "Another Claude session", "<agent-message",
             "Base directory", "**Role:**", "<local-command", "Caveat", "This session is being continued",
             "<bash-", "[Request interrupted by user for tool use]")
INTERRUPT = "[Request interrupted"
REVIEWERS = {"reviewer", "reviewer-fast", "codex-reviewer"}
FINDING_RE = re.compile(r"\[\d+(?:\.\d+)?/10\]")
TABLE_RE = re.compile(r"\|\s*#\s*\|\s*Score", re.I)
TABLE_ROW_RE = re.compile(r"^\|\s*\d+\s*\|\s*([\d.]+)/10\s*\|\s*([\w-]+)", re.M)
PUSHBACK_RE = re.compile(
    r"false positive|not a (real )?bug|noise|wrong finding|disagree|did not apply|declined|not applied|refuted"
    r"|already (handled|guarded)|overrul", re.I)
REWORK_RE = re.compile(
    r"verify (failed|found)|pipeline (failed|is red|went red)|job [`\w:-]+ failed"
    r"|review (missed|did not catch|didn.t catch)|missed by the review|lenses? (missed|did not)", re.I)
SECRET_RES = {
    "anthropic key": re.compile(r"sk-ant-[A-Za-z0-9_-]{20,}"),
    "openai key": re.compile(r"sk-proj-[A-Za-z0-9_-]{20,}"),
    "github token": re.compile(r"gh[pousr]_[A-Za-z0-9]{30,}"),
    "gitlab token": re.compile(r"glpat-[A-Za-z0-9_-]{20,}"),
    "aws access key": re.compile(r"AKIA[0-9A-Z]{16}"),
    "slack token": re.compile(r"xox[abprs]-[A-Za-z0-9-]{10,}"),
    "private key": re.compile(r"-----BEGIN [A-Z ]*PRIVATE KEY-----"),
}
ERROR_KINDS = [
    (r"denied by a built-in Claude Code safety check", "safety-check denial"),
    (r"permission|not allowed|denied", "permission denied"),
    (r"hook", "hook block"),
    (r"File has not been read yet", "edit before read"),
    (r"modified since", "file modified since read"),
    (r"String to replace not found|old_string", "edit string not found"),
    (r"does not exist|No such file|ENOENT", "file not found"),
    (r"session limit|rate_limit|usage limit", "usage limit"),
    (r"timed out|timeout", "timeout"),
    (r"InputValidationError|Invalid tool parameters", "tool input invalid"),
    (r"Blocked:", "blocked command"),
    (r"interrupted", "interrupted"),
    (r"too large|exceeds maximum", "output too large"),
]
MULTIWORD = {"pnpm", "glab", "orca", "git", "playwright-cli", "npx", "docker", "npm", "dotnet", "gh"}


def redact(text):
    for kind, pattern in SECRET_RES.items():
        text = pattern.sub(f"[{kind} redacted]", text)
    return text


def clip(text, n):
    text = redact(re.sub(r"\s+", " ", text or "")).strip()
    return text if len(text) <= n else text[:n] + "..."


def tool_result_text(block):
    content = block.get("content")
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        return " ".join(b.get("text", "") for b in content if isinstance(b, dict))
    return ""


def command_head(cmd):
    words = re.sub(r"^((cd|source|export)\s+\S+\s*(&&|;|\n)\s*)+", "", cmd.strip()).split()
    if not words:
        return "?"
    return " ".join(words[:2]) if words[0] in MULTIWORD else words[0]


def error_kind(tool, message, cmd):
    head = message[:400]
    if "Exit code" in head:
        return f"{tool}: exit nonzero [{command_head(cmd)}]"
    for pattern, label in ERROR_KINDS:
        if re.search(pattern, head, re.I):
            return f"{tool}: {label}"
    return f"{tool}: other"


def error_message_key(message):
    m = re.search(r"Reason: \[([^\]]+)\]", message)
    if m:
        return "classifier: " + m.group(1)
    return re.sub(r"[0-9a-f]{6,}|\d+", "N", re.sub(r"\s+", " ", message))[:90]


def is_human(text):
    return not text.lstrip().startswith(NOT_HUMAN)


def scan_secrets(path, found):
    with open(path, "rb") as fh:
        for raw in fh:
            line = raw.decode("utf-8", "replace")
            for kind, pattern in SECRET_RES.items():
                n = len(pattern.findall(line))
                if n:
                    found[kind] += n


def scan_errors(path, errors, sink):
    names, cmds = {}, {}
    for d in tr.records(path):
        content = (d.get("message") or {}).get("content")
        if not isinstance(content, list):
            continue
        for b in content:
            if not isinstance(b, dict):
                continue
            if b.get("type") == "tool_use":
                names[b.get("id")] = b.get("name")
                inp = b.get("input") if isinstance(b.get("input"), dict) else {}
                cmds[b.get("id")] = inp.get("command", "") or ""
            elif b.get("type") == "tool_result" and b.get("is_error"):
                message = tool_result_text(b)
                cmd = cmds.get(b.get("tool_use_id"), "")
                kind = error_kind(names.get(b.get("tool_use_id"), "?"), message, cmd)
                errors[kind] += 1
                sink.append((kind, error_message_key(message), cmd, message))


def subagent_extract(path, clip_n):
    meta = tr.subagent_meta(path)
    brief, report, first, last = None, "", None, None
    for d in tr.records(path):
        ts = tr.parse_ts(d.get("timestamp"))
        if ts:
            first, last = first or ts, ts
        content = (d.get("message") or {}).get("content")
        if d.get("type") == "user" and brief is None:
            brief = tr.text_of(content)
        if d.get("type") == "assistant" and isinstance(content, list):
            for b in content:
                if not isinstance(b, dict):
                    continue
                if b.get("type") == "text" and b.get("text", "").strip():
                    report = b["text"]
                elif b.get("type") == "tool_use" and b.get("name") == "SubagentHandback":
                    report = (b.get("input") or {}).get("message", "") or report
    return {
        "type": tr.subagent_type(path, meta), "description": meta.get("description"),
        "minutes": round((last - first) / 60, 1) if first else None,
        "brief_chars": len(brief or ""), "brief": clip(brief, clip_n),
        "report_chars": len(report), "report": clip(report, clip_n),
        "findings": len(FINDING_RE.findall(report)),
    }


def snippets(text, pattern, width=160):
    return [clip(text[max(0, m.start() - width):m.end() + width], 2 * width + 40) for m in pattern.finditer(text)]


def main_extract(path, clip_n, known, cutoff):
    humans, commands, interrupts = [], [], 0
    seen_first, dispatched, first_ts = False, False, None
    tables, pushback, rework = [], [], []
    for d in tr.records(path):
        ts = tr.parse_ts(d.get("timestamp"))
        if ts is None or ts < cutoff:
            continue
        first_ts = first_ts or ts
        commands += tr.commands_in(d, known)
        content = (d.get("message") or {}).get("content")
        if d.get("type") == "user" and not d.get("isMeta") and not d.get("isCompactSummary"):
            text = tr.text_of(content)
            dispatched = dispatched or tr.is_dispatched(text)
            if not text.strip() or not is_human(text):
                continue
            if text.lstrip().startswith(INTERRUPT):
                interrupts += 1
                text = "[interrupted]"
            if seen_first and len(humans) < MAX_HUMANS:
                humans.append({"at": (d.get("timestamp") or "")[:16], "text": clip(text, clip_n)})
            seen_first = True
            pushback += snippets(text, PUSHBACK_RE)
        elif d.get("type") == "assistant" and isinstance(content, list):
            for b in content:
                if not (isinstance(b, dict) and b.get("type") == "text"):
                    continue
                text = b.get("text", "")
                if TABLE_RE.search(text):
                    rows = TABLE_ROW_RE.findall(text)
                    tail = text[text.lower().find("### summary"):] if "### summary" in text.lower() else text[-400:]
                    tables.append({"kept": [{"score": float(s), "lens": lens} for s, lens in rows],
                                   "summary": clip(tail, 2 * clip_n)})
                pushback += snippets(text, PUSHBACK_RE)
                rework += snippets(text, REWORK_RE)
    return {
        "commands": commands, "dispatched": dispatched, "first_ts": first_ts, "humans": humans,
        "interrupts": interrupts, "review_tables": tables,
        "review_pushback": pushback[:MAX_SNIPPETS], "rework": rework[:MAX_SNIPPETS],
    }


def date_of(ts):
    return datetime.fromtimestamp(ts, timezone.utc).strftime("%Y-%m-%d") if ts else None


def sessions_in_scope(root, cutoff, known, wanted):
    for path, kind in tr.transcript_files(root, cutoff):
        if kind == "main":
            commands = []
            for d in tr.records(path):
                commands += tr.commands_in(d, known)
                if commands:
                    break
            if commands and commands[0] in wanted:
                yield path, commands[0]


def analyze(root, days, wanted=None, clip_n=300, now=None, known=None):
    known = tr.repo_commands() if known is None else known
    wanted = set(wanted or known)
    cutoff = tr.cutoff_for(days, now)
    sessions, secrets = [], []
    errors_by_kind, sessions_by_kind, examples = Counter(), defaultdict(set), defaultdict(Counter)
    example_of = {}
    by_command = defaultdict(Counter)
    for path, command in sessions_in_scope(root, cutoff, known, wanted):
        project, session = os.path.relpath(path, root).split(os.sep)[:2]
        session = session[:-len(".jsonl")]
        row = main_extract(path, clip_n, known, cutoff)
        subs = sorted(glob.glob(os.path.join(root, project, session, "subagents", "agent-*.jsonl")))
        found, errors, sink = Counter(), Counter(), []
        for p in [path] + subs:
            scan_secrets(p, found)
            scan_errors(p, errors, sink)
        for kind, key, cmd, message in sink:
            sessions_by_kind[kind].add(session)
            examples[kind][key] += 1
            example_of.setdefault((kind, key), (cmd, message))
        errors_by_kind.update(errors)
        label = command + ("[fleet-worker]" if row["dispatched"] else "")
        by_command[label].update(errors)
        date = date_of(row.pop("first_ts"))
        secrets += [{"session": session, "date": date, "kind": k, "count": n} for k, n in found.items()]
        sessions.append({
            "session": session, "project": tr.project_label(project), "date": date, "command": label,
            **row, "tool_errors": sum(errors.values()),
            "agents": [subagent_extract(p, clip_n) for p in subs],
        })
    sessions.sort(key=lambda s: (s["command"], s["date"] or ""))
    return {
        "days": days,
        "sessions_by_command": dict(Counter(s["command"] for s in sessions)),
        "tool_errors": [
            {"kind": kind, "count": n, "sessions": len(sessions_by_kind[kind]),
             "top": [{"message": key, "count": c, "example_cmd": clip(example_of[(kind, key)][0], 150),
                      "example_error": clip(example_of[(kind, key)][1], 200)}
                     for key, c in examples[kind].most_common(3)]}
            for kind, n in errors_by_kind.most_common()
        ],
        "tool_errors_by_command": {k: dict(v.most_common(10)) for k, v in by_command.items()},
        "secrets": secrets,
        "sessions": sessions,
    }


def timeline(root, prefix, clip_n=300):
    """One session's events in order: human and assistant text, agent briefs and reports, errors."""
    matches = [p for p in glob.glob(os.path.join(root, "*", prefix + "*.jsonl"))]
    if len(matches) != 1:
        return {"error": f"{len(matches)} sessions match {prefix!r}"}
    events, names, last_text = [], {}, None
    for d in tr.records(matches[0]):
        at = (d.get("timestamp") or "")[:16]
        content = (d.get("message") or {}).get("content")
        if d.get("type") == "assistant" and isinstance(content, list):
            for b in content:
                if not isinstance(b, dict):
                    continue
                if b.get("type") == "text" and b.get("text", "").strip():
                    last_text = (at, b["text"])
                elif b.get("type") == "tool_use":
                    names[b.get("id")] = b.get("name")
                    inp = b.get("input") if isinstance(b.get("input"), dict) else {}
                    if b.get("name") in ("Agent", "Task"):
                        events.append({"at": at, "kind": f"agent brief [{inp.get('subagent_type')}]",
                                       "text": clip(f"{inp.get('description')}: {inp.get('prompt', '')}", clip_n)})
                    elif b.get("name") == "Skill":
                        events.append({"at": at, "kind": "skill", "text": clip(f"{inp.get('skill')} {inp.get('args', '')}", 150)})
        elif d.get("type") == "user" and not d.get("isMeta"):
            if isinstance(content, list):
                for b in content:
                    if isinstance(b, dict) and b.get("type") == "tool_result":
                        text = tool_result_text(b)
                        name = names.get(b.get("tool_use_id"), "?")
                        if b.get("is_error"):
                            events.append({"at": at, "kind": f"error [{name}]", "text": clip(text, 200)})
                        elif name in ("Agent", "Task") and "Async agent launched" not in text:
                            events.append({"at": at, "kind": "agent report", "text": clip(text, clip_n)})
            text = tr.text_of(content)
            if text.strip() and is_human(text):
                if last_text:
                    events.append({"at": last_text[0], "kind": "assistant", "text": clip(last_text[1], clip_n)})
                    last_text = None
                events.append({"at": at, "kind": "human", "text": clip(text, clip_n)})
    if last_text:
        events.append({"at": last_text[0], "kind": "assistant", "text": clip(last_text[1], clip_n)})
    return {"session": os.path.basename(matches[0])[:-len(".jsonl")], "events": events}


def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--days", type=float, default=14)
    ap.add_argument("--root", default=tr.DEFAULT_ROOT)
    ap.add_argument("--command", action="append", help="limit to sessions whose first command is this")
    ap.add_argument("--clip", type=int, default=300, help="characters kept per message, brief or report")
    ap.add_argument("--session", help="print one session's timeline instead")
    a = ap.parse_args()
    out = timeline(a.root, a.session, a.clip) if a.session else analyze(a.root, a.days, a.command, a.clip)
    json.dump(out, sys.stdout, indent=1)
    print()


if __name__ == "__main__":
    main()
