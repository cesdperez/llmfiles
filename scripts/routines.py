#!/usr/bin/env python3
"""Scheduled routines that launchd runs: a nightly repo update followed by /orcacleanup, a
weekday /dailyworkrecap draft, and /glabsummary, which installs switched off.

Usage:
  routines.py install [job ...]   write every plist, load the named jobs (default: nightly morning)
  routines.py uninstall           unload and remove every routine's plist
  routines.py run <job>           what launchd starts
  routines.py render <job> <dir>  write one plist to <dir> without loading it

Schedules, budgets and models can be overridden in local/routines.json
(LLMFILES_ROUTINES_CONFIG overrides its path and is baked into the plists at install,
template in local.example/).
"""

import json
import os
import plistlib
import shutil
import subprocess
import sys
import time
from concurrent.futures import ThreadPoolExecutor
from datetime import date, datetime
from pathlib import Path

HOME = Path.home()
REPO = Path(__file__).resolve().parent.parent
INSTALLED_REPO = HOME / "llmfiles"
AGENTS_DIR = HOME / "Library" / "LaunchAgents"
LOG_DIR = HOME / "Library" / "Logs" / "llmfiles-routines"
CONFIG_ENV = "LLMFILES_ROUTINES_CONFIG"
LABEL_PREFIX = "com.llmfiles.routines."
WEEKDAYS = [1, 2, 3, 4, 5]
JOBS = {
    "nightly": {"hour": 3, "minute": 0, "weekdays": [], "model": "sonnet", "max_budget_usd": 3},
    "morning": {"hour": 8, "minute": 30, "weekdays": WEEKDAYS, "max_budget_usd": 10},
    "glabsummary": {"hour": 9, "minute": 0, "weekdays": WEEKDAYS, "max_budget_usd": 20},
}
DEFAULT_INSTALL = ["nightly", "morning"]
PATH_TOOLS = ("claude", "orca", "glab", "twg", "gh", "git", "docker", "jq", "python3", "node")
BASE_PATH = [str(HOME / ".local/bin"), "/opt/homebrew/bin", "/usr/local/bin",
             "/usr/bin", "/bin", "/usr/sbin", "/sbin"]
CLAUDE_TIMEOUT_S = 45 * 60
SHAREPOINT = "mcp__claude_ai_Microsoft_365__sharepoint_"
MORNING_DENY = [
    "Bash(glab:*)", "Bash(twg:*)", "Bash(gh:*)", "Bash(curl:*)",
    *(f"mcp__claude_ai_Slack__slack_{verb}_*"
      for verb in ("send", "schedule", "create", "update", "add")),
    *(f"{SHAREPOINT}{verb}*" for verb in ("copy", "create", "move", "rename", "update", "upload")),
    "mcp__claude_ai_Claude_Docs__*", "mcp__claude_ai_Claude_Data__*",
    "Artifact", "ArtifactData", "ArtifactComments",
]
GLABSUMMARY_DENY = [
    "Bash(glab mr approve:*)", "Bash(glab mr merge:*)", "Bash(glab mr revoke:*)",
    "Bash(glab api -X DELETE:*)", "Bash(glab api --method DELETE:*)",
]
UNLOAD_POLLS = 40
BOOTSTRAP_TRIES = 4

UNATTENDED = (
    "This is a scheduled run and nobody is at the keyboard. Never ask a question: take the "
    "default for every choice and carry on. End with what you skipped or could not do and why, "
    "because your final reply is the only log. Run Bash commands in the foreground with a "
    "timeout of up to 600000 ms, since the run ends when your reply does."
)
NO_POSTING = (
    " Post nothing anywhere: no Slack message, draft, reaction or canvas, and no Jira or GitLab "
    "write. Stop after the notes, without offering a Slack draft. Your final reply is saved "
    "as the draft."
)


def run(cmd, cwd=None, timeout=120, env=None):
    try:
        result = subprocess.run(cmd, cwd=cwd, capture_output=True, text=True,
                                timeout=timeout, env=env)
    except (OSError, subprocess.TimeoutExpired) as error:
        return 1, "", str(error)
    return result.returncode, result.stdout.strip(), result.stderr.strip()


def git(repo, *args, timeout=120):
    # A scheduled fetch must fail rather than wait on a credential or host-key prompt.
    env = {**os.environ, "GIT_TERMINAL_PROMPT": "0"}
    env.setdefault("GIT_SSH_COMMAND", "ssh -o BatchMode=yes")
    return run(["git", "-C", str(repo), *args], timeout=timeout, env=env)


def log(job, message):
    print(f"{datetime.now().isoformat(timespec='seconds')} {job}: {message}", flush=True)


