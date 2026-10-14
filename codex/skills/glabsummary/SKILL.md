---
name: glabsummary
description: Triage the llmfiles GitLab review queue and run fast or multi-lens reviews when explicitly requested.
---

Read `~/llmfiles/codex/compatibility.md`, then `~/llmfiles/commands/glabsummary.md`. Execute the command body with the Codex adaptations taking precedence. Use the user's text after `$glabsummary` as its arguments.

Pass the compatibility adaptations to each per-MR worker. For escalations, load `~/llmfiles/codex/skills/glablensedreview/SKILL.md` and execute it in dispatched mode, one MR at a time. Collect and close the fast-review workers before dispatching the lensed reviews so their slots are available.
