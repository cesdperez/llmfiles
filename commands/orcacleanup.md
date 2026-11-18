---
description: Clean up what agent runs left behind across every repo Orca knows. It removes merged worktrees and branches, Docker Compose projects and processes whose checkout is gone, stale verify locks and settled Orca workers. It runs unattended and keeps anything it cannot prove is finished. Say "dry run" to only list what it would do.
argument-hint: '[dry run]'
allowed-tools: Bash, Read
---

Run the cleanup, adding `--dry-run` when `$ARGUMENTS` asks for a dry run:

```bash
python3 ~/llmfiles/scripts/orca-cleanup.py [--dry-run]
```

It takes a few minutes, because it fetches every repo and asks GitLab or GitHub about
squash-merged branches. Start it with Bash `run_in_background`.

The script decides and acts. Do not remove, kill or delete anything yourself, and do not
rerun a failed action: report it. What it never touches goes in
`~/llmfiles/local/orcacleanup.json` (template in `local.example/`). Every action is appended
to `~/.cache/orcacleanup/log.jsonl`, and a deleted branch's entry holds the command that
restores it.

Report in plain English, grouped by kind, one line per item:

```
orcacleanup - <n> removed, <n> kept, <n> errors[ (dry run)]
Removed: <kind>: <target>, <why>
Kept: <kind>: <target>, <why>
Errors: <kind>: <target>, <error>
```

Collapse a kind with more than 5 items into a count plus the first 3. In a dry run,
branches of worktrees it would remove are not listed yet: the branch pass sees them once
the worktree is gone.
