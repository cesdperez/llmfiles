#!/usr/bin/env python3
"""Collect the MRs a team or a repo merged since a date, grouped into changes, with
whether each reached production.

Prints the draft Slack message for /teamdigest and /repodigest. Usage:
merge-digest.py (--team TEAM | --repo PATH) [--since DATE]

A team's MRs are every MR in the repos only it owns, plus those its members wrote
anywhere else in the GitLab group.

Auth goes through `glab api` on purpose. The token in ~/.config/glab-cli/config.yml
is OAuth2 with a refresh cycle, so reading it directly would break on expiry and
would put a live credential in the caller's context.
"""

import argparse
import json
import re
import subprocess
import sys
from concurrent.futures import ThreadPoolExecutor
from datetime import date, timedelta
from pathlib import Path
from urllib.parse import quote

import work_config

WORK = work_config.load("jira_base_url", "gitlab_group")
GROUP = WORK["gitlab_group"]
# Jira numbers are never zero-padded, which rules out ADR-0003 and RFC ids.
JIRA_KEY = re.compile(r"\b([A-Z][A-Z0-9]{1,9}-[1-9]\d{0,5})\b")
PROD_ENVS = ("production", "prod")
HOUSEKEEPING = re.compile(r"^(chore|ci|docs|test|build|refactor|style)\b", re.I)


def api(path):
    """Returns parsed JSON, or None, so one failed call degrades one repo."""
    for _ in range(3):
        try:
            r = subprocess.run(
                ["glab", "api", path], capture_output=True, text=True, timeout=30
            )
        except (subprocess.TimeoutExpired, OSError):
            continue
        if r.returncode != 0:
            if "404" in r.stderr or "403" in r.stderr:
                return None
            continue
        try:
            return json.loads(r.stdout)
        except json.JSONDecodeError:
            return None
    return None


def pages(path):
    page = 1
    while batch := api(f"{path}&per_page=100&page={page}"):
        yield from batch
        page += 1


def load_directory():
    work_config.load("platform_directory")
    # Ruby ships with macOS and parses YAML in its stdlib; Python does not.
    path = Path(WORK["platform_directory"]).expanduser()
    script = "puts JSON.generate(YAML.load_file(ARGV[0]))"
    out = subprocess.run(
        ["ruby", "-ryaml", "-rjson", "-e", script, str(path)],
        capture_output=True,
        text=True,
        check=True,
    )
    return json.loads(out.stdout)


def find_team(directory, query):
    q = query.lower()
    for team in directory["teams"]:
        keys = {team["id"].lower(), team["id"].lower().removeprefix("team-")}
        keys |= {p.lower() for p in team.get("jira_projects", [])}
        if q in keys:
            return team
    matches = [t for t in directory["teams"] if q in t["name"].lower()]
    if len(matches) == 1:
        return matches[0]
    names = ", ".join(
        f"{t['id']} ({'/'.join(t.get('jira_projects', []))})"
        for t in directory["teams"]
    )
    sys.exit(f"no single team matches {query!r}. Teams: {names}")


def sole_repos(directory, team_id):
    """Paths of the repos only this team owns, so every MR merged there is the team's."""
    owners = {}
    for domain in directory["domains"]:
        for feature in domain.get("features", []):
            for repo in feature.get("platform_repositories", []):
                owners.setdefault(repo, set()).add(feature.get("team"))
    paths = {
        r["git"].removesuffix(".git").split("gitlab.com/", 1)[1]
        for r in directory["repositories"]
        if owners.get(r["id"], set()) - {None} == {team_id}
    }
    return expand_groups(paths)


def expand_groups(paths):
    """Some directory entries are GitLab groups the team owns whole."""
    expanded = set()
    for path in paths:
        pid = quote(path, safe="")
        if api(f"projects/{pid}") or not api(f"groups/{pid}"):
            expanded.add(path)
            continue
        projects = pages(f"groups/{pid}/projects?include_subgroups=true&archived=false")
        expanded |= {p["path_with_namespace"] for p in projects}
    return expanded


def by_members(members, since):
    """MRs the members merged anywhere in the group, by project id."""
    base = (
        f"groups/{quote(GROUP, safe='')}/merge_requests"
        f"?state=merged&merged_after={since}T00:00:00Z"
    )
    with ThreadPoolExecutor(max_workers=8) as ex:
        batches = ex.map(
            lambda m: list(pages(f"{base}&author_username={quote(m)}")), members
        )
    found = {}
    for mr in (mr for batch in batches for mr in batch):
        found.setdefault(mr["project_id"], []).append(mr)
    return found


def prod_sha(pid):
    """The commit of the newest successful deploy to a prod environment: None when
    the repo has no prod environment, "" when it never deployed there."""
    envs = {e["name"] for e in api(f"projects/{pid}/environments?per_page=100") or []}
    prod_envs = [e for e in PROD_ENVS if e in envs]
    if not prod_envs:
        return None
    newest = []
    # Some repos keep an abandoned `production` beside the live `prod`.
    for env in prod_envs:
        newest += (
            api(
                f"projects/{pid}/deployments?environment={env}&status=success"
                "&order_by=updated_at&sort=desc&per_page=1"
            )
            or []
        )
    return max(newest, key=lambda d: d["updated_at"])["sha"] if newest else ""


def in_prod(pid, sha, deployed):
    if deployed is None:
        return None
    if not deployed or not sha:
        return False
    base = api(f"projects/{pid}/repository/merge_base?refs[]={sha}&refs[]={deployed}")
    return bool(base) and base["id"] == sha


