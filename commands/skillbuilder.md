---
description: Build a Claude Code skill for a tech stack, library, or CLI tool
allowed-tools: Read, Grep, Glob, WebFetch, WebSearch, Write
---

# Skill Builder

Build a Claude Code skill for: **$ARGUMENTS**

## What a skill is for

A skill exists to wrangle determinism out of a stochastic system. The goal is **predictability**: the agent taking the same *process* every run, not producing the same *output*. Every decision below is judged against that, not against how clever or complete the skill reads. A `SKILL.md` is domain-specific instructions Claude loads when relevant; its frontmatter `description` decides when.

## Phase 1: Identify skill type

Determine if $ARGUMENTS is:
- **Tech stack/library/language**: framework, runtime, language, or dev tool (e.g. .NET 10, React 19, Go, FastAPI)
- **CLI tool**: command-line tool (e.g. glab, gh, docker, kubectl)

## Phase 2: Research

### For tech stacks/libraries/languages

1. **Official documentation**: docs, migration guides, best practices. Extract coding conventions, recommended patterns, performance tips, common pitfalls, version-specific changes.
2. **GitHub search**: `SKILL.md {tech}`, `CLAUDE.md {tech}`, `AGENTS.md {tech}`, `copilot-instructions.md {tech}`, `.cursorrules {tech}`, `{tech} best practices` in popular repos.
3. **Key information to extract**: project structure, naming conventions, testing patterns, common commands (build/test/lint), dependency management, error handling, security, performance.

### For CLI tools

1. **Official documentation**: docs, man pages, tutorials. Extract command reference, common workflows, auth setup.
2. **GitHub search**: `SKILL.md {cli}`, `CLAUDE.md {cli}`, `.cursorrules {cli}`, `{cli} workflow`, `{cli} automation`, and CI/CD configs (`.github/workflows`, `.gitlab-ci.yml`).
3. **Key information to extract**: core commands and options, auth/config, common workflows (create/list/update/delete), output formats, error and retry patterns, integration with other tools.

## Phase 3: Decide invocation mode

This is the first authoring decision and the current skill set has none like it, so make it explicitly. Two modes, each spending a different cost:

- **Model-invoked** (default for tech/CLI reference skills): keeps its `description` in context every turn, so the agent fires it on its own and other skills can reach it. It costs **context load**. Mechanics: omit `disable-model-invocation`; write a rich, trigger-heavy `description`.
- **User-invoked**: only the user typing its name invokes it, and no other skill can reach it. Zero context load, but it spends **cognitive load** (the user is now the index that must remember it exists). Mechanics: `disable-model-invocation: true`; the `description` becomes a plain one-line human summary, triggers stripped.

Pick model-invocation only when the agent should reach the skill on its own. A skill that is a multi-step *procedure* the user runs deliberately (a pipeline, a generator, a review) is usually user-invoked. A skill that is *ambient knowledge* the agent should apply whenever a topic comes up (a framework's conventions, a CLI's commands) is model-invoked. Tech-stack and CLI skills are almost always the latter.

## Phase 4: Write the description

The `description` does two jobs: state what the skill is, and list the **branches** that should trigger it. Every word is permanent context load, so it earns harder pruning than the body.

- **Front-load the leading word** the skill is built around (the tech name, the CLI command). The description is where it does its invocation work.
- **One trigger per branch.** Synonyms that rename a single branch are duplication ("load testing, performance testing, stress testing" is one branch written three times). Keep only genuinely distinct triggers.
- **Cover the phrasings a user would actually say**, including the bare tool/command name.
- **Cut identity already stated in the body.**

Pattern: `{What it does}. Use when {distinct trigger}, {distinct trigger}, or when the user mentions {names/commands}.`

Examples:
- Tech: `Best practices for .NET 10 development. Use when writing C# code, building ASP.NET APIs, working with Entity Framework, or when the user mentions .NET, dotnet, or C#.`
- CLI: `Automate GitLab workflows with glab. Use when creating merge requests, managing issues or pipelines, or when the user mentions glab or GitLab from the terminal.`

## Phase 5: Structure the content (information hierarchy)

Content is either **steps** (ordered actions) or **reference** (facts consulted on demand); a skill can be all steps, all reference, or both. Place each piece on the hierarchy by how immediately the agent needs it:

1. **In-skill step / reference** in `SKILL.md`: what the agent does or consults directly.
2. **External reference** in a sibling file (`references/*.md`), reached by a **context pointer**, loaded only when the pointer fires.

