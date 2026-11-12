#!/usr/bin/env python3
"""Ledger of conductor builder runs and A/B comparisons, used to tune opencode/builders.md.

Usage:
  builder-evals.py append run --kind KIND --builder NAME --session ID [--session ID]
                              --passed yes|no --escalated yes|no [--repo PATH]
  builder-evals.py append ab --kind KIND --winner a|b|none --entrant JSON --entrant JSON [--repo PATH]
  builder-evals.py summary

A run row covers one brief: one --session per attempt, so a narrowed retry adds a session.
Each A/B entrant is {"session", "builder", "check_passed", "files_outside_scope", "rewrites",
"escalated", "score", "why"}. Model, provider and wall time come from the opencode session API.

Rows go to local/builder-evals.jsonl, or to LLMFILES_BUILDER_EVALS. `summary` emits JSON.
"""

import argparse
import json
import os
import subprocess
import sys
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path

DEFAULT_PATH = Path(__file__).resolve().parent.parent / "local" / "builder-evals.jsonl"
AB_ENTRANT_KEYS = ("session", "builder", "check_passed", "files_outside_scope", "rewrites", "escalated", "score", "why")


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


def yes(value):
    if value not in ("yes", "no"):
        raise argparse.ArgumentTypeError("expected yes or no")
    return value == "yes"


def entrant(text):
    try:
        value = json.loads(text)
    except json.JSONDecodeError as error:
        raise argparse.ArgumentTypeError(f"invalid JSON: {error}") from error
    missing = [key for key in AB_ENTRANT_KEYS if key not in value]
    if missing:
        raise argparse.ArgumentTypeError(f"entrant lacks: {', '.join(missing)}")
    return value


def run_row(args):
    attempts = [session(session_id) for session_id in args.session]
    models = {attempt["model"] for attempt in attempts}
    if len(models) > 1:
        sys.exit(f"sessions ran on different models {sorted(models)}; pass only the builder's own sessions and mark a handoff with --escalated yes")
    return {
        "type": "run", "kind": args.kind, "builder": args.builder,
        "model": attempts[0]["model"], "provider": attempts[0]["provider"],
        "passed": args.passed, "retries": len(attempts) - 1, "escalated": args.escalated,
        "wall_s": round(sum(attempt["wall_s"] for attempt in attempts), 1),
        "cost": sum(attempt["cost"] for attempt in attempts),
    }


def ab_row(args):
    if len(args.entrant) != 2:
        sys.exit("an A/B row needs exactly two --entrant values, A first")
    entrants = [{**value, **session(value["session"])} for value in args.entrant]
    return {"type": "ab", "kind": args.kind, "winner": args.winner, "entrants": entrants}


def append(args):
    row = run_row(args) if args.row == "run" else ab_row(args)
    row = {"ts": datetime.now(timezone.utc).isoformat(timespec="seconds"), "repo": args.repo, **row}
    path = ledger_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a") as ledger:
        ledger.write(json.dumps(row) + "\n")
    print(json.dumps(row))


def stats(runs, entries):
    passed = [run for run in runs if run["passed"]]
    scores = [entry["score"] for entry, _ in entries if isinstance(entry.get("score"), (int, float))]
    wins = [entry for entry, won in entries if won]
    return {
        "runs": len(runs),
        "pass_rate": ratio(len(passed), len(runs)),
        "avg_retries": average([run["retries"] for run in runs]),
        "escalation_rate": ratio(sum(run["escalated"] for run in runs), len(runs)),
        "avg_wall_s": average([run["wall_s"] for run in runs]),
        "ab_entries": len(entries),
        "ab_win_rate": ratio(len(wins), len(entries)),
        "ab_avg_score": average(scores),
    }


def ratio(part, whole):
    return round(part / whole, 2) if whole else None


def average(values):
    return round(sum(values) / len(values), 1) if values else None


def summary(_args):
    path = ledger_path()
    rows = [json.loads(line) for line in path.read_text().splitlines() if line.strip()] if path.exists() else []
    runs, entries = defaultdict(list), defaultdict(list)
    for row in rows:
        if row["type"] == "run":
            runs[(row["model"], row["kind"])].append(row)
        else:
            for index, value in enumerate(row["entrants"]):
                entries[(value["model"], row["kind"])].append((value, row["winner"] == "ab"[index]))
    models = {}
    for model in sorted({model for model, _ in runs.keys() | entries.keys()}):
        kinds = sorted({kind for m, kind in runs.keys() | entries.keys() if m == model})
        model_runs = [run for kind in kinds for run in runs[(model, kind)]]
        model_entries = [entry for kind in kinds for entry in entries[(model, kind)]]
        models[model] = {
            **stats(model_runs, model_entries),
            "by_kind": {kind: stats(runs[(model, kind)], entries[(model, kind)]) for kind in kinds},
        }
    providers = defaultdict(int)
    for run_rows in runs.values():
        for run in run_rows:
            providers[run["provider"]] += 1
    total = sum(providers.values())
    print(json.dumps({
        "ledger": str(path),
        "models": models,
        "provider_split": {name: {"runs": count, "share": ratio(count, total)} for name, count in sorted(providers.items())},
    }, indent=2))


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    commands = parser.add_subparsers(dest="command", required=True)
    commands.add_parser("summary").set_defaults(func=summary)
    rows = commands.add_parser("append").add_subparsers(dest="row", required=True)
    run = rows.add_parser("run")
    run.add_argument("--builder", required=True)
    run.add_argument("--session", action="append", required=True)
    run.add_argument("--passed", type=yes, required=True)
    run.add_argument("--escalated", type=yes, required=True)
    ab = rows.add_parser("ab")
    ab.add_argument("--winner", choices=["a", "b", "none"], required=True)
    ab.add_argument("--entrant", type=entrant, action="append", required=True)
    for row in (run, ab):
        row.add_argument("--kind", required=True)
        row.add_argument("--repo", default=os.getcwd())
        row.set_defaults(func=append)
    args = parser.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
