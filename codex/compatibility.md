# Running Claude workflows in Codex

These adaptations take precedence over Claude-specific instructions in `commands/`, `agents/`, `skills/`, and `shared/`. Keep the source workflow's scope, scoring, output, and write policy unless its Codex entry file explicitly replaces them.

## Loading and arguments

- Read referenced Markdown files directly. In command and agent files, execute the body after YAML frontmatter; the frontmatter configures Claude, not Codex.
- Treat `$ARGUMENTS` as the user's text following the invoked skill. Preserve the source defaults when no arguments were given. Parse arguments before constructing shell commands and quote each value separately.
- `/name` references mean the matching Codex skill in `~/llmfiles/codex/skills/<name>/SKILL.md`. Load that entry file and its adaptations when a workflow dispatches another command. A skill reference is not a shell command.
- `Read`, `Grep`, `Glob`, `Bash`, `WebSearch`, and `WebFetch` refer to the equivalent available Codex tools. Load skill files directly in place of Claude's `Skill` tool. Source `allowed-tools` fields do not configure Codex permissions.
- Use a temporary directory for a source workflow's `<scratchpad>`.

## Delegation

- Use installed Codex agent roles from `~/llmfiles/codex/agents/`, mapping Claude's `Explore` to `explorer`. Supply each role's mandate, inputs, output contract, and write policy.
- Carry this file and the calling skill's adaptations into every delegated brief, including nested dispatches. They must apply when a child reads a shared protocol or `glab-cli` itself.
- Spawn independent work up to the available concurrency limit, then wait, collect results, and close finished threads. A source workflow's agent caps limit the total work, not the number of simultaneously available Codex slots.
- When custom roles are unavailable but delegation is supported, read the matching TOML and use its instructions, model, and effort in the supported spawn mechanism. Otherwise run the mandates sequentially and disclose that limitation. Never drop a lens because no slot is available.
- Inspection agents make no edits, commits, pushes, or external writes. The `verify` lens may run the affected flow and existing tests. These are behavioral restrictions; custom agents inherit the parent session's permissions.
- Treat Claude's `background` and `maxTurns` as source metadata. Use Codex's available agent lifecycle and wait for required results before reporting completion.

## GitLab and notifications

- When the shared `glab-cli` skill asks for a Claude signature, sign as `_Comment made by Codex <model> (<effort>)_`. Use the current session's model and effort when known; omit unknown fields. Read neither from Claude settings.
- Preserve the caller's posting policy, thresholds, inline anchors, markers, idempotency checks, and follow-up behavior. Installing or discovering a skill does not invoke its posting workflow.
- Replace `PushNotification` with an available notification tool only if it supports the requested notification. If none exists, finish with the terminal report and mention that the notification was unavailable.
- For repository conventions, read applicable `AGENTS.md` guidance as well as the `CLAUDE.md` files explicitly used by the review protocol. Report a conflicting rule rather than silently applying the other assistant's configuration.
