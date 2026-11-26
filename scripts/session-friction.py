#!/usr/bin/env python3
"""Compact extracts of the sessions that ran a command, for reading friction without the transcripts.

Usage: session-friction.py [--days 14] [--root ~/.claude/projects] [--command NAME ...] [--clip 300]
       session-friction.py --session <id prefix> [--root ...]

Emits JSON on stdout. Per session: the human messages after the first (corrections, nudges,
interrupts), each subagent's brief and report cut short with its review findings, review tables
with the findings that survived, review pushback and rework signals in what the human typed, and
tool errors. Across
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
SLASH_COMMAND = ("<command-name>", "<command-message>")
INTERRUPT = "[Request interrupted"
FINDING_RE = re.compile(r"\[\d+(?:\.\d+)?/10\]")
TABLE_RE = re.compile(r"\|\s*#\s*\|\s*Score", re.I)
TABLE_ROW_RE = re.compile(r"^\|\s*\d+\s*\|\s*([\d.]+)/10\s*\|\s*([\w-]+)", re.M)
PUSHBACK_RE = re.compile(
    r"false positive|not a (real )?bug|noise|wrong finding|disagree|did not apply|declined|not applied|refuted"
    r"|already (handled|guarded)|overrul", re.I)
REWORK_RE = re.compile(
    r"verify (failed|found)|pipeline (failed|is red|went red)|job [`\w:-]+ failed"
    r"|review (missed|did not catch|didn.t catch)|missed by the review|lenses? (missed|did not)", re.I)
# Redaction runs in this order, so an anthropic key is gone before the openai pattern sees it.
# Separate patterns, each starting with a literal, because one alternation scans a hundred times slower.
SECRET_PATTERNS = [
    ("anthropic key", r"sk-ant-[A-Za-z0-9_-]{20,}"),
    ("openai key", r"sk-(?:(?:proj|svcacct|admin)-[A-Za-z0-9_-]{20,}|[A-Za-z0-9]{32,})"),
    ("github token", r"gh[pousr]_[A-Za-z0-9]{30,}|github_pat_[A-Za-z0-9_]{20,}"),
    ("gitlab token", r"glpat-[A-Za-z0-9_-]{20,}"),
    ("aws access key", r"AKIA[0-9A-Z]{16}"),
    ("slack token", r"xox[abprs]-[A-Za-z0-9-]{10,}"),
    ("google key", r"AIza[0-9A-Za-z_-]{35}"),
    ("jwt", r"eyJ[A-Za-z0-9_-]{10,}\.eyJ[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]{10,}"),
    # A digit tells a token from prose such as "Bearer token-from-the-environment".
    ("bearer token", r"Bearer\s+(?=[A-Za-z0-9._~+/=-]*\d)[A-Za-z0-9._~+/=-]{20,}"),
    # Through the END line, or to the end of the text when the key was cut before it.
    ("private key", r"-----BEGIN [A-Z ]*PRIVATE KEY-----(?s:.*?-----END [A-Z ]*PRIVATE KEY-----|.*)"),
]
SECRET_RES = [(kind, re.compile(pattern)) for kind, pattern in SECRET_PATTERNS]
HOME = os.path.expanduser("~")
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


def redact(text):
    """Text with every secret replaced by its kind, and the home directory shortened to ~."""
    text = (text or "").replace(HOME, "~")
    for kind, pattern in SECRET_RES:
        text = pattern.sub(f"[{kind} redacted]", text)
    return text


def clip(text, n):
    text = re.sub(r"\s+", " ", redact(text)).strip()
    return text if len(text) <= n else text[:n] + "..."


def snippets(text, pattern, width=160):
    text = redact(text)
    return [clip(text[max(0, m.start() - width):m.end() + width], 2 * width + 40) for m in pattern.finditer(text)]


def error_kind(tool, message, cmd):
    head = message[:400]
    if "Exit code" in head:
        return f"{tool}: exit nonzero [{tr.bash_head(cmd)}]"
    for pattern, label in ERROR_KINDS:
        if re.search(pattern, head, re.I):
            return f"{tool}: {label}"
    return f"{tool}: other"


def error_message_key(message):
    m = re.search(r"Reason: \[([^\]]+)\]", message)
    if m:
        return "classifier: " + m.group(1)
    return re.sub(r"[0-9a-f]{6,}|\d+", "N", re.sub(r"\s+", " ", message))[:90]


def classify_human(text):
    """'human', 'command' for a typed slash command, or None for text no person wrote."""
    head = text.lstrip()
    if not head or head.startswith(tr.NOT_HUMAN):
        return None
    return "command" if head.startswith(SLASH_COMMAND) else "human"


def windowed(path, cutoff):
    """Each record with its raw line and whether its timestamp falls in the period."""
    with open(path, "rb") as fh:
        for raw in fh:
            try:
                d = json.loads(raw)
            except ValueError:
                continue
            ts = tr.parse_ts(d.get("timestamp"))
            yield d, ts, raw, ts is not None and ts >= cutoff


class FileFindings:
    """Tool errors and secrets of one transcript, from records inside the period."""

    def __init__(self):
        self.secrets = Counter()
        self.errors = []
        self._tools = {}

    def feed(self, d, raw):
        line = raw.decode("utf-8", "replace")
        for kind, pattern in SECRET_RES:
            for _ in pattern.finditer(line):
                self.secrets[kind] += 1
        content = (d.get("message") or {}).get("content")
        for b in content if isinstance(content, list) else []:
            if not isinstance(b, dict):
                continue
            if b.get("type") == "tool_use":
                inp = b.get("input") if isinstance(b.get("input"), dict) else {}
                self._tools[b.get("id")] = (b.get("name"), redact(inp.get("command", "") or ""))
            elif b.get("type") == "tool_result" and b.get("is_error"):
                tool, cmd = self._tools.get(b.get("tool_use_id"), ("?", ""))
                message = redact(tr.tool_result_text(b))
                self.errors.append((error_kind(tool, message, cmd), error_message_key(message), cmd, message))


class MainExtract:
    def __init__(self, known, clip_n):
        self.head, self.clip_n = tr.SessionHead(known), clip_n
        self.humans, self.tables, self.pushback, self.rework = [], [], [], []
        self.interrupts, self.seen_first, self.first_ts = 0, False, None

    def feed(self, d, ts, in_window):
        self.head.feed(d)
        if not in_window:
            return
        self.first_ts = self.first_ts or ts
        content = (d.get("message") or {}).get("content")
        if d.get("type") == "user":
            self.user_text(tr.human_text(d), d.get("timestamp") or "")
        elif d.get("type") == "assistant" and isinstance(content, list):
            for b in content:
                if isinstance(b, dict) and b.get("type") == "text":
                    self.assistant_text(b.get("text", ""))

    def user_text(self, text, at):
        kind = classify_human(text)
        if kind is None:
            return
        # A coordinator wrote the dispatch preamble, yet it is the session's first message.
        if kind == "human" and not tr.is_dispatched(text):
            if text.lstrip().startswith(INTERRUPT):
                self.interrupts += 1
                text = "[interrupted]"
            if self.seen_first and len(self.humans) < MAX_HUMANS:
                self.humans.append({"at": at[:16], "text": clip(text, self.clip_n)})
            self.pushback += snippets(text, PUSHBACK_RE)
            self.rework += snippets(text, REWORK_RE)
        self.seen_first = True

    def assistant_text(self, text):
        if TABLE_RE.search(text):
            text = redact(text)
            rows = TABLE_ROW_RE.findall(text)
            i = text.lower().find("### summary")
            tail = text[i:] if i >= 0 else text[-400:]
            self.tables.append({"kept": [{"score": float(s), "lens": lens} for s, lens in rows],
                                "summary": clip(tail, 2 * self.clip_n)})

    def result(self):
        return {"dispatched": self.head.dispatched, "humans": self.humans, "interrupts": self.interrupts,
                "review_tables": self.tables, "review_pushback": self.pushback[:MAX_SNIPPETS],
                "rework": self.rework[:MAX_SNIPPETS]}


class SubagentExtract:
    def __init__(self, path, clip_n):
        self.path, self.clip_n = path, clip_n
        self.brief, self.report, self.first, self.last = None, "", None, None

    def feed(self, d, ts, in_window):
        if not in_window:
            return
        self.first, self.last = self.first or ts, ts
        content = (d.get("message") or {}).get("content")
        if d.get("type") == "user" and self.brief is None:
            self.brief = tr.text_of(content)
        if d.get("type") == "assistant" and isinstance(content, list):
            for b in content:
                if not isinstance(b, dict):
                    continue
                if b.get("type") == "text" and b.get("text", "").strip():
                    self.report = b["text"]
                elif b.get("type") == "tool_use" and b.get("name") == "SubagentHandback":
                    self.report = (b.get("input") or {}).get("message", "") or self.report

    def result(self):
        meta = tr.subagent_meta(self.path)
        return {
            "type": tr.subagent_type(self.path, meta), "description": meta.get("description"),
            "minutes": round((self.last - self.first) / 60, 1) if self.first else None,
            "brief_chars": len(self.brief or ""), "brief": clip(self.brief, self.clip_n),
            "report_chars": len(self.report), "report": clip(self.report, self.clip_n),
            "findings": len(FINDING_RE.findall(self.report)),
        }


def read_file(path, cutoff, extract):
    """One pass over a transcript, feeding its extract and its errors and secrets."""
    findings = FileFindings()
    for d, ts, raw, in_window in windowed(path, cutoff):
        extract.feed(d, ts, in_window)
        if in_window:
            findings.feed(d, raw)
    return findings


def date_of(ts):
    return datetime.fromtimestamp(ts, timezone.utc).strftime("%Y-%m-%d") if ts else None


class ErrorTally:
    def __init__(self):
        self.by_kind, self.sessions, self.messages, self.example = Counter(), defaultdict(set), defaultdict(Counter), {}
        self.by_command = defaultdict(Counter)

    def add(self, session, command, errors):
        for kind, key, cmd, message in errors:
            self.by_kind[kind] += 1
            self.by_command[command][kind] += 1
            self.sessions[kind].add(session)
            self.messages[kind][key] += 1
            self.example.setdefault((kind, key), (cmd, message))

    def result(self):
        return {
            "tool_errors": [
                {"kind": kind, "count": n, "sessions": len(self.sessions[kind]),
                 "top": [{"message": key, "count": c, "example_cmd": clip(self.example[(kind, key)][0], 150),
                          "example_error": clip(self.example[(kind, key)][1], 200)}
                         for key, c in self.messages[kind].most_common(3)]}
                for kind, n in self.by_kind.most_common()
            ],
            "tool_errors_by_command": {k: dict(v.most_common(10)) for k, v in self.by_command.items()},
        }


def session_row(path, root, cutoff, known, clip_n, revs):
    """A main session's extract, its subagents' extracts, and the errors and secrets across them."""
    main = MainExtract(known, clip_n)
    findings = [read_file(path, cutoff, main)]
    project, session = tr.session_of(path, root)
    agents = []
    for sub in tr.subagent_paths(root, project, session):
        extract = SubagentExtract(sub, clip_n)
        findings.append(read_file(sub, cutoff, extract))
        if extract.first:
            agents.append(extract.result())
    errors = [e for f in findings for e in f.errors]
    secrets = sum((f.secrets for f in findings), Counter())
    row = {"session": session, "project": tr.project_label(project), "date": date_of(main.first_ts),
           "commands": main.head.commands, "command": main.head.command(),
           "setup_rev": revs.at(main.head.start), **main.result(), "tool_errors": len(errors), "agents": agents}
    return row, errors, secrets, main.head.start


def collect(root, days, wanted=None, clip_n=300, now=None, known=None, revs=None):
    """The extracts of the period's sessions whose command is wanted, read once for one or more reports."""
    known = tr.repo_commands() if known is None else known
    wanted = set(wanted or known | {c for _, c in tr.IMPLIED_COMMANDS} | {tr.ORCA_WORKER})
    cutoff = tr.cutoff_for(days, now)
    revs = tr.SetupRevs() if revs is None else revs
    rows = []
    for path, kind in tr.transcript_files(root, cutoff):
        if kind != "main":
            continue
        row, errors, found, start = session_row(path, root, cutoff, known, clip_n, revs)
        if row["command"].removesuffix("[fleet-worker]") in wanted and row["date"]:
            rows.append((row, errors, found, start))
    return {"days": days, "rows": rows}


