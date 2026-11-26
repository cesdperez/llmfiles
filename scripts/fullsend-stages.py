#!/usr/bin/env python3
"""Minutes per /fullsend stage, read from the `orca worktree set --comment "<n>/8 <stage>"`
calls each /fullsend session makes at a stage boundary.

Usage: fullsend-stages.py [--days 14] [--root ~/.claude/projects]

Emits JSON on stdout: {"runs": [...], "stages": {"<n> <stage>": {n, median, p75, p90, total}}}.
A stage runs from its first mark to the next stage's first mark, the last one to the end of the
session. Stages are keyed by number, labelled with the name most runs gave it.
"""

import argparse
import json
import os
import re
import statistics
import sys
from collections import Counter

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import transcripts as tr  # noqa: E402

MARK_RE = re.compile(r"""--comment\s+["'](\d+)/\d+\s*([A-Za-z -]*)""")
MIN_STAGES = 4
# A stage open longer than this waited on a person or sat overnight, so it says nothing about working time.
MAX_STAGE_MIN = 600


def marks_in(path, cutoff):
    marks, start, last, fullsend = [], None, None, False
    for d in tr.records(path):
        ts = tr.parse_ts(d.get("timestamp"))
        start = start or ts
        if ts is None or ts < cutoff:
            continue
        last = ts
        fullsend = fullsend or "fullsend" in tr.commands_in(d, {"fullsend"})
        if d.get("type") != "assistant":
            continue
        for b in (d.get("message") or {}).get("content") or []:
            if isinstance(b, dict) and b.get("type") == "tool_use" and b.get("name") == "Bash":
                m = MARK_RE.search((b.get("input") or {}).get("command", ""))
                if m:
                    marks.append((ts, int(m.group(1)), m.group(2).strip().lower()))
    return (marks if fullsend else []), start, last


def run_of(path, root, cutoff, revs):
    marks, start, last = marks_in(path, cutoff)
    first = {}
    for ts, n, name in marks:
        first.setdefault(n, (ts, n, name))
    if len(first) < MIN_STAGES:
        return None
    order = sorted(first.values())
    stages, names = {}, {}
    for (stage_start, n, name), (end, *_) in zip(order, order[1:] + [(last,)], strict=True):
        names[n] = name
        minutes = (end - stage_start) / 60
        if minutes <= MAX_STAGE_MIN:
            stages[n] = round(minutes, 1)
    project, session = tr.session_of(path, root)
    return {"project": tr.project_label(project), "session": session, "start": start, "setup_rev": revs.at(start),
            "total_min": round((last - order[0][0]) / 60, 1), "stages": stages, "names": names}


def summary(values):
    v = sorted(values)
    return {"n": len(v), "median": round(statistics.median(v), 1), "p75": v[int(len(v) * .75)],
            "p90": v[int(len(v) * .9)], "total": round(sum(v), 1)}


def collect(root, days, now=None, revs=None):
    cutoff = tr.cutoff_for(days, now)
    revs = tr.SetupRevs() if revs is None else revs
    runs = [r for p, kind in tr.transcript_files(root, cutoff) if kind == "main" and (r := run_of(p, root, cutoff, revs))]
    return {"days": days, "runs": runs}


def analyze(root, days, now=None, revs=None):
    return report(collect(root, days, now, revs))


def report(scanned, keep=None):
    """Stage minutes over the runs whose (start, setup_rev) keep accepts, or all of them."""
    days = scanned["days"]
    runs = [dict(r) for r in scanned["runs"] if not keep or keep(r["start"], r["setup_rev"])]
    names = {}
    for r in runs:
        for n, name in r.pop("names").items():
            names.setdefault(n, Counter())[name] += 1
    label = {n: f"{n} {c.most_common(1)[0][0]}".strip() for n, c in names.items()}
    per_stage = {}
    for r in runs:
        del r["start"]
        r["stages"] = {label[n]: minutes for n, minutes in sorted(r["stages"].items())}
        for name, minutes in r["stages"].items():
            per_stage.setdefault(name, []).append(minutes)
    ordered = sorted(per_stage, key=lambda name: int(name.split()[0]))
    return {"days": days, "runs": sorted(runs, key=lambda r: -r["total_min"]),
            "stages": {name: summary(per_stage[name]) for name in ordered}}


def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--days", type=float, default=14)
    ap.add_argument("--root", default=tr.DEFAULT_ROOT)
    a = ap.parse_args()
    json.dump(analyze(a.root, a.days), sys.stdout, indent=1)
    print()


if __name__ == "__main__":
    main()
