---
name: jira-cli
description: Manage Jira issues, sprints, and epics from the command line using jira-cli. Use when creating Jira tickets, listing issues, transitioning tasks, managing sprints, searching with JQL, or when the user mentions jira, jira-cli, or ticket management.
---

# Jira CLI

## Overview

jira-cli (`jira`) is an interactive command-line tool for Atlassian Jira. It enables issue creation, transitions, sprint management, and JQL queries without the web interface.

## Authentication

CLI is already authenticated and setup.

## Essential Commands

### List Issues

```bash
jira issue list                           # Interactive list
jira issue list -a$(jira me)              # My issues
jira issue list -s"To Do"                 # By status
jira issue list -yHigh                    # By priority
jira issue list --created -7d             # Last 7 days
jira issue list -q "summary ~ 'search'"   # JQL query
jira issue list -ax                       # Unassigned
jira issue list --plain                   # Plain text output
jira issue list --raw                     # JSON output
```

### Create Issue

```bash
jira issue create                         # Interactive
jira issue create -tBug -s"Summary" -yHigh -b"Description" --no-input
jira issue create -tTask -s"Summary" -PEPIC-42 --no-input  # Link to epic
echo "Description from stdin" | jira issue create -s"Summary" -tTask

# With template file (for complex descriptions)
jira issue create -p PROJECT -t Task -s "Summary" -T /tmp/description.md --no-input

# Full example with all fields
jira issue create \
  -p PROJECT \
  -t Bug \
  -s "Summary" \
  -T /tmp/description.md \
  -l label1 -l label2 \
  -y High \
  -a "assignee" \
  --component Frontend \
  --no-input
```

### Transition/Move Issue

```bash
jira issue move ISSUE-1 "In Progress"
jira issue move ISSUE-1 Done -RFixed      # With resolution
jira issue move                           # Interactive
```

### Assign Issue

```bash
jira issue assign ISSUE-1 $(jira me)      # Assign to self
jira issue assign ISSUE-1 "John Doe"
jira issue assign ISSUE-1 x               # Unassign
```

### Edit Issue

```bash
jira issue edit ISSUE-1 -s"New summary" --no-input
jira issue edit ISSUE-1 --label -old --label new  # Modify labels

# Update description via stdin (note: -T flag not supported for edit)
cat /tmp/description.md | jira issue edit ISSUE-1 --no-input
echo "New description" | jira issue edit ISSUE-1 --no-input
```

### View & Comment

```bash
jira issue view ISSUE-1
jira issue view ISSUE-1 --comments 5
jira issue comment add ISSUE-1 "Comment text"
```

### Link Issues

```bash
jira issue link ISSUE-1 ISSUE-2 "blocks"
jira issue link ISSUE-1 ISSUE-2 "relates to"
```

## Sprint & Epic Management

```bash
# Sprints
jira sprint list
jira sprint list -p PROJECT
jira sprint add SPRINT_ID ISSUE-1

# Epics
jira epic list
jira epic create -s"Epic name" -b"Description"
jira epic add EPIC-1 ISSUE-2              # Add issue to epic
jira epic remove EPIC-1 ISSUE-2
```

## Common Workflows

### Find and transition my blocked tickets

```bash
jira issue list -a$(jira me) -s"Blocked" --plain
jira issue move ISSUE-1 "In Progress"
```

### Create bug with full details

```bash
jira issue create -tBug \
  -s"Login fails on Safari" \
  -yHigh \
  -b"Steps to reproduce..." \
  -lbug -lsafari \
  --component Frontend \
  --no-input
```

### Bulk search with JQL

```bash
jira issue list -q "project = PROJ AND status = 'To Do' AND priority = High ORDER BY created DESC"
```

## Ticket Creation Workflow

When helping users create tickets, gather these details:
- **Required**: Project key, issue type, summary
- **Optional**: Description, labels, priority, assignee, components

### Description Template

For complex tickets, write to a temp file and use `-T` flag. Keep descriptions **concise and actionable** - avoid verbose explanations. DRY between sections. Only include sections that add value; skip empty or obvious ones.

Structure:

```markdown
## Context
What's happening now, why it's a problem

## Desired State
What should happen instead

## Affected Systems
- System/project 1
- System/project 2

## Implementation Details
Technical approach, examples, code snippets in fenced blocks

## Acceptance Criteria
[] Criterion 1
[] Criterion 2

## Dependencies
Any blockers or related work
```

### Ticket Creation Example

```bash
# 1. Write description to temp file
cat > /tmp/jira-description.md << 'EOF'
...
EOF

# 2. Create ticket
jira issue create \
  -p CPT \
  -t Bug \
  -s "Login fails on Safari 17" \
  -T /tmp/jira-description.md \
  -y High \
  -l safari -l auth \
  --no-input

# 3. Get available projects if needed
jira project list
```

## Output Formats

| Flag | Format | Use Case |
|------|--------|----------|
| (default) | Interactive TUI | Browsing, navigation |
| `--plain` | Plain text | Scripting, piping |
| `--raw` | JSON | Parsing, automation |
| `--csv` | CSV | Exports, spreadsheets |

## Interactive Navigation

| Key | Action |
|-----|--------|
| `j/k` or arrows | Navigate |
| `v` | View issue |
| `m` | Move/transition |
| `Enter` | Open in browser |
| `c` | Copy URL |
| `Ctrl+k` | Copy issue key |
| `q` | Quit |

## Key Flags Reference

| Flag | Purpose |
|------|---------|
| `-p` | Project key |
| `-t` | Issue type (Bug, Task, Story) |
| `-s` | Summary or status filter |
| `-b` | Body/description |
| `-y` | Priority |
| `-a` | Assignee |
| `-l` | Label |
| `-P` | Parent epic |
| `-R` | Resolution |
| `-T` | Template file for description |
| `-q` | Raw JQL query |
| `--no-input` | Non-interactive mode |
| `-c` | Config file path |
| `--component` | Component name |

## Pitfalls to Avoid

1. **Forgetting `--no-input` in scripts** - Without it, commands hang waiting for input
2. **Status names must match exactly** - Use quotes: `-s"In Progress"` not `-sIn Progress`
3. **JQL needs proper quoting** - Wrap the entire query: `-q "summary ~ 'text'"`
4. **`jira me` returns username** - Use `$(jira me)` for dynamic assignment
5. **Labels with `-` prefix remove** - `--label -old` removes, `--label new` adds
6. **`-T` flag only works on create** - Use stdin piping for edit: `cat file.md | jira issue edit ISSUE-1 --no-input`
