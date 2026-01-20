---
name: jira-cli
description: Interact with Jira issues, epics, and sprints directly from the terminal. Use when managing Jira tickets, listing assigned work, creating bug reports, or transitioning issues without opening the browser.
---

# Jira CLI

## Overview
This skill enables efficient interaction with Atlassian Jira from the terminal using the `jira-cli` (binary name `jira`). It supports creating, editing, and viewing issues, epics, and sprints, with both interactive and non-interactive modes.

## Key Patterns
- **Interactive by Default**: Most commands launch an interactive TUI unless flagged otherwise. Use `--no-input` for scripting or quick one-off commands.
- **Filtering**: Extensive short-flags for common filters: `-s` (status), `-y` (priority), `-t` (type), `-a` (assignee), `-r` (reporter).
- **JQL Integration**: Use `-q / --jql` to run raw JQL queries when standard flags aren't enough.
- **Context Awareness**: The CLI relies on a configuration file (usually `~/.jira/.config.yml`) for the current project context. Use `-c` to switch configs.
- **Templates**: Accepts Markdown templates for descriptions and comments via `--template`.

## Commands
### Core Setup
- `jira init`: Initialize configuration (interactive).
- `jira me`: Print the logged-in user's name/ID.

### Issue Management
- `jira issue list`: List issues (interactive TUI).
- `jira issue list --plain`: List issues in plain text (good for piping).
- `jira issue create`: Create a new issue.
- `jira issue view [ISSUE-KEY]`: View issue details.
- `jira issue edit [ISSUE-KEY]`: Edit issue fields.
- `jira issue move [ISSUE-KEY] [STATUS]`: Transition an issue.
- `jira issue assign [ISSUE-KEY] [USER]`: Assign an issue.
- `jira issue comment add [ISSUE-KEY]`: Add a comment.

### Epic & Sprint
- `jira epic list`: List epics.
- `jira epic add [EPIC-KEY] [ISSUE-KEYS...]`: Add issues to an epic.
- `jira sprint list --current`: List issues in the active sprint.

## Workflow: Assisted Ticket Creation
Follow this process when asking to create a ticket or when the user provides vague requirements:

1. **Gather Information**: Ensure you have these details:
   - **Project Key**: Run `jira project list` if unknown (e.g., CPT, LXP).
   - **Issue Type**: Task, Bug, Story.
   - **Summary**: A clear, concise title.
   - **Metadata**: Assignee (default to self if unsure), Labels, Priority.

2. **Draft the Description**:
   - Create a structured description in a temporary file (e.g., `/tmp/jira_desc.md`) to ensure quality.
   - **Conciseness**: Keep summaries and descriptions focused. Avoid fluff and DRY.
   - **Structure**:
     - *Context*: What is happening now?
     - *Expected Outcome*: What should happen?
     - *Acceptance Criteria*: Checklist `[ ]` of verifiable steps.
     - *Technical Notes*: Dependencies, specific files, or implementation details.

3. **Execute Creation**:
   - Use the template flag `-T` and `--no-input` for reliability.
   - **Base Command**:
     ```bash
     jira issue create \
       -p PROJECTS \
       -t Task \
       -s "Summary here" \
       -T /tmp/jira_desc.md \
       --no-input
     ```
   - **Full Command** (with metadata):
     ```bash
     jira issue create \
       -p PROJECTS \
       -t Bug \
       -s "Summary here" \
       -T /tmp/jira_desc.md \
       -l backend -l bug \
       -y High \
       -a $(jira me) \
       --no-input
     ```

## Common Tasks

### 1. Daily Standup / Work Check
List high-priority issues assigned to you in the current sprint or generally.
```bash
# List all "In Progress" issues assigned to me
jira issue list -s"In Progress" -a$(jira me)

# List current sprint issues assigned to me
jira sprint list --current -a$(jira me)
```

### 2. Creating a Bug Report (Quick)
Quickly file a bug without the interactive prompt using inline flags.
```bash
jira issue create \
  -tBug \
  -s"Login fails with 500 error" \
  -yHigh \
  -lbackend -lurgent \
  -b"Step to reproduce: ..." \
  --no-input
```

### 3. Transitioning & Commenting
Move a ticket to "Done" and add a closing comment.
```bash
jira issue move ISSUE-123 "Done" \
  --comment "Fixed the race condition in the auth handler."
```

## Pitfalls to Avoid
1. **Ambiguous Assignees**: When assigning users, if the name matches multiple people, the CLI will prompt interactively. Use exact usernames or emails for scripts.
2. **Missing Configuration**: Running commands outside of an initialized context will fail. Ensure `jira init` has been run or `JIRA_CONFIG_FILE` is set.
3. **Markdown Rendering**: Jira uses a specific flavor of Markdown. Complex formatting might look different in the terminal vs the web UI.
4. **Cloud vs On-Prem**: Auth mechanisms differ. Cloud uses `JIRA_API_TOKEN` (API Token), while On-Prem might use PATs or Basic Auth.

## Quick Reference
| Task | Command |
|------|---------|
| **List Issues** | `jira issue list` |
| **View Issue** | `jira issue view KEY-1` |
| **Myself** | `$(jira me)` |
| **JQL Query** | `jira issue list -q "project = X AND fixVersion is EMPTY"` |
| **Open in Browser** | `jira open KEY-1` |
