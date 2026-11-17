#!/usr/bin/env python3
"""Ledger of conductor builder runs and finished tasks, used to tune opencode/builders.md.

Usage:
  builder-evals.py append run --kind KIND --builder NAME --session ID [--session ID]
                              --passed yes|no --escalated yes|no [--fallback-from MODEL] [--repo PATH]
  builder-evals.py append run --kind KIND --builder NAME --quota-error --model MODEL [--repo PATH]
  builder-evals.py append task --task TITLE --briefs N --fix-briefs N --escalations N --findings N
                               --green yes|no [--repo PATH]
  builder-evals.py summary [--since 7d|24h|YYYY-MM-DD]
  builder-evals.py usage [--since 7d|24h|YYYY-MM-DD]

A run row covers one brief: one --session per attempt, so a narrowed retry adds a session.
--quota-error marks a builder that hit its provider's usage limit, which says nothing about the
builder, so `summary` keeps it out of pass and escalation rates. It takes --model instead of
sessions, because a session cut off by a quota error may have no model or timing. The builder that
took the brief over logs its own row with --fallback-from set to the quota-hit model.
Model, provider and wall time come from the opencode session API.

A task row covers one user task from start to finish: briefs sent, fix briefs after review,
escalations, review findings scoring 7 or more, and whether the final check or pipeline went green.

`summary` flags each model and kind that misses the routing bar in opencode/builders.md. `usage`
reads every opencode session in the window, not the ledger, so it also covers the conductor,
reviewers, workers and search agents.

Rows go to local/builder-evals.jsonl, or to LLMFILES_BUILDER_EVALS. `summary` and `usage` emit JSON.
"""

import argparse
import json
import os
import subprocess
import sys
from collections import defaultdict
from datetime import datetime, timedelta, timezone
from pathlib import Path

DEFAULT_PATH = Path(__file__).resolve().parent.parent / "local" / "builder-evals.jsonl"
# The routing bar in opencode/builders.md; change both together.
BAR_MIN_RUNS = 20
BAR_PASS_RATE = 0.95
BAR_ESCALATION_RATE = 0.03
BAR_QUOTA_ERROR_RATE = 0.1
BAR_CONFIDENCE_Z = 1.96


def ledger_path():
    return Path(os.environ.get("LLMFILES_BUILDER_EVALS", DEFAULT_PATH)).expanduser()


def session(session_id):
    result = subprocess.run(
        ["opencode", "api", "GET", f"/api/session/{session_id}"], capture_output=True, text=True,
    )
    try:
        data = json.loads(result.stdout)["data"]
    except (json.JSONDecodeError, KeyError, TypeError):
        sys.exit(f"cannot read opencode session {session_id}: {result.stdout or result.stderr}".strip())
    model, time = data.get("model"), data.get("time")
    if not model or not time:
        sys.exit(f"session {session_id} has no model or timing; pass a builder's session ID")
    # A busy session has no idle time yet, so its last update is the best end mark.
    end = time.get("idle") or time["updated"]
    return {
        "model": f"{model['providerID']}/{model['id']}" + (f"#{model['variant']}" if model.get("variant") else ""),
        "provider": model["providerID"],
        "wall_s": round((end - time["created"]) / 1000, 1),
        "cost": data.get("cost", 0),
    }


def opencode_get(path):
    result = subprocess.run(["opencode", "api", "GET", path], capture_output=True, text=True)
    try:
        return json.loads(result.stdout)
    except json.JSONDecodeError:
        sys.exit(f"cannot read opencode {path}: {result.stdout or result.stderr}".strip())


def since(value):
    unit = {"h": "hours", "d": "days"}.get(value[-1:])
    try:
        if unit:
            return datetime.now(timezone.utc) - timedelta(**{unit: float(value[:-1])})
        moment = datetime.fromisoformat(value)
    except ValueError as error:
        raise argparse.ArgumentTypeError("expected 7d, 24h or an ISO date") from error
    return moment if moment.tzinfo else moment.replace(tzinfo=timezone.utc)


def count(value):
    if not value.isdigit():
        raise argparse.ArgumentTypeError("expected a whole number")
    return int(value)


def yes(value):
    if value not in ("yes", "no"):
        raise argparse.ArgumentTypeError("expected yes or no")
    return value == "yes"


def quota_row(args):
    return {
        "type": "run", "kind": args.kind, "builder": args.builder,
        "model": args.model, "provider": args.model.split("/", 1)[0],
        "passed": False, "retries": 0, "escalated": False, "wall_s": 0, "cost": 0, "quota_error": True,
    }


