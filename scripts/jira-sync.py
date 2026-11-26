#!/usr/bin/env python3
"""Compare an epic's child tickets in Jira with what merged to main in GitLab, for /jirasync.

Usage: jira-sync.py <EPIC-KEY>

Emits JSON on stdout: the epic, "tickets" keyed by Jira key (status, assignee and the merged
MRs that name the key, "matched_in" saying where: title, source_branch or description), and
the diff as key lists: "merged_not_done", "done_nothing_merged", "missing_assignee" and
"assign_to_me" (merged work I authored on a ticket assigned to someone else or nobody).
GitLab's MR search covers only title and description, so an MR that names the key only in its
source branch is never found.
"errors" lists the lookups that failed, so a missing MR is never mistaken for a ticket with
nothing merged.

Reads Jira through `twg` and GitLab through `glab api`, both read-only.
"""

import json
import os
import re
import subprocess
import sys
from concurrent.futures import ThreadPoolExecutor
from urllib.parse import quote

import work_config

WORK = work_config.load("gitlab_group", "git_author", "jira_base_url")
MAIN_BRANCHES = {"main", "master"}
JIRA_FIELDS = "summary,status,assignee,issuetype"
EPIC_KEY = re.compile(r"^[A-Z][A-Z0-9]+-\d+$")
GLAB_ATTEMPTS = 3
PER_PAGE = 100
EVIDENCE = {"title", "source_branch"}


class CommandError(Exception):
    pass


def run_json(cmd, env=None):
    # stdout only: twg and glab write progress and warnings to stderr, which breaks JSON parsing.
    result = subprocess.run(cmd, capture_output=True, text=True, env=env)
    if result.returncode != 0:
        raise CommandError(f"{' '.join(cmd[:4])} exited {result.returncode}: {result.stderr.strip()}")
    try:
        return json.loads(result.stdout)
    except json.JSONDecodeError as error:
        raise CommandError(f"{' '.join(cmd[:4])} printed no JSON ({error}): {result.stderr.strip()}") from None


def twg_env():
    # TWG_AGENT_DEFAULTS switches the output to YAML, whatever -o says.
    return {k: v for k, v in os.environ.items() if k != "TWG_AGENT_DEFAULTS"}


def twg_query(jql):
    issues, cursor = [], None
    while True:
        cmd = ["twg", "jira", "workitem", "query", "--jql", jql, "--fields", JIRA_FIELDS,
               "-n", "100", "-o", "json"]
        page = run_json(cmd + (["--after", cursor] if cursor else []), env=twg_env())
        issues += page.get("data", {}).get("issues", [])
        info = page.get("pageInfo") or {}
        if not info.get("hasNextPage") or not info.get("nextCursor"):
            return issues
        cursor = info["nextCursor"]


def my_account_id():
    return run_json(["twg", "whoami", "-o", "json"], env=twg_env()).get("data", {}).get("accountId")


def glab_api(path):
    for attempt in range(GLAB_ATTEMPTS):
        try:
            data = run_json(["glab", "api", path])
        except CommandError:
            # Group-wide MR search runs close to GitLab's request timeout, so retry before failing.
            if attempt == GLAB_ATTEMPTS - 1:
                raise
            continue
        if isinstance(data, dict) and "message" in data:
            if attempt == GLAB_ATTEMPTS - 1:
                raise CommandError(f"glab api {path}: {data['message']}")
            continue
        return data


def names_key(text, key):
    return re.search(rf"(?<![A-Za-z0-9]){re.escape(key)}(?!\d)", text or "", re.IGNORECASE) is not None


def search_merged(key, group):
    # state=all times out on the group endpoint, state=merged does not. The search is a substring
    # match, so KEY-1 also returns KEY-10 to KEY-199 and the real hit can sit past page one.
    mrs, page = [], 1
    while True:
        batch = glab_api(f"groups/{quote(group, safe='')}/merge_requests?state=merged&scope=all"
                         f"&non_archived=false&search={quote(key)}&per_page={PER_PAGE}&page={page}")
        mrs += batch
        if len(batch) < PER_PAGE:
            return mrs
        page += 1


