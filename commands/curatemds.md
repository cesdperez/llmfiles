---
description: Curate a repo's agent-facing .md files (CLAUDE.md, AGENTS.md, rules, skills, commands, agents, and the docs they route to) so agents load less and hit fewer wrong turns. Use when the user asks for /curatemds, or to curate, tidy or DRY agent docs. Proposes first. "autofix" applies, "deep" adds reviewers that check claims against the code, and "commit" or "ship to main" go further.
argument-hint: '[a path | this branch | a boundary, e.g. "stop at group level"] [autofix] [deep] [commit|ship to main] [unattended]'
---

# /curatemds

Read `~/llmfiles/shared/agent-docs-bar.md`. It is the bar for every step below.

**Goal:** an agent working in this repo loads less, rereads less, and hits fewer traps.

## Arguments

Read `$ARGUMENTS` as plain words, in any order:

- **A scope**: a path, "this branch", or a boundary. See [Scope](#scope).
- **"autofix"**, "autoapply", "fix all" or `--apply`: apply without waiting for approval. Without it, propose and stop.
- **"deep"** or `--deep`: add the [Deep](#deep) steps. Run them only when asked, because the reviewers cost several hundred thousand tokens.
- **"commit"**, "push", "ship to main" or "open a PR": see [Shipping](#shipping). Without one, leave the edits uncommitted.
- **"unattended"**: nobody will answer, so it implies autofix.
- **Any other text** steers the pass: a topic to look at first, or a fact the docs should state. Put each such fact in the doc that owns its topic, as the state of things today.

## Scope

Take the first that applies:

1. The scope the arguments name.
2. The work of this session or branch, when the arguments say "this branch" or the run follows work done in this session. That is the agent docs it wrote or changed, plus the docs its code changes made false or left without a mention.
3. The whole repo.

For 2, name the files in one line before the audit, so a wrong guess costs one message.

A file outside the repo is in scope only when the arguments name it or this session wrote it. That keeps agent memory and the user's global instructions out. A nested repo with its own git root is out unless the boundary says otherwise.

## Quick (default)

One pass in this session, without subagents.

1. **Inventory:** every `CLAUDE.md` and `AGENTS.md` in the scope, `.claude/` rules, skills, commands, and agents, and every doc those files route an agent to, such as `docs/*.md` and the README. Note per file its line count and whether it loads every session or on demand. These are working notes: the report carries only the totals.
2. **Audit** against the bar:
   - lines that fail the deletion test, or that the model can infer;
   - the same fact in two files, and files that contradict each other;
   - instructions that misfire on Opus 5.5;
   - always-loaded material that belongs in an on-demand file;
   - paths, scripts, and commands named that no longer exist. Check them with `ls`, `grep`, and the package scripts. Run a documented command when it is fast and changes nothing. The rest belongs to deep.
3. **Propose:** the [table](#proposal). Stop here without autofix.
4. **Apply** in this session, following [Apply](#apply).

## Deep

Runs the quick steps with this added:

- **Audit:** spawn `reviewer` agents in one message, one per disjoint file set, or one for a small set. Each returns every finding with its evidence:
  - the quick checks for its files;
  - claims that are false against today's code, with the code that proves it;
  - gaps an agent would hit, such as an undocumented trap or a command that fails when run.

  Until every reviewer is back, audit only the files you kept, and edit and commit nothing. A reviewer cites line numbers, and an edit under it moves them.
- **Additions:** a skill, a script, a rule, or a `settings.json` allowlist. Each one must remove repeated work or a failure the audit found. The proposal lists them with that failure, then the rejected ideas with one line each.
- **Apply:** for a large set, spawn `worker` agents on disjoint file sets in one message. Hand each its rows from the table, the bar, the evidence behind each row, and the rules in [Apply](#apply).
- **Adversarial review:** spawn one `reviewer` on the diff. It reads the old text from git, so copy no files for it. It reports every command, ID, path, guardrail, exception and step that was lost without a row, and every kept or added claim that is false against the code. Fix each item you can confirm against the old text or the code.

Add a `reviewer` that calls the Skill tool with "claude-api" and args `prompt-audit <scoped path>` only when the arguments say "prompt audit", or when the bar is older than the newest model. On the bar's own model it repeats what the other reviewers find.

## Proposal

| File | Change | Why | Value 1-10 |
|---|---|---|---|

A row changes what an agent does or loads: a false claim, a contradiction, a duplicate, a trap, a missing route, or always-loaded text that can load on demand. Rewording, reordering or restyling text that is true and clear is not a row.

Value says how far the row moves the goal: 8 and up for a claim or command that sends an agent wrong, 5 to 7 for a contradiction, a duplicate or text moved out of an always-loaded file, lower for the rest.

Docs that already meet the bar are a valid result. Say so, change nothing, and ship nothing.

## Apply

- Apply the rows in the table and nothing else. A problem found on the way gets a row before it gets a fix.
- Delete or move before you reword. A moved or shortened passage keeps every command, ID, path, exception and reason unless its row says why one goes, and it gains no reason the source did not state. A rewrite that drops an exception or invents a reason fails silently, so read the diff once for both after the last edit.

## Shipping

Only when the arguments name an endpoint.

- Stage the files this run edited, by name. The checkout can hold someone else's changes.
- Reach the base branch the way the repo's own docs say. When they say nothing, an endpoint means what "Arguments" and "Repo kind" in `~/llmfiles/commands/fullsend.md` say it means.
- In a dispatched Orca worker, or with "unattended", follow "Worker mode" and "Sharing a repo with sibling worktrees" in `~/llmfiles/shared/orca-fleet.md`.

## Output

One message. With autofix it is the only one that carries the table.

- The table, saying per row whether it was applied.
- Lines before and after, for all files and for the files loaded every session.
- What was left as it is although the bar reads against it, one line each with the reason.
- Bugs found outside the docs. Report them, and fix them only when asked. In worker mode they go on the `Open:` line.
- In quick mode, one line naming the claims this pass could not check and deep would, when there are any.
