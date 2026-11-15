# CLAUDE.md

Agent config repo: Claude Code commands, agents, skills and shared protocols, with Codex adapters under `codex/` and opencode adapters under `opencode/`. Read `README.md` for the layout, file formats and install steps before adding, renaming or moving a file.

- Claude files are the source. A Codex or opencode file loads the matching Claude body and holds only what differs, except the opencode conductor and its builders.
- `hooks/pre-commit` rejects em dashes in staged lines and runs yamllint, shellcheck, ruff and `hooks/check-repo.py` on the whole tree. `python3 hooks/check-repo.py` checks frontmatter, names, models and every `~/llmfiles/` path, so run it after adding, renaming or moving a skill, command or agent.
- Org-specific values go in gitignored `local/`, with a template in `local.example/`, because this repo is public.
