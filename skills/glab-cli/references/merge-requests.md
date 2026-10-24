# Merge Request Command Catalog

Creation defaults (flags, title format, branch naming) live in
`~/llmfiles/skills/glab-cli/SKILL.md`. Every `mr create` below carries them.

## Create MR Variants

```bash
# Draft MR
glab mr create --draft \
    --title "feat(PROJ-123): add user authentication" \
    --assignee @me \
    --remove-source-branch \
    --squash-before-merge \
    --yes

# With reviewers and labels
glab mr create \
    --title "feat(PROJ-123): add user authentication" \
    --description "Description" \
    --assignee @me \
    --reviewer username1,username2 \
    --label feature,needs-review \
    --remove-source-branch \
    --squash-before-merge \
    --yes
```

## Update MR

```bash
# Update title and description
glab mr update <mr_id> \
    --title "<new title>" \
    --description "<new description>"

# Mark as ready (remove draft)
glab mr update <mr_id> --ready

# Mark as draft
glab mr update <mr_id> --draft

# Add/remove labels
glab mr update <mr_id> --label new-label --unlabel old-label

# Change assignees (prefix with + to add, - to remove)
glab mr update <mr_id> --assignee +newuser,-olduser
```

## View & Inspect MR

```bash
glab mr view <mr_id> --comments           # View with comments
glab mr view <mr_id> --web                # Open in browser
```

## List MRs

```bash
glab mr list                              # Open MRs
glab mr list --author=username            # By author
glab mr list --draft                      # Only drafts
glab mr list --merged                     # Merged MRs
glab mr list --label needs-review         # By label
glab mr list --source-branch feature      # By source branch
glab mr list --output json                # JSON output
```

## MR Actions

```bash
glab mr approve <mr_id>                   # Approve
glab mr revoke <mr_id>                    # Revoke approval
glab mr close <mr_id>                     # Close without merging
glab mr reopen <mr_id>                    # Reopen closed MR
glab mr rebase <mr_id>                    # Rebase against target
```

## Output Formats

| Flag | Format | Use Case |
|------|--------|----------|
| (default) | Text | Human readable |
| `--output json` | JSON | Parsing, automation |
| `--web` | Browser | Full GitLab UI |

## Key Flags Reference

| Flag | Purpose |
|------|---------|
| `-t, --title` | MR title |
| `-d, --description` | Description text |
| `-l, --label` | Add labels |
| `-a, --assignee` | Assign users |
| `--reviewer` | Request reviewers |
| `-y, --yes` | Skip confirmation prompts |
| `-f, --fill` | Auto-fill from commits |
| `--draft` | Mark as draft/WIP |
| `-r, --ready` | Mark as ready |
| `--remove-source-branch` | Delete branch on merge |
| `--squash-before-merge` | Squash commits |
| `-R, --repo` | Target different repo |
| `-F, --output` | Output format (text/json) |
