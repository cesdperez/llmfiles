#!/usr/bin/env python3
"""The tuning ledger: one JSON object per line recording why each setup change was made and
whether its metric moved. Git keeps the diffs, so an entry points to commits by sha.
The fields are described in local.example/tunesetup/ledger.md.

Usage: tuning-ledger.py [--ledger PATH] validate
       tuning-ledger.py add '<entry json>'          (id defaults to <date>-<n>)
       tuning-ledger.py list [--status S] [--source S] [--open] [--today D]
       tuning-ledger.py pending [--repo ~/llmfiles] [--branch main]
       tuning-ledger.py measure [--days 28] [--root ~/.claude/projects] [--today D]
       tuning-ledger.py set <id> key=value key+=item ...  (value parsed as JSON when it parses;
                                                     += appends to a list such as where)
"""

import argparse
import importlib.util
import itertools
import json
import os
import re
import subprocess
import sys
from datetime import date, datetime, timedelta

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import transcripts as tr  # noqa: E402

DEFAULT_LEDGER = os.path.expanduser("~/llmfiles/local/tunesetup/ledger.jsonl")
OUTPUTS = ("usage", "stages", "friction")
SCRIPTS = {"usage": "claude-usage.py", "stages": "fullsend-stages.py", "friction": "session-friction.py"}
MEASURE_DAYS = 28
DAY = 86400
ENUMS = {
    "source": ("tunesetup", "whichmodels", "manual"),
    "status": ("proposed", "applied", "rejected", "reverted"),
    "expected": ("up", "down"),
    "moved": ("as_expected", "flat", "against"),
    "verdict": ("kept", "reverted", "inconclusive"),
}
REQUIRED = ("id", "date", "source", "change", "files", "where", "why", "metric", "status")
DEFAULTS = {"baseline": None, "baseline_days": None, "hand_counted": False, "expected": None,
            "reversed_by": None, "note": None, "measured": None, "measured_before": None, "measured_on": None,
            "moved": None, "verdict": None}
DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")
MIN_DAYS = 7
MIN_MOVE = 0.05


def is_number(v):
    return isinstance(v, (int, float)) and not isinstance(v, bool)


def validate_entry(e):
    errors = [f"missing {k}" for k in REQUIRED if k not in e]
    errors += [f"unknown field {k}" for k in e if k not in REQUIRED and k not in DEFAULTS]
    e = {**DEFAULTS, **e}
    errors += [f"{k} must be one of {', '.join(v)}" for k, v in ENUMS.items() if e.get(k) is not None and e[k] not in v]
    for k in ("date", "measured_on"):
        if e.get(k) is not None and not DATE_RE.match(str(e[k])):
            errors.append(f"{k} must be YYYY-MM-DD")
    for k in ("files", "where"):
        if not isinstance(e.get(k, []), list):
            errors.append(f"{k} must be a list")
    for k in ("baseline", "baseline_days", "measured", "measured_before"):
        if e[k] is not None and not is_number(e[k]):
            errors.append(f"{k} must be a number")
    metric = e.get("metric")
    if metric is not None and not isinstance(metric, str):
        errors.append("metric must be a string or null")
    elif metric is not None:
        if e["baseline"] is None or e["expected"] is None:
            errors.append("a metric needs a baseline and an expected direction")
        if not e["hand_counted"] and metric.split(":", 1)[0] not in OUTPUTS:
            errors.append(f"metric must start with {', '.join(o + ':' for o in OUTPUTS)} unless hand_counted")
    if e.get("status") == "proposed" and not (e.get("files") or e.get("where")):
        errors.append("a proposal names the files or settings it would touch")
    if e.get("status") == "applied" and not e.get("where"):
        errors.append("an applied entry names its commits or settings key in where")
    if e["measured"] is not None and e["measured_on"] is None:
        errors.append("measured needs measured_on")
    return errors


def load(path):
    if not os.path.exists(path):
        return []
    with open(path) as f:
        return [json.loads(line) for line in f if line.strip()]


def validate_file(path):
    errors, seen = [], set()
    with open(path) as f:
        for n, line in enumerate(f, 1):
            if not line.strip():
                continue
            try:
                e = json.loads(line)
            except json.JSONDecodeError as exc:
                errors.append(f"line {n}: not JSON ({exc.msg})")
                continue
            problems = validate_entry(e)
            if e.get("id") in seen:
                problems.append(f"repeated id {e['id']}")
            seen.add(e.get("id"))
            errors += [f"line {n}: {p}" for p in problems]
    return errors


def save(path, entries):
    tmp = f"{path}.tmp"
    with open(tmp, "w") as f:
        f.writelines(json.dumps(e) + "\n" for e in entries)
    os.replace(tmp, path)


