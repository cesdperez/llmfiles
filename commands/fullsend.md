---
description: Take a task from a Jira ticket, Slack thread, or plain words all the way to a reviewed, browser-verified draft MR with a green pipeline. Say "ship to main" or "ship to prod" to go further.
argument-hint: <jira key|jira url|slack url|task text> [ship to main|ship to prod]
allowed-tools: Agent, Skill, Read, Grep, Glob, Bash, Edit, Write, AskUserQuestion, Monitor
---

**Role:** controller of one end-to-end delivery run. You own the stage order, the ledger,
and the human checkpoints. Delegate the pieces whose conclusion is all you need.

"Full send" means: ask everything up front in one batch, then work without stopping until
the endpoint is reached.

## Arguments

`$ARGUMENTS` holds the task source and, optionally, the endpoint in plain words:

- **Endpoint** (default `mr`): `mr` stops at a draft MR with a green pipeline. "ship to main"
  or "merge" (`main`) also merges once the pipeline is green. "ship to prod" (`prod`) also
  deploys to production and checks it is healthy.
- **Source**: a Jira key or URL (read with `twg-jira`), a Slack thread URL (read it in full),
  a backlog or plan file reference, or free text.

Read `~/llmfiles/local/work.json` for the org values. `platform_directory` and `team_id`
there name the reviewer roster.

## Ledger

Keep the run state in `$(git rev-parse --git-dir)/fullsend-ledger.md` of the primary repo.
That path is per worktree and never committed. Record: source, endpoint, answers from
intake, repos and branches, current stage, review findings left unfixed, QA results, MR
links. Update it at each stage boundary. On start, if a ledger exists, resume from its stage
instead of starting over.

## Progress in Orca

At each stage boundary, publish the stage to this worktree's Orca card. Runs outside Orca
skip it silently:

```bash
command -v orca >/dev/null && orca worktree set --worktree current --comment "<n>/7 <stage>" --workspace-status <status> --json >/dev/null 2>&1 || true
```

Use `--worktree current`, never `active`: `active` is whichever card the user has open.
Status is `in-progress` for stages 1 to 4, `in-review` from stage 5, `completed` at the
handoff. Add `--unread` whenever the run stops for the user. Add `--gitlab-mr <url>` once
the MR exists.

## Stages

### 0. Intake

Read the source fully: the ticket with its links and comments, or the whole Slack thread.
Find the repos involved and the acceptance criteria. Collect every open question
(ambiguous scope, feature flags to create, test accounts, which environment to verify on)
and ask them in one AskUserQuestion call, each with a recommended default. If nothing is
unclear, ask nothing.

After intake, stop for the user only for things only they can do: create a feature
flag, grant a permission, pass 2FA, approve a manual pipeline job outside the endpoint.
Mark the card `--unread` and give one concise instruction.

### 1. Setup

- `git fetch` and branch every involved repo from the latest `origin/main`, using the branch
  naming rule in `glab-cli`. Use the same branch name in every repo.
- Work in the current checkout for the repo you were started in. For each other repo, add a
  sibling worktree `<repo>-<jira-key>` from `origin/main`. Note each path in the ledger,
  because the handoff removes them.
- Jira: assign to the user and move to In Progress.

### 2. Implement

- Commit as you go, granularly, with the commit title format from `glab-cli`.
- Run only the tests that cover the change. Run a full suite only when the repo's
  instructions say it is cheap, or when the change is cross-cutting.
- Delegate to `worker` agents when parts are independent. When the task splits into many
  independent units, or the user asked for a workflow, run them as a Workflow. Never run two
  implementers in the same checkout.
- Keep docs that describe the changed behaviour in sync in the same commits.

### 3. Review

Run `/code-review main...HEAD medium --fix` per repo, then commit the fixes. Run a second
round only if the first one changed code. Stop after two rounds: write any finding still
open to the ledger, and carry it into the MR description if it matters to a reviewer.

### 4. Verify

Prove the acceptance criteria in the running app, not only in tests. Delegate this to a
`worker` with the criteria, the repos, and how to start them.

- Start the local stack the repo's instructions describe. APIs: exercise with curl. UI: use
  `playwright-cli` at desktop (1440x900) and mobile (390x844) sizes, with session name
  `-s=<branch>` so concurrent runs do not share a browser.
- One shared local stack serves every run on this machine. Before starting it, take the
  lock `mkdir ~/.cache/fullsend/qa.lock` (create the parent first). If it exists, wait for
  it with Monitor. Remove the lock when verify ends, also on failure.
- Report Pass or Fail per criterion with one line of evidence, and keep screenshots for
  failures and for the main UI change.
- On a Fail, fix it, then repeat stages 3 and 4 once. A second Fail stops the run: report it.

### 5. MR

Push each branch and open one draft MR per repo with the flags in `glab-cli`, assigned to
the user. On a GitHub remote, open a draft PR with `gh` instead.

- Reviewers: one or two engineers from the `team_id` team in `platform_directory`, ranked
  by commits to that repo in the last 90 days. Use only members with a `gitlab` handle from
  that file. Never add anyone outside it, and never the user.
- Description: follow **Writing MR Text** in `glab-cli`. Link the ticket and the sibling
  MRs. Add one line saying what was verified and where, for example "Verified locally:
  signup and resend flows, desktop and mobile." Write only what is true of the final diff.
  Never cite the ledger, plans, or notes.
- Jira: comment with the MR links and move to In Review. Write it per the `jira-writing`
  skill.

### 6. Green

Watch each MR pipeline with Monitor until it finishes. Fix failures caused by the change
and push. A failure that is not caused by the change (flaky job, infra) gets one retry,
then goes in the report. Stop after three fix attempts per pipeline.

Endpoint `main`: mark the MR ready, merge it once the pipeline is green, and confirm the
main pipeline passes. Endpoint `prod`: then run the deploy jobs through staging and prod,
check health with the tools the repo uses (dashboards, smoke tests), and move Jira to Done.

### 7. Handoff

Clean up: stop the servers you started, remove the sibling worktrees and the lock, delete
any local branch that has no MR. Then report in plain English:

```
<ticket> - <endpoint reached>
MRs: <url> (pipeline green|failing: <job>)
Verified: <criteria passed>/<total>, <environment>
Open: <unfixed review findings, failed criteria, or "nothing">
Try it: <local URL left running on request, or preview URL>
```
