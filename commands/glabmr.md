- Create a new branch if we're in the main branch. Branch names include the Jira code: `feat/PROJ-123-description`.
- Commit any changes remaining
- Push changes if remaining
- Use glab cli to create an MR with proper title and description. Be concise. Commit and MR titles are Conventional Commits with the Jira code as the scope: `type(PROJ-123): description` (e.g. `fix(PE-209): correct OTLP receiver hostname`). NOT `PROJ-123 type: description` (confirmed by Sajad Hashemian 2026-06-30 on newhabitz MRs). If the user didn't provide a Jira code, ask for it — omit the scope if they don't have one.

use syntax:
```
glab mr create \
    --title "<title>" \
    --description "<description>" \
    --remove-source-branch \
    --squash-before-merge \
    --yes
```