def add(path, e):
    entries = load(path)
    e = {**DEFAULTS, **e}
    if not e.get("id"):
        n = sum(1 for x in entries if x["id"].startswith(f"{e.get('date')}-")) + 1
        e["id"] = f"{e.get('date')}-{n}"
    errors = validate_entry(e) + (["repeated id"] if any(x["id"] == e["id"] for x in entries) else [])
    if errors:
        raise ValueError("; ".join(errors))
    os.makedirs(os.path.dirname(os.path.abspath(path)), exist_ok=True)
    with open(path, "a") as f:
        f.write(json.dumps(e) + "\n")
    return e["id"]


def update(path, entry_id, fields, appends=None):
    entries = load(path)
    match = [e for e in entries if e["id"] == entry_id]
    if not match:
        raise KeyError(entry_id)
    changed = {**match[0], **fields}
    for k, item in (appends or {}).items():
        changed[k] = [*changed.get(k, []), item]
    errors = validate_entry(changed)
    if errors:
        raise ValueError("; ".join(errors))
    save(path, [changed if e["id"] == entry_id else e for e in entries])
    return changed


def open_entries(entries, today):
    cutoff = (date.fromisoformat(today) - timedelta(days=MIN_DAYS)).isoformat()
    return [e for e in entries if e["status"] == "applied" and e.get("verdict") is None
            and e.get("metric") and e["date"] <= cutoff]


def metric_value(metric, outputs):
    """(value, days of the output it came from), or None. A path segment picks a dict key, or
    the element of a list whose `kind` equals it."""
    name, _, path = metric.partition(":")
    node = outputs.get(name)
    if node is None:
        return None
    days = node.get("days")
    segs = path.split("/")
    for i, seg in enumerate(segs):
        if isinstance(node, dict) and seg in node:
            node = node[seg]
        elif isinstance(node, list):
            node = next((x for x in node if isinstance(x, dict) and x.get("kind") == seg), None)
            # session-friction lists only the kinds that occurred, so an absent kind counted zero.
            if node is None and segs[i + 1:] == ["count"]:
                return 0, days
        else:
            return None
    return (node, days) if is_number(node) else None


def measured_value(e, outputs):
    found = metric_value(e["metric"], outputs)
    if found is None:
        return None
    value, days = found
    if e.get("baseline_days") and days:
        value = value * e["baseline_days"] / days
    return round(value, 4)


def judge(e, measured):
    base = e["baseline"]
    change = (measured - base) / abs(base) if base else measured - base
    if abs(change) < MIN_MOVE:
        return "flat", "inconclusive"
    if (change > 0) == (e["expected"] == "up"):
        return "as_expected", "kept"
    return "against", None


def load_script(name):
    spec = importlib.util.spec_from_file_location(name.replace("-", "_")[:-3], os.path.join(os.path.dirname(__file__), name))
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def split_for(e, revs):
    """How to tell an entry's sessions apart: by whether the setup they started on holds every
    sha in where that resolves, or by the entry's date when none resolves or main never held
    them all. Returns (kind, the moment main first held the change, keep-after, keep-before)."""
    commits = [c for c in (revs.resolve(w) for w in e["where"]) if c]
    switch = revs.first_containing(commits) if commits else None
    if switch is not None:
        def holds(rev, test):
            return rev is not None and test(revs.contains(rev, c) for c in commits)
        return ("commit", switch, lambda start, rev: holds(rev, all),
                lambda start, rev: not holds(rev, any))
    switch = datetime.fromisoformat(e["date"]).timestamp()
    return ("date", switch, lambda start, rev: start is not None and start >= switch,
            lambda start, rev: start is not None and start < switch)


def side_days(revs, keep, switch, cutoff, now):
    """Days within [cutoff, now] that main spent on setups keep accepts."""
    inside = (ts for ts in [*(ts for ts, _ in revs.timeline), switch] if cutoff < ts < now)
    points = sorted({cutoff, now, *inside})
    return sum(b - a for a, b in itertools.pairwise(points) if keep(a, revs.at(a))) / DAY


def side_value(e, scans, keep, days):
    """The metric over the sessions keep accepts, or None when it accepts none."""
    name = e["metric"].partition(":")[0]
    if days <= 0 or name not in scans:
        return None
    accepted = []

    def counted(start, rev):
        accepted.append(keep(start, rev))
        return accepted[-1]

    scanned = scans[name](counted)
    return measured_value(e, {name: {**scanned, "days": days}}) if any(accepted) else None


