#!/usr/bin/env python3
"""Remove what agent runs left behind across the repos Orca knows: merged worktrees,
merged branches, compose projects and processes of checkouts that are gone, stale
locks and settled Orca workers. Unattended, so it acts only on positive evidence
and keeps anything it cannot prove is finished.

Usage: orca-cleanup.py [--dry-run]

Emits JSON on stdout: {"dry_run", "done", "kept", "errors", "log"}. "done" lists each
action with its reason, and "undo" where one exists. "kept" lists only what looked
finished but was kept, with the reason. Every action is also appended to the log.

Keep rules come from local/orcacleanup.json (LLMFILES_ORCACLEANUP_CONFIG overrides it):
{"keep_compose_projects": [...], "keep_paths": [<globs>], "keep_branches": [<globs>]}.
"""

import fnmatch
import json
import os
import signal
import subprocess
import sys
import tempfile
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

HOUR = 3600
ACTIVE_WINDOW_S = 4 * HOUR
EMPTY_WORKTREE_IDLE_S = 72 * HOUR
TEMP_WORKTREE_IDLE_S = 24 * HOUR
AGENT_BRANCH_AGE_S = 14 * 24 * HOUR
LOCK_STALE_S = HOUR
AGENT_BRANCH_PREFIXES = ("worktree-agent-", "worktree-opencode-")
BUSY_AGENT_STATES = {"working", "blocked", "waiting"}
NEVER_KILL = {"zsh", "bash", "sh", "fish", "login", "tmux", "screen", "ssh", "vim", "nvim", "less"}
QA_LOCK = Path.home() / ".cache/fullsend/qa.lock"
LOG = Path.home() / ".cache/orcacleanup/log.jsonl"
CONFIG = Path(__file__).resolve().parent.parent / "local" / "orcacleanup.json"
TEMP_ROOTS = (
    str(Path.home() / ".claude/runtime"),
    os.path.realpath(tempfile.gettempdir()),
    "/tmp",
    "/private/tmp",
    "/private/var/folders",
)


def inside(path, root):
    return path == root or path.startswith(root.rstrip("/") + "/")


def under_temp_root(path):
    return any(inside(path, root) for root in TEMP_ROOTS)


def worktree_verdict(facts):
    """Return (verdict, reason). A None verdict is not worth reporting."""
    if facts["is_main"] or not facts["exists"]:
        return None, ""
    if facts["kept_path"] or facts["pinned"]:
        return ("keep", "pinned or on the keep list") if facts["merged"] else (None, "")
    if facts["agent_busy"] or facts["worker_live"]:
        return ("keep", "an agent is still working in it") if facts["merged"] else (None, "")
    if facts["temp_root"]:
        if facts["idle_s"] >= TEMP_WORKTREE_IDLE_S:
            return "force-remove", "throwaway worktree under a temp directory, idle for a day"
        return None, ""
    if not facts["merged"]:
        return None, ""
    if facts["idle_s"] < ACTIVE_WINDOW_S:
        return "keep", "merged, but active in the last 4 hours"
    if facts["dirty"]:
        return "keep", "merged, but has uncommitted changes"
    if facts.get("empty") and facts["idle_s"] < EMPTY_WORKTREE_IDLE_S:
        return None, ""
    return "remove", facts["merged"]


def prune_leads(removable, children):
    """Drop every worktree that still has a kept descendant, so a hub lead goes last."""
    removable = set(removable)
    changed = True
    while changed:
        changed = False
        for parent in list(removable):
            if any(child not in removable for child in children.get(parent, [])):
                removable.discard(parent)
                changed = True
    return removable


def compose_verdict(unit, kept_projects, removed_roots, exists):
    if unit["name"] in kept_projects:
        files = unit["config_files"]
        if files and any(not exists(f) for f in files) and any(exists(f) for f in files):
            return "repair"
        return None
    workdir = unit["working_dir"]
    if not exists(workdir) or any(inside(workdir, root) for root in removed_roots):
        return "down"
    return None