def load_settings(repo=REPO):
    path = Path(os.environ.get(CONFIG_ENV, repo / "local" / "routines.json")).expanduser()
    local = json.loads(path.read_text()) if path.exists() else {}
    return {job: {**defaults, **local.get(job, {})} for job, defaults in JOBS.items()}


def installed_settings():
    return load_settings(INSTALLED_REPO)


def label(job):
    return LABEL_PREFIX + job


def render_plist(job, settings, repo, python, path_env, home=HOME, log_dir=LOG_DIR, env=None):
    when = {"Hour": settings["hour"], "Minute": settings["minute"]}
    interval = [{"Weekday": day, **when} for day in settings["weekdays"]] or when
    log_file = str(log_dir / f"{job}.log")
    return {
        "Label": label(job),
        "ProgramArguments": [python, str(repo / "scripts" / "routines.py"), "run", job],
        "StartCalendarInterval": interval,
        "EnvironmentVariables": {"PATH": path_env, "HOME": str(home), **(env or {})},
        "WorkingDirectory": str(repo),
        "StandardOutPath": log_file,
        "StandardErrorPath": log_file,
    }


def launchd_path():
    """launchd starts jobs with a bare PATH and no shell profile, so bake in today's tool dirs."""
    found = [str(Path(p).parent) for p in map(shutil.which, PATH_TOOLS) if p]
    return ":".join(dict.fromkeys(found + BASE_PATH))


def write_plist(job, settings, directory):
    python = shutil.which("python3") or sys.executable
    config = os.environ.get(CONFIG_ENV)
    env = {CONFIG_ENV: str(Path(config).expanduser().absolute())} if config else None
    plist = render_plist(job, settings[job], INSTALLED_REPO, python, launchd_path(), env=env)
    path = Path(directory) / f"{label(job)}.plist"
    path.write_bytes(plistlib.dumps(plist))
    return path


def launchctl(*args):
    return run(["launchctl", *args])


def unload(target):
    """Boot the job out and wait until launchd no longer lists it; not loaded counts as done."""
    launchctl("bootout", target)
    for _ in range(UNLOAD_POLLS):
        if launchctl("print", target)[0]:
            return True
        time.sleep(0.25)
    return False


def bootstrap(domain, path):
    # launchd answers EIO while a just-booted-out job is still tearing down.
    for _ in range(BOOTSTRAP_TRIES):
        code, _, err = launchctl("bootstrap", domain, str(path))
        if code == 0:
            return ""
        if "Input/output error" not in err and code != 5:
            return err
        time.sleep(1)
    return err


def install(jobs):
    if not (INSTALLED_REPO / "scripts" / "routines.py").exists():
        sys.exit(f"{INSTALLED_REPO}/scripts/routines.py is missing: merge and pull first.")
    settings, domain, ok = installed_settings(), f"gui/{os.getuid()}", True
    AGENTS_DIR.mkdir(parents=True, exist_ok=True)
    LOG_DIR.mkdir(parents=True, exist_ok=True)
    for job in JOBS:
        target = f"{domain}/{label(job)}"
        if not unload(target):
            print(f"{job}: still loaded after bootout, left as is")
            ok = False
            continue
        path = write_plist(job, settings, AGENTS_DIR)
        if job not in jobs:
            # Disabled, launchd also skips the plist at the next login.
            code, _, err = launchctl("disable", target)
            print(f"{job}: disable failed: {err}" if code else f"{job}: written switched off, {path}")
            ok = ok and code == 0
            continue
        code, _, err = launchctl("enable", target)
        err = bootstrap(domain, path) if code == 0 else f"enable failed: {err}"
        print(f"{job}: not loaded: {err}" if err else f"{job}: loaded, {path}")
        ok = ok and not err
    return ok


def uninstall():
    domain, ok = f"gui/{os.getuid()}", True
    for job in JOBS:
        if not unload(f"{domain}/{label(job)}"):
            print(f"{job}: still loaded after bootout")
            ok = False
            continue
        path = AGENTS_DIR / f"{label(job)}.plist"
        if path.exists():
            path.unlink()
            print(f"{job}: removed {path}")
    return ok


def orca_repos():
    code, out, _ = run(["orca", "worktree", "list", "--json"])
    try:
        worktrees = json.loads(out)["result"]["worktrees"] if code == 0 else None
    except (json.JSONDecodeError, KeyError, TypeError):
        worktrees = None
    if worktrees is None:
        return None
    return [w["path"] for w in worktrees if w.get("isMainWorktree")]


def is_main_repo(path):
    """A repo with its own git dir. Linked worktrees are left to their main repo, which owns the
    default branch."""
    dot_git = Path(path, ".git")
    if dot_git.is_dir():
        return True
    try:
        line = dot_git.read_text().strip()
    except OSError:
        return False
    if not line.startswith("gitdir:"):
        return False
    gitdir = Path(path, line.removeprefix("gitdir:").strip())
    return "/worktrees/" not in gitdir.as_posix() and not (gitdir / "commondir").exists()


