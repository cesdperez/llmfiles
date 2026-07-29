---
description: Commit, push, and open a GitLab MR with a Conventional Commit title scoped to the Jira code.
argument-hint: [jira-code] [description]
---

- Create a new branch if we're in the main branch. Branch names include the Jira code: `feat/PROJ-123-description`.
- Commit any changes remaining
- Push changes if remaining
- Use glab cli to create an MR with proper title and description. Write the description per the **Writing MR Text** standard in the `glab-cli` skill: what changed then why, bullets over paragraphs, link the ticket rather than retelling it, no filler, no emoji. Commit and MR titles are Conventional Commits with the Jira code as the scope: `type(PROJ-123): description` (e.g. `fix(PE-209): correct OTLP receiver hostname`). NOT `PROJ-123 type: description` (confirmed by Sajad Hashemian 2026-06-30 on newhabitz MRs). If the user didn't provide a Jira code, ask for it. Omit the scope if they don't have one.

use syntax:
```
glab mr create \
    --title "<title>" \
    --description "<description>" \
    --remove-source-branch \
    --squash-before-merge \
    --yes
```