def should_kill(proc, removed_roots, exists):
    if proc["command"] in NEVER_KILL:
        return False
    cwd = proc["cwd"]
    return not exists(cwd) or any(inside(cwd, root) for root in removed_roots)


def branch_verdict(facts):
    if facts["checked_out"] or facts["is_base"] or facts["kept"]:
        return None
    if facts["merged"]:
        return "delete"
    if facts["name"].startswith(AGENT_BRANCH_PREFIXES) and facts["age_s"] >= AGENT_BRANCH_AGE_S:
        return "delete"
    return None


def lock_is_stale(lock):
    owner = lock / "owner"
    stamp = owner if owner.exists() else lock
    return run_process_gone(lock / "pid") or time.time() - stamp.stat().st_mtime > LOCK_STALE_S


# Only a qa-lock.sh `run` records its pid. A `take` span has none and relies on its touches.
def run_process_gone(pid_file):
    try:
        os.kill(int(pid_file.read_text()), 0)
    except ProcessLookupError:
        return True
    except (OSError, ValueError):
        return False
    return False


def run(cmd, cwd=None, timeout=120):
    try:
        result = subprocess.run(cmd, cwd=cwd, capture_output=True, text=True, timeout=timeout)
    except (OSError, subprocess.TimeoutExpired) as error:
        return 1, "", str(error)
    return result.returncode, result.stdout, result.stderr.strip()


def git(repo, *args):
    return run(["git", "-C", str(repo), *args])


def orca_json(*args):
    code, out, _ = run(["orca", *args, "--json"])
    try:
        return json.loads(out).get("result", {}) if code == 0 else {}
    except json.JSONDecodeError:
        return {}


def forge(repo):
    _, url, _ = git(repo, "remote", "get-url", "origin")
    if "github.com" in url:
        return "github"
    return "gitlab" if "gitlab" in url else None


def merged_mr(repo, branch, tip):
    kind = forge(repo)
    if kind == "gitlab":
        code, out, _ = run(["glab", "mr", "list", "--source-branch", branch, "--merged", "-F", "json"], cwd=repo)
        mrs = json.loads(out or "[]") if code == 0 else []
        hit = next((mr for mr in mrs if mr.get("sha") == tip), None)
        return f"MR !{hit['iid']} merged" if hit else None
    if kind == "github":
        code, out, _ = run(["gh", "pr", "list", "--head", branch, "--state", "merged",
                            "--json", "number,headRefOid"], cwd=repo)
        prs = json.loads(out or "[]") if code == 0 else []
        hit = next((pr for pr in prs if pr.get("headRefOid") == tip), None)
        return f"PR #{hit['number']} merged" if hit else None
    return None


def merged_evidence(repo, branch, tip, base, lookup_mr=True):
    if git(repo, "merge-base", "--is-ancestor", tip, base)[0] == 0:
        return f"ancestor of {base}"
    code, out, _ = git(repo, "cherry", base, tip)
    lines = out.split()
    if code == 0 and out.strip() and "+" not in lines[::2]:
        return f"patches already in {base}"
    if lookup_mr and branch:
        return merged_mr(repo, branch, tip)
    return None


def never_committed(repo, branch):
    """A branch whose reflog holds only its creation never got work of its own."""
    code, out, _ = git(repo, "reflog", "show", "--format=%H", f"refs/heads/{branch}", "--")
    return code == 0 and len(out.split()) == 1


def fetch(repo):
    if git(repo, "remote", "get-url", "origin")[0] != 0:
        return 0, "", ""
    return run(["git", "-C", repo, "fetch", "--prune", "--quiet", "origin"], timeout=90)


def base_ref(repo):
    code, out, _ = git(repo, "symbolic-ref", "--short", "refs/remotes/origin/HEAD")
    if code == 0 and out.strip():
        return out.strip()
    for name in ("main", "master"):
        if git(repo, "rev-parse", "--verify", "--quiet", name)[0] == 0:
            return name
    return None