def root_repos(root):
    if not root or not Path(root).expanduser().is_dir():
        return []
    _, out, _ = run(["find", str(Path(root).expanduser()), "-maxdepth", "5",
                     "-name", ".git", "-prune"])
    return [str(Path(line).parent) for line in out.splitlines() if line]


def discover_repos(orca, root):
    seen, repos = set(), []
    for path in (orca or []) + root:
        real = os.path.realpath(path)
        if real not in seen and is_main_repo(real):
            seen.add(real)
            repos.append(real)
    return sorted(repos)


def update_verdict(facts):
    """("current" | "merge" | "update-ref" | "skip", reason) for one repo's default branch."""
    default = facts.get("default")
    if not facts["has_origin"]:
        return "skip", "no origin remote"
    if facts.get("fetch_error"):
        return "skip", f"fetch failed: {facts['fetch_error']}"
    if facts.get("error"):
        return "skip", facts["error"]
    if not default:
        return "skip", "origin/HEAD is unset, run git remote set-head origin --auto"
    if not facts["local_exists"]:
        return "skip", f"no local {default} branch"
    if facts["behind"] == 0:
        return "current", ""
    if facts["ahead"]:
        return "skip", f"{default} diverged: {facts['ahead']} local and {facts['behind']} remote commits"
    if facts["rebasing"]:
        return "skip", f"a rebase of {default} is in progress"
    checked_out = facts["checked_out_in"]
    if checked_out and checked_out != facts["repo"]:
        return "skip", f"{default} is checked out in another worktree, {checked_out}"
    if checked_out and facts["dirty"]:
        return "skip", f"{default} is checked out with uncommitted changes"
    return ("merge", "") if checked_out else ("update-ref", "")


class QueryFailed(Exception):
    pass


def query(repo, *args):
    code, out, err = git(repo, *args)
    if code:
        raise QueryFailed(f"git {' '.join(args)} failed: {err or f'exit {code}'}")
    return out


def worktrees(repo):
    code, out, _ = git(repo, "worktree", "list", "--porcelain")
    if code:
        return None
    trees, current = [], {}
    for line in out.splitlines() + [""]:
        if not line:
            if current:
                trees.append(current)
            current = {}
            continue
        key, _, value = line.partition(" ")
        current[key] = value or True
    return trees


def branch_holder(trees, ref):
    holder = next((t["worktree"] for t in trees if t.get("branch") == ref), None)
    return os.path.realpath(holder) if holder else None


def rebase_head(tree_path):
    for name in ("rebase-merge", "rebase-apply"):
        head_name = Path(tree_path, query(tree_path, "rev-parse", "--git-path", name), "head-name")
        if head_name.exists():
            return head_name.read_text().strip()
    return None


def repo_facts(repo):
    facts = {"repo": repo, "has_origin": git(repo, "remote", "get-url", "origin")[0] == 0}
    if not facts["has_origin"]:
        return facts
    code, _, err = git(repo, "fetch", "--prune", "--quiet", "origin", timeout=180)
    if code:
        return {**facts, "fetch_error": err or f"exit {code}"}
    _, remote_head, _ = git(repo, "symbolic-ref", "--short", "refs/remotes/origin/HEAD")
    default = remote_head.removeprefix("origin/") or None
    facts["default"] = default
    facts["local_exists"] = bool(default) and git(
        repo, "rev-parse", "--verify", "--quiet", f"refs/heads/{default}")[0] == 0
    if not facts["local_exists"]:
        return facts
    try:
        return {**facts, **branch_facts(repo, default)}
    except QueryFailed as error:
        return {**facts, "error": str(error)}


def branch_facts(repo, default):
    ref = f"refs/heads/{default}"
    local_oid = query(repo, "rev-parse", "--verify", ref)
    # Fails when origin/HEAD dangles, as after the default branch is renamed upstream.
    remote_oid = query(repo, "rev-parse", "--verify", f"refs/remotes/origin/{default}")
    ahead, behind = (int(n) for n in query(
        repo, "rev-list", "--left-right", "--count", f"{local_oid}...{remote_oid}").split())
    trees = worktrees(repo)
    if trees is None:
        raise QueryFailed("git worktree list failed")
    holder = branch_holder(trees, ref)
    dirty = bool(holder) and bool(query(holder, "status", "--porcelain", "--untracked-files=no"))
    return {"ahead": ahead, "behind": behind, "local_oid": local_oid, "remote_oid": remote_oid,
            "checked_out_in": holder, "dirty": dirty,
            "rebasing": any(rebase_head(t["worktree"]) == ref for t in trees if t.get("detached"))}


