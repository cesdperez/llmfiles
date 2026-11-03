# Orca fleet

How a coordinator session runs other agent sessions through Orca orchestration, and how a
run behaves as one of those workers. Used by `/fleet` (coordinator) and by `/fullsend` and
`/bugbounty` (worker mode).

Orca's own `orchestration` skill is the authority on the protocol. Load a reference from it
(`orca skills get orchestration --reference references/<file>.md`) only when a command
fails or a worker's state is unclear. The commands below are the ones that work.

## Behaviour that is not in Orca's docs

- A chat session can be the coordinator. Orca pushes "You have N orchestration
  messages" into the coordinator chat for every message, idle or not, including each
  worker's heartbeat every 5 minutes. The push does not say the type and cannot be turned
  off. Keep a background `check --wait` running, because a push is best-effort.
- Workers start in the user's default mode, usually a chat. `send --to dispatch:<id>`
  reaches them, but `orca terminal send` does not.
- Orca puts its worker preamble in front of the spec, so a spec that starts with
  `/fullsend` is not expanded as a slash command. Write "Invoke the fullsend skill with:
  <args>" and the worker calls it through the Skill tool. That works only for a command
  without `disable-model-invocation`: the harness refuses the Skill call otherwise, so
  every command a worker runs (`/fullsend`, `/bugbounty`) stays model-invocable.
- The preamble tells workers to post nothing to Slack, GitHub or other channels. A spec
  that needs pushes, MRs, PRs or Jira updates must say so.
- A chat is bound to one Run at a time. A second `run-create` rebinds it without warning,
  and `run-use --id <run_id>` binds it back. Pass `--run` explicitly on `task-create` and
  `check`.
- A task whose dependencies have already settled is `ready` as soon as it is created.
- `worker-start` on a task with `--worktree new-top-level --base-branch origin/<base>`
  cuts the worktree at start time. Run `git fetch origin` just before, so a dependent task
  builds on what its dependencies shipped.
- Only `orca worktree create --reference <jira key or url>` links a worktree to its Jira
  issue on the Orca card. `worker-start` and `worktree set` take no `--reference`, and a link
  cannot be added later. `worker-start` sets no parent worktree either. So a task that needs
  a Jira link or a parent gets its worktree from `worktree create`, without `--agent`, and
  its worker from `worker-start --worktree path:<path>`.

## Coordinator commands

```bash
orca orchestration run-create --objective "<objective>" --json
orca orchestration task-create --task-title "<title>" --spec "<spec>" [--deps '["task_x"]'] --json
orca orchestration task-list --ready --brief --json
orca orchestration worker-start --task <task_id> --worktree new-top-level \
  --repo path:<repo root> --name <slug> --base-branch origin/<base> --agent claude --json
# A task with a Jira source: the worktree first, with one --reference per key, then the worker.
orca worktree create --repo path:<repo root> --name <slug> --no-parent \
  --base-branch origin/<base> --reference <JIRA-KEY> --json
orca orchestration worker-start --task <task_id> --worktree path:<worktree path> \
  --agent claude --json
orca orchestration check --run <run_id> --wait --types worker_done,escalation,question \
  --timeout-ms 3600000 --json 2>/dev/null \
  | jq 'if .result.messages then .result.messages |= map(select(.type != "heartbeat")) else . end'
orca orchestration reply --id <message_id> --body "<answer>" --json
orca orchestration send --to dispatch:<dispatch_id> --subject "<subject>" --body "<text>" --json
orca orchestration check --run <run_id> --ack <delivery_id> --json
orca orchestration worker-release --dispatch <dispatch_id> --json
orca orchestration worker-list --run <run_id> --json
```

- Start the wait with Bash `run_in_background` and a 2-hour timeout: its exit re-invokes
  the session. Its stderr carries a keepalive line every 15 seconds, and the `jq` drops the
  heartbeats saved up in the delivery. The ack still covers them.
