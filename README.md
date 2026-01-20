# llmfiles

Dotfiles for LLM coding assistants. Centralize your skills, commands, and agent instructions in one place and symlink them to work with Claude Code, VS Code + Copilot, OpenCode, and Antigravity.

## Structure

```
llmfiles/
├── skills/
│   └── <skill-name>/
│       └── SKILL.md
├── commands/
│   └── <command-name>.md
├── shared/
│   └── AGENTS.md
├── CLAUDE.md
└── README.md
```

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

### AGENTS.md (`shared/AGENTS.md`)

Universal instructions for AI assistants. Works across VS Code Copilot, Antigravity, and others.

## Installation

### Claude Code

```bash
# Global instructions (AGENTS.md as your global CLAUDE.md)
ln -sf ~/llmfiles/shared/AGENTS.md ~/.claude/CLAUDE.md

# Skills (symlink individually to preserve existing skills)
mkdir -p ~/.claude/skills
for skill in ~/llmfiles/skills/*/; do
  ln -sf "$skill" ~/.claude/skills/
done

# Commands (symlink individually to preserve existing commands)
mkdir -p ~/.claude/commands
for cmd in ~/llmfiles/commands/*.md; do
  ln -sf "$cmd" ~/.claude/commands/
done
```

### VS Code + GitHub Copilot

```bash
# Per-project
ln -sf ~/llmfiles/shared/AGENTS.md ./AGENTS.md
```

### OpenCode

OpenCode reads `AGENTS.md` from project root.

### Antigravity

```bash
ln -sf ~/llmfiles/shared/AGENTS.md ./AGENTS.md
```