def group_changes(mrs):
    """MRs sharing a Jira key are steps of one change."""
    changes = {}
    for mr in mrs:
        changes.setdefault(mr["jira"][0] if mr["jira"] else mr["ref"], []).append(mr)
    return [
        {
            "jira": sorted({k for mr in group for k in mr["jira"]}),
            "in_prod": None
            if all(mr["in_prod"] is None for mr in group)
            else all(mr["in_prod"] is not False for mr in group),
            "mrs": [
                {k: mr[k] for k in ("ref", "url", "title", "in_prod")} for mr in group
            ],
        }
        for group in changes.values()
    ]


def collect_repo(project_ref, sole, since, mrs=None):
    """Every MR merged into the project when `mrs` is None, else those of `mrs`
    that target its default branch. `project_ref` is a path or an id."""
    pid = quote(str(project_ref), safe="")
    project = api(f"projects/{pid}")
    if not project:
        return {"repo": str(project_ref), "error": "project not readable"}
    path = project["path_with_namespace"]
    if mrs is not None and path in sole:
        return None
    branch = project["default_branch"]
    if mrs is None:
        mrs = pages(
            f"projects/{pid}/merge_requests?state=merged&target_branch={quote(branch)}"
            f"&merged_after={since}T00:00:00Z"
        )
    mrs = [m for m in mrs if m["target_branch"] == branch]
    if not mrs:
        return None
    deployed = prod_sha(pid)

    def describe(m):
        sha = m.get("merge_commit_sha") or m.get("squash_commit_sha") or m.get("sha")
        return {
            "ref": f"!{m['iid']}",
            "url": m["web_url"],
            "title": m["title"],
            "jira": sorted(set(JIRA_KEY.findall(f"{m['title']} {m['source_branch']}"))),
            "in_prod": in_prod(pid, sha, deployed),
        }

    with ThreadPoolExecutor(max_workers=6) as ex:
        described = list(ex.map(describe, sorted(mrs, key=lambda m: m["merged_at"])))
    housekeeping = [m for m in described if HOUSEKEEPING.match(m["title"])]
    return {
        "repo": path.removeprefix(GROUP + "/"),
        "has_prod": deployed is not None,
        "changes": group_changes([m for m in described if m not in housekeeping]),
        "housekeeping": [
            {k: m[k] for k in ("ref", "url", "in_prod")} for m in housekeeping
        ],
    }


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    who = ap.add_mutually_exclusive_group(required=True)
    who.add_argument("--team", help="team id, Jira project key, or part of its name")
    who.add_argument(
        "--repo", help="GitLab project path, such as backend/education-api"
    )
    ap.add_argument("--since", default=(date.today() - timedelta(days=7)).isoformat())
    args = ap.parse_args()
    since = date.fromisoformat(args.since).isoformat()

    if args.repo:
        path = args.repo.removeprefix(GROUP + "/")
        repo = collect_repo(f"{GROUP}/{path}", set(), since)
        print(render(path, date.fromisoformat(since), [repo] if repo else []))
        return

    directory = load_directory()
    team = find_team(directory, args.team)
    members = {m["gitlab"] for m in team.get("members", []) if m.get("gitlab")}
    sole = sole_repos(directory, team["id"])
    jobs = [(path, None) for path in sorted(sole)]
    jobs += by_members(members, since).items()

    with ThreadPoolExecutor(max_workers=8) as ex:
        repos = [
            r
            for r in ex.map(lambda j: collect_repo(j[0], sole, since, j[1]), jobs)
            if r
        ]
    repos.sort(key=lambda r: -len(r.get("changes", [])))

    print(render(team["name"], date.fromisoformat(since), repos))


def link(text, url):
    return f"[{text}]({url})"


def render(name, since, repos):
    """The Slack message with each change's MR titles in place of its summary line,
    then, under a rule, what the writer needs to know but readers do not."""
    mrs = [
        mr
        for r in repos
        for mr in [m for c in r.get("changes", []) for m in c["mrs"]]
        + r.get("housekeeping", [])
    ]
    waiting = sum(mr["in_prod"] is False for mr in mrs)
    in_prod = sum(mr["in_prod"] is True for mr in mrs)
    span = f"{since:%-d %b} to {date.today():%-d %b}"
    lines = [
        f"*:deployparrot: {name}: merged {span}*",
        f"{len(mrs)} MRs, {in_prod} in prod, {waiting} :waiting: not in prod yet",
    ]
    for repo in repos:
        if repo.get("error"):
            continue
        lines.append("")
        if len(repos) > 1:
            lines.append(f"*{repo['repo']}*")
        for change in repo["changes"]:
            mark = ":waiting: " if change["in_prod"] is False else ""
            titles = " || ".join(mr["title"] for mr in change["mrs"])
            links = [link(k, WORK["jira_base_url"] + k) for k in change["jira"]]
            links += [link(mr["ref"], mr["url"]) for mr in change["mrs"]]
            lines.append(f"- {mark}{titles} {' '.join(links)}")
        if repo["housekeeping"]:
            links = " ".join(
                link(mr["ref"], mr["url"])
                + (":waiting:" if mr["in_prod"] is False else "")
                for mr in repo["housekeeping"]
            )
            lines.append(f"- Housekeeping: {links}")
    no_prod = [r["repo"] for r in repos if "has_prod" in r and not r["has_prod"]]
    unreadable = [r["repo"] for r in repos if r.get("error")]
    lines += ["", "---"]
    if no_prod:
        lines.append("No prod environment, so never marked: " + ", ".join(no_prod))
    if unreadable:
        lines.append("Unreadable: " + ", ".join(unreadable))
    return "\n".join(lines)


if __name__ == "__main__":
    main()
