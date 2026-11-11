#!/usr/bin/env python3
"""Render a written merge digest as a filterable HTML page for an Artifact.

Takes the digest after its change lines are rewritten (the note below `---` included)
and a notes JSON. For a team: {"areas": {area: [repo]}, "tldr": {repo: line}}.
For one repo: {"groups": {group: {"tldr": line, "mrs": ["!12", ...]}}}, where each change
line joins the group listing its first MR. Both take {"epics": {key: line}, "unplanned": line}.

Each change line is grouped under the epics of its Jira tickets, read through twg. Lines with
no ticket, or whose tickets have no epic, are unplanned. --list-epics prints that grouping so
the notes can describe each epic.
"""

import argparse
import json
import re
import subprocess
import sys
from pathlib import Path

TEMPLATE = Path(__file__).resolve().parent.parent / "shared" / "digest-page.html"
LINK = re.compile(r"\[([^\]]+)\]\((https?://[^)]+)\)")
HEADER = re.compile(r"\*(?::[\w-]+: )?(.+?): merged (.+)\*")
NO_PROD = "No prod environment, so never marked: "
EPIC_LEVEL = 1


def twg_issues(keys):
    out = {}
    keys = sorted(keys)
    for i in range(0, len(keys), 50):
        run = subprocess.run(
            ["twg", "jira", "workitem", "bulk-get", *keys[i : i + 50],
             "--fields", "summary,parent,status,issuetype", "-o", "json"],
            capture_output=True, text=True, check=True)
        # twg prints a YAML envelope that points at the full JSON on disk.
        path = re.search(r'^\s*stdout: "(.+)"$', run.stdout, re.M)[1]
        for item in json.loads(Path(path).read_text())["data"]["items"]:
            if item.get("ok"):
                out[item["data"]["key"]] = item["data"]
    return out


def epic_index(keys):
    """Map each ticket to its epic, climbing from a subtask to its parent's epic."""
    issues = twg_issues(keys)
    parents = {p["key"] for i in issues.values() if (p := i.get("parent"))}
    issues |= twg_issues(parents - issues.keys())
    grand = {p["key"] for k in parents if k in issues and (p := issues[k].get("parent"))}
    issues |= twg_issues(grand - issues.keys())

    def epic_of(key, depth=0):
        i = issues.get(key)
        if not i or depth > 2:
            return None
        if i["issuetype"].get("hierarchyLevel", 0) >= EPIC_LEVEL:
            return key
        return epic_of(i["parent"]["key"], depth + 1) if i.get("parent") else None

    info = {k: {"summary": i["summary"], "status": i["status"]["name"]} for k, i in issues.items()}
    return {k: epic_of(k) for k in keys}, info


def group_epics(repos, notes):
    keys = {t["k"] for r in repos for i in r["items"] for t in i["tickets"]}
    epic_of, info = epic_index(keys) if keys else ({}, {})
    epics, unplanned = {}, {"key": "unplanned", "items": []}
    for r in repos:
        for item in r["items"]:
            if item["house"]:
                continue
            found = sorted({e for t in item["tickets"] if (e := epic_of.get(t["k"]))})
            item["epics"] = found or ["unplanned"]
            for e in found:
                epics.setdefault(e, {"key": e, "items": []})["items"].append((r, item))
            if not found:
                unplanned["items"].append((r, item))

    def card(g):
        rows = g.pop("items")
        mrs = {m["k"] + r["name"]: (r, i) for r, i in rows for m in i["mrs"]}
        tickets = sorted({t["k"] for _, i in rows for t in i["tickets"]} - {g["key"]})
        return g | {
            "mrs": len(mrs),
            "waiting": sum(1 for r, i in mrs.values() if i["waiting"]),
            "prod": sum(1 for r, i in mrs.values() if r["prodEnv"] and not i["waiting"]),
            "lines": len(rows),
            "repos": sorted({r["name"] for r, _ in rows}, key=lambda n: -sum(1 for r, _ in rows if r["name"] == n)),
            "tickets": [{"k": t, **info.get(t, {"summary": "", "status": ""}),
                         "epic": epic_of.get(t)} for t in tickets],
        }

    out = sorted((card(g) for g in epics.values()), key=lambda g: -g["mrs"])
    for g in out:
        g |= info.get(g["key"], {"summary": g["key"], "status": ""})
        g["d"] = notes.get("epics", {}).get(g["key"], "")
    rest = card(unplanned) | {"summary": "Unplanned work", "status": "", "d": notes.get("unplanned", "")}
    return out, rest


