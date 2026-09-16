#!/usr/bin/env python3
"""Collect the GitLab review queue: open, non-draft MRs where the authenticated
user is a requested reviewer and has not yet approved.

Emits JSON on stdout: {"user": ..., "skipped": {...}, "queue": [ ... ]}

Auth goes through `glab api` on purpose. The token in ~/.config/glab-cli/config.yml
is OAuth2 with a refresh cycle, so reading it directly would break on expiry and
would put a live credential in the caller's context.
"""

import argparse
import json
import os
import subprocess
import sys
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta, timezone

REPO_ROOT = os.path.expanduser("~/projects/acme")
BOT_HINTS = ("sonar", "gitlab-bot", "dependabot", "renovate", "[bot]")
MAX_NOTE_CHARS = 600
MY_USERNAME = ""  # set in main() once /user resolves

# Staleness is measured on last activity, not creation date: an MR opened months
# ago but discussed today is still live work, while a quiet one is dead weight.
DEFAULT_MAX_IDLE_DAYS = 30


def parse_ts(s):
    return datetime.strptime(s[:19], "%Y-%m-%dT%H:%M:%S").replace(tzinfo=timezone.utc)


def api(path, attempts=3):
    """Returns parsed JSON, or None. Never raises: a single hung or failed call
    must degrade one field, not abort the whole report."""
    for attempt in range(attempts):
        try:
            r = subprocess.run(
                ["glab", "api", path], capture_output=True, text=True, timeout=30
            )
        except (subprocess.TimeoutExpired, OSError):
            continue
        if r.returncode != 0:
            # 404/403 are permanent; retrying only burns time
            if "404" in r.stderr or "403" in r.stderr:
                return None
            continue
        try:
            return json.loads(r.stdout)
        except json.JSONDecodeError:
            return None
    return None


def is_bot(author):
    if author.get("bot"):
        return True
    ident = (author.get("username", "") + " " + author.get("name", "")).lower()
    return any(h in ident for h in BOT_HINTS)


def local_path(path_with_namespace):
    """acme/backend/orders-api -> ~/projects/acme/backend/orders-api"""
    rel = path_with_namespace.split("/", 1)[1] if "/" in path_with_namespace else ""
    p = os.path.join(REPO_ROOT, rel)
    return p if os.path.isdir(os.path.join(p, ".git")) else None


def diff_stats(pid, iid):
    d = api("/projects/%d/merge_requests/%d/changes" % (pid, iid))
    if not d:
        return {"files": 0, "added": 0, "removed": 0, "paths": []}
    files, added, removed, paths = 0, 0, 0, []
    for c in d.get("changes", []):
        files += 1
        a = sum(1 for l in c.get("diff", "").split("\n") if l.startswith("+"))
        r = sum(1 for l in c.get("diff", "").split("\n") if l.startswith("-"))
        added, removed = added + a, removed + r
        paths.append({"path": c["new_path"], "added": a, "removed": r})
    paths.sort(key=lambda p: -(p["added"] + p["removed"]))
    return {"files": files, "added": added, "removed": removed, "paths": paths}


def open_threads(pid, iid):
    """Unresolved, human-authored discussion threads."""
    d = api("/projects/%d/merge_requests/%d/discussions?per_page=100" % (pid, iid))
    out = []
    if not d:
        return out
    for disc in d:
        notes = [n for n in disc.get("notes", []) if not n.get("system")]
        if not notes or is_bot(notes[0]["author"]):
            continue
        # resolvable threads only; a thread with no resolved=True note is open
        if not any(n.get("resolvable") for n in notes):
            continue
        if any(n.get("resolved") for n in notes):
            continue
        first, last = notes[0], notes[-1]
        pos = first.get("position") or {}
        path = pos.get("new_path") or pos.get("old_path")
        line = pos.get("new_line") or pos.get("old_line")
        out.append(
            {
                "author": first["author"]["name"],
                "anchor": ("%s:%s" % (path, line) if line else path),
                "created": first["created_at"][:10],
                "replies": len(notes) - 1,
                "last_author": last["author"]["name"],
                "waiting_on_me": last["author"]["username"] != MY_USERNAME,
                "body": first["body"][:MAX_NOTE_CHARS],
                "last_body": last["body"][:MAX_NOTE_CHARS] if len(notes) > 1 else None,
            }
        )
    return out