Create the skill at `~/llmfiles/skills/{tech-or-cli-name}/SKILL.md`. Starting structure (drop sections that do not earn their place):

```markdown
---
name: {lowercase-hyphenated-name}
description: {see Phase 4}
# add `disable-model-invocation: true` only if Phase 3 chose user-invoked
---

# {Skill Title}

## Overview
{1-2 sentences on what this skill enables}

## Key Patterns
{The most important conventions - specific, not generic}

## Commands
{Essential commands with real, working examples}

## Common Tasks
{Step-by-step for 2-3 frequent workflows}

## Pitfalls to Avoid
{Top 3-5 real mistakes, each with what to do instead}

## Quick Reference
{Cheat sheet of the most-used items}
```

**Progressive disclosure**: when `SKILL.md` grows past what stays legible (target under ~500 lines, but shorter is better), move reference material out to `references/*.md` and point at it. The cleanest split test is by **branch**: inline what every use needs, push behind a pointer what only some uses reach. A pointer's *wording*, not its target, decides how reliably the agent follows it, so name what the file holds ("full flag reference in [references/flags.md]").

**Leading words**: a leading word is a compact concept already in the model's pretraining that the agent thinks with while running the skill (*tight* loop, *red* test, *tracer bullet*). One well-chosen word can retire a phrase restated across the skill. Hunt for restatements a single word collapses.

## Phase 6: Prune

- **Single source of truth**: each fact lives in exactly one place, so a change is a one-place edit.
- **Relevance**: every line still bears on what the skill does.
- **No-op test**, sentence by sentence: does this sentence change behaviour versus the model's default? "Be thorough" when the agent is already thorough-ish is a no-op; delete it or replace it with a stronger leading word. Delete whole failing sentences rather than trimming words.
- **Prompt the positive**: steer by stating the target behaviour, not by banning the wrong one (naming the elephant makes it more available). Keep a prohibition only as a hard guardrail, and pair it with what to do instead.
- **No em dashes** in any content you write (repo style): use a comma, colon, or rewrite.

## Phase 7: Validate

Read the skill back and check it against the failure modes. Each maps to a fix:

- **Premature completion**: a step ends before it is genuinely done. Sharpen its completion criterion into something checkable ("every command verified against the installed version", not "commands look right").
- **Duplication**: the same meaning in two places. Collapse to one.
- **Sprawl**: too long even when every line is live. Disclose reference behind pointers; split by branch.
- **No-op**: a line the model already obeys. Cut it.
- **Sediment**: stale content left because removing feels risky. Prune it.

Then verify: description triggers on realistic queries; commands and code are real and version-correct; nothing generic that applies everywhere.

### Usefulness assessment

Rate how much the skill adds beyond your existing knowledge, and report the score:

| Score | Meaning | Action |
|-------|---------|--------|
| 0-2 | Low value: you already know this well (common languages, mainstream frameworks at stable versions) | Consider skipping, or narrow to version-specific/opinionated content only |
| 3-5 | Moderate: adds specific patterns/commands you might forget | Keep it focused on the non-obvious parts |
| 6-8 | High: niche tool, specific CLI, or domain you do not inherently know | Good candidate |
| 9-10 | Essential: proprietary tool, internal conventions, or tech newer than your training cutoff | Must-have |

Increases value: niche/less-popular tools (glab > git), CLIs with many subcommands, **recent versions of known tech** (new APIs, deprecations, breaking changes), opinionated conventions, team-specific patterns, tools released after your cutoff.
Decreases value: mainstream tech at stable versions, APIs unchanged for years, generic best practices, anything easily inferred from context.

When a specific version is requested and you are unsure it is within your training data, assume it is valuable (6+) and focus on version-specific content. If the score is 0-2, ask the user whether to proceed or narrow scope (e.g. "React 19 Server Components" over "React").

## Note on granularity

If building this skill would push the user's set of user-invoked skills past what they can remember, that piled-up cognitive load is cured by a **router skill**: one user-invoked skill that names the others and when to reach for each (the `twg` family in this repo is an example). Flag this to the user rather than silently adding to the pile.

## Output

Create the skill file and report:
- Path created: `~/llmfiles/skills/{name}/SKILL.md`
- Invocation mode chosen and why (Phase 3)
- Trigger phrases covered
- Key patterns included
- **Usefulness score: X/10** with justification
- Any limitations or areas needing manual review
