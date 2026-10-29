---
name: bugbounty
description: Run the llmfiles bug bounty on a running app when explicitly requested: parallel hunters attack it from every angle (functionality, look, responsiveness, accessibility, races, load, abuse) with playwright-cli and API calls, workers fix findings test-first, in cycles, until it meets a stated bar. "ship to main" or "ship to prod" go further.
---

Read `~/llmfiles/codex/compatibility.md`, then `~/llmfiles/commands/bugbounty.md`. Execute the command body with the Codex adaptations taking precedence. Use the user's text after `$bugbounty` as its arguments.

Ask the intake questions in one message and wait for the answers. Where Codex has no worktree isolation for agents, create a worktree per fix group with `git worktree add` and give its path to the worker. Replace Monitor with polling the pipeline or deploy status.
