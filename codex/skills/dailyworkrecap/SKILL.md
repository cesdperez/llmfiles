---
name: dailyworkrecap
description: Draft the llmfiles daily work recap from git, GitLab, Claude transcripts, and available Slack evidence when explicitly requested.
---

Read `~/llmfiles/codex/compatibility.md`, then `~/llmfiles/commands/dailyworkrecap.md`. Execute the command body with the Codex adaptations and the following replacements taking precedence. Use the user's text after `$dailyworkrecap` as its arguments.

- The existing collector returns Claude transcripts only. Read them using the source command's schema; do not claim Codex sessions were included. State this coverage in the sources footer.
- For transcript timestamps, take the day's UTC boundaries from the collector's `window`, computed in the machine's local timezone. If that differs from `timezone` in `~/llmfiles/local/work.json`, recompute them with `zoneinfo.ZoneInfo(<timezone>)`.
- Replace the hardcoded Claude Slack tool names with available connected Slack search and thread-reading tools. If using TWG, load the installed `twg` and `twg-agentic-search` skills and follow their search workflow. Preserve the source's search intent and evidence requirements.
- If Slack or the Microsoft 365 calendar is unavailable, continue with the other sources, state the missing coverage, and omit Slack-derived conclusions about unanswered requests.
- Return the draft and private notes in the terminal. Posting requires a separate user request, as in the source workflow.
