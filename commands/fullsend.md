---
description: Take a task from a Jira ticket, Slack thread, or plain words all the way to a reviewed, browser-verified draft MR with a green pipeline. Say "ship to main" or "ship to prod" to go further.
argument-hint: <jira key|jira url|slack url|task text> [ship to main|ship to prod]
allowed-tools: Agent, SendMessage, Skill, Workflow, Read, Grep, Glob, Bash, Edit, Write, AskUserQuestion, Monitor, ToolSearch
---

**Role:** controller of one end-to-end delivery run. You own the stage order, the ledger,
and the human checkpoints. Delegate the pieces whose conclusion is all you need.

"Full send" means: ask everything up front in one batch, then work without stopping until
the endpoint is reached or a stage is blocked.

## Arguments

`$ARGUMENTS` holds the task source and, optionally, the endpoint:

- **Endpoint** (default `mr`): `mr` stops at a draft MR with a green pipeline. The phrase
  "ship to main" sets `main`, which also merges once the pipeline is green. The phrase
  "ship to prod" sets `prod`, which also deploys to production and checks it is healthy.
  Only these exact phrases count: a task text can say "merge" without asking for one.
- **Source**: a Jira key or URL (read with `twg-jira`), a Slack thread URL (read it in full),
  a backlog or plan file reference, or free text.

Read `~/llmfiles/local/work.json` for the org values. `platform_directory` and `team_id`
there name the reviewer roster.

## Ledger

The home repo is the one the session started in. Keep the run state in
`$(git rev-parse --git-dir)/fullsend-ledger.md` of the home repo. Inside a linked worktree
`--git-dir` resolves to that worktree's own directory, so concurrent runs never share a
ledger, and it is never committed.

Record: source, endpoint, intake questions with their answers, repos with branch and base,
current stage, blocked stages and why, review findings left unfixed, QA results, MR links.
Update it at each stage boundary.

On start, if a ledger exists for the same source, resume from its stage. A ledger for
another source belongs to an unfinished run: ask whether to resume it or replace it.

## Blocked stages

A stage is blocked when it cannot proceed for a reason the run cannot fix: no remote, a
denied push, a repo without CI, a second verify failure. Record the reason in the ledger,
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
and `completed` when the endpoint is reached. Pass the id, not the label: ids of columns
made in the app need not match their label. Otherwise use the defaults: `in-progress` for
stages 0 to 4, `in-review` from stage 5, `completed` at the endpoint. Set only ids that are
configured. A blocked stage keeps its status, with the comment
`blocked: <reason>`. Add `--unread` whenever the run stops for the user. Add
`--gitlab-mr <url>` once the MR exists.

## Stages

### 0. Intake

Read the source fully: the ticket with its links and comments, or the whole Slack thread.
Find the repos involved and the acceptance criteria. Collect every open question
(ambiguous scope, feature flags to create, test accounts, which environment to verify on,
whether to leave a server running to try it) and ask them in one batch, each with a
recommended default. AskUserQuestion holds four questions per call, so use as few calls as
fit. If nothing is unclear, ask nothing. If asking is not possible (headless or delegated
run), take the defaults and record them in the ledger.

Without a Jira key, ask whether to create a ticket (written per `jira-writing`). With no
ticket, skip every Jira step, and use a short task slug wherever a Jira key is named below.

After intake, stop for the user only for things only they can do: create a feature flag,
grant a permission, pass 2FA, approve a manual pipeline job outside the endpoint. Mark the
card `--unread` and give one concise instruction.

### 1. Setup

- In every involved repo, `git fetch origin` and resolve the base: the remote default
  branch (`git symbolic-ref --short refs/remotes/origin/HEAD`). With no remote, use the
  local default branch and record in the ledger that the MR stage will be blocked.
- Branch from the base, using the branch naming rule in `glab-cli`. Use the same branch
  name in every repo. Record the base per repo in the ledger: stage 3 diffs against it.
- Work in the current checkout for the home repo. For each other repo, add a sibling
  worktree `<repo>-<jira-key>` from the base and record its path.
- Jira: assign to the user and move to In Progress.

### 2. Implement

- Commit as you go, granularly, with the commit title format from `glab-cli`.
- Run only the tests that cover the change. Run a full suite only when the repo's
  instructions say it is cheap, or when the change is cross-cutting. Without a test suite,
  the verify stage carries the proof.
