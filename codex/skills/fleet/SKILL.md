---
name: fleet
description: Run the llmfiles Orca fleet coordinator when explicitly requested. Several tasks become supervised Orca sessions, one worktree each, run in parallel or in order, each running $fullsend or the named command to the endpoint asked.
---

Read `~/llmfiles/codex/compatibility.md`, then `~/llmfiles/commands/fleet.md`. Execute the command body with the Codex adaptations taking precedence. Use the user's text after `$fleet` as its arguments.

Start workers with `--agent codex`, and write each spec's first line as "Invoke the $<command> skill with: ...". In a handoff without supervision, start the prompt with `$<command>`. Ask the plan confirmation in one message and wait for the answer. Run `check --wait` in the foreground with a timeout your shell allows, and repeat it.
