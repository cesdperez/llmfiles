# Running Claude workflows in opencode

These adaptations take precedence over the Claude-specific instructions in `~/llmfiles/commands/`, `agents/`, `skills/` and `shared/`. Keep each workflow's scope, scoring, output and write policy.

## Tools

- `Agent` is the `subagent` tool, and `SendMessage` is the same tool with the child's `sessionID`. To run agents in parallel, call `subagent` several times in one turn and wait for every report before the next step. Background mode suits only work that can run while you continue elsewhere.
- Claude's `Explore` is the `explore` agent. Every other agent name is the same.
- `Bash` is `shell`. `Read`, `Edit`, `Write`, `Glob`, `Grep`, `WebFetch`, `WebSearch` and `Skill` are their lower-case opencode tools. A command's `allowed-tools`, `background` and `maxTurns` configure Claude only.
- A fork has no equivalent. Brief a `worker` with the context it needs instead.
- `Workflow` has no equivalent. Run the same fan-out with parallel subagents.
- `Artifact` has no equivalent. Write the page to a file in the scratch directory and give its path.
- `PushNotification` has no equivalent. End with the terminal report.
- A workflow's `<scratchpad>` is a temporary directory you create.

## Agents

- `worker`, `reviewer`, `reviewer-fast` and `general-purpose` run on Claude. `worker-fast`, `gitlab`, `explore`, `codex-worker` and `codex-reviewer` run on ChatGPT models.
- `codex-worker` and `codex-reviewer` run their task on the GPT model themselves. There is no `codex exec` step, and they have network access.
- A subagent cannot start its own subagents.
- When a subagent fails on a usage or rate limit, rerun the same brief on the other provider: `worker` and `general-purpose` with `codex-worker`, `reviewer` and `reviewer-fast` with `codex-reviewer`, and the ChatGPT agents with `worker`, or `reviewer` for the read-only ones.

## GitLab

When the `glab-cli` skill asks for a Claude signature, sign as `_Comment made by opencode <model> (<effort>)_`, with your model ID and its variant. Omit what you do not know.
