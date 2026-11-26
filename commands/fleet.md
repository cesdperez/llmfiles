---
description: Run several items of work as supervised Orca sessions, grouped by the code they touch into one worktree per group, in parallel or in order. Items come from this conversation, a list of Jira keys, GitHub issues, Slack threads or text, or a Jira or GitHub query. Each worker runs /fullsend (or the command named) to the endpoint asked, and this session answers their questions, chains what depends on what, and reports. "no supervision" hands the tasks off instead and frees this session.
argument-hint: '[plan text | jira keys | issue urls | jql:<query> | gh:<search>] [ship to main|ship to prod|open a PR] [fix leftovers] [one worktree per item] [unattended] [no supervision]'
allowed-tools: Skill, Read, Grep, Glob, Bash, AskUserQuestion, Monitor, ToolSearch, PushNotification
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

- **Nothing, or plan text**: take the items from this conversation, ordered the way the
  user said ("then", "when that is done", "after X ships").
- **Sources**: Jira keys or URLs, GitHub issue URLs, Slack thread URLs. Each one is an
  item.
- **A query**: `jql:<query>` (call the Skill tool with "twg-jira" to run it) or
  `gh:<search>` (`gh issue list --search "<search>" --state open`). Each result is a
  candidate item. Read each one well enough to group them and order them.
- **An endpoint phrase**, passed to every `/fullsend` task: "ship to main", "ship to prod",
  "open a PR". Without one, each `/fullsend` task uses its own default per repo kind.
