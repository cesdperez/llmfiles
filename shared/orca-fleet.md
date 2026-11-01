# Orca fleet

How a coordinator session runs other agent sessions through Orca orchestration, and how a
run behaves as one of those workers. Used by `/fleet` (coordinator) and by `/fullsend` and
`/bugbounty` (worker mode).

Orca's own `orchestration` skill is the authority on the protocol. Load a reference from it
(`orca skills get orchestration --reference references/<file>.md`) only when a command
fails or a worker's state is unclear. The commands below are the ones that work.

## Behaviour that is not in Orca's docs

- A chat session can be the coordinator. Orca also pushes "You have N orchestration
  messages" into the coordinator chat, but only while a turn is running. Keep a
  background `check --wait` so an idle coordinator is woken too.
- Workers start in the user's default mode, usually a chat. `send --to dispatch:<id>`
  reaches them, but `orca terminal send` does not.
- Orca puts its worker preamble in front of the spec, so a spec that starts with
  `/fullsend` is not expanded as a slash command. Write "Invoke the fullsend skill with:
  <args>" and the worker calls it through the Skill tool.
- The preamble tells workers to post nothing to Slack, GitHub or other channels. A spec
  that needs pushes, MRs, PRs or Jira updates must say so.
- A chat is bound to one Run at a time. A second `run-create` rebinds it without warning,
  and `run-use --id <run_id>` binds it back. Pass `--run` explicitly on `task-create` and
  `check`.
- A task whose dependencies have already settled is `ready` as soon as it is created.
- `worker-start` on a task with `--worktree new-top-level --base-branch origin/<base>`
  cuts the worktree at start time. Run `git fetch origin` just before, so a dependent task
  builds on what its dependencies shipped.

## Coordinator commands

```bash
orca orchestration run-create --objective "<objective>" --json
orca orchestration task-create --task-title "<title>" --spec "<spec>" [--deps '["task_x"]'] --json
orca orchestration task-list --ready --brief --json
orca orchestration worker-start --task <task_id> --worktree new-top-level \
  --repo path:<repo root> --name <slug> --base-branch origin/<base> --agent claude --json
orca orchestration check --run <run_id> --wait --types worker_done,escalation,question \
  --timeout-ms 3600000 --json
orca orchestration reply --id <message_id> --body "<answer>" --json
orca orchestration send --to dispatch:<dispatch_id> --subject "<subject>" --body "<text>" --json
orca orchestration check --run <run_id> --ack <delivery_id> --json
orca orchestration worker-release --dispatch <dispatch_id> --json
orca orchestration worker-list --run <run_id> --json
```

- Start the wait with Bash `run_in_background` and a 2-hour timeout: its exit re-invokes
  the session.
- A delivery replays until it is acknowledged. Process every message in it before the
  `--ack`.
- A dependent task moves from `pending` to `ready` when its dependencies settle. Nothing
  starts it automatically.
- Release each worker after its `worker_done`. Otherwise its terminal stays open.
- `worker-start` takes `--model` and `--effort`. Pass them only when the user names a
  model. Without them, the worker uses the user's agent default.

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
