---
name: glab-cli
description: GitLab CLI for merge requests and CI/CD pipelines. Use when creating MRs, reviewing merge requests, checking pipeline status, or when the user mentions glab, GitLab CLI, or merge request operations.
---

# GitLab CLI (glab)

## Overview

glab brings GitLab to your terminal. Manage merge requests, pipelines, and repositories without leaving the command line.

## Authentication

CLI is already authenticated. Check status with:

```bash
glab auth status
```

## Merge Request Commands

### MR Creation Defaults

Always include these flags when creating MRs:
- `--remove-source-branch` - Delete branch when merged
- `--squash-before-merge` - Squash commits when merged
- `--yes` - Skip confirmation prompts

**MR Title Format**: If the user provides a Jira ticket code, prefix the title with it (e.g., `PROJ-123 Add user authentication`). If not provided, ask for it. If the user doesn't know or it's not applicable, omit it.

### Create MR

```bash
# Standard MR creation
glab mr create \
    --title "<title>" \
    --description "<description>" \
    --remove-source-branch \
    --squash-before-merge \
    --yes

# Auto-fill from commits
glab mr create --fill \
    --remove-source-branch \
    --squash-before-merge \
    --yes

# Draft MR
glab mr create --draft \
    --title "WIP: feature" \
    --remove-source-branch \
    --squash-before-merge \
    --yes

# With reviewers and labels
glab mr create \
    --title "Add feature" \
    --description "Description" \
    --reviewer username1,username2 \
    --label feature,needs-review \
    --remove-source-branch \
    --squash-before-merge \
    --yes
```

### Update MR

```bash
# Update title and description
glab mr update <mr_id> \
    --title "<new title>" \
    --description "<new description>"

# Mark as ready (remove draft)
glab mr update <mr_id> --ready

# Mark as draft
glab mr update <mr_id> --draft

# Add/remove labels (prefix with - to remove)
glab mr update <mr_id> --label new-label --unlabel old-label

# Change assignees (prefix with + to add, - to remove)
glab mr update <mr_id> --assignee +newuser,-olduser
```

### View & Inspect MR

```bash
# View MR details
glab mr view <mr_id>

# JSON output for parsing
glab mr view <mr_id> --output json

# View diff
glab mr diff <mr_id>

# View with comments
glab mr view <mr_id> --comments

# Open in browser
glab mr view <mr_id> --web
```

### List MRs

```bash
glab mr list                              # Open MRs
glab mr list --assignee=@me               # Assigned to me
glab mr list --reviewer=@me               # I'm reviewing
glab mr list --author=username            # By author
glab mr list --draft                      # Only drafts
glab mr list --merged                     # Merged MRs
glab mr list --label needs-review         # By label
glab mr list --source-branch feature      # By source branch
glab mr list --output json                # JSON output
```

### MR Actions

```bash
glab mr merge <mr_id>                     # Merge MR
glab mr merge <mr_id> --squash            # Squash and merge
glab mr approve <mr_id>                   # Approve
glab mr revoke <mr_id>                    # Revoke approval
glab mr close <mr_id>                     # Close without merging
glab mr reopen <mr_id>                    # Reopen closed MR
glab mr checkout <mr_id>                  # Checkout branch locally
glab mr rebase <mr_id>                    # Rebase against target
glab mr note <mr_id> -m "Comment"         # Add comment
```

## CI/CD Commands

```bash
glab ci view                              # Interactive pipeline view
glab ci status                            # Current pipeline status
glab ci list                              # List recent pipelines
glab ci trace <job_id>                    # Stream job logs
glab ci run                               # Trigger new pipeline
glab ci retry <job_id>                    # Retry failed job
glab ci cancel                            # Cancel running pipeline
glab ci lint                              # Validate .gitlab-ci.yml
```

## Common Workflows

### Create MR for Current Branch

```bash
# Push and create MR in one step
glab mr create \
    --fill \
    --remove-source-branch \
    --squash-before-merge \
    --yes
```

### Review an MR

```bash
# View details and diff
glab mr view 624 --output json
glab mr diff 624

# Approve and merge
glab mr approve 624
glab mr merge 624 --squash
```

### Check Pipeline Before Merge

```bash
glab ci status
glab mr view <mr_id> --output json | jq '.pipeline'
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

## Environment Variables

| Variable | Purpose |
|----------|---------|
| `GITLAB_TOKEN` | API authentication token |
| `GITLAB_HOST` | Self-hosted GitLab URL |
| `BROWSER` | Browser for `--web` |

## Working Outside a Git Repository

Most `glab` commands require being inside a git repository. Use the API directly for cross-project operations.

### List All Your Open MRs (Global)

```bash
# List all open MRs you created across all projects
glab api "merge_requests?scope=created_by_me&state=opened" --paginate

# Format nicely with jq
glab api "merge_requests?scope=created_by_me&state=opened" --paginate | \
    jq -r '.[] | "\(.iid)\t\(.title)\t\(.web_url)"'
```

### Close/Update MR via API

Project paths must be URL-encoded (slashes → `%2F`):

```bash
# Close an MR
glab api --method PUT "projects/goodhabitz%2Fbackend%2Fmy-project/merge_requests/123" \
    -f state_event=close

# Reopen an MR
glab api --method PUT "projects/goodhabitz%2Fbackend%2Fmy-project/merge_requests/123" \
    -f state_event=reopen
```

### Common API Scopes for MRs

| Scope | Description |
|-------|-------------|
| `created_by_me` | MRs you authored |
| `assigned_to_me` | MRs assigned to you |
| `review_requests_for_me` | MRs awaiting your review |

## Pitfalls to Avoid

1. **Forgetting `--yes` in scripts** - Without it, commands prompt for confirmation
2. **Not pushing before MR** - Use `--fill` which auto-pushes, or push manually first
3. **Squash flag timing** - `--squash-before-merge` is on create/update, `--squash` is on merge
4. **Assignee modification** - Use `+` to add, `-` to remove, or plain to replace all
5. **JSON parsing** - Use `--output json` not `--json`
6. **GitHub CLI flag confusion** - Use `--description` for MR body, not `--body` (which is gh's syntax)
7. **Not in a git repo** - Use `glab api` for cross-project operations when outside a repo