def enrich(mr):
    pid, iid = mr["project_id"], mr["iid"]
    appr = api("/projects/%d/merge_requests/%d/approvals" % (pid, iid))
    # user_has_approved is authoritative. Matching your username against
    # approved_by returns stale/partial data on some MRs.
    if appr and appr.get("user_has_approved"):
        return {"skip": "already_approved"}
    # A failed approvals call keeps the MR in the queue (better to show one I
    # already approved than to hide one needing review), but say so.
    degraded = None if appr else "approvals lookup failed, approval state unknown"
    appr = appr or {}
    detail = api("/projects/%d/merge_requests/%d" % (pid, iid)) or {}
    pipeline = detail.get("head_pipeline") or {}
    return {
        "iid": iid,
        "project_id": pid,
        "project": detail.get("references", {}).get("full", "").split("!")[0],
        "path_with_namespace": (detail.get("references", {}).get("full", "") or "").split("!")[0],
        "title": mr["title"],
        "url": mr["web_url"],
        "author": mr["author"]["name"],
        "created": mr["created_at"][:10],
        "updated": mr["updated_at"][:10],
        "branch": "%s -> %s" % (mr["source_branch"], mr["target_branch"]),
        "description": (mr.get("description") or "")[:1500],
        "approvals": "%d/%s"
        % (len(appr.get("approved_by", [])), appr.get("approvals_required")),
        "approved_by": [a["user"]["name"] for a in appr.get("approved_by", [])],
        # conflicts deliberately not reported: GitLab blocks the merge anyway
        "merge_status": detail.get("detailed_merge_status"),
        "pipeline": pipeline.get("status"),
        "diff": diff_stats(pid, iid),
        "open_threads": open_threads(pid, iid),
        "local_repo": local_path(
            (detail.get("references", {}).get("full", "") or "").split("!")[0]
        ),
        "degraded": degraded,
    }


def main():
    global MY_USERNAME
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument(
        "--max-idle-days",
        type=int,
        default=DEFAULT_MAX_IDLE_DAYS,
        help="drop MRs with no activity in this many days (0 disables)",
    )
    args = ap.parse_args()

    me = api("/user")
    if not me:
        sys.exit("glab api /user failed. Run: glab auth status")
    MY_USERNAME = me["username"]

    mrs = api(
        "/merge_requests?scope=all&state=opened&reviewer_id=%d&per_page=100&order_by=updated_at"
        % me["id"]
    )
    if mrs is None:
        sys.exit("failed to list merge requests")

    drafts = [m for m in mrs if m.get("draft") or m.get("work_in_progress")]
    live = [m for m in mrs if m not in drafts]

    # Filter on staleness before enrichment: saves 3 API calls per dropped MR.
    stale = []
    if args.max_idle_days > 0:
        cutoff = datetime.now(timezone.utc) - timedelta(days=args.max_idle_days)
        fresh = []
        for m in live:
            if parse_ts(m["updated_at"]) < cutoff:
                stale.append(
                    {
                        "ref": "%s!%d" % (m["references"]["full"].split("!")[0], m["iid"]),
                        "title": m["title"],
                        "url": m["web_url"],
                        "author": m["author"]["name"],
                        "updated": m["updated_at"][:10],
                        "idle_days": (datetime.now(timezone.utc) - parse_ts(m["updated_at"])).days,
                    }
                )
            else:
                fresh.append(m)
        live = fresh

    with ThreadPoolExecutor(max_workers=8) as ex:
        results = list(ex.map(enrich, live))

    queue = [r for r in results if "skip" not in r]
    queue.sort(key=lambda r: r["updated"], reverse=True)

    json.dump(
        {
            "user": me["username"],
            "max_idle_days": args.max_idle_days,
            "skipped": {
                "draft": len(drafts),
                "idle": len(stale),
                "already_approved_by_me": sum(1 for r in results if "skip" in r),
            },
            # listed so nothing disappears silently; report as a one-line aside
            "stale": sorted(stale, key=lambda s: -s["idle_days"]),
            "total_assigned": len(mrs),
            "queue": queue,
        },
        sys.stdout,
        indent=2,
    )
    print()


if __name__ == "__main__":
    main()
