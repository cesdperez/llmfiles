#!/usr/bin/env python3
"""Collect one day of GoodHabitz work signal for /dailyworkrecap.

Emits JSON on stdout with the deterministic half of the recap: git commits,
merge requests authored, GitLab review activity, and the Claude Code session
transcripts that overlap the day. The interpretive half (what the work was
about, Slack, meetings) is left to the agents the command spawns.

Auth goes through `glab api` on purpose. The token in ~/.config/glab-cli/config.yml
is OAuth2 with a refresh cycle, so reading it directly would break on expiry and
would put a live credential in the caller's context.
"""

import json
import os
import re
import subprocess
import sys
from concurrent.futures import ThreadPoolExecutor
from datetime import date, datetime, time, timedelta, timezone
from pathlib import Path

REPO_ROOT = Path.home() / "projects" / "goodhabitz"
SESSION_ROOT = Path.home() / ".claude" / "projects"
GIT_AUTHOR = "cesardanielperez@goodhabitz.com"
GITLAB_GROUP = "goodhabitz/"
JIRA_KEY = re.compile(r"\b([A-Z]{2,5}-\d{1,5})\b")

# Session dirs are cwd-slugs. Personal projects live under the same root, so the
# recap has to opt in by slug rather than scan everything.
SESSION_SLUG_HINT = "goodhabitz"
SESSION_SLUG_SKIP = "personal-projects"


def resolve_day(arg):
    """Default to yesterday, rolling a weekend back to Friday.

    A recap run on Monday almost always wants Friday, not Sunday.
    """
    if arg:
        return date.fromisoformat(arg)
    day = date.today() - timedelta(days=1)
    while day.isoweekday() > 5:
        day -= timedelta(days=1)
    return day


def utc_window(day):
    """Local-midnight-to-midnight for `day`, expressed in UTC."""
    start = datetime.combine(day, time.min).astimezone()
    return start.astimezone(timezone.utc), (start + timedelta(days=1)).astimezone(timezone.utc)


def sh(args, cwd=None):
    r = subprocess.run(args, cwd=cwd, capture_output=True, text=True)
    return r.stdout.strip() if r.returncode == 0 else ""


def glab(path):
    out = sh(["glab", "api", path])
    if not out:
        return None
    try:
        return json.loads(out)
    except json.JSONDecodeError:
        return None


def git_repos():
    out = sh(["find", str(REPO_ROOT), "-maxdepth", "5", "-name", ".git", "-type", "d", "-prune"])
    return [Path(line).parent for line in out.splitlines() if line]


def repo_commits(repo, day):
    """Commits authored on `day`, deduped by subject, flagged as landed or not.

    A subject shows up two or three times across --all: the feature branch, the
    rebase, and the copy on the default branch. The subject is the stable key.
    """
    span = [f"--since={day}T00:00:00", f"--until={day + timedelta(days=1)}T00:00:00"]
    args = ["git", "-C", str(repo), "log", "--no-merges", f"--author={GIT_AUTHOR}"]

    raw = sh(args + ["--all", "--pretty=%h%x1f%s"] + span)
    if not raw:
        return []

    default = sh(["git", "-C", str(repo), "symbolic-ref", "--short", "HEAD"]) or "main"
    landed = set(sh(args + [default, "--pretty=%s"] + span).splitlines())

    seen, commits = set(), []
    for line in raw.splitlines():
        sha, _, subject = line.partition("\x1f")
        if subject in seen:
            continue
        seen.add(subject)
        commits.append(
            {
                "repo": str(repo.relative_to(REPO_ROOT)),
                "sha": sha,
                "subject": subject,
                "on_default_branch": subject in landed,
            }
        )
    return commits


def collect_commits(day):
    repos = git_repos()
    with ThreadPoolExecutor(max_workers=16) as pool:
        results = pool.map(lambda r: repo_commits(r, day), repos)
    return [c for group in results for c in group]


def collect_authored_mrs(day):
    nxt = day + timedelta(days=1)
    data = glab(
        "/merge_requests?scope=created_by_me&per_page=100"
        f"&updated_after={day}T00:00:00Z&updated_before={nxt}T23:59:59Z"
    )
    if not data:
        return []
    return [
        {
            "ref": m["references"]["full"].replace(GITLAB_GROUP, "", 1),
            "title": m["title"],
            "state": m["state"],
            "draft": m.get("draft", False),
            "url": m["web_url"],
        }
        for m in data
    ]


