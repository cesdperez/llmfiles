---
name: tunesetup
description: Review the Claude Code setup in llmfiles over the last period and propose evidence-backed changes when explicitly requested.
---

Read `~/llmfiles/codex/compatibility.md`, then `~/llmfiles/commands/tunesetup.md`. Use the source's comparison, scripts, friction and evidence mandates, proposal rules, report and saved files with these replacements. Use the user's text after `$tunesetup` as its period and focus.

- The scripts read Claude Code transcripts under `~/.claude/projects`, so the review covers Claude Code sessions only. Codex session history is not measured; say so in the report.
- Where the source loads the `claude-api` skill for missing prices, read the current list prices from Anthropic's official pricing page instead.
- Run the friction and outside-evidence mandates as two `worker` agents, or in sequence when no slot is free.
- Proposals target the Claude files in this repo. A Codex-only adapter or agent is in scope only when the friction read names it.
