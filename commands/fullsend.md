---
description: Take a task from a Jira ticket, Slack thread, or plain words all the way to a reviewed, browser-verified draft MR with a green pipeline (work repos) or a local branch (personal repos). Say "open a PR", "ship to main" or "ship to prod" to go further.
argument-hint: <jira key|jira url|slack url|task text>... [open a PR|ship to main|ship to prod] [fix leftovers] [unattended] [in a new worktree]
allowed-tools: Agent, SendMessage, Skill, Workflow, Read, Grep, Glob, Bash, Edit, Write, AskUserQuestion, Monitor, TaskStop, ToolSearch
---

**Role:** controller of one end-to-end delivery run. You own the stage order, the ledger,
the Orca card, the questions, dispatching agents and checking their reports. Agents read the
code, images and logs, and make the changes: this session's context has to last every
stage, so it holds conclusions, not file contents. This overrides the global rule to keep a
fix in the session that investigated it.

"Full send" means: ask everything up front in one batch, then work unattended until the
endpoint is reached or a stage is blocked. Put status notes in the same message as the next
tool call. Waiting on an agent, a pipeline or the lock is not a stop: the stage ends when
what it waits on has finished. The waits for the lock and for pipelines happen in this
session. An agent's prompt cache lasts 5 minutes, so an agent that waits longer pays to
rewrite its whole context: send an agent in when its work can start at once. A skill this
run calls returns control to the run: its final report is a status note, so the next
stage's tool call goes in the same message.

## Arguments

`$ARGUMENTS` holds the task source and, optionally, the endpoint:

- **Endpoint** (default per repo kind, below): `branch` stops at reviewed, verified
  commits on a local branch. `mr` stops at a draft MR with a green pipeline. The phrase
  "open a PR" or "open an MR" sets `mr`. The phrase "ship to main" sets `main`, which also
  merges once the pipeline is green. The phrase "ship to prod" sets `prod`, which also
  deploys to production and checks it is healthy. Only these exact phrases count: a task
  text can say "merge" without asking for one.