def merged_mrs(key, group=WORK["gitlab_group"]):
    mrs = search_merged(key, group)
    return [
        {
            "ref": mr["references"]["full"],
            "title": mr["title"],
            "url": mr["web_url"],
            "author": mr["author"]["name"],
            "author_username": mr["author"]["username"],
            "merged_at": mr.get("merged_at"),
            "matched_in": matched,
        }
        for mr in mrs
        if mr.get("target_branch") in MAIN_BRANCHES
        for matched in [[f for f in ("title", "source_branch", "description") if names_key(mr.get(f), key)]]
        if matched
    ]


def ticket(issue, merged, me):
    status = issue.get("status") or {}
    assignee = issue.get("assignee")
    return {
        "key": issue["key"],
        "summary": (issue.get("summary") or "").strip(),
        "type": (issue.get("issuetype") or {}).get("name"),
        "status": status.get("name"),
        "done": (status.get("statusCategory") or {}).get("key") == "done",
        "assignee": {"name": assignee.get("displayName"), "email": assignee.get("emailAddress"),
                     "account_id": assignee.get("accountId")}
        if assignee else None,
        "url": WORK["jira_base_url"] + issue["key"],
        "merged": merged,
        "merged_by_me": any(mr["author_username"] == me["gitlab_username"]
                            and EVIDENCE & set(mr["matched_in"]) for mr in merged),
    }


def assigned_to_me(t, me):
    assignee = t["assignee"]
    if not assignee:
        return False
    if assignee["account_id"] and me.get("account_id"):
        return assignee["account_id"] == me["account_id"]
    # Jira hides emails under some privacy settings, so email is only the fallback.
    return (assignee["email"] or "").lower() == me["email"].lower()


def diff(tickets, me, failed):
    """Key lists for the command to act on. A ticket whose MR lookup failed is in none of the
    merged lists, because an empty result there proves nothing."""
    known = [t for t in tickets if t["key"] not in failed]
    return {
        "merged_not_done": [t["key"] for t in known if t["merged"] and not t["done"]],
        "done_nothing_merged": [t["key"] for t in known if t["done"] and not t["merged"]],
        "missing_assignee": [t["key"] for t in tickets if not t["assignee"]],
        "assign_to_me": [t["key"] for t in known
                         if t["merged_by_me"] and not assigned_to_me(t, me)],
    }


def issue_summary(issue):
    return {"key": issue["key"], "summary": (issue.get("summary") or "").strip(),
            "type": (issue.get("issuetype") or {}).get("name"),
            "status": (issue.get("status") or {}).get("name"),
            "url": WORK["jira_base_url"] + issue["key"]}


def main():
    if len(sys.argv) != 2 or not EPIC_KEY.match(sys.argv[1].upper()):
        sys.exit(__doc__)
    epic_key = sys.argv[1].upper()
    try:
        epic = twg_query(f"key = {epic_key}")
        if not epic:
            sys.exit(f"{epic_key} not found")
        kind = (epic[0].get("issuetype") or {}).get("name")
        if kind != "Epic":
            sys.exit(f"{epic_key} is a {kind}, not an Epic")
        children = twg_query(f"parent = {epic_key} ORDER BY key ASC")
        me = {"gitlab_username": glab_api("user")["username"], "email": WORK["git_author"],
              "account_id": my_account_id()}
    except CommandError as error:
        sys.exit(str(error))

    errors, merged = [], {}

    def lookup(key):
        try:
            return key, merged_mrs(key), None
        except CommandError as error:
            return key, [], str(error)

    with ThreadPoolExecutor(max_workers=6) as pool:
        for key, mrs, error in pool.map(lookup, [i["key"] for i in children]):
            merged[key] = mrs
            if error:
                errors.append({"key": key, "error": error})

    tickets = [ticket(i, merged[i["key"]], me) for i in children]
    print(json.dumps({
        "epic": issue_summary(epic[0]),
        "me": me,
        "tickets": {t["key"]: t for t in tickets},
        **diff(tickets, me, {e["key"] for e in errors}),
        "errors": errors,
    }, indent=2))


if __name__ == "__main__":
    main()