- While the wait runs, answer a push with no tool call and no text. The wait wakes the
  session for every message that needs action, and the heartbeats are acked with that
  delivery. Without a running wait, start one.
- A delivery replays until it is acknowledged. Process every message in it before the
  `--ack`.
- A dependent task moves from `pending` to `ready` when its dependencies settle. Nothing
  starts it automatically.
- Keep a worker's chat open after its `worker_done`: it is the user's record of what ran.
  `worker-release` closes it, so release a worker only when its worktree is removed.
- `worker-start` takes `--model` and `--effort`. Pass them only when the user names a
  model. Without them, the worker uses the user's agent default.

## Repos under a hub

These rules apply when the session runs in a hub, as `~/llmfiles/shared/meta-hub.md`
defines it. In a single repo, worktrees stay as above.

- Register a repo before its first worktree with
  `python3 ~/llmfiles/scripts/orca-add-repo.py <repo path>`, never a bare `orca repo add`.
  It files the repo under the hub's project group. A `warning` in its output does not stop
  the run.
- Nest each batch of work under the hub's card, so each one folds on its own. A batch is
  a Run, or the tasks of one "no supervision" handoff:
  - its first worktree, the lead: `--parent-worktree path:<hub root>`;
  - every other worktree of the batch, in any repo: `--parent-worktree path:<lead path>`.
- Remove the lead last. While any child of the lead is kept, keep the lead.

## Worker mode

A run is in worker mode when its prompt starts with Orca's dispatched-worker preamble.
The preamble gives the exact `ask`, escalation, `check` and `worker_done` commands. Use
them as written. Then:

- **Questions.** Send intake questions in one `ask`, each with a recommended default.
  Do not use AskUserQuestion: the coordinator cannot see or answer it. The coordinator
  answers, or replies "take the default", and records that item for the user.
- **Things only the user can do** (a feature flag, a permission, 2FA): send an
  escalation, then do the stages that do not depend on it.
- **Follow-ups.** Run the preamble's `check` at each stage boundary and act on what
  arrives.
- **Publishing.** The coordinator authorizes the run's own pushes, MR or PR, and Jira
  steps. Post nothing else.
- **Finish.** Send `worker_done` once, after the handoff. Use `--outcome succeeded` when
  the endpoint was reached, and `--outcome failed` when the run is blocked. The body is the
  handoff report. Put every item that needs the user in its `Open:` line (`Decide:` in
  `/bugbounty`), because the coordinator files them from there.

The phrase "unattended" without a preamble means nobody will answer. Take the recommended
defaults and record them in the ledger. A stage that needs the user is blocked. Its items
go in the report's `Open:` line and are filed as in [Items for the user](#items-for-the-user).

## Sharing a repo with sibling worktrees

- **Shipping to the base.** Rebase onto `origin/<base>` right before shipping. Rerun the
  tests the rebase touched, then `git push origin HEAD:<base>`. A rejected push means a
  sibling shipped first: fetch, rebase, and try again. Never force-push the base.
- **Ports.** A server or test runner on a fixed port may reuse a process another
  worktree started (Playwright's `reuseExistingServer` does). Before a suite that
  starts a server, check who is listening on its port (`lsof -nP -iTCP:<port>
  -sTCP:LISTEN`) and use a free port when the config allows. Stop only processes this
  checkout started.

## Items for the user

An item that needs the user goes back to where the work came from, so personal and work
repos use the same rule:

- **GitHub issue source, or a personal repo with a GitHub remote:** one issue per item,
  with `gh issue create`. Search the open issues first, so a rerun does not file the same
  item twice.
- **Jira source:** a comment on that ticket, written per the `jira-writing` skill.
- **Anything else** (a work repo with no ticket, a Slack thread, free text): the final
  report only.

Each item states the problem, what was decided or tried, and what the user needs to
decide. Title it so it is clear without the body.