- Small changes stay in this session. Delegate to `worker` agents when parts are
  independent. When the task splits into many independent units, or the user asked for a
  workflow, run them as a Workflow. Never run two implementers in the same checkout.
- Keep docs that describe the changed behaviour in sync in the same commits.

### 3. Review

The `/code-review` skill always reviews the session's starting directory, whatever path
you are in. So:

- Home repo, when the session started inside it: run `/code-review <base>...HEAD medium --fix`.
- Every other repo, or when the session started elsewhere: spawn a fresh `reviewer` per
  repo with its path and `<base>...HEAD`. Ask it for the same review at medium threshold:
  correctness bugs first, then reuse and simplification, high-confidence findings only.
  Apply its findings yourself.

Commit the fixes. Run a second round with a fresh reviewer, only if the first one changed
code. Stop after two rounds: write any finding still open to the ledger, and carry it into
the MR description if it matters to a reviewer.

### 4. Verify

Prove the acceptance criteria in the running app, not only in tests. Delegate this to a
`worker` with the criteria, the checkouts, how to start them, and the lock rule below.

- One shared local stack serves every run on this machine. The worker takes the lock
  before starting it: `mkdir -p ~/.cache/fullsend && mkdir ~/.cache/fullsend/qa.lock`, then
  writes the branch name into `qa.lock/owner`. If the lock exists, wait for it with Monitor.
  A lock older than one hour is from a crashed run: remove it and take it. The worker
  removes its own lock when verify ends, also on failure. Nothing else touches the lock.
- Start the stack from this run's checkouts, so it serves this branch and not another
  run's code.
- APIs: exercise with curl. UI: use `playwright-cli` at desktop (1440x900) and mobile
  (390x844) sizes. Run it from `$(git rev-parse --git-dir)/fullsend-qa/` of the home repo,
  because it writes logs into its working directory. Use the branch name with `/` replaced
  by `-` as the session name: playwright-cli treats `/` as a path.
- Report Pass or Fail per criterion with one line of evidence. Save screenshots of failures
  and of the main UI change in `fullsend-qa/`.
- On a Fail, fix it, then repeat stages 3 and 4 once. A second Fail blocks the run.

### 5. MR

Push each branch and open one draft MR per repo (`glab mr create --draft` with the flags in
`glab-cli`), assigned to the user. On a GitHub remote, open a draft PR with `gh` instead.

- Reviewers: one or two engineers from the `team_id` team in `platform_directory`, taken
  only from members with a `gitlab` handle. Rank them by MRs they merged in that repo in the
  last 90 days (`glab mr list --merged --author <handle>`). Never add anyone outside the
  roster, and never the user.
- Description: load `plainenglish`, then follow **Writing MR Text** in `glab-cli`. Link the
  ticket and the sibling MRs. Add one line saying what was verified and where, for example
  "Verified locally: signup and resend flows, desktop and mobile." Write only what is true
  of the final diff. Never cite the ledger, plans, or notes.
- Jira: comment with the MR links and move to In Review. Write it per `jira-writing`.

### 6. Green

Watch each MR pipeline with Monitor until it finishes. Fix failures caused by the change
and push. A failure that is not caused by the change (flaky job, infra) gets one retry,
then goes in the report. Stop after three fix attempts per pipeline.

Endpoint `main`: mark the MR ready, merge it once the pipeline is green, and confirm the
main pipeline passes. With MRs in several repos, merge in dependency order (provider before
consumer) and wait for each main pipeline before the next merge. Endpoint `prod`: then run
the deploy jobs through staging and prod, check health with the tools the repo uses
(dashboards, smoke tests), and move Jira to Done.

### 7. Handoff

Clean up only what this run made and what is safe to lose:

- Stop the servers you started, unless intake asked to leave one running.
- Remove a sibling worktree only when its branch has no uncommitted or unpushed changes.
- Delete a local branch only if this run created it and it is merged.
- Delete the ledger and `fullsend-qa/` once the endpoint is reached. A blocked run keeps
  them, so it can resume.

Then report in plain English:

```
<ticket or slug> - <endpoint reached | blocked at <stage>: <reason>>
MRs: <url> (pipeline green|failing: <job>), or none
Verified: <criteria passed>/<total>, <environment>
Open: <blocked stages, unfixed findings, failed criteria, kept branches and worktrees, or "nothing">
Try it: <URL of the server left running, the preview URL, or the command to start it>
```