def analyze(root, days, wanted=None, clip_n=300, now=None, known=None, revs=None):
    return report(collect(root, days, wanted, clip_n, now, known, revs))


def report(scanned, keep=None):
    """The extracts and tallies over the sessions whose (start, setup_rev) keep accepts, or all of them."""
    days = scanned["days"]
    sessions, secrets, tally = [], [], ErrorTally()
    for row, errors, found, start in scanned["rows"]:
        if keep and not keep(start, row["setup_rev"]):
            continue
        tally.add(row["session"], row["command"], errors)
        secrets += [{"session": row["session"], "date": row["date"], "kind": k, "count": n} for k, n in found.items()]
        sessions.append(row)
    sessions.sort(key=lambda s: (s["command"], s["date"]))
    return {"days": days, "sessions_by_command": dict(Counter(s["command"] for s in sessions)),
            **tally.result(), "secrets": secrets, "sessions": sessions}


def timeline(root, prefix, clip_n=300):
    """One session's events in order: human and assistant text, agent briefs and reports, errors."""
    matches = glob.glob(os.path.join(root, "*", prefix + "*.jsonl"))
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
                    if b.get("name") in tr.AGENT_TOOLS:
                        events.append({"at": at, "kind": f"agent brief [{inp.get('subagent_type')}]",
                                       "text": clip(f"{inp.get('description')}: {inp.get('prompt', '')}", clip_n)})
                    elif b.get("name") == "Skill":
                        events.append({"at": at, "kind": "skill", "text": clip(f"{inp.get('skill')} {inp.get('args', '')}", 150)})
        elif d.get("type") == "user" and not d.get("isMeta"):
            for b in content if isinstance(content, list) else []:
                if isinstance(b, dict) and b.get("type") == "tool_result":
                    text = tr.tool_result_text(b)
                    name = names.get(b.get("tool_use_id"), "?")
                    if b.get("is_error"):
                        events.append({"at": at, "kind": f"error [{name}]", "text": clip(text, 200)})
                    elif name in tr.AGENT_TOOLS and "Async agent launched" not in text:
                        events.append({"at": at, "kind": "agent report", "text": clip(text, clip_n)})
            text = tr.text_of(content)
            kind = classify_human(text)
            if kind:
                if last_text:
                    events.append({"at": last_text[0], "kind": "assistant", "text": clip(last_text[1], clip_n)})
                    last_text = None
                events.append({"at": at, "kind": kind, "text": clip(text, clip_n)})
    if last_text:
        events.append({"at": last_text[0], "kind": "assistant", "text": clip(last_text[1], clip_n)})
    return {"session": os.path.basename(matches[0]).removesuffix(".jsonl"), "events": events}


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
