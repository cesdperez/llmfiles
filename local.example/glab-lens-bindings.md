# GitLab review lens bindings

Optional. Loaded by `~/llmfiles/shared/glab-mr-context.md`. `$REPO_ROOT` is `repo_root`
from `local/work.json`.

- **code-standards** reads, most-specific-wins: the repo's `CLAUDE.md`, its group
  `CLAUDE.md` (`web/CLAUDE.md`, `backend/CLAUDE.md`, ...), `$REPO_ROOT/CLAUDE.md`, and the
  repo's lint and format config.
- **reuse** also checks `web/packages` (`@acme/*`) for existing helpers.
- **cross-repo-impact** sweeps the local mirror in one batched pass, then maps each hit's
  repo to its owning team:
  ```bash
  rg -n --no-heading -g '!**/node_modules/**' -g '!**/.git/**' -g '!**/dist/**' \
     -e '<symbol1>' -e '<symbol2>' -e '<route>' \
     "$REPO_ROOT" \
     -g '!<rest>/**'
  ```
- **ticket-alignment** uses `twg jira workitem get <KEY>`, keys matching `[A-Z]{2,10}-\d+`,
  capped at 3, preferring keys in the title or branch name.
