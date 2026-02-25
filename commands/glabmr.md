- Create a new branch if we're in the main branch
- Commit any changes remaining
- Push changes if remaining
- Use glab cli to create an MR with proper title and description. Be concise. If the user provided a Jira ticket code, prefix the title with it (e.g. `PROJ-123 Add user authentication`). If not, ask for it — skip the prefix if they don't have one.

use syntax:
```
glab mr create \
    --title "<title>" \
    --description "<description>" \
    --remove-source-branch \
    --squash-before-merge \
    --yes
```