class Cleanup:
    def __init__(self, dry_run, config):
        self.dry_run = dry_run
        self.keep_projects = set(config.get("keep_compose_projects", []))
        self.keep_paths = config.get("keep_paths", [])
        self.keep_branches = config.get("keep_branches", [])
        self.done, self.kept, self.errors = [], [], []
        self.removed_roots = set()
        self.ancestors = self.process_ancestors()

    def act(self, kind, target, why, cmd=None, undo=None, cwd=None):
        entry = {"kind": kind, "target": target, "why": why}
        if undo:
            entry["undo"] = undo
        if not self.dry_run and cmd:
            code, _, err = run(cmd, cwd=cwd) if isinstance(cmd, list) else cmd()
            if code != 0:
                self.errors.append({**entry, "error": err})
                return False
        self.done.append(entry)
        if not self.dry_run:
            LOG.parent.mkdir(parents=True, exist_ok=True)
            with LOG.open("a") as log:
                log.write(json.dumps({"at": time.strftime("%Y-%m-%dT%H:%M:%S"), **entry}) + "\n")
        return True

    def keep(self, kind, target, why):
        self.kept.append({"kind": kind, "target": target, "why": why})

    def stale_lock(self):
        if QA_LOCK.exists() and lock_is_stale(QA_LOCK):
            self.act("lock", str(QA_LOCK), "its run process is gone or its owner was untouched for over an hour",
                     cmd=["rm", "-rf", str(QA_LOCK)])

    def reclaimable_workers(self, workers):
        for row in workers:
            if row.get("terminalState") == "reclaimable":
                self.release(row, "settled worker still owns its terminal")

    def release(self, row, why):
        self.act("worker", row["dispatchId"], why,
                 cmd=["orca", "orchestration", "worker-release", "--dispatch", row["dispatchId"], "--json"])

    def worktrees(self, orca_worktrees, agents, workers):
        busy = {a["worktreeId"].split("::")[-1] for a in agents if a.get("state") in BUSY_AGENT_STATES}
        live = {w["workspace"].split("::")[-1] for w in workers if w.get("liveness") == "live"}
        mains = self.mains = {w["repoId"]: w["path"] for w in orca_worktrees if w["isMainWorktree"]}
        with ThreadPoolExecutor(max_workers=8) as pool:
            fetched = dict(zip(mains.values(), pool.map(fetch, mains.values()), strict=True))
        for repo, (code, _, err) in fetched.items():
            if code != 0:
                self.errors.append({"kind": "fetch", "target": repo, "error": err})
        self.bases = {repo: base_ref(repo) for repo in mains.values()}

        verdicts, children, by_id = {}, {}, {}
        now = time.time()
        for wt in orca_worktrees:
            path, repo = wt["path"], mains.get(wt["repoId"])
            by_id[wt["id"]] = wt
            children[wt["id"]] = wt.get("childWorktreeIds") or []
            if not repo or not self.bases.get(repo) or wt["isMainWorktree"]:
                continue
            branch = (wt.get("branch") or "").removeprefix("refs/heads/") or None
            exists = os.path.isdir(path)
            facts = {
                "path": path,
                "is_main": False,
                "exists": exists,
                "pinned": wt.get("isPinned", False),
                "kept_path": any(fnmatch.fnmatch(path, glob) for glob in self.keep_paths),
                "dirty": exists and bool(git(path, "status", "--porcelain")[1].strip()),
                "merged": exists and merged_evidence(repo, branch, wt["head"], self.bases[repo]),
                "empty": bool(branch) and never_committed(repo, branch),
                "temp_root": under_temp_root(path),
                "idle_s": now - (wt.get("lastActivityAt") or 0) / 1000,
                "agent_busy": path in busy,
                "worker_live": path in live,
            }
            verdict, why = worktree_verdict(facts)
            verdicts[wt["id"]] = (verdict, why, wt)
            if verdict == "keep":
                self.keep("worktree", path, why)

        removable = {i for i, (v, _, _) in verdicts.items() if v in ("remove", "force-remove")}
        for wt_id in removable - prune_leads(removable, children):
            self.keep("worktree", by_id[wt_id]["path"], "lead of worktrees that are kept")
        removable = prune_leads(removable, children)
        self.to_remove = [verdicts[i] for i in removable]
        self.removed_roots = {wt["path"] for _, _, wt in self.to_remove}
        self.workers = workers

    def processes(self):
        code, out, _ = run(["lsof", "-a", "-d", "cwd", "-u", str(os.getuid()), "-Fpcn"])
        procs, current = [], {}
        for line in out.splitlines() if code == 0 else []:
            tag, value = line[:1], line[1:]
            if tag == "p":
                current = {"pid": int(value)}
                procs.append(current)
            elif tag in ("c", "n"):
                current["command" if tag == "c" else "cwd"] = value
        targets = [p for p in procs if "cwd" in p and p["pid"] not in self.ancestors
                   and should_kill(p, self.removed_roots, os.path.exists)]
        for proc in targets:
            self.act("process", f"{proc['command']} ({proc['pid']})", f"runs in {proc['cwd']}, which is gone",
                     cmd=lambda pid=proc["pid"]: self.signal(pid, signal.SIGTERM))
        if targets and not self.dry_run:
            time.sleep(3)
            for proc in targets:
                self.signal(proc["pid"], signal.SIGKILL)

    @staticmethod
    def signal(pid, sig):
        try:
            os.kill(pid, sig)
        except ProcessLookupError:
            pass
        except PermissionError as error:
            return 1, "", str(error)
        return 0, "", ""

    @staticmethod
    def process_ancestors():
        pids, pid = {os.getpid()}, os.getppid()
        while pid > 1 and pid not in pids:
            pids.add(pid)
            code, out, _ = run(["ps", "-o", "ppid=", "-p", str(pid)])
            pid = int(out.strip()) if code == 0 and out.strip() else 1
        return pids

    def containers(self):
        code, ids, _ = run(["docker", "ps", "-aq"])
        if code != 0 or not ids.split():
            return
        code, out, err = run(["docker", "inspect", *ids.split()])
        if code != 0:
            self.errors.append({"kind": "docker", "target": "inspect", "error": err})
            return
        down, lock_held = set(), QA_LOCK.exists() and not lock_is_stale(QA_LOCK)
        for container in json.loads(out):
            labels = container["Config"].get("Labels") or {}
            name = container["Name"].lstrip("/")
            owner = labels.get("llmfiles.worktree")
            if owner and (not os.path.exists(owner) or any(inside(owner, r) for r in self.removed_roots)):
                self.act("container", name, f"started for {owner}, which is gone",
                         cmd=["docker", "rm", "-f", container["Id"]])
                continue
            project = labels.get("com.docker.compose.project")
            if not project:
                continue
            unit = {
                "name": project,
                "working_dir": labels.get("com.docker.compose.project.working_dir", ""),
                "config_files": [f for f in labels.get("com.docker.compose.project.config_files", "").split(",") if f],
            }
            verdict = compose_verdict(unit, self.keep_projects, self.removed_roots, os.path.exists)
            if verdict == "down" and project not in down:
                down.add(project)
                self.compose_down(project, unit["working_dir"])
            elif verdict == "repair":
                self.compose_repair(unit, labels.get("com.docker.compose.service"), name, lock_held)

    def compose_down(self, project, workdir):
        def down():
            code, out, err = run(["docker", "compose", "-p", project, "down", "--volumes", "--remove-orphans"])
            if code != 0:
                return code, out, err
            _, volumes, _ = run(["docker", "volume", "ls", "-q", "--filter", f"label=com.docker.compose.project={project}"])
            return run(["docker", "volume", "rm", *volumes.split()]) if volumes.split() else (0, "", "")
        self.act("compose", project, f"its checkout {workdir} is gone", cmd=down)

    def compose_repair(self, unit, service, name, lock_held):
        live_files = [f for f in unit["config_files"] if os.path.exists(f)]
        why = "serves a removed worktree through a missing override"
        if lock_held:
            self.keep("compose", name, f"{why}, but the machine lock is held")
            return
        files = [arg for f in live_files for arg in ("-f", f)]
        self.act("repair", name, f"{why}: recreated from its own files",
                 cmd=["docker", "compose", "-p", unit["name"], "--project-directory", unit["working_dir"],
                      *files, "up", "-d", "--force-recreate", "--no-deps", service])

    def remove_worktrees(self):
        for verdict, why, wt in self.to_remove:
            path = wt["path"]
            for row in self.workers:
                if row["workspace"].split("::")[-1] == path and row.get("terminalState") in ("retained", "reclaimable"):
                    self.release(row, f"its worktree {path} is being removed")
            force = ["--force"] if verdict == "force-remove" else []
            checkout = (wt.get("branch") or "").removeprefix("refs/heads/") or wt["head"]
            undo = f"git -C {self.mains.get(wt['repoId'])} worktree add {path} {checkout}"
            self.act("worktree", path, why, undo=undo,
                     cmd=["orca", "worktree", "rm", "--worktree", f"path:{path}", *force, "--json"])

    def branches(self, repos):
        for repo in repos:
            if not self.dry_run:
                git(repo, "worktree", "prune")
            base = self.bases.get(repo)
            if not base:
                continue
            _, listing, _ = git(repo, "worktree", "list", "--porcelain")
            checked_out = {line[len("branch refs/heads/"):] for line in listing.splitlines()
                           if line.startswith("branch refs/heads/")}
            fmt = "%(refname:short)%09%(objectname)%09%(upstream)%09%(committerdate:unix)"
            _, refs, _ = git(repo, "for-each-ref", "refs/heads", f"--format={fmt}")
            for line in refs.splitlines():
                name, tip, upstream, stamp = line.split("\t")
                facts = {
                    "name": name,
                    "checked_out": name in checked_out,
                    "is_base": name == base.removeprefix("origin/"),
                    "kept": any(fnmatch.fnmatch(name, glob) for glob in self.keep_branches),
                    "merged": None,
                    "age_s": time.time() - int(stamp or 0),
                }
                if not (facts["checked_out"] or facts["is_base"] or facts["kept"]):
                    facts["merged"] = merged_evidence(repo, name, tip, base, lookup_mr=bool(upstream))
                if branch_verdict(facts):
                    why = facts["merged"] or "agent scratch branch, untouched for two weeks"
                    self.act("branch", f"{repo}:{name}", why, cmd=["git", "-C", repo, "branch", "-D", name],
                             undo=f"git -C {repo} branch {name} {tip}")

    def stray_agent_dirs(self, repos):
        for repo in repos:
            root = Path(repo) / ".claude/worktrees"
            for entry in root.iterdir() if root.is_dir() else []:
                if entry.is_dir() and not (entry / ".git").exists():
                    self.keep("dir", str(entry), "left in .claude/worktrees but no longer a worktree")


def load_config():
    path = Path(os.environ.get("LLMFILES_ORCACLEANUP_CONFIG", CONFIG)).expanduser()
    return json.loads(path.read_text()) if path.exists() else {}


def main():
    cleanup = Cleanup("--dry-run" in sys.argv[1:], load_config())
    orca_worktrees = orca_json("worktree", "list").get("worktrees")
    if orca_worktrees is None:
        sys.exit("orca worktree list failed: is Orca running?")
    agents = orca_json("agent", "list").get("agents", [])
    workers = orca_json("orchestration", "worker-list").get("workers", [])
    repos = [w["path"] for w in orca_worktrees if w["isMainWorktree"] and os.path.isdir(w["path"])]

    cleanup.stale_lock()
    cleanup.reclaimable_workers(workers)
    cleanup.worktrees(orca_worktrees, agents, workers)
    cleanup.processes()
    cleanup.containers()
    cleanup.remove_worktrees()
    cleanup.branches(repos)
    cleanup.stray_agent_dirs(repos)
    print(json.dumps({"dry_run": cleanup.dry_run, "done": cleanup.done, "kept": cleanup.kept,
                      "errors": cleanup.errors, "log": str(LOG)}, indent=2))


if __name__ == "__main__":
    main()