def run_row(args):
    if args.quota_error:
        return quota_row(args)
    attempts = [session(session_id) for session_id in args.session]
    models = {attempt["model"] for attempt in attempts}
    if len(models) > 1:
        sys.exit(f"sessions ran on different models {sorted(models)}; pass only the builder's own sessions and mark a handoff with --escalated yes")
    row = {
        "type": "run", "kind": args.kind, "builder": args.builder,
        "model": attempts[0]["model"], "provider": attempts[0]["provider"],
        "passed": args.passed, "retries": len(attempts) - 1, "escalated": args.escalated,
        "wall_s": round(sum(attempt["wall_s"] for attempt in attempts), 1),
        "cost": sum(attempt["cost"] for attempt in attempts),
    }
    if args.fallback_from:
        row["fallback_from"] = args.fallback_from
    return row


def task_row(args):
    return {
        "type": "task", "task": args.task, "briefs": args.briefs, "fix_briefs": args.fix_briefs,
        "escalations": args.escalations, "findings": args.findings, "green": args.green,
    }


def append(args):
    row = {"run": run_row, "task": task_row}[args.row](args)
    row = {"ts": datetime.now(timezone.utc).isoformat(timespec="seconds"), "repo": args.repo, **row}
    path = ledger_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a") as ledger:
        ledger.write(json.dumps(row) + "\n")
    print(json.dumps(row))


def stats(rows):
    runs = [row for row in rows if not row.get("quota_error")]
    quota_errors = len(rows) - len(runs)
    passes = sum(run["passed"] for run in runs)
    escalations = sum(run["escalated"] for run in runs)
    return {
        "runs": len(runs),
        "passes": passes,
        "pass_rate": ratio(passes, len(runs)),
        "avg_retries": average([run["retries"] for run in runs]),
        "escalations": escalations,
        "escalation_rate": ratio(escalations, len(runs)),
        "avg_wall_s": average([run["wall_s"] for run in runs]),
        "quota_errors": quota_errors,
        "quota_error_rate": ratio(quota_errors, len(rows)),
    }


def ratio(part, whole):
    return round(part / whole, 2) if whole else None


def average(values):
    return round(sum(values) / len(values), 1) if values else None


def task_stats(tasks):
    return {
        "tasks": len(tasks),
        "green_rate": ratio(sum(task["green"] for task in tasks), len(tasks)),
        **{f"avg_{key}": average([task[key] for task in tasks]) for key in ("briefs", "fix_briefs", "escalations", "findings")},
    }


def wilson(part, whole):
    z = BAR_CONFIDENCE_Z
    rate = part / whole
    center = (rate + z * z / (2 * whole)) / (1 + z * z / whole)
    spread = z * (rate * (1 - rate) / whole + z * z / (4 * whole * whole)) ** 0.5 / (1 + z * z / whole)
    return round(center - spread, 2), round(center + spread, 2)


def flags(models):
    found = []
    for model, model_stats in models.items():
        if (model_stats["quota_error_rate"] or 0) > BAR_QUOTA_ERROR_RATE:
            found.append(f"{model}: quota_error_rate {model_stats['quota_error_rate']} is above {BAR_QUOTA_ERROR_RATE}")
        for kind, kind_stats in model_stats["by_kind"].items():
            if kind_stats["runs"] < BAR_MIN_RUNS:
                continue
            # A rate past the bar is noise until its confidence bound is past it too.
            _, pass_high = wilson(kind_stats["passes"], kind_stats["runs"])
            if pass_high < BAR_PASS_RATE:
                found.append(f"{model} {kind}: pass_rate {kind_stats['pass_rate']} (upper bound {pass_high}) is below {BAR_PASS_RATE}")
            escalation_low, _ = wilson(kind_stats["escalations"], kind_stats["runs"])
            if escalation_low > BAR_ESCALATION_RATE:
                found.append(f"{model} {kind}: escalation_rate {kind_stats['escalation_rate']} (lower bound {escalation_low}) is above {BAR_ESCALATION_RATE}")
    return found


def summary(args):
    path = ledger_path()
    rows = [json.loads(line) for line in path.read_text().splitlines() if line.strip()] if path.exists() else []
    if args.since:
        rows = [row for row in rows if datetime.fromisoformat(row["ts"]) >= args.since]
    runs, tasks = defaultdict(list), []
    # A ledger can hold rows of retired types, such as "ab", which the summary skips.
    for row in rows:
        if row["type"] == "run":
            runs[(row["model"], row["kind"])].append(row)
        elif row["type"] == "task":
            tasks.append(row)
    models = {}
    for model in sorted({model for model, _ in runs}):
        kinds = sorted({kind for m, kind in runs if m == model})
        models[model] = {
            **stats([run for kind in kinds for run in runs[(model, kind)]]),
            "by_kind": {kind: stats(runs[(model, kind)]) for kind in kinds},
        }
    providers = defaultdict(int)
    for run_rows in runs.values():
        for run in run_rows:
            if not run.get("quota_error"):
                providers[run["provider"]] += 1
    total = sum(providers.values())
    print(json.dumps({
        "ledger": str(path),
        "since": args.since.isoformat(timespec="seconds") if args.since else None,
        "flags": flags(models),
        "tasks": task_stats(tasks),
        "models": models,
        "provider_split": {name: {"runs": runs_on, "share": ratio(runs_on, total)} for name, runs_on in sorted(providers.items())},
    }, indent=2))


