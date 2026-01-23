---
description: Build a Claude Code skill for a tech stack, library, or CLI tool
allowed-tools: Read, Grep, Glob, WebFetch, WebSearch, Write
---

# Skill Builder

Build a Claude Code skill for: **$ARGUMENTS**

## What's a Skill?

A skill is a `SKILL.md` file containing domain-specific instructions that Claude Code automatically loads when relevant. Each skill has a `description` in its frontmatter with trigger phrases—when users mention those phrases, Claude Code injects the skill's instructions into context.

## Phase 1: Identify Skill Type

Determine if $ARGUMENTS is:
- **Tech stack/library/language**: Framework, runtime, language, or development tool (e.g., .NET 10, React 19, Go, FastAPI)
- **CLI tool**: Command-line interface tool (e.g., glab, gh, docker, kubectl)

## Phase 2: Research

### For Tech Stacks/Libraries/Languages

1. **Official Documentation**
   - Search for official docs, migration guides, and best practices
   - Look for: coding conventions, recommended patterns, performance tips, common pitfalls
   - Find version-specific changes if a version is specified

2. **GitHub Search**
   - Search: `SKILL.md {tech}` for existing Claude skills
   - Search: `CLAUDE.md {tech}` for project instructions using this tech
   - Search: `AGENTS.md {tech}` or `copilot-instructions.md {tech}` for AI assistant configs
   - Search: `.cursorrules {tech}` or `cursor rules {tech}` for Cursor AI configs
   - Search: `{tech} best practices` in popular repos

3. **Key Information to Extract**
   - Project structure conventions
   - Naming conventions (files, functions, variables)
   - Testing patterns and frameworks
   - Common commands (build, test, lint)
   - Dependency management
   - Error handling patterns
   - Security best practices
   - Performance optimization tips

### For CLI Tools

1. **Official Documentation**
   - Search for official docs, man pages, and tutorials
   - Look for: command reference, common workflows, authentication setup

2. **GitHub Search**
   - Search: `SKILL.md {cli}` for existing Claude skills
   - Search: `CLAUDE.md {cli}` or `.cursorrules {cli}` for AI assistant configs using this CLI
   - Search: `{cli} workflow` or `{cli} automation` in repos
   - Look at how the CLI is used in CI/CD configs (.github/workflows, .gitlab-ci.yml)

3. **Key Information to Extract**
   - Core commands and their options
   - Authentication/configuration patterns
   - Common workflows (create, list, update, delete operations)
   - Output formats and parsing
   - Error handling and retry patterns
   - Integration with other tools

## Phase 3: Create the Skill

Create the skill at: `~/llmfiles/skills/{tech-or-cli-name}/SKILL.md`

### SKILL.md Structure

```markdown
---
name: {lowercase-hyphenated-name}
description: {what it does} + {when to trigger}. Use when {specific trigger phrases users would say}.
---

# {Skill Title}

## Overview
{1-2 sentences on what this skill enables}

## Key Patterns
{Most important conventions and patterns - be specific, not generic}

## Commands
{Essential commands with examples - for tech stacks: build/test/lint; for CLIs: core operations}

## Common Tasks
{Step-by-step for 2-3 frequent workflows}

## Pitfalls to Avoid
{Top 3-5 mistakes and how to prevent them}

## Quick Reference
{Cheat sheet of most-used items}
```

### Quality Checklist

Before finalizing, verify:

- [ ] **Description is specific**: Includes concrete trigger terms users would naturally say
- [ ] **Under 500 lines**: If longer, split into supporting files with progressive disclosure
- [ ] **Actionable content**: Every section helps the agent do something, not just explain
- [ ] **No generic advice**: Everything is specific to this tech/CLI
- [ ] **Examples are real**: Commands and code snippets actually work
- [ ] **Trigger coverage**: Description covers common phrasings (e.g., for Docker: "container", "dockerfile", "docker compose", "build image")

### Description Formula

Good descriptions follow this pattern:
```
{What it does}. {When to use it}. Use when {trigger phrase 1}, {trigger phrase 2}, or {trigger phrase 3}.
```

Examples:
- Tech: `Best practices for .NET 10 development. Use when writing C# code, creating ASP.NET APIs, working with Entity Framework, or when the user mentions .NET, dotnet, or C#.`
- CLI: `Automate GitLab workflows with glab CLI. Use when creating merge requests, managing issues, or interacting with GitLab from the terminal.`

## Phase 4: Validation

After creating the skill:

1. **Read it back** and verify it follows the structure
2. **Check the description** triggers on realistic user queries
3. **Verify commands** are accurate for the current version
4. **Ensure conciseness** - remove anything that doesn't directly help the agent
5. **Evaluate usefulness** - Rate the skill's effectiveness from 0-10:

### Usefulness Assessment

Score the skill based on how much it enhances your existing knowledge:

| Score | Meaning | Action |
|-------|---------|--------|
| 0-2 | **Low value** - You already know this well (common languages, mainstream frameworks) | Consider not creating the skill, or focus only on version-specific/opinionated content |
| 3-5 | **Moderate value** - Adds some specific patterns, commands, or conventions you might forget | Keep it focused on the non-obvious parts |
| 6-8 | **High value** - Niche tool, specific CLI, or domain with patterns you don't inherently know | Good candidate for a skill |
| 9-10 | **Essential** - Proprietary tool, internal conventions, or rapidly changing tech you can't know | Must-have skill |

**Factors that increase usefulness:**
- Niche or less popular tools (glab > git)
- CLIs with many subcommands and flags
- **New versions of known tech** - Even mainstream tech (e.g., .NET 10, React 19, Python 3.13) benefits from skills when the version is recent or after your training cutoff. Focus on: new APIs, deprecated patterns, migration guides, breaking changes.
- Opinionated conventions not universally agreed upon
- Company/team-specific patterns
- Tools released after your training cutoff

**Factors that decrease usefulness:**
- Mainstream languages at stable versions you know well
- Stable APIs that haven't changed in years
- Generic best practices that apply everywhere
- Information easily inferred from context

**Important:** When a specific version is requested, check if that version is within your training data. If uncertain or if it's a recent release, assume the skill is valuable (score 6+) and focus on version-specific content.

Report the score with a brief justification. If score is 0-2, ask the user if they still want the skill or if they'd prefer to focus on something more specific (e.g., "React 19 Server Components" instead of "React").

## Output

Create the skill file and report:
- Path created: `~/llmfiles/skills/{name}/SKILL.md`
- Trigger phrases covered
- Key patterns included
- **Usefulness score: X/10** with justification
- Any limitations or areas needing manual review
