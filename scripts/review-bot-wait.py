#!/usr/bin/env python3
"""Waits until a review bot has finished its pass on a GitLab MR. Run it with Bash
run_in_background right after requesting the bot: it polls on its own, so the session
spends nothing while the bot reviews, and its exit re-invokes the session.

Usage: review-bot-wait.py --mr <iid> --bot <username> --since <iso time>
                          [--busy-marker <text>] [-C <checkout>] [--interval 30] [--timeout 2700]

Only the bot's notes created at or after --since count: record the time just before the
request. The pass counts as finished once one of them exists and none holds --busy-marker.
A bot that posts a status note when it starts and edits it when it ends needs the marker,
or the wait ends on the start note.

Prints one JSON line on stdout: {"state", "mr", "bot"}.
Exit codes: 0 finished, 2 glab kept failing or answered with something unreadable, or bad
arguments, 3 no finished pass within --timeout.
"""

import argparse
import json
import subprocess
import sys
import time
from datetime import datetime, timezone

MAX_CLI_FAILURES = 5
CALL_TIMEOUT_S = 60
PER_PAGE = 100


class CliError(Exception):
    pass


def run(cmd, cwd=None):
    try:
        done = subprocess.run(cmd, capture_output=True, text=True, cwd=cwd, timeout=CALL_TIMEOUT_S)
    except (OSError, subprocess.TimeoutExpired) as e:
        raise CliError(f"{cmd[0]}: {e}") from e
    if done.returncode != 0:
        raise CliError(f"{' '.join(cmd[:3])}: {done.stderr.strip() or done.returncode}")
    return done.stdout


def api_for(checkout, runner=run):
    def api(path):
        try:
            return json.loads(runner(["glab", "api", path], checkout))
        except json.JSONDecodeError as e:
            raise CliError(f"glab api {path}: unreadable answer") from e
    return api


def parse_ts(text):
    ts = datetime.fromisoformat(text.replace("Z", "+00:00"))
    return ts if ts.tzinfo else ts.replace(tzinfo=timezone.utc)


def notes_since(api, mr, since):
    notes, page = [], 1
    while True:
        batch = api(f"projects/:id/merge_requests/{mr}/notes?order_by=created_at&sort=desc"
                    f"&per_page={PER_PAGE}&page={page}")
        notes += batch
        if len(batch) < PER_PAGE or any(parse_ts(n["created_at"]) < since for n in batch):
            return notes
        page += 1


def finished(notes, bot, since, busy_marker):
    mine = [n for n in notes if n["author"]["username"] == bot and parse_ts(n["created_at"]) >= since]
    if busy_marker and any(busy_marker in n["body"] for n in mine):
        return False
    return bool(mine)


def wait(fetch_notes, bot, busy_marker, since, interval, timeout, sleep=time.sleep, clock=time.monotonic):
    start, failures = clock(), 0
    while True:
        try:
            if finished(fetch_notes(), bot, since, busy_marker):
                return 0, "finished"
            failures = 0
        except (CliError, KeyError, TypeError, ValueError):
            failures += 1
            if failures >= MAX_CLI_FAILURES:
                return 2, "error"
        if clock() - start >= timeout:
            return 3, "timeout"
        sleep(interval)


def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--mr", required=True)
    ap.add_argument("--bot", required=True)
    ap.add_argument("--since", required=True, type=parse_ts)
    ap.add_argument("--busy-marker", default="")
    ap.add_argument("-C", dest="checkout", default=None)
    ap.add_argument("--interval", type=float, default=30)
    ap.add_argument("--timeout", type=float, default=2700)
    a = ap.parse_args()
    api = api_for(a.checkout)
    code, state = wait(lambda: notes_since(api, a.mr, a.since), a.bot, a.busy_marker, a.since,
                       a.interval, a.timeout)
    print(json.dumps({"state": state, "mr": a.mr, "bot": a.bot}))
    sys.exit(code)


if __name__ == "__main__":
    main()