def measure(path, today, days=MEASURE_DAYS, root=tr.DEFAULT_ROOT, revs=None, now=None):
    """Fills measured, measured_before, moved and verdict on each open script entry. The period's
    sessions that started on a setup holding the change are compared with those that started
    before it, or with the baseline when none did. A move against the expected direction leaves
    the verdict to the person, who reverts or keeps it."""
    entries = open_entries(load(path), today)
    revs = tr.SetupRevs() if revs is None else revs
    now = now or datetime.now().timestamp()
    cutoff = tr.cutoff_for(days, now)
    needed = {e["metric"].partition(":")[0] for e in entries if not e.get("hand_counted")} & set(OUTPUTS)
    scans = {}
    for name in needed:
        module = load_script(SCRIPTS[name])
        scanned = module.collect(root, days, now=now, revs=revs)
        scans[name] = lambda keep, m=module, sc=scanned: m.report(sc, keep)
    results = []
    for e in entries:
        if e.get("hand_counted"):
            results.append({"id": e["id"], "metric": e["metric"], "moved": "hand_count"})
            continue
        split, switch, after, before = split_for(e, revs)
        value = side_value(e, scans, after, side_days(revs, after, switch, cutoff, now))
        if value is None:
            results.append({"id": e["id"], "metric": e["metric"], "split": split, "moved": "no_value"})
            continue
        prior = side_value(e, scans, before, side_days(revs, before, switch, cutoff, now))
        moved, verdict = judge({**e, "baseline": e["baseline"] if prior is None else prior}, value)
        update(path, e["id"], {"measured": value, "measured_before": prior, "measured_on": today,
                               "moved": moved, "verdict": verdict})
        results.append({"id": e["id"], "metric": e["metric"], "split": split, "baseline": e["baseline"],
                        "before": prior, "measured": value, "expected": e["expected"], "moved": moved,
                        "verdict": verdict})
    return results


def pending(entries, repo, branch):
    """Each proposal's candidate commits (on the branch since its date, touching its files) and
    the settings keys it names, which no commit shows and are checked by hand."""
    out = {}
    for e in entries:
        if e["status"] != "proposed":
            continue
        commits = []
        if e["files"]:
            commits = subprocess.run(
                ["git", "-C", repo, "log", branch, f"--since={e['date']}T00:00:00", "--format=%h %ad %s",
                 "--date=short", "--", *e["files"]],
                capture_output=True, text=True, check=True).stdout.splitlines()
        out[e["id"]] = {"commits": commits, "check_by_hand": e["where"]}
    return out


def select(entries, status=None, source=None):
    return [e for e in entries if (not status or e["status"] == status) and (not source or e["source"] == source)]


def parse_value(raw):
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        return raw


def parse_fields(pairs):
    """`key=value` pairs to set, and `key+=item` pairs to append to a list field."""
    fields, appends = {}, {}
    for pair in pairs:
        key, _, raw = pair.partition("=")
        if key.endswith("+"):
            appends[key[:-1]] = parse_value(raw)
        else:
            fields[key] = parse_value(raw)
    return fields, appends


def emit(data):
    json.dump(data, sys.stdout, indent=1)
    print()


def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--ledger", default=DEFAULT_LEDGER)
    sub = ap.add_subparsers(dest="cmd", required=True)
    sub.add_parser("validate")
    p = sub.add_parser("add")
    p.add_argument("entry")
    p = sub.add_parser("list")
    p.add_argument("--status", choices=ENUMS["status"])
    p.add_argument("--source", choices=ENUMS["source"])
    p.add_argument("--open", action="store_true")
    p.add_argument("--today", default=date.today().isoformat())
    p = sub.add_parser("pending")
    p.add_argument("--repo", default=os.path.expanduser("~/llmfiles"))
    p.add_argument("--branch", default="main")
    p = sub.add_parser("measure")
    p.add_argument("--days", type=float, default=MEASURE_DAYS, help="the period read on both sides of each change")
    p.add_argument("--root", default=tr.DEFAULT_ROOT)
    p.add_argument("--today", default=date.today().isoformat())
    p = sub.add_parser("set")
    p.add_argument("id")
    p.add_argument("fields", nargs="+")
    a = ap.parse_args()

    try:
        if a.cmd == "validate":
            errors = validate_file(a.ledger)
            print("\n".join(errors) or f"ok, {len(load(a.ledger))} entries")
            sys.exit(1 if errors else 0)
        if a.cmd == "add":
            print(add(a.ledger, json.loads(a.entry)))
        elif a.cmd == "list":
            entries = open_entries(load(a.ledger), a.today) if a.open else load(a.ledger)
            emit(select(entries, a.status, a.source))
        elif a.cmd == "pending":
            emit(pending(load(a.ledger), a.repo, a.branch))
        elif a.cmd == "measure":
            emit(measure(a.ledger, a.today, a.days, a.root))
        elif a.cmd == "set":
            print(json.dumps(update(a.ledger, a.id, *parse_fields(a.fields))))
    except (ValueError, KeyError) as exc:
        sys.exit(f"error: {exc}")


if __name__ == "__main__":
    main()