- **"fix leftovers"**, also meant by "boy scout" or "clean up what you find": passed to
  every `/fullsend` task, and it allows the follow-up wave in [Coordinate](#3-coordinate).
- **"one worktree per item"**: skip the grouping in [Plan](#1-plan).
- **"unattended"**: skip the plan confirmation, and add "unattended" to every worker's
  arguments.
- **"no supervision"**: hand the tasks off and end. See
  [Handoff without supervision](#handoff-without-supervision).

## 1. Plan

For each item, record the source or a self-contained description, the repos, and the files
it will likely touch. Find those files with a quick grep, not a full read. Read
`~/llmfiles/shared/meta-hub.md` when this session runs in a hub as that file defines it:
its ordering rules apply.

A task is a region of code, not an item. Every worktree pays for an install, a review, a
verify, an MR and a pipeline whatever the size of its change, so a worktree per item pays
that many times over for small changes.

- **Group** items into one task when they will touch the same files, or the same package
  or app for the same concern. The task runs them as one `/fullsend` with several sources:
  one worktree, one MR, a commit per item. A command that takes one target, such as
  `bugbounty`, keeps one task per target.
- **Small items** get no worktree of their own. One whose edit is one or two files joins
  the task nearest its files. Those with no neighbour share one task.
- **Split** a group only when it would pass about 800 changed lines or 5 items, or when
  an item must be reverted on its own. Parts that share files run in order, so the later
  one builds on the earlier.
- **Order** the rest only as the user said. Tasks that share no files run in parallel.
- **Cap**: run at most 3 workers at once on this machine, counted across every Run.
  `orca orchestration worker-list --terminal-state active --json` without `--run` lists
  them all. Each `/fullsend` starts its own agents and test runs, and more workers than
  that wait on memory and on the machine lock instead of working.
- **Hold back** a task that conflicts with most of the others, such as a large refactor:
  make it depend on all of them.

Give each task a slug and its command (`fullsend` by default, or the one the user named,
for example `bugbounty` or `locallensedreview --autofix`).

Show the plan as a table (slug, items, command, depends on, files), under one line that
counts the items and the worktrees, and ask one AskUserQuestion to confirm it. Skip the
question when there is a single task, because the conversation already agreed on it, or
when "unattended" or "no supervision" was given.

When an item for a work repo, as `fullsend.md` classifies repos, has no Jira key, the
confirmation also asks whether to create tickets for those items. With a single task, ask
that question alone. On yes, create them before Launch (call the Skill tool with
"jira-writing" and "twg-jira"), and each key becomes its item's source. Otherwise, and
always when "unattended" or "no supervision" was given, create none, and the spec says
so, so the worker does not ask again.

## Handoff without supervision

With "no supervision", create no Run, and do not wait or report on the workers: this session
may close right after. A worker that cannot ask anyone takes its defaults and files the
items for the user itself. Tasks that depend on each other cannot be chained without a
coordinator, so hand off only the tasks with no dependencies. List the rest in the
summary as not started.

For each task, run `git fetch origin`, then:

```bash
orca worktree create --repo path:<repo root> --name <slug> --no-parent \
  --base-branch origin/<base> [--reference <JIRA-KEY>] --agent claude --json \
  --prompt "/<command> <sources or full task text> <endpoint phrase> [fix leftovers] unattended

<the context block from the spec in Launch, without the authorization line>"
```

Pass one `--reference` per Jira key the task comes from, so the Orca card links its
ticket. Under a hub, register the repo and replace `--no-parent` with the parent
`orca-fleet.md` gives the handoff's lead or its other tasks. Keep `--agent` and `--prompt`:
a handoff has no worker to start. The prompt carries no
Orca preamble, so it starts with the slash command, which Claude Code expands. Then reply with one line per task: slug, worktree name, and command.

## 2. Launch

Create one Run, then one task per row with its `--deps`. Then start every ready task, up to
the cap. Run `git fetch origin` before each start. Each worker gets a new top-level
worktree named after the slug, cut from `origin/<base>`. A task from Jira or under a hub
gets its worktree as `orca-fleet.md` shows.

Each spec is self-contained, because the worker cannot see this conversation:

```
Invoke the <command> skill with: <sources or full task text> <endpoint phrase> [fix leftovers] [unattended]

Context: <decisions from this conversation that the task depends on, and what the
sibling tasks change, so the worker leaves those alone>
Files: <files it will likely touch>
This coordinator authorizes the run's own pushes, MR or PR with its review requests, thread replies and merge, and Jira steps.
Follow ~/llmfiles/shared/orca-fleet.md: worker mode, and sharing a repo with sibling worktrees.
```

For a task that is not `/fullsend` or `/bugbounty`, also state the endpoint as an
instruction, for example "commit the fixes, then ship to main as orca-fleet.md describes".

## Adding tasks to a live Run

This chat keeps its Run while any task in it has not settled. A later `/fleet`, or a plain
request in this chat to launch more work, adds tasks to that Run. Find it with
`orca orchestration run-current --json`, and do not call `run-create` while it has open tasks.

Plan the new items against the open tasks, grouped as in [Plan](#1-plan). An item in the
region of a running task goes to that worker with `send`, while its Orca card shows stage
2 or lower: the worker adds it as one more source. Past that stage, the item becomes a
task that depends on it. Items in no open task's region form new tasks that run in
parallel, within the cap. Confirm only when the request is ambiguous. Create tasks with
`task-create --run <run_id>`, start the ready ones, and keep the same background wait.
Under a hub, their worktrees go under the Run's existing lead.
A "no supervision" request is a handoff, and stays outside the Run.

## 3. Coordinate

Keep one background `check --wait` running. Each time it returns, process the whole
delivery, acknowledge it, start the tasks that became ready, and start the wait again.
An Orca push that arrives while the wait runs gets no tool call and no reply, as
`orca-fleet.md` explains.

- **question**: answer from this conversation and the repo. A decision only the user
  should make: reply with the default the worker proposed, and add the question to the
  items for the user.
- **escalation**: unblock the worker with Orca, git, glab or Jira actions this session can
  take, for example approving or merging a sibling's MR. An unblock that needs a code change
  or an investigation becomes a new task in the Run: reply to the worker that it waits for
  that task, and tell it when the task settles.
  Otherwise reply that the stage stays blocked, and add it to the items for the user.
- **worker_done**: check the claim, because the dependent tasks build on it:
  - endpoint `main`: the branch is merged: its MR state is `merged`, or, for a local merge
    with no MR, its tip is an ancestor of `origin/<base>`. Ancestry alone misses a squash
    merge;
  - endpoint `prod`: production serves the change;
  - endpoint `mr`: the MR is open, marked ready, and its pipeline is green.
  Collect its `Open:` items. Then remove its worktree if the rule in [Close](#4-close)
  allows it, without waiting for the rest of the Run: Orca has already closed the worker's
  chat, so the worktree would stay in the sidebar with nothing to read in it.
- **Leftovers**: an `Open:` item that is work, not a decision, never starts a task on its
  own, because a worktree per leftover relearns the region each time. Without "fix
  leftovers", it goes to the items for the user. With it, collect them until every task
  has settled, group them as in [Plan](#1-plan), and start one follow-up wave. What that
  wave leaves open goes to the items for the user.
- **A usage limit**: a worker that stops on one sends nothing and stays stopped until told
  to go on, so the `worker-list` check after empty waits finds it. Wait for the reset in a
  background command, restarted at its 2-hour timeout, then `send` it a message to resume
  its run from its ledger. Without a known reset time, send the resume each hour until the
  worker goes on.
- **A failed task**: its dependents stay `pending`. Do not retry it, because `/fullsend`
  has its own fix loops. Report it with the tasks it held back.

An empty wait is a checkpoint. After three empty waits in a row, run `worker-list` and
act on what it reports, following Orca's `references/recovery-and-cleanup.md`.

The Run is done when every task has settled or is held back by a failed task.

## 4. Close

- File the items for the user as `orca-fleet.md` describes.
- Remove a worker's worktree only when its branch is merged, as `worker_done` checks it,
  and has no uncommitted changes: `worker-release` its dispatch, then
  `orca worktree rm --worktree path:<path> --run-hooks`. Without `--run-hooks` Orca skips
  the repo's archive hook, and what the hook frees (ports, containers) stays taken. Keep
  the other worktrees: they are the deliverable or the evidence.
- Send a PushNotification with the one-line summary.

Then report in plain English, one line per task:

```
<objective> - <n>/<total> done, <n> failed, <n> held back
<slug>: <endpoint reached | failed at <stage>: <reason> | held back by <slug>>, <evidence: commit on main, MR url, prod check>
Decide: <items for the user, each with where it was filed, or "nothing">
Kept: <worktrees kept and why, or "nothing">
```
