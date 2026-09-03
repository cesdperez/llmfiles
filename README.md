# llmfiles

This repo is to LLM coding assistants what [dotfiles](https://wiki.archlinux.org/title/Dotfiles) are to your shell, a single place to manage your configuration, symlinked wherever tools expect it. The name comes from there.

Manages skills, commands, agents, and agent instructions in one place to work with Claude Code, Copilot, OpenCode, and Antigravity.

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
│   ├── AGENTS.md
│   ├── glab-mr-context.md
│   └── review-lenses.md
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
session's own model and effort never leak into delegated work. Two tiers: the session runs the
most capable model, every agent here runs `opus`. Effort is the dial within that tier.

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

### AGENTS.md (`shared/AGENTS.md`)

Universal instructions for AI assistants. Works across VS Code Copilot, Antigravity, and others.

### Shared protocols (`shared/<name>.md`)

Content reused by several commands, extracted so it lives in one place. Commands load it with an explicit read, for example `Read ~/llmfiles/shared/review-lenses.md`.

Deliberately not skills: a skill is auto-listed with its description and can activate in unrelated sessions, whereas a shared protocol should load only when a command asks for it. Use a skill when the knowledge should surface on its own (`glab-cli`), a shared protocol when it should not (`review-lenses`).

Current protocols:
- `review-lenses.md`, the lens catalog and parallel fan-out contract, used by `/glablensedreview`, `/locallensedreview`.
- `glab-mr-context.md`, GitLab MR setup (batched fetch, read-only MR-head worktree, diff anchor map, prior-pass marker check) plus the goodhabitz lens bindings, used by `/glablensedreview` and the per-MR agents of `/glabsummary`.

## Installation

### Claude Code

```bash
# Global instructions
ln -sf ~/llmfiles/shared/AGENTS.md ~/.claude/CLAUDE.md
```

**Option A: Symlink entire directories (recommended)**

Easier to maintain: new files automatically appear, deletions propagate cleanly.

```bash
# Skills, commands, and agents (entire directories)
ln -sf ~/llmfiles/skills ~/.claude/skills
ln -sf ~/llmfiles/commands ~/.claude/commands
ln -sf ~/llmfiles/agents ~/.claude/agents
```

Anything spawned without a named agent follows `CLAUDE_CODE_SUBAGENT_MODEL`. Set it in the
`env` block of `~/.claude/settings.json` so the two-tier split also covers ad hoc delegation:

```json
"env": { "CLAUDE_CODE_SUBAGENT_MODEL": "opus" }
```

**Option B: Symlink individual files**

Use this if you have existing skills/commands you want to preserve alongside llmfiles.

```bash
# Skills (symlink individually)
mkdir -p ~/.claude/skills
for skill in ~/llmfiles/skills/*/; do
  ln -sf "$skill" ~/.claude/skills/
done

# Commands (symlink individually)
mkdir -p ~/.claude/commands
for cmd in ~/llmfiles/commands/*.md; do
  ln -sf "$cmd" ~/.claude/commands/
done
```

### OpenCode

OpenCode stores configuration in `~/.config/opencode`.

```bash
# Global instructions
ln -sf ~/llmfiles/shared/AGENTS.md ~/.config/opencode/AGENTS.md
```

**Option A: Symlink entire directories (recommended)**

```bash
# Skills and commands
ln -sf ~/llmfiles/skills ~/.config/opencode/skills
ln -sf ~/llmfiles/commands ~/.config/opencode/commands
```

**Option B: Symlink individual files**

Use this if you have existing skills/commands you want to preserve alongside llmfiles.

```bash
# Skills (symlink individually)
mkdir -p ~/.config/opencode/skills
for skill in ~/llmfiles/skills/*/; do
  ln -sf "$skill" ~/.config/opencode/skills/
done

# Commands (symlink individually)
mkdir -p ~/.config/opencode/commands
for cmd in ~/llmfiles/commands/*.md; do
  ln -sf "$cmd" ~/.config/opencode/commands/
done
```

### Antigravity

Antigravity stores configuration in `~/.gemini` and uses `GEMINI.md` for instructions.

```bash
# Global instructions
ln -sf ~/llmfiles/shared/AGENTS.md ~/.gemini/GEMINI.md
```

**Option A: Symlink entire directories (recommended)**

```bash
# Skills and commands
ln -sf ~/llmfiles/skills ~/.gemini/antigravity/global_skills
ln -sf ~/llmfiles/commands ~/.gemini/antigravity/workflows
```

**Option B: Symlink individual files**

Use this if you have existing skills/commands you want to preserve alongside llmfiles.

```bash
# Skills (symlink individually)
mkdir -p ~/.gemini/antigravity/global_skills
for skill in ~/llmfiles/skills/*/; do
  ln -sf "$skill" ~/.gemini/antigravity/global_skills/
done

# Commands (symlink individually)
mkdir -p ~/.gemini/antigravity/workflows
for cmd in ~/llmfiles/commands/*.md; do
  ln -sf "$cmd" ~/.gemini/antigravity/workflows/
done
```