def sessions_since(start):
    cutoff = start.timestamp() * 1000
    cursor = None
    while True:
        page = opencode_get("/api/session?limit=200" + (f"&cursor={cursor}" if cursor else ""))
        for data in page.get("data", []):
            # The list is sorted by last update, newest first.
            if data["time"]["updated"] < cutoff:
                return
            yield data
        cursor = (page.get("cursor") or {}).get("next")
        if not cursor or not page.get("data"):
            return


def usage(args):
    start = args.since or datetime.now(timezone.utc) - timedelta(days=7)
    groups = defaultdict(list)
    for data in sessions_since(start):
        model = data.get("model") or {}
        name = f"{model.get('providerID')}/{model.get('id')}" + (f"#{model['variant']}" if model.get("variant") else "")
        groups[(data.get("agent") or "unknown", name, model.get("providerID") or "unknown")].append(data)
    agents, providers = [], defaultdict(int)
    for (agent, model, provider), group in sorted(groups.items()):
        tokens = [data.get("tokens") or {} for data in group]
        fresh = sum(t.get("input", 0) + t.get("output", 0) + t.get("reasoning", 0) for t in tokens)
        providers[provider] += fresh
        outcomes = [data.get("outcome") for data in group]
        agents.append({
            "agent": agent, "model": model, "sessions": len(group),
            "failed": outcomes.count("failed"), "interrupted": outcomes.count("interrupted"),
            "tokens": fresh,
            "cache_read": sum((t.get("cache") or {}).get("read", 0) for t in tokens),
            "avg_wall_s": average([((data["time"].get("idle") or data["time"]["updated"]) - data["time"]["created"]) / 1000 for data in group]),
        })
    total = sum(providers.values())
    print(json.dumps({
        "since": start.isoformat(timespec="seconds"),
        "agents": sorted(agents, key=lambda entry: -entry["tokens"]),
        "provider_token_split": {name: {"tokens": tokens, "share": ratio(tokens, total)} for name, tokens in sorted(providers.items())},
    }, indent=2))


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    commands = parser.add_subparsers(dest="command", required=True)
    for name, func in (("summary", summary), ("usage", usage)):
        report = commands.add_parser(name)
        report.add_argument("--since", type=since)
        report.set_defaults(func=func)
    rows = commands.add_parser("append").add_subparsers(dest="row", required=True)
    run = rows.add_parser("run")
    run.add_argument("--builder", required=True)
    run.add_argument("--session", action="append")
    run.add_argument("--passed", type=yes)
    run.add_argument("--escalated", type=yes)
    run.add_argument("--quota-error", action="store_true")
    run.add_argument("--model")
    run.add_argument("--fallback-from")
    task = rows.add_parser("task")
    task.add_argument("--task", required=True)
    for key in ("--briefs", "--fix-briefs", "--escalations", "--findings"):
        task.add_argument(key, type=count, required=True)
    task.add_argument("--green", type=yes, required=True)
    run.add_argument("--kind", required=True)
    for row in (run, task):
        row.add_argument("--repo", default=os.getcwd())
        row.set_defaults(func=append)
    args = parser.parse_args()
    if args.command == "append" and args.row == "run":
        check_outcome(parser, args)
    args.func(args)


def check_outcome(parser, args):
    if args.quota_error:
        if args.model is None or "/" not in args.model:
            parser.error("--quota-error needs --model provider/model")
        if args.session or args.passed is not None or args.escalated is not None or args.fallback_from:
            parser.error("--quota-error takes --model in place of --session, --passed, --escalated and --fallback-from")
    elif args.model is not None:
        parser.error("--model goes with --quota-error; other rows read the model from --session")
    elif not args.session or args.passed is None or args.escalated is None:
        parser.error("a run row needs --session, --passed and --escalated, or --quota-error with --model")
    elif len(args.session) == 1 and not args.passed and not args.escalated:
        parser.error("a failed brief gets a narrowed retry or an escalation before it settles; log it once, after that")


if __name__ == "__main__":
    main()
