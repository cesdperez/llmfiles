#!/usr/bin/env python3
"""Register a repo in Orca and file it under the project group of the closest
registered repo that contains it, so a repo under ~/projects/goodhabitz lands in
the goodhabitz group instead of the sidebar's top level.

Usage: orca-add-repo.py <repo path>

Emits JSON on stdout: {"path", "registered", "group_id", "warning"}.
A grouping failure is a warning, not an error: the repo stays registered and
ungrouped, and the caller's run goes on.
"""

import json
import os
import shutil
import subprocess
import sys

# The CLI has no command to move a repo into a group. The app's runtime does,
# so this calls it through the client library the CLI itself is built on.
RPC_SCRIPT = """
const {RuntimeClient} = require(process.argv[1]);
(async () => {
  const client = new RuntimeClient(undefined, undefined, null, null);
  try {
    const result = await client.call('projectGroup.moveProject', JSON.parse(process.argv[2]));
    console.log(JSON.stringify({ok: result.ok !== false}));
  } catch (error) {
    console.log(JSON.stringify({ok: false, error: error.message}));
  }
  process.exit(0);
})();
"""


def orca_json(*args):
    result = subprocess.run(["orca", *args, "--json"], capture_output=True, text=True)
    return json.loads(result.stdout or "{}")


def registered_repos():
    return orca_json("repo", "list")["result"]["repos"]


def find_repo(repos, path):
    return next((repo for repo in repos if os.path.realpath(repo["path"]) == path), None)


def closest_ancestor(repos, path):
    ancestors = [
        repo for repo in repos
        if path.startswith(os.path.realpath(repo["path"]).rstrip("/") + "/")
    ]
    return max(ancestors, key=lambda repo: len(repo["path"]), default=None)


def orca_app_contents():
    launcher = os.path.realpath(shutil.which("orca") or "")
    app = launcher[: launcher.find(".app") + 4] if ".app" in launcher else "/Applications/Orca.app"
    return os.path.join(app, "Contents")


def move_to_group(path, group_id):
    contents = orca_app_contents()
    client_library = os.path.join(
        contents, "Resources", "app.asar.unpacked", "out", "cli", "runtime-client.js"
    )
    params = json.dumps({"repo": f"path:{path}", "groupId": group_id})
    result = subprocess.run(
        [os.path.join(contents, "MacOS", "Orca"), "-e", RPC_SCRIPT, client_library, params],
        capture_output=True,
        text=True,
        env={**os.environ, "ELECTRON_RUN_AS_NODE": "1"},
    )
    try:
        return json.loads(result.stdout.strip().splitlines()[-1])
    except (IndexError, json.JSONDecodeError):
        return {"ok": False, "error": (result.stderr or "no output").strip()[:300]}


def main():
    if len(sys.argv) != 2:
        sys.exit("usage: orca-add-repo.py <repo path>")
    path = os.path.realpath(os.path.expanduser(sys.argv[1]))
    report = {"path": path, "registered": False, "group_id": None, "warning": None}

    repos = registered_repos()
    repo = find_repo(repos, path)
    if repo is None:
        added = orca_json("repo", "add", "--path", path)
        if not added.get("ok"):
            sys.exit(f"orca repo add failed: {added.get('error')}")
        report["registered"] = True
        repos = registered_repos()
        repo = find_repo(repos, path)

    report["group_id"] = repo.get("projectGroupId")
    ancestor = closest_ancestor(repos, path)
    target_group = ancestor.get("projectGroupId") if ancestor else None
    if target_group and target_group != report["group_id"]:
        moved = move_to_group(path, target_group)
        if moved.get("ok"):
            report["group_id"] = target_group
        else:
            report["warning"] = f"left ungrouped: {moved.get('error')}"

    print(json.dumps(report))


if __name__ == "__main__":
    main()
