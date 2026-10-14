---
name: whichagents
description: Recommend how to execute a task in Codex using one session, subagents, or separate worktrees when explicitly requested.
---

Read `~/llmfiles/codex/compatibility.md`, then `~/llmfiles/commands/whichagents.md` for the source's inspection and output contract. Replace its Claude execution modes and platform constraints with the Codex choices below. Use the user's text after `$whichagents` as the task, or the most recently described task when none was supplied.

1. Use one session when the work fits one context, needs shared state, or runs a local stack whose ports and processes would collide.
2. Use subagents for independent investigations, review lenses, or changes to separate files. Choose installed roles by their mandates and schedule within the current concurrency limit. Include the time and token cost of collecting and checking their results.
3. Use separate worktrees for concurrent edits that would otherwise touch the same checkout. Give each worker an explicit ownership boundary, then integrate and verify the combined change in the main session.

Check which agent tools, custom roles, and worktree support are actually available before recommending them. Claude's Workflow tool, agent-team lifecycle, `ultracode`, and cost multipliers are not Codex capabilities or estimates. If subagents are unavailable, recommend one session.

Return the source's **Use**, **Why**, **Shape**, **Cost**, and **Switch if** fields. Describe cost qualitatively unless measured evidence supports a multiplier. Recommend only; wait for the user to ask you to start the proposed execution mode.
