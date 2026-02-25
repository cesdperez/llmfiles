---
description: Generate an OpenCode skill for a CLI tool with local detection, man pages, docs, and user context
allowed-tools: Read, Grep, Glob, WebFetch, WebSearch, Bash, Write, question
---

# CLI Skill Builder

Generate a skill for: **$ARGUMENTS**

## Phase 1: Local Detection

Run these commands to detect the CLI and its version:

```bash
which $CLI_NAME
$CLI_NAME --version 2>&1 || $CLI_NAME version 2>&1
$CLI_NAME --help 2>&1 | head -100
```

Capture:
- Install path
- Version number
- Available subcommands (from --help)

## Phase 2: Man Page & Docs

Fetch:
1. `man $CLI_NAME` output (if available)
2. Official docs - search for "$CLI_NAME CLI official documentation"
3. Quick start guide if available

Extract:
- Core commands and their purposes
- Common flags/options
- Authentication/config setup
- Output formats

## Phase 3: User Context (Interactive)

Ask the user:

1. **"What projects or contexts do you use this CLI with?"**
   - Example: "I use kubectl with 3 clusters: prod-us, staging-us, dev-us"

2. **"Any aliases or shortcuts you use?"**
   - Example: "alias k=kubectl", "k9s for interactive"

3. **"What are the most common operations you do?"**
   - Example: "deployments, pods, logs, port-forward"

4. **"Anything the AI should know about your setup?"**
   - Example: "we use kubeconfig files per cluster in ~/.kube/"

5. **"Any pitfalls or gotchas you've encountered?"**

## Phase 4: Create Skill

Create at: `~/llmfiles/skills/{cli-name}/SKILL.md`

Structure:

```markdown
---
name: {cli-name}
description: {what it does}. Use when {trigger phrases}.
---

# {CLI Name} Skill

## Local Setup
- Version: {version}
- Install path: {path}
- Aliases: {user aliases}

## Your Context
{user's projects/clusters/environments}

## Commands
{core commands with examples}

## Common Tasks
{user's frequent operations}

## Your Gotchas
{pitfalls user mentioned}

## Quick Reference
{cheat sheet}
```

## Phase 5: Validate

- Read back the skill
- Verify it loads correctly
- Test trigger phrases work

Report path created and usefulness score.
