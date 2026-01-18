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
├── install.sh
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

```markdown
# Agent Instructions

## Code Style
- Keep functions small and focused
- Write self-documenting code

## Patterns
- Prefer composition over inheritance
```

## Installation

### Claude Code

```bash
ln -sf ~/.llmfiles/skills ~/.claude/skills
ln -sf ~/.llmfiles/commands ~/.claude/commands
ln -sf ~/.llmfiles/shared/AGENTS.md ~/.claude/CLAUDE.md
```

### VS Code + GitHub Copilot

```bash
# Per-project
ln -sf ~/.llmfiles/shared/AGENTS.md ./AGENTS.md
```

### OpenCode

OpenCode reads `AGENTS.md` from project root.

### Antigravity

```bash
ln -sf ~/.llmfiles/shared/AGENTS.md ./AGENTS.md
```

