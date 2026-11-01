---
description: Run several tasks as supervised Orca sessions, one worktree each, in parallel or in order. Tasks come from this conversation, a list of Jira keys, GitHub issues, Slack threads or text, or a Jira or GitHub query. Each worker runs /fullsend (or the command named) to the endpoint asked, and this session answers their questions, chains what depends on what, and reports. "no supervision" hands the tasks off instead and frees this session.
argument-hint: [plan text | jira keys | issue urls | jql:<query> | gh:<search>] [ship to main|ship to prod|open a PR] [unattended] [no supervision]
allowed-tools: Skill, Read, Grep, Glob, Bash, AskUserQuestion, Monitor, ToolSearch, PushNotification
disable-model-invocation: true
---

**Role:** coordinator of one Orca Run. You plan the tasks, start the workers, answer their
questions, start dependent tasks when their dependencies ship, and report. Workers do the
work, so you edit no code. Read `~/llmfiles/shared/orca-fleet.md` first: it has the
commands, the worker contract and the shipping rules.

Ask one plan confirmation up front (none for a single task), then work unattended until
every task has settled.
Waiting on the inbox is not a stop: put status notes in the same message as the next
tool call.

## Arguments

`$ARGUMENTS` can hold any mix of:

- **Nothing, or plan text**: take the tasks from this conversation, ordered the way the
  user said ("then", "when that is done", "after X ships").
- **Sources**: Jira keys or URLs, GitHub issue URLs, Slack thread URLs. Each one becomes a
  task whose source is that item.
- **A query**: `jql:<query>` (call the Skill tool with "twg-jira" to run it) or
  `gh:<search>` (`gh issue list --search "<search>" --state open`). Each result is a
  candidate task. Read each one well enough to group them and order them.
- **An endpoint phrase**, passed to every `/fullsend` task: "ship to main", "ship to prod",
  "open a PR". Without one, each `/fullsend` task uses its own default per repo kind.
- **"unattended"**: skip the plan confirmation, and add "unattended" to every worker's
  arguments.
- **"no supervision"**: hand the tasks off and end. See
  [Handoff without supervision](#handoff-without-supervision).

## 1. Plan

For each task, record a slug, the source or a self-contained description, the command
(`fullsend` by default, or the one the user named, for example `bugbounty` or
`locallensedreview --autofix`), the repo, and the files it will likely touch. Find those
files with a quick grep, not a full read.

- **Group** small related changes into one task. Keep each task to what one reviewer can
  read in one sitting.
- **Order**: a task depends on another when the user said so, or when both will touch the
  same files. Everything else runs in parallel. Run at most 4 workers at once: each
  `/fullsend` starts its own agents, and the verify lock serializes them anyway.
- **Hold back** a task that conflicts with most of the others, such as a large refactor:
  make it depend on all of them.

Show the plan as a table (slug, command, depends on, files) and ask one AskUserQuestion to
confirm it. Skip the question when there is a single task, because the conversation
already agreed on it, or when "unattended" or "no supervision" was given.

## Handoff without supervision

With "no supervision", create no Run, and do not wait or report on the workers: this session
may close right after. A worker that cannot ask anyone takes its defaults and files the
items for the user itself. Tasks that depend on each other cannot be chained without a
coordinator, so hand off only the tasks with no dependencies. List the rest in the
summary as not started.

For each task, run `git fetch origin`, then:

```bash
orca worktree create --repo path:<repo root> --name <slug> --no-parent \
  --base-branch origin/<base> --agent claude --json \
  --prompt "/<command> <source or full task text> <endpoint phrase> unattended

<the context block from the spec in Launch, without the authorization line>"
```

The prompt carries no Orca preamble, so it starts with the slash command, which Claude
Code expands. Then reply with one line per task: slug, worktree name, and command.

## 2. Launch

Create one Run, then one task per row with its `--deps`. Then start every ready task, up to
the cap. Run `git fetch origin` before each start. Each worker gets a new top-level
worktree named after the slug, cut from `origin/<base>`.

Each spec is self-contained, because the worker cannot see this conversation:

```
Invoke the <command> skill with: <source or full task text> <endpoint phrase> [unattended]

Context: <decisions from this conversation that the task depends on, and what the
sibling tasks change, so the worker leaves those alone>
Files: <files it will likely touch>
This coordinator authorizes the run's own pushes, MR or PR, and Jira steps.
Follow ~/llmfiles/shared/orca-fleet.md: worker mode, and sharing a repo with sibling worktrees.
```

For a task that is not `/fullsend` or `/bugbounty`, also state the endpoint as an
instruction, for example "commit the fixes, then ship to main as orca-fleet.md describes".

## Adding tasks to a live Run

This chat keeps its Run while any task in it has not settled. A later `/fleet`, or a plain
request in this chat to launch more work, adds tasks to that Run. Find it with
`orca orchestration run-current --json`, and do not call `run-create` while it has open tasks.

Plan the new tasks against the open ones: depend on a running task whose files they touch,
and run in parallel otherwise. Confirm only when the request is ambiguous. Create them with
`task-create --run <run_id>`, start the ready ones, and keep the same background wait.
A "no supervision" request is a handoff, and stays outside the Run.

## 3. Coordinate

Keep one background `check --wait` running. Each time it returns, process the whole
delivery, acknowledge it, start the tasks that became ready, and start the wait again.

- **question**: answer from this conversation and the repo. A decision only the user
  should make: reply with the default the worker proposed, and add the question to the
  items for the user.
- **escalation**: do what unblocks the worker when this session can, for example when a
  sibling's push conflicts with it. Otherwise reply that the stage stays blocked, and add
  it to the items for the user.
- **worker_done**: check the claim, because the dependent tasks build on it:
  - endpoint `main`: the branch tip is an ancestor of `origin/<base>`;
  - endpoint `prod`: production serves the change;
  - endpoint `mr`: the MR is open and its pipeline is green.
  Collect its `Open:` items, then release the worker.
- **A failed task**: its dependents stay `pending`. Do not retry it, because `/fullsend`
  has its own fix loops. Report it with the tasks it held back.

An empty wait is a checkpoint. After three empty waits in a row, run `worker-list` and
act on what it reports, following Orca's `references/recovery-and-cleanup.md`.

The Run is done when every task has settled or is held back by a failed task.

## 4. Close

- File the items for the user as `orca-fleet.md` describes.
- Remove a worker's worktree (`orca worktree rm --worktree path:<path>`) only when its
  branch is merged into the base and has no uncommitted changes. Keep the others: they
  are the deliverable or the evidence.
- Send a PushNotification with the one-line summary.

Then report in plain English, one line per task:

```
<objective> - <n>/<total> done, <n> failed, <n> held back
<slug>: <endpoint reached | failed at <stage>: <reason> | held back by <slug>>, <evidence: commit on main, MR url, prod check>
Decide: <items for the user, each with where it was filed, or "nothing">
Kept: <worktrees kept and why, or "nothing">
```