def collect_events(day):
    """GitLab activity feed for the day, bucketed by what it says about the work.

    `after`/`before` on this endpoint are exclusive, hence the +/- 1 day, and
    created_at is UTC, so the local-day filter happens here.
    """
    start, end = utc_window(day)
    data = glab(
        f"/events?after={day - timedelta(days=1)}&before={day + timedelta(days=1)}&per_page=100"
    )
    if not data:
        return {}, {}

    paths = {}
    ids = {e["project_id"] for e in data if e.get("project_id")}
    with ThreadPoolExecutor(max_workers=16) as pool:
        for pid, project in zip(ids, pool.map(lambda i: glab(f"/projects/{i}"), ids)):
            if project:
                paths[pid] = project["path_with_namespace"].replace(GITLAB_GROUP, "", 1)

    buckets = {"approved": [], "commented": [], "opened": [], "merged": [], "closed": []}
    action_map = {"approved": "approved", "opened": "opened", "accepted": "merged", "closed": "closed"}

    for e in data:
        ts = datetime.fromisoformat(e["created_at"].replace("Z", "+00:00"))
        if not (start <= ts < end):
            continue

        project = paths.get(e.get("project_id"), str(e.get("project_id")))
        note = e.get("note") or {}
        if note:
            if note.get("noteable_type") != "MergeRequest":
                continue
            bucket, iid = "commented", note.get("noteable_iid")
        elif e.get("target_type") == "MergeRequest":
            bucket, iid = action_map.get(e.get("action_name")), e.get("target_iid")
        else:
            continue

        if not bucket or not iid:
            continue
        buckets[bucket].append(
            {"ref": f"{project}!{iid}", "title": e.get("target_title", ""), "url": f"https://gitlab.com/{GITLAB_GROUP}{project}/-/merge_requests/{iid}"}
        )

    return buckets, paths


def collect_sessions(day):
    """Transcripts whose first-to-last timestamp span overlaps the day.

    Entries are appended in order, so first and last line bound the file. That
    beats reading multi-megabyte transcripts just to date them.
    """
    start, end = utc_window(day)
    found = []

    for path in SESSION_ROOT.glob("*/*.jsonl"):
        slug = path.parent.name
        if SESSION_SLUG_HINT not in slug or SESSION_SLUG_SKIP in slug:
            continue
        try:
            if datetime.fromtimestamp(path.stat().st_mtime, timezone.utc) < start:
                continue
            with path.open("rb") as fh:
                first = fh.readline().decode("utf-8", "replace")
                fh.seek(0, os.SEEK_END)
                size = fh.tell()
                fh.seek(max(0, size - 65536))
                tail = fh.read().decode("utf-8", "replace").splitlines()
        except OSError:
            continue

        stamps = [
            datetime.fromisoformat(m.replace("Z", "+00:00"))
            for m in re.findall(r'"timestamp":"([^"]+)"', first + "\n" + "\n".join(tail[-40:]))
        ]
        if not stamps or min(stamps) >= end or max(stamps) < start:
            continue
        found.append({"path": str(path), "project": path.parent.name})

    return sorted(found, key=lambda s: s["path"])


def main():
    day = resolve_day(sys.argv[1] if len(sys.argv) > 1 else None)
    commits = collect_commits(day)
    mrs = collect_authored_mrs(day)
    events, _ = collect_events(day)
    sessions = collect_sessions(day)

    text = " ".join(
        [c["subject"] for c in commits]
        + [m["title"] for m in mrs]
        + [e["title"] for bucket in events.values() for e in bucket]
    )
    mine = {m["ref"] for m in mrs}
    reviewed = {e["ref"] for e in events.get("approved", []) + events.get("commented", [])} - mine

    print(
        json.dumps(
            {
                "day": str(day),
                "weekday": day.strftime("%A"),
                "commits": commits,
                "mrs_authored": mrs,
                "review_activity": events,
                "mrs_reviewed": sorted(reviewed),
                "jira_keys": sorted(set(JIRA_KEY.findall(text))),
                "sessions": sessions,
            },
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
