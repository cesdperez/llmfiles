# llmfiles

This repo is to LLM coding assistants what [dotfiles](https://wiki.archlinux.org/title/Dotfiles) are to your shell, a single place to manage your configuration, symlinked wherever tools expect it. The name comes from there.

Manages Claude Code skills, commands, agents, and global instructions in one place.

## Structure

```
llmfiles/
├── agents/
│   └── <agent-name>.md
├── skills/
│   └── <skill-name>/
│       └── SKILL.md
├── commands/
│   └── <command-name>.md
├── scripts/
│   └── <script-name>.py
├── shared/
│   ├── CLAUDE.md
│   ├── glab-mr-context.md
│   └── review-lenses.md
├── statusline/
│   └── statusline-command.sh
├── CLAUDE.md
├── README.md
└── TODO.md
```

`TODO.md` holds work that is scoped but not built yet, so a decision made once does not have to be re-derived later.

## File Formats

### Skills (`skills/<name>/SKILL.md`)

Reusable knowledge modules that AI assistants auto-activate based on context.

```markdown
---
name: skill-name
description: When to use this skill (max 1024 chars)
---

Instructions and knowledge go here.
```

### Commands (`commands/<name>.md`)

Slash commands triggered with `/command-name`.

```markdown
---
description: Brief description
allowed-tools: Read, Grep, Glob
---

Prompt content here. Use $ARGUMENTS for user input.
```

### Agents (`agents/<name>.md`)

Named subagents the orchestrator delegates to. Each pins a model alias and an effort so the
session's own model and effort never leak into delegated work. The session and every agent
whose output needs judgment run `opus`. Agents whose tasks have known steps (`Explore`,
`gitlab`, `worker-fast`) run `sonnet`, where speed matters more than the quality gap on hard
reasoning. Effort is the dial within each model, and it is re-tuned on every release: a level
name does not mean the same amount of thinking across models (Sonnet `medium` is not Opus
`medium`), so pick a level from an effort sweep on your own tasks, not from its name.

```markdown
---
name: agent-name
description: When the orchestrator should pick this agent
model: opus
effort: high
disallowedTools: Edit, Write, NotebookEdit
---

Standing instructions for the agent.
```

Model aliases (`opus`, `fable`, `sonnet`) resolve to the newest model of that family, so the
files need no edit when a new version ships. Files named after a built-in agent (`Explore`,
`general-purpose`) replace it.

### Scripts (`scripts/<name>.py`)

Deterministic data gathering a command would otherwise re-derive from scratch every run.
Emit JSON on stdout so the command can reason over the result instead of over shell quoting.

Commands call them by absolute path (`python3 ~/llmfiles/scripts/<name>.py`), so no symlink
is needed.

- `daily-work-recap.py`, one day of git commits, merge requests, GitLab review activity and
  matching Claude Code transcripts, used by `/dailyworkrecap`.
- `glab-review-queue.py`, assigned GitLab merge requests with approval state, diffs,
  pipelines, and unresolved threads, used by `/glabsummary`.

### Status line (`statusline/statusline-command.sh`)

Claude Code status line: path, git branch, model and effort, context window usage. It reads
the session JSON on stdin and needs `jq`.

### Global instructions (`shared/CLAUDE.md`)

User-level instructions for every Claude Code session, linked to `~/.claude/CLAUDE.md`.

### Shared protocols (`shared/<name>.md`)

Content reused by several commands, extracted so it lives in one place. Commands load it with an explicit read, for example `Read ~/llmfiles/shared/review-lenses.md`.

Deliberately not skills: a skill is auto-listed with its description and can activate in unrelated sessions, whereas a shared protocol should load only when a command asks for it. Use a skill when the knowledge should surface on its own (`glab-cli`), a shared protocol when it should not (`review-lenses`).

Current protocols:
- `review-lenses.md`, the lens catalog and parallel fan-out contract, used by `/glablensedreview`, `/locallensedreview`.
- `glab-mr-context.md`, GitLab MR setup (batched fetch, read-only MR-head worktree, diff anchor map, prior-pass marker check) plus the acme lens bindings, used by `/glablensedreview` and the per-MR agents of `/glabsummary`.

## Installation

```bash
# Global instructions
ln -sf ~/llmfiles/shared/CLAUDE.md ~/.claude/CLAUDE.md
```

Commands and agents are whole-directory symlinks. Skills are linked one by one, because
Claude Code writes its own synced Anthropic skills into `~/.claude/skills/synced/`, and a
directory symlink would land those inside this repo.

```bash
ln -sf ~/llmfiles/commands ~/.claude/commands
ln -sf ~/llmfiles/agents ~/.claude/agents

mkdir -p ~/.claude/skills
for skill in ~/llmfiles/skills/*/; do
  ln -sf "${skill%/}" ~/.claude/skills/
done
```

Re-run the skills loop after adding a skill here.

The status line is a file symlink, referenced from `~/.claude/settings.json`:

```bash
ln -sf ~/llmfiles/statusline/statusline-command.sh ~/.claude/statusline-command.sh
```

```json
"statusLine": { "type": "command", "command": "bash ~/.claude/statusline-command.sh" }
```

Anything spawned without a named agent follows `CLAUDE_CODE_SUBAGENT_MODEL`. Set it in the
`env` block of `~/.claude/settings.json` so ad hoc delegation, whose task shape is unknown, also runs on Opus:

```json
"env": { "CLAUDE_CODE_SUBAGENT_MODEL": "opus" }
```