def update_repo(repo):
    try:
        return apply_update(repo)
    except Exception as error:  # one bad repo must not stop the nightly or /orcacleanup
        return "skip", str(error)


def apply_update(repo):
    facts = repo_facts(repo)
    verdict, reason = update_verdict(facts)
    if verdict in ("current", "skip"):
        return verdict, reason
    default, old, new = facts["default"], facts["local_oid"], facts["remote_oid"]
    trees = worktrees(repo)
    if trees is None or branch_holder(trees, f"refs/heads/{default}") != facts["checked_out_in"]:
        return "skip", f"the worktree holding {default} changed during the run"
    if verdict == "merge":
        code, _, err = git(repo, "merge", "--ff-only", "--quiet", new)
    else:
        code, _, err = git(repo, "update-ref", f"refs/heads/{default}", new, old)
    if code:
        return "skip", f"{verdict} failed: {err}"
    return "updated", f"{default} {old[:8]}..{new[:8]}"


def work_root():
    path = Path(os.environ.get("LLMFILES_WORK_CONFIG", REPO / "local" / "work.json")).expanduser()
    return json.loads(path.read_text()).get("repo_root") if path.exists() else None


def update_all(job):
    orca = orca_repos()
    if orca is None:
        log(job, "orca worktree list failed, so only repo_root repos are updated")
    repos = discover_repos(orca, root_repos(work_root()))
    with ThreadPoolExecutor(max_workers=8) as pool:
        results = list(pool.map(update_repo, repos))
    for repo, (verdict, reason) in zip(repos, results, strict=True):
        if verdict != "current":
            log(job, f"{verdict} {repo}: {reason}")
    counts = {v: sum(1 for r in results if r[0] == v) for v in ("updated", "current", "skip")}
    log(job, f"repos: {counts['updated']} updated, {counts['current']} current, {counts['skip']} skipped")


def claude(prompt, settings, extra="", disallowed=()):
    cmd = ["claude", "-p", prompt, "--permission-mode", "auto", "--permission-prompts", "none",
           "--append-system-prompt", UNATTENDED + extra, "--output-format", "text"]
    if settings.get("model"):
        cmd += ["--model", settings["model"]]
    if settings.get("max_budget_usd") is not None:
        cmd += ["--max-budget-usd", str(settings["max_budget_usd"])]
    if disallowed:
        # The deny also reaches the subagents the command spawns.
        cmd += ["--disallowedTools", ",".join(disallowed)]
    return run(cmd, cwd=REPO, timeout=CLAUDE_TIMEOUT_S)


def run_command(job, prompt, settings, out_file=None, **kwargs):
    # A user slash command expands under -p even with disable-model-invocation: true.
    log(job, f"starting {prompt}")
    code, out, err = claude(prompt, settings, **kwargs)
    if out_file and code == 0 and out.strip():
        out_file.write_text(out + "\n")
        log(job, f"wrote {out_file}")
    else:
        if out_file:
            log(job, f"no draft written, so {out_file} keeps any earlier draft")
        if out:
            print(out, flush=True)
    if err:
        log(job, f"stderr: {err}")
    log(job, f"{prompt} exited {code}")
    return code


def run_job(job):
    settings = load_settings()[job]
    LOG_DIR.mkdir(parents=True, exist_ok=True)
    if job == "nightly":
        update_all(job)
        return run_command(job, "/orcacleanup", settings)
    if job == "morning":
        draft = LOG_DIR / f"dailyworkrecap-{date.today()}.md"
        return run_command(job, "/dailyworkrecap", settings, out_file=draft,
                           extra=NO_POSTING, disallowed=MORNING_DENY)
    return run_command(job, "/glabsummary", settings, disallowed=GLABSUMMARY_DENY)


def main():
    args = sys.argv[1:]
    if not args or args[0] not in ("install", "uninstall", "run", "render"):
        sys.exit(__doc__)
    named = args[1:] if args[0] == "install" else args[1:2]
    unknown = [job for job in named if job not in JOBS]
    if unknown:
        sys.exit(f"unknown job {unknown[0]}, pick from {', '.join(JOBS)}")
    if args[0] == "install":
        sys.exit(0 if install(args[1:] or DEFAULT_INSTALL) else 1)
    elif args[0] == "uninstall":
        sys.exit(0 if uninstall() else 1)
    elif args[0] == "run" and len(args) == 2:
        sys.exit(run_job(args[1]))
    elif args[0] == "render" and len(args) == 3:
        print(write_plist(args[1], installed_settings(), args[2]))
    else:
        sys.exit(__doc__)


if __name__ == "__main__":
    main()
