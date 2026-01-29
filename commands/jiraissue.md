Help the user create a Jira ticket using the `jira-cli` tool.

## Workflow

1. **Gather Information**: Ask the user for the following details (if not already provided):
   - Project key (e.g., CPT, PET, LE, ACT, ALE)
   - Issue type (e.g., Task, Bug, Story)
   - Summary/title of the issue
   - Description (can be provided inline or ask to draft it)
   - Optional: labels, priority, assignee, components

2. **Draft Ticket**: If the user hasn't provided a full description, help them draft a clear, structured ticket description that includes:
   - Current state / Problem description
   - Desired state / Expected outcome
   - Affected systems/projects
   - Implementation details or examples (if applicable)
   - Acceptance criteria
   - Technical notes (if applicable)
   - Dependencies

3. **Create Ticket**: Use the jira-cli to create the ticket:
   - If description is long/complex, write it to a temporary file and use `--template` flag
   - Use appropriate flags for the provided information
   - Always use `--no-input` for non-interactive creation
   - Return the created ticket URL to the user

## Command Syntax Reference

```bash
# Basic creation with template
jira issue create \
  -p <PROJECT_KEY> \
  -t <ISSUE_TYPE> \
  -s "<SUMMARY>" \
  -T /tmp/jira-ticket-description.md \
  --no-input

# With additional fields
jira issue create \
  -p <PROJECT_KEY> \
  -t <ISSUE_TYPE> \
  -s "<SUMMARY>" \
  -T /tmp/jira-ticket-description.md \
  -l <label1> \
  -l <label2> \
  -y <priority> \
  -a <assignee> \
  --no-input
```

## Available Projects

Run `jira project list` to see available projects if needed.

## Notes

- Keep ticket descriptions concise, clear, and actionable
- Use markdown formatting in descriptions
- Include code examples in fenced code blocks when relevant
- Add acceptance criteria as checklists using `[ ]` syntax
