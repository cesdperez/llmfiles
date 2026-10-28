---
name: fullsend
description: Run the llmfiles end-to-end delivery of a task (Jira, Slack, or text) to a reviewed, browser-verified draft MR when explicitly requested; "ship to main" or "ship to prod" go further.
---

Read `~/llmfiles/codex/compatibility.md`, then `~/llmfiles/commands/fullsend.md`. Execute the command body with the Codex adaptations taking precedence. Use the user's text after `$fullsend` as its arguments.

Where the command runs `/code-review`, run `$locallensedreview branch medium --autofix` instead. Ask the intake questions in one message and wait for the answers.
