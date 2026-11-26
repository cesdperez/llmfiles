#!/usr/bin/env python3
"""Waits until the CI of one commit settles, then exits with its outcome. Run it with
Bash run_in_background from the checkout: it polls on its own, so the session spends
nothing while it waits, and its exit re-invokes the session.

Usage: pipeline-wait.py [--sha HEAD] [--ref <branch> | --mr <iid>] [-C <checkout>]
                        [--interval 30] [--appear-timeout 600] [--timeout 6600]

The origin remote picks the forge. GitHub goes through `gh`, anything else through
`glab`. On GitLab it follows the newest pipeline for the commit, so a pipeline started
again for the same commit replaces the old one. On GitHub it follows the newest run of
each workflow and event, and settles once every one has completed.

--ref keeps only pipelines on that branch. After a fast-forward merge the base and the
feature branch share a commit, and only the base's pipeline says the base is green.
--mr <iid> (GitLab) follows the MR's head pipeline once it is for this commit, which
also finds a merged results pipeline: that one runs on a merge commit whose parent is
this commit. On GitHub, --mr is ignored, since a PR's runs are on its head commit.

Prints one JSON line on stdout: {"state", "sha", "url", "failed_jobs", "manual_jobs"}.
Exit codes:
  0  success. GitHub workflows that were skipped or neutral count, as long as one ran.
  1  failed, canceled or timed out. failed_jobs names the jobs that broke it; a job
     allowed to fail is left out.
  2  the forge CLI kept failing or answered with something unreadable, or bad arguments.
  3  nothing ran the commit: no pipeline within --appear-timeout, or a GitLab pipeline
     (or every GitHub run) was skipped. That is not green, since no job checked it.
  4  the pipeline waits on a person: a GitLab `manual` job that blocks it, or a GitHub
     run in `action_required` or `waiting`. manual_jobs names them.
  5  still running at --timeout. Start the wait again. The default stays under the
     2-hour limit of a background Bash command.
"""

import argparse
import json
import subprocess
import sys
import time

GITLAB_DONE = {"success": 0, "failed": 1, "canceled": 1, "skipped": 3, "manual": 4}
GITHUB_OK = {"success", "neutral", "skipped"}
GITHUB_WAITS_ON_PERSON = {"action_required"}
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


def api_for(cli, checkout, runner=run):
    def api(path):
        try:
            return json.loads(runner([cli, "api", path], checkout))
        except json.JSONDecodeError as e:
            raise CliError(f"{cli} api {path}: unreadable answer") from e
    return api


def all_pages(api, path, key=None):
    sep = "&" if "?" in path else "?"
    items, page = [], 1
    while True:
        body = api(f"{path}{sep}per_page={PER_PAGE}&page={page}")
        batch = body[key] if key else body
        items += batch
        if len(batch) < PER_PAGE:
            return items
        page += 1


def gitlab_pipeline(api, sha, ref=None, mr=None):
    if mr:
        head = api(f"projects/:id/merge_requests/{mr}").get("head_pipeline")
        if not head:
            return None
        if head["sha"] == sha or sha in api(f"projects/:id/repository/commits/{head['sha']}")["parent_ids"]:
            return head
        return None
    ref_filter = f"&ref={ref}" if ref else ""
    pipelines = api(f"projects/:id/pipelines?sha={sha}{ref_filter}&order_by=id&sort=desc&per_page=1")
    return pipelines[0] if pipelines else None


def gitlab_status(api, sha, ref=None, mr=None):
    p = gitlab_pipeline(api, sha, ref, mr)
    if p is None:
        return None
    state = p["status"]
    result = {"state": state, "url": p.get("web_url"), "failed_jobs": [], "manual_jobs": []}
    if state in ("failed", "canceled", "manual"):
        jobs = all_pages(api, f"projects/:id/pipelines/{p['id']}/jobs")
        result["failed_jobs"] = [j["name"] for j in jobs if j["status"] == "failed" and not j.get("allow_failure")]
        result["manual_jobs"] = [j["name"] for j in jobs if j["status"] == "manual" and not j.get("allow_failure")]
    return result


def gitlab_code(status):
    return GITLAB_DONE.get(status["state"])


