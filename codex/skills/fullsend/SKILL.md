---
name: fullsend
description: Run the llmfiles end-to-end delivery of a task (Jira, Slack, or text) to a reviewed, browser-verified MR with a green pipeline, its review threads answered and marked ready (work repos), or a local branch (personal repos) when explicitly requested; "open a PR", "ship to main" or "ship to prod" go further.
---

Read `~/llmfiles/codex/compatibility.md`, then `~/llmfiles/commands/fullsend.md`. Execute the command body with the Codex adaptations taking precedence. Use the user's text after `$fullsend` as its arguments.

Run its `/locallensedreview` step as `$locallensedreview`. Ask the intake questions in one message and wait for the answers.