def parse_items(lines):
    repos, cur = [], None
    for line in lines:
        if m := re.fullmatch(r"\*([^*]+)\*", line):
            cur = {"name": m[1], "items": []}
            repos.append(cur)
        elif line.startswith("- ") and cur:
            body = line[2:]
            waiting = ":waiting:" in body
            body = body.replace(":waiting:", "").strip()
            house = body.startswith("Housekeeping:")
            first = LINK.search(body)
            links = LINK.findall(body)
            cur["items"].append({
                "text": "" if house or not first else body[: first.start()].strip(),
                "waiting": waiting,
                "house": house,
                "tickets": [{"k": k, "u": u} for k, u in links if not k.startswith("!")],
                "mrs": [{"k": k, "u": u} for k, u in links if k.startswith("!")],
            })
    return repos


def split_groups(repo, groups):
    """Turn one repo's change lines into one row per group, so the page reads like a team's."""
    group_of = {ref: g for g, spec in groups.items() for ref in spec.get("mrs", [])}
    rows = {g: [] for g in groups}
    for item in repo["items"]:
        g = "Housekeeping" if item["house"] else group_of.get(item["mrs"][0]["k"] if item["mrs"] else "", "Other")
        rows.setdefault(g, []).append(item)
    return [{"name": g, "items": items} for g, items in rows.items() if items]


def build(message, notes, no_prod_check=False):
    text, _, note = message.partition("\n---\n")
    lines = text.strip().splitlines()
    team, period = HEADER.fullmatch(lines[0]).groups()
    no_prod = set()
    for line in note.splitlines():
        if line.startswith(NO_PROD):
            no_prod = set(line[len(NO_PROD):].strip().split(", "))

    repos = parse_items(lines[1:])
    mode = "team"
    if "groups" in notes:
        mode = "repo"
        repo = repos[0]["name"] if repos else team
        if repo in no_prod or no_prod_check:
            no_prod = {"*"}
        repos = split_groups(repos[0], notes["groups"]) if repos else []
        notes = {**notes, "areas": {repo: [r["name"] for r in repos]},
                 "tldr": {g: spec.get("tldr", "") for g, spec in notes["groups"].items()}}
    elif no_prod_check:
        no_prod = {"*"}
    area_of = {r: a for a, rs in notes.get("areas", {}).items() for r in rs}
    tldr = notes.get("tldr", {})
    for r in repos:
        r["area"] = area_of.get(r["name"], "Other")
        r["mrs"] = sum(len(i["mrs"]) for i in r["items"])
        r["waiting"] = sum(len(i["mrs"]) for i in r["items"] if i["waiting"])
        r["prodEnv"] = "*" not in no_prod and r["name"] not in no_prod
        r["inProd"] = r["mrs"] - r["waiting"] if r["prodEnv"] else None
        changes = sum(1 for i in r["items"] if not i["house"])
        r["tldr"] = tldr.get(r["name"]) or ("" if changes else "Maintenance only: dependencies, CI and docs.")

    areas = [a for a in notes.get("areas", {}) if any(r["area"] == a for r in repos)]
    if any(r["area"] == "Other" for r in repos):
        areas.append("Other")
    total = sum(r["mrs"] for r in repos)
    prod = sum(r["inProd"] or 0 for r in repos)
    waiting = sum(r["waiting"] for r in repos)
    epics, unplanned = group_epics(repos, notes)
    return {
        "epics": epics, "unplanned": unplanned,
        "mode": mode, "team": team, "range": period, "repos": repos, "areas": areas,
        "total": total, "prod": prod, "waiting": waiting,
        "noProd": total - prod - waiting, "repoCount": len(repos),
    }


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("message", type=Path)
    ap.add_argument("notes", type=Path)
    ap.add_argument("--title", required=True, help="page name, e.g. 'PE Merge Digest 2-11 Nov'")
    ap.add_argument("-o", "--out", type=Path, required=True)
    ap.add_argument("--no-prod-check", action="store_true", help="the draft has no prod marks (GitHub)")
    ap.add_argument("--list-epics", action="store_true", help="print the epic grouping and exit")
    a = ap.parse_args()

    data = build(a.message.read_text(), json.loads(a.notes.read_text()), a.no_prod_check)
    if a.list_epics:
        for g in [*data["epics"], data["unplanned"]]:
            print(f"{g['key']} {g['summary']} [{g['status']}]: {g['mrs']} MRs in {', '.join(g['repos'])}")
            for t in g["tickets"]:
                print(f"  {t['k']} {t['summary']} [{t['status']}]")
        return
    if missing := [r["name"] for r in data["repos"] if not r["tldr"]]:
        sys.exit(f"notes.tldr is missing: {', '.join(missing)}")
    payload = json.dumps(data, ensure_ascii=False).replace("</", "<\\/")
    html = TEMPLATE.read_text().replace("/*TITLE*/", a.title).replace("/*DATA*/null", payload)
    a.out.write_text(html)
    print(f"{data['total']} MRs, {data['prod']} in prod, {data['waiting']} waiting, {data['repoCount']} repos -> {a.out}")


if __name__ == "__main__":
    main()
