---
name: locallensedreview
description: Run the llmfiles multi-lens audit of local changes with optional verification or autofix when explicitly requested.
---

Read `~/llmfiles/codex/compatibility.md`, then `~/llmfiles/commands/locallensedreview.md`. Execute the command body with the Codex adaptations taking precedence. Use the user's text after `$locallensedreview` as its arguments.

Pass the compatibility adaptations to every lens that loads `shared/review-lenses.md`. Schedule all selected lenses within the available Codex slots. Fix the findings at the fix bar sequentially, only when `--autofix` was requested.
