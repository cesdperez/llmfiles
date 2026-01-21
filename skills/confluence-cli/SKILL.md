---
name: confluence-cli
description: Manage Atlassian Confluence pages from the terminal. Use when reading wiki pages, searching Confluence, creating or updating documentation, copying page trees, managing attachments, or when the user mentions confluence, wiki pages, or confluence-cli.
---

# Confluence CLI

## Overview

CLI tool for Atlassian Confluence (npm package `confluence-cli` v1.13.0 by pchuri). Supports reading, creating, updating, searching, copying pages, managing attachments, and exporting with markdown support.

## Configuration

### API Paths

- **Atlassian Cloud**: `/wiki/rest/api`
- **Self-hosted/Data Center**: `/rest/api`

### Interactive Setup

```bash
confluence init
```

## Core Commands

| Command | Purpose |
|---------|---------|
| `read <pageId>` | Read page content |
| `info <pageId>` | Get page metadata |
| `search <query>` | Search pages |
| `find <title>` | Find page by title |
| `spaces` | List all spaces |
| `children <pageId>` | Show child pages |
| `create <title> <spaceKey>` | Create new page |
| `create-child <title> <parentId>` | Create child page |
| `update <pageId>` | Update existing page |
| `edit <pageId>` | Export page for editing |
| `delete <pageIdOrUrl>` | Delete page |
| `copy-tree <sourceId> <targetId>` | Copy page hierarchy |
| `attachments <pageId>` | List/download attachments |
| `export <pageId>` | Export page + attachments |
| `stats` | Show usage statistics |

## Content Formats

Use `--format` with these values:
- `storage` - Confluence native XML (default for create/update)
- `html` - HTML markup
- `markdown` - GitHub-flavored markdown
- `text` - Plain text (read only)

## Common Tasks

### Read a Page

```bash
# As plain text (default)
confluence read 123456789

# As markdown
confluence read 123456789 --format markdown

# As HTML
confluence read 123456789 --format html

# From URL
confluence read "https://domain.atlassian.net/wiki/viewpage.action?pageId=123456789"
```

### Create a Page

```bash
# From markdown file
confluence create "Page Title" SPACEKEY --file ./doc.md --format markdown

# Inline content
confluence create "Page Title" SPACEKEY --content "# Heading\nBody text" --format markdown

# As child of another page
confluence create-child "Child Title" 123456789 --file ./child.md --format markdown
```

### Update a Page

```bash
# Update content from file
confluence update 123456789 --file ./updated.md --format markdown

# Update title only
confluence update 123456789 --title "New Title"

# Update both
confluence update 123456789 --title "New Title" --file ./content.md --format markdown
```

### Delete a Page

```bash
# With confirmation prompt
confluence delete 123456789

# Skip confirmation (for scripts)
confluence delete 123456789 --yes

# By URL
confluence delete "https://domain.atlassian.net/wiki/viewpage.action?pageId=123456789" -y
```

### Search and Find

```bash
# Search by text
confluence search "API documentation" --limit 20

# Find by exact title
confluence find "Project Specs"

# Find in specific space
confluence find "Project Specs" --space DEVSPACE
```

### Copy Page Trees

```bash
# Copy entire hierarchy
confluence copy-tree 123456789 987654321 "Docs Backup"

# Preview without copying
confluence copy-tree 123456789 987654321 --dry-run

# Exclude patterns (wildcards: *, ?)
confluence copy-tree 123456789 987654321 --exclude "temp*,*draft*,test*"

# Limit depth
confluence copy-tree 123456789 987654321 --max-depth 3

# Custom suffix for root page
confluence copy-tree 123456789 987654321 --copy-suffix " (Backup)"

# Slow down for rate limits
confluence copy-tree 123456789 987654321 --delay-ms 200

# Exit on first error
confluence copy-tree 123456789 987654321 --fail-on-error

# Quiet mode (no progress output)
confluence copy-tree 123456789 987654321 --quiet
```

### Edit Workflow

```bash
# Export to local file
confluence edit 123456789 --output ./page.xml

# Edit locally, then update
confluence update 123456789 --file ./page.xml --format storage
```

### View Page Hierarchy

```bash
# List direct children
confluence children 123456789

# Recursive tree view
confluence children 123456789 --recursive --format tree

# With IDs and URLs
confluence children 123456789 --recursive --show-id --show-url

# Limit depth
confluence children 123456789 --recursive --max-depth 3

# As JSON (for scripting)
confluence children 123456789 --recursive --format json
```

### Manage Attachments

```bash
# List all attachments
confluence attachments 123456789

# List with limit
confluence attachments 123456789 --limit 10

# Filter by pattern
confluence attachments 123456789 --pattern "*.png"

# Download all attachments
confluence attachments 123456789 --download

# Download specific types to directory
confluence attachments 123456789 --pattern "*.pdf" --download --dest ./docs
```

### Export Page with Attachments

```bash
# Export as markdown with all attachments
confluence export 123456789 --dest ./exported

# Export as HTML
confluence export 123456789 --format html --dest ./exported

# Custom content filename
confluence export 123456789 --file README.md --dest ./exported

# Custom attachments directory
confluence export 123456789 --attachments-dir images --dest ./exported

# Only referenced attachments
confluence export 123456789 --referenced-only --dest ./exported

# Filter attachments
confluence export 123456789 --pattern "*.png" --dest ./exported

# Content only, no attachments
confluence export 123456789 --skip-attachments --dest ./exported
```

## Pitfalls to Avoid

1. **Wrong content format**: Default is `storage` (XML) for create/update. Use `--format markdown` for markdown files.

2. **Missing page ID**: Commands need numeric page ID, not page title. Use `confluence find "Title"` to get the ID first.

3. **Modern URL format unsupported**: URLs like `/wiki/spaces/SPACE/pages/123/Title` return 404. Use `viewpage.action?pageId=123` format or extract the page ID from the `/pages/{ID}/` segment.

4. **API path mismatch**: Cloud uses `/wiki/rest/api`, self-hosted uses `/rest/api`. Wrong path causes 404 errors.

5. **Rate limiting on copy-tree**: Large copies may hit rate limits. Use `--delay-ms 200` to slow down requests.

6. **Overwriting without backup**: Use `confluence export <id> --dest ./backup` before major updates.

## Quick Reference

```bash
# Setup
confluence init

# Read/Find
confluence read <id> --format markdown
confluence search "query" --limit 10
confluence find "Title" --space KEY
confluence info <id>

# Create
confluence create "Title" SPACE --file doc.md --format markdown
confluence create-child "Title" <parentId> --file doc.md --format markdown

# Update
confluence update <id> --file doc.md --format markdown
confluence update <id> --title "New Title"

# Delete
confluence delete <id> --yes

# Hierarchy
confluence children <id> --recursive --format tree
confluence copy-tree <source> <target> --dry-run
confluence copy-tree <source> <target> --exclude "temp*"

# Attachments
confluence attachments <id> --pattern "*.png" --download --dest ./images

# Export
confluence export <id> --format markdown --dest ./output
confluence export <id> --referenced-only --dest ./output

# Explore
confluence spaces
confluence stats
```