def github_status(api, sha, ref=None):
    branch = f"&branch={ref}" if ref else ""
    runs = all_pages(api, f"repos/{{owner}}/{{repo}}/actions/runs?head_sha={sha}{branch}", "workflow_runs")
    if not runs:
        return None
    newest = {}
    for r in sorted(runs, key=lambda r: r["id"]):
        newest[(r["workflow_id"], r.get("event"))] = r
    runs = list(newest.values())
    pending = [r for r in runs if r["status"] != "completed"]
    if pending:
        # A run in `waiting` holds for a deployment approval, which only a person gives.
        state = "action_required" if all(r["status"] == "waiting" for r in pending) else "running"
        return {"state": state, "url": pending[0]["html_url"], "failed_jobs": [],
                "manual_jobs": [r["name"] for r in pending if state == "action_required"]}
    broken = [r for r in runs if r["conclusion"] not in GITHUB_OK]
    waiting = [r for r in broken if r["conclusion"] in GITHUB_WAITS_ON_PERSON]
    failed = [r for r in broken if r not in waiting]
    result = {"state": "success", "url": runs[0]["html_url"], "failed_jobs": [],
              "manual_jobs": [r["name"] for r in waiting]}
    if failed:
        result.update(state="failed", url=failed[0]["html_url"])
        for r in failed:
            jobs = all_pages(api, f"repos/{{owner}}/{{repo}}/actions/runs/{r['id']}/jobs", "jobs")
            result["failed_jobs"] += [f"{r['name']} / {j['name']}" for j in jobs
                                      if j.get("conclusion") not in GITHUB_OK | {None}]
    elif waiting:
        result.update(state="action_required", url=waiting[0]["html_url"])
    elif all(r["conclusion"] == "skipped" for r in runs):
        result["state"] = "skipped"
    return result


def github_code(status):
    return {"success": 0, "failed": 1, "skipped": 3, "action_required": 4}.get(status["state"])


def wait(status_of, code_of, sha, interval, appear_timeout, timeout, sleep=time.sleep, clock=time.monotonic):
    start, failures, seen = clock(), 0, False
    while True:
        try:
            status = status_of(sha)
            failures = 0
        except (CliError, KeyError, TypeError, ValueError) as e:
            failures += 1
            if failures >= MAX_CLI_FAILURES:
                return 2, {"state": "error", "sha": sha, "error": f"{type(e).__name__}: {e}"}
            status = None if not seen else {"state": "unknown"}
        if status is not None:
            seen = True
            code = code_of(status)
            if code is not None:
                return code, {**status, "sha": sha}
        elapsed = clock() - start
        if not seen and elapsed >= appear_timeout:
            return 3, {"state": "none", "sha": sha}
        if elapsed >= timeout:
            return 5, {**(status or {"state": "running"}), "sha": sha}
        sleep(interval)


def forge_of(origin_url):
    return "github" if "github.com" in origin_url else "gitlab"


def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--sha", default="HEAD")
    target = ap.add_mutually_exclusive_group()
    target.add_argument("--ref")
    target.add_argument("--mr")
    ap.add_argument("-C", dest="checkout", default=None)
    ap.add_argument("--interval", type=float, default=30)
    ap.add_argument("--appear-timeout", type=float, default=600)
    ap.add_argument("--timeout", type=float, default=6600)
    a = ap.parse_args()
    try:
        sha = run(["git", "rev-parse", a.sha], a.checkout).strip()
        forge = forge_of(run(["git", "remote", "get-url", "origin"], a.checkout))
    except CliError as e:
        print(json.dumps({"state": "error", "error": str(e)}))
        sys.exit(2)
    if forge == "github":
        api = api_for("gh", a.checkout)
        status_of, code_of = (lambda s: github_status(api, s, a.ref)), github_code
    else:
        api = api_for("glab", a.checkout)
        status_of, code_of = (lambda s: gitlab_status(api, s, a.ref, a.mr)), gitlab_code
    code, result = wait(status_of, code_of, sha, a.interval, a.appear_timeout, a.timeout)
    print(json.dumps(result))
    sys.exit(code)


if __name__ == "__main__":
    main()
