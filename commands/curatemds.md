---
description: Curate the agent-facing .md files in a repo (CLAUDE.md, AGENTS.md, rules, skills, commands, agents, and the docs they route to) to the Opus 5.5 bar, so agents load less and hit fewer wrong turns. Quick inline pass by default; --deep adds claims checked against the code, Anthropic's prompt audit, additions, and an adversarial review of the diff.
argument-hint: [scope or boundary, e.g. "only docs/" or "stop at group level"] [--deep] [--apply]
disable-model-invocation: true
---

# /curatemds

Read `~/llmfiles/shared/agent-docs-bar.md`. It is the bar for every step below.

**Goal:** an agent working in this repo loads less, rereads less, and hits fewer traps. `$ARGUMENTS` narrows the scope or sets a boundary.

Propose first and wait for approval. With `--apply`, go straight from the proposal to applying it.

Leave out model and effort pinning (that is `/whichmodels`) and the user's setup outside this repo. A nested repo with its own git root is outside the scope unless the boundary says otherwise.

## Quick (default)

A short pass in this session, without subagents.

1. **Inventory:** every `CLAUDE.md` and `AGENTS.md` inside the scope, `.claude/` rules, skills, commands, and agents, and every doc those files route an agent to, such as `docs/*.md` and the README. Note per file its line count and whether it loads every session or on demand.
2. **Audit** against the bar:
   - lines that fail the deletion test, or that the model can infer;
   - the same fact in two files, and files that contradict each other;
   - instructions that misfire on Opus 5.5;
   - always-loaded material that belongs in an on-demand file;
   - paths, scripts, and commands named that no longer exist. Check them with `ls`, `grep`, and the package scripts. Running the commands belongs to `--deep`.
3. **Propose:** the table below, then stop unless `--apply` was given or the user approves.
4. **Apply** in this session.

## Deep (`--deep`)

Runs the quick steps with this added:

- **Audit:** for a large set, spawn `reviewer` agents in one message, one per disjoint file set. Besides the quick checks, each returns:
  - claims that are false against today's code, with the code that proves it;
  - gaps an agent would hit, such as an undocumented trap or a command that fails when run.

  Alongside them, or alone for a small set, spawn one `reviewer` that calls the Skill tool with "claude-api" and args `prompt-audit <repo root or scoped path>`, and returns its findings. That audit carries Anthropic's current model-specific checks, so it stays right after a model release when the bar has not caught up. Where it and the bar disagree, follow the audit. If the skill is unavailable, continue with the bar and say so in the output.
- **Additions:** a skill, a script, a rule, or a `settings.json` allowlist. Each one must remove repeated work or a failure the audit found. The proposal lists them with that failure, then the rejected ideas with one line each.
- **Apply:** for a large set, spawn `worker` agents on disjoint file sets in one message. Hand each its rows from the table, the bar, and the evidence behind each row.
- **Adversarial review:** spawn one `reviewer` with the old and new files. It reports every command, ID, path, guardrail, and step that was lost without a reason, and every kept or added claim that is false against the code. Fix what it confirms.

## Proposal

| File | Change | Why | Value 1-10 |
|---|---|---|---|

Below the table, list any bugs found outside the docs. Report them, and fix them only when asked.

## Output

- What changed per file: cuts, moves, fixes, and additions.
- Lines before and after, for all files and for the files loaded every session.
- In quick mode, one line naming what `--deep` would add for this repo, when it would add anything.

Commit only when asked.
