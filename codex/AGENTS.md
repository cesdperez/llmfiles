# Codex instructions

Read `~/llmfiles/shared/CLAUDE.md` for the shared coding, testing, writing, and skill-maintenance preferences. The Codex instructions below replace its Claude-specific delegation rules.

## Delegation

Use the installed agents defined in `~/llmfiles/codex/agents/`: `worker` for implementation and investigations, `worker-fast` for known mechanical steps, `reviewer` and `reviewer-fast` for audits, `explorer` for locating code, `general-purpose` for other delegated tasks, and `gitlab` for MR creation. Their TOML files select the model and effort independently of the main session.

When a command requests parallel work, schedule agents within the available concurrency limit, collect every result, and close completed threads before starting the next batch. If delegation is unavailable, complete the work sequentially and report that limitation.

## Claude compatibility

Read `~/llmfiles/codex/compatibility.md` when executing a command from `~/llmfiles/commands/`, using the shared review protocols, or writing GitLab text with the `glab-cli` skill. Apply those adaptations in the main session and in delegated briefs.

Claude files remain the primary sources. Keep Codex-specific changes under `~/llmfiles/codex/`; shared knowledge skills remain under `~/llmfiles/skills/`.
