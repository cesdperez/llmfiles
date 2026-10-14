---
name: glablensedreview
description: Run the llmfiles multi-lens GitLab MR review and follow-up workflow when explicitly requested; supports dry-run.
---

Read `~/llmfiles/codex/compatibility.md`, then `~/llmfiles/commands/glablensedreview.md`. Execute the command body with the Codex adaptations taking precedence. Use the user's text after `$glablensedreview` as its arguments.

Pass the compatibility adaptations to every lens. Preserve `--dry-run`, dispatched mode, posting thresholds, and follow-up markers. A missing notification tool does not prevent the review or terminal report.