- **Source**: a Jira key or URL (call the Skill tool with "twg-jira" to read it), a Slack
  thread URL (read it in full),
  a backlog or plan file reference, or free text. More than one source is still one run:
  see [Several sources](#several-sources).
- **"fix leftovers"**: an adjacent problem this run finds may be fixed in the run. Stage 2
  says which ones.
- **"unattended"**: nobody will answer questions. See
  [Worker mode and unattended runs](#worker-mode-and-unattended-runs).
- **Another worktree**: any wording that asks for a new, different, separate or another
  worktree, such as "in a new worktree", hands the run off. Unlike the endpoint phrases,
  this needs no exact phrase. See [Handoff to a new worktree](#handoff-to-a-new-worktree).

Read `~/llmfiles/local/work.json` for the org values. `platform_directory` and `team_id`
there name the reviewer roster.

## Handoff to a new worktree

Hand the run off when the arguments ask for another worktree, or when this session runs in
Orca at a hub, as `~/llmfiles/shared/meta-hub.md` defines it. A run that works from this
chat in another worktree leaves that worktree's card with no chat, so the new card gets
its own session instead. Ask no intake questions here: the new session asks them.

At a hub, the worktree is for the repo the task changes most, registered first as
`orca-fleet.md` describes. Run `git fetch origin` in it, then:

```bash
orca worktree create --repo path:<repo root> --name <slug> --parent-worktree current \
  --base-branch origin/<base> [--reference <JIRA-KEY>] --agent claude --surface chat --json \
  --prompt "/fullsend <task source> <endpoint phrase> [unattended]

<everything this conversation agreed about the task, and the other repos it touches>"
```

The new session sees only the prompt, so it carries every decision made here. Reply with
the worktree name and end the run.

## Repo kind

Classify each involved repo by its `origin` URL. A repo is **work** when the URL path
starts with `gitlab_group/` from `work.json`. Every other repo is **personal**, including
one with no remote.

- Work repos default to endpoint `mr` and use every Jira and reviewer step.
- Personal repos default to endpoint `branch`: the user checks the branch and merges it.
  Skip Jira and reviewers. Open a PR only when the endpoint is `mr` from an explicit
  phrase. "ship to main" without "open a PR" merges the branch into its base locally, then
  pushes the base if it tracks a remote.

## Several sources

Several sources are one run, because a run pays for its review, verify, MR and pipeline
whatever its size. Read every source at intake and ask their questions in one batch.

- One branch and one MR per repo. Each commit delivers one source and carries that
  source's key.
- Wherever a stage names the Jira key in a branch, worktree or file name, use the first
  ticket's.
- Verify proves the acceptance criteria of every source, and the MR description links
  every ticket.
- Every Jira step runs for each ticket.
- The ledger lists every source, and matches a later run that names the same ones.
- In worker mode, an item the coordinator sends before stage 3 joins the run as one more
  source.

## Worker mode and unattended runs

When the prompt starts with Orca's dispatched-worker preamble, or holds "unattended", follow
the worker mode section of `~/llmfiles/shared/orca-fleet.md`. Its rules for questions, the
items only the user can do, and the final report take precedence over the rules below.
When `git worktree list` shows other worktrees of this repo, also follow its section on
sharing a repo with sibling worktrees.

## Ledger

The home repo is the one the session started in. Keep the run state in
`$(git rev-parse --git-dir)/fullsend-ledger.md` of the home repo. Inside a linked worktree
`--git-dir` resolves to that worktree's own directory, so concurrent runs never share a
ledger, and it is never committed.

Record: source, its acceptance criteria, endpoint, intake questions with their answers,
repos with branch and base, current stage, blocked stages and why, review findings left
unfixed, QA results, MR links.
Update it at each stage boundary.

On start, if a ledger exists for the same source, resume from its stage. A ledger for
another source belongs to an unfinished run: ask whether to resume it or replace it.

When the home checkout is a hub, as `~/llmfiles/shared/meta-hub.md` defines it, read that
file too. Several runs share a hub, so wherever this file names `fullsend-ledger.md` or
`fullsend-qa/`, use `fullsend-ledger-<jira-key>.md` and `fullsend-qa-<jira-key>/`, and
leave other sources' ledgers alone.

## Blocked stages

A stage is blocked when it cannot proceed for a reason the run cannot fix: no remote, a
denied push, a repo without CI, a Fail in the verify rerun. Record the reason in the ledger,
skip the stages that depend on it, and go to the handoff. Never discard work to get past a
block.

## Progress in Orca

At each stage boundary, publish the stage to this worktree's Orca card:

```bash
orca worktree set --worktree current --comment "<n>/7 <stage>" --workspace-status <status> --json
```

Use `--worktree current`, never `active`: `active` is whichever card the user has open.
At stage 0, a `selector_not_found` error means the run is outside Orca: skip every later
Orca call. Any other error goes in the ledger, and the run continues.

The board columns are the workspace statuses. At stage 0, read the configured ones from Orca's live state.
`orca-data.json` is a stale export, so do not read it:

```bash
sqlite3 -readonly "$HOME/Library/Application Support/orca/profiles/local-default/profile-state.db" \
  "select payload from profile_state_documents where domain = 'ui'" |
  python3 -I -c 'import json,sys; [print(s["id"], s["label"], sep="\t") for s in json.load(sys.stdin)["workspaceStatuses"]]'
```

If columns labelled Implement, Review, Verify, MR and Green all exist (any case), use one
column per stage: Implement for stages 0 to 2, then the column named after stages 3 to 6,
and `completed` when the endpoint is reached. Stages 3 and 4 run together, so publish
`3/7 review and verify` in Review, then `4/7 verify` in Verify once the review has
reported. The fix round and its rerun stay in Verify. Pass the id, not the label: ids of
columns made in the app need not match their label. Otherwise use the defaults:
`in-progress` for stages 0 to 4, `in-review` from stage 5, `completed` at the endpoint.
Set only ids that are configured. A blocked stage keeps its status, with the comment
`blocked: <reason>`. Add `--unread` whenever the run stops for the user. Add
`--gitlab-mr <url>` once the MR exists.

## The machine lock

Every run on this machine shares its CPU and memory. Browser suites running in several
worktrees at once starve each other, and tests that pass alone then fail. One lock,
`~/.cache/fullsend/qa.lock`, makes the heavy commands take turns.

- Heavy is: a browser or end-to-end suite, a full test suite or the repo's whole verify
  script, a repeated run that measures a flaky test, and the local stack of stage 4. Tests
  scoped to the change need no lock.
- Take it only through `~/llmfiles/scripts/qa-lock.sh`, and give this section to every
  agent that runs tests. Hand-rolled `mkdir`/`rm` once let a run whose take failed run its
  suite anyway and then delete another run's lock.
- One command: `~/llmfiles/scripts/qa-lock.sh run <branch> -- <command>`. It waits for the
  lock, keeps it fresh, releases it also on failure, and exits with the command's code. A
  wait can outlast the Bash timeout, so run it in the background when the lock is held.
- An agent runs heavy commands only under a token this session took for it, so no agent
  waits for the lock. An agent that needs one mid-task reports the command back.
- This session takes the lock for an agent: run `~/llmfiles/scripts/qa-lock.sh take
  <branch>` in the background with a 2-hour timeout, started again when the timeout stops
  it, and send the agent its brief with the token it prints. The agent runs its heavy
  commands directly, never through `run`, which would wait on its own lock. It runs
  `~/llmfiles/scripts/qa-lock.sh touch "$token"` at least every 30 minutes and
  `~/llmfiles/scripts/qa-lock.sh release "$token"` when its heavy work ends.
- The token is the holder, because release removes the lock only for its own token. So
  this session also releases it when the agent reports or is stopped, which does nothing
  when the agent already did. Before releasing for a stopped agent, stop what it started,
  such as the stage 4 stack.
- A lock whose owner was not touched for over an hour is from a crashed run; the script
  clears it while waiting.
- Count a flaky test's failures only under the lock. A failure under another run's load
  says nothing about the test.

## Stages

### 0. Intake

Read the source fully: the ticket with its links and comments, or the whole Slack thread.
Send the codebase exploration to a `worker` (or `Explore` when only locations are needed): it
returns the repos involved, the files to change, the approach, and the open questions it
found. That worker owns the working set, so it implements in stage 2. Collect every open
question (ambiguous scope, feature flags to create, test accounts, which environment to verify on,
whether to leave a server running to try it) and ask them in one batch, each with a
recommended default. AskUserQuestion holds four questions per call, so use as few calls as
fit. If nothing is unclear, ask nothing. In worker mode, ask through the coordinator. If asking
is not possible (headless, delegated or unattended run), take the defaults and record them
in the ledger.

Write each source's acceptance criteria to the ledger: the ticket's own, or ones derived
from the task text when it has none. Stages 3 and 4 read them from there.

Without a Jira key and with a work repo involved, ask whether to create a ticket (call the
Skill tool with "jira-writing" to write it). With no ticket, skip every Jira step, and use a short task slug
wherever a Jira key is named below.

After intake, stop for the user only for things only they can do: create a feature flag,
grant a permission, pass 2FA, approve a manual pipeline job outside the endpoint. Mark the
card `--unread` and give one concise instruction.

### 1. Setup

- In every involved repo, `git fetch origin` and resolve the base: the remote default
  branch (`git symbolic-ref --short refs/remotes/origin/HEAD`). With no remote, use the
  local default branch. For endpoint `mr` or later, record in the ledger that the MR stage
  will be blocked.
- Branch from the base, using the branch naming rule in `glab-cli` (call the Skill tool
  with "glab-cli"; the later stages use it too). Use the same branch
  name in every repo. Record the base per repo in the ledger: stage 3 diffs against it.
- Work in the current checkout for the home repo. For each other repo, add a sibling
  worktree `<repo>-<jira-key>` from the base and record its path. Inside Orca, register the
  repo with `python3 ~/llmfiles/scripts/orca-add-repo.py <repo root>`, then create the
  worktree with `orca worktree create --repo path:<repo root> --name <repo>-<jira-key>
  --parent-worktree current --base-branch origin/<base> --reference <jira-key> --json`,
  so its card links the ticket. `worktree set` cannot add the link later. Without a ticket,
  leave out `--reference`: Orca reads its value as a Jira key.
- At a hub outside Orca, leave the home checkout on its branch: every involved repo gets a worktree.
  The first takes `--parent-worktree current`, and the others take
  `--parent-worktree path:<first worktree>`, so the run folds under one card.
- Jira: assign to the user and move to In Progress.

### 2. Implement

- Deliver the acceptance criteria at the scope asked. Adjacent problems you notice go in
  the ledger and the handoff's Open line, not in the diff.
- With "fix leftovers", fix an adjacent problem in this run when it sits in a file the run
  already changes and needs no new decision. It gets its own commit, made before stage 3
  so the review covers it. Every other one still goes in the Open line.
- Commit as you go, granularly, with the commit title format from `glab-cli`.
- Run only the tests that cover the change. Run a full suite only when the repo's
  instructions say it is cheap, or when the change is cross-cutting, and under
  [the machine lock](#the-machine-lock). Without a test suite, the verify stage carries
  the proof.
- The intake `worker` implements, continued with SendMessage, and later fixes from review
  and verify go to it too. Publish `2/7 implement` in the message that sends it the
  implement brief, or the card shows intake for the whole implementation. Only a change of
  one or two files whose exact edit was known at intake stays in this session.
- Independent parts get a `worker` each, with `isolation: "worktree"`. A part whose brief is
  complete and needs no network or follow-up goes to `codex-worker` instead, with the same
  isolation. Its brief names no repo path, or Codex edits that checkout instead of the
  isolated one. When the task splits into many independent units, or the user asked for a
  workflow, run them as a Workflow.
- **Stall check.** A background agent appends each step to the output file named when it
  launches, a symlink that `find -L` follows. Beside each agent the run waits on, run this
  in the background with a 2-hour timeout. It ends at least 15 minutes after it starts, once
  the agent has gone 15 minutes without a step:

  ```bash
  t0=$(date +%s)
  until [ $(($(date +%s) - t0)) -ge 900 ] && [ -n "$(find -L <output file> -mmin +15)" ]; do sleep 60; done
  ```

  Then look at what the agent runs (`ps`) and whether what it waits on can still arrive.
  When it cannot, such as an environment that is down or scaled to zero, stop the agent
  with TaskStop and block the stage with that reason. Otherwise, or when the timeout stops
  the check, start it again. Stop the check when the agent reports.
- Keep docs in sync in the same commits: docs that describe the changed behaviour, and
  any trap this run hit that the repo's agent docs did not warn about, written in the file
  that owns that topic. Both follow `~/llmfiles/shared/agent-docs-bar.md`.

### 3. Review

Stages 3 and 4 start in the same message, on the same commit: neither changes the code, so
neither waits for the other. That message takes the machine lock for the stage 4 verify
worker, which launches as soon as the take returns, and calls the Skill tool with
"locallensedreview" and args `--base <recorded base> --intent <ledger path> --compact`,
once per repo, from inside that repo's checkout. Leave out `--autofix`, and do not rerun it after the fixes. The intent is
the ledger's sources, their acceptance criteria and the intake answers.

Write the findings at its fix bar to the ledger for the fix round in stage 4. Write every
other finding there too, and carry it into the MR description if it matters to a
reviewer. The printed report ends the skill, not the run: the message that holds it also
moves the card to stage 4.

### 4. Verify

Prove the acceptance criteria in the running app, not only in tests. Delegate this to a
`worker` with the criteria, the checkouts, how to start them, and
[the machine lock](#the-machine-lock).

- One shared local stack serves every run on this machine. The worker gets the lock's
  token in its brief and releases it after it stops the stack.
- Start the stack from this run's checkouts, so it serves this branch and not another
  run's code. Run Compose from the checkout and label every `docker run` container
  `--label llmfiles.worktree=<checkout path>`: `/orcacleanup` finds leftovers of a crashed
  run by the checkout they name.
- APIs: exercise with curl. UI: call the Skill tool with "playwright-cli", then check at
  desktop (1440x900) and mobile (390x844) sizes. Run it from `$(git rev-parse --git-dir)/fullsend-qa/` of the home repo,
  because it writes logs into its working directory. Use the branch name with `/` replaced
  by `-` as the session name: playwright-cli treats `/` as a path.
- Report Pass or Fail per criterion with one line of evidence. Save screenshots of failures
  and of the main UI change in `fullsend-qa/`.
- **Fix round.** Once review and verify have both reported, send the review findings at the
  fix bar and every verify Fail to the implementing worker in one SendMessage, to fix and
  commit: the controller holds conclusions, not file contents. With neither, go to stage 5.
- **Rerun.** After the fixes, this session takes the lock again, and the verify worker
  reruns only what they could change: the tests scoped to the changed files, every
  criterion that failed, and every criterion whose code path a fix touched. Review fixes
  get no other verify, so a criterion a fix might reach is rerun. A Fail in the rerun
  blocks the run.
- Run the [stall check](#2-implement) on the verify worker.

### 5. MR

Skip this stage and stage 6 at endpoint `branch`.

Push each branch and open one draft MR per repo (`glab mr create --draft` with the flags in
`glab-cli`), assigned to the user. On a GitHub remote, open a draft PR with `gh` instead.

- Reviewers: one or two engineers from the `team_id` team in `platform_directory`, taken
  only from members with a `gitlab` handle. Rank them by MRs they merged in that repo in the
  last 90 days (`glab mr list --merged --author <handle>`). Never add anyone outside the
  roster, and never the user.
- Description: call the Skill tool with "plainenglish", then follow **Writing MR Text** in
  `glab-cli`. Link the
  ticket and the sibling MRs. Add one line saying what was verified and where, for example
  "Verified locally: signup and resend flows, desktop and mobile." Write only what is true
  of the final diff. Never cite the ledger, plans, or notes.
- Jira: comment with the MR links and move to In Review. Write it per `jira-writing`
  (call the Skill tool with "jira-writing" if it is not loaded).

### 6. Green

Watch each MR pipeline with Monitor until it finishes. A Monitor that expires first has not
seen the end, so start it again. The implementing worker fixes failures caused by the
change, pushes, and reports without waiting on the pipeline. A failure that is not caused
by the change (flaky job, infra) gets one retry, then goes in the report. Stop after three
fix attempts per pipeline.

Endpoint `main`: mark the MR ready, merge it once the pipeline is green, and confirm the
main pipeline passes. With MRs in several repos, merge in dependency order (provider before
consumer) and wait for each main pipeline before the next merge. Endpoint `prod`: then run
the deploy jobs through staging and prod, check health with the tools the repo uses
(dashboards, smoke tests), and move Jira to Done.

### 7. Handoff

Clean up only what this run made and what is safe to lose:

- Stop the servers you started, unless intake asked to leave one running.
- Remove a sibling worktree only when its branch has no uncommitted or unpushed changes.
- Delete a local branch only if this run created it and it is merged. At endpoint
  `branch`, keep it: it is the deliverable.
- Delete the ledger and `fullsend-qa/` once the endpoint is reached. A blocked run keeps
  them, so it can resume.

Then report in plain English:

```
<ticket or slug> - <endpoint reached | blocked at <stage>: <reason>>
MRs: <url> (pipeline green|failing: <job>), or branches: <repo>:<branch> (<n> commits)
Verified: <criteria passed>/<total>, <environment>
Open: <blocked stages, unfixed findings, failed criteria, kept branches and worktrees, or "nothing">
Try it: <URL of the server left running, the preview URL, or the command to start it>
```
