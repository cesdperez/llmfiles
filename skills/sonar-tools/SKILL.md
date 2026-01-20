---
name: sonar-tools
description: Run sonar-tools CLI commands for SonarCloud administration. Use when the user asks about SonarQube audits, findings export, measures export, LOC reports, configuration management, housekeeping, or any sonar-tools command.
---

# sonar-tools (SonarCloud)

## Overview

sonar-tools is a Python CLI suite for SonarCloud administration. It provides commands for auditing, exporting findings/metrics, housekeeping, and configuration management.

## Authentication

Assume these environment variables are configured:
- `SONAR_HOST_URL` (https://sonarcloud.io)
- `SONAR_TOKEN`
- `SONAR_ORGANIZATION`

## Find Project Key by Name

Users will provide project names, not keys. Keys are like `goodhabitz_55014192`. Use fuzzy search:

```bash
# Step 1: Save projects list
curl -s -u "$SONAR_TOKEN:" "$SONAR_HOST_URL/api/components/search?qualifiers=TRK&organization=$SONAR_ORGANIZATION&ps=500" > /tmp/sonar_projects.json
```

```bash
# Step 2: Search by partial name (case-insensitive)
jq -r '.components[] | "\(.key) | \(.name)"' /tmp/sonar_projects.json | grep -i "SEARCH_TERM"
```

## Export Findings

**Important:** The `--types` flag doesn't filter reliably. Export all findings to JSON, then filter with jq.

```bash
# Export all findings for a project (redirect stderr to get clean JSON)
sonar-findings-export -o "${SONAR_ORGANIZATION}" -k PROJECT_KEY --format json 2>/dev/null > /tmp/findings.json

# Count by type
jq '[.[] | .type] | group_by(.) | map({type: .[0], count: length})' /tmp/findings.json
```

### All Issues (summary)

```bash
# All open issues with counts by type and severity
jq -r '.[] | select(.status == "OPEN") | "\(.type) | \(.severity)"' /tmp/findings.json | sort | uniq -c | sort -rn
```

### Security Issues (Vulnerabilities)

```bash
# All vulnerabilities
jq -r '.[] | select(.type == "VULNERABILITY") | "[\(.severity)] \(.message)\n  File: \(.file):\(.line)\n  Rule: \(.rule)\n  Status: \(.status)\n"' /tmp/findings.json

# Open vulnerabilities only
jq -r '.[] | select(.type == "VULNERABILITY" and .status == "OPEN") | "[\(.severity)] \(.message)\n  File: \(.file):\(.line)\n  Rule: \(.rule)\n"' /tmp/findings.json
```

### Reliability Issues (Bugs)

```bash
# All bugs
jq -r '.[] | select(.type == "BUG") | "[\(.severity)] \(.message)\n  File: \(.file):\(.line)\n  Rule: \(.rule)\n  Status: \(.status)\n"' /tmp/findings.json

# Open bugs only
jq -r '.[] | select(.type == "BUG" and .status == "OPEN") | "[\(.severity)] \(.message)\n  File: \(.file):\(.line)\n  Rule: \(.rule)\n"' /tmp/findings.json
```

### Maintainability Issues (Code Smells)

```bash
# All code smells (can be large!)
jq -r '.[] | select(.type == "CODE_SMELL") | "[\(.severity)] \(.message)\n  File: \(.file):\(.line)\n  Rule: \(.rule)\n  Status: \(.status)\n"' /tmp/findings.json

# Open code smells only
jq -r '.[] | select(.type == "CODE_SMELL" and .status == "OPEN") | "[\(.severity)] \(.message)\n  File: \(.file):\(.line)\n"' /tmp/findings.json

# Open code smells - critical/blocker only
jq -r '.[] | select(.type == "CODE_SMELL" and .status == "OPEN" and (.severity == "BLOCKER" or .severity == "CRITICAL")) | "[\(.severity)] \(.message)\n  File: \(.file):\(.line)\n"' /tmp/findings.json
```

### Security Hotspots

```bash
# Hotspots to review
jq -r '.[] | select(.type == "SECURITY_HOTSPOT" and .status == "TO_REVIEW") | "[\(.vulnerabilityProbability // "?")] \(.message)\n  File: \(.file):\(.line)\n  Key: \(.key)\n"' /tmp/findings.json
```

## List Projects Failing Quality Gate

```bash
curl -s -u "$SONAR_TOKEN:" "$SONAR_HOST_URL/api/components/search?qualifiers=TRK&organization=$SONAR_ORGANIZATION&ps=500" | jq -r '.components[].key' | while read key; do
  qg_status=$(curl -s -u "$SONAR_TOKEN:" "$SONAR_HOST_URL/api/qualitygates/project_status?projectKey=$key" | jq -r '.projectStatus.status')
  if [ "$qg_status" = "ERROR" ]; then
    echo "$key"
  fi
done
```

## List Projects with Hotspots to Review

Use the `/api/hotspots/search` API directly (more efficient than exporting findings per project).

```bash
# First, ensure projects list is cached
curl -s -u "$SONAR_TOKEN:" "$SONAR_HOST_URL/api/components/search?qualifiers=TRK&organization=$SONAR_ORGANIZATION&ps=500" > /tmp/sonar_projects.json
```

```bash
# Count hotspots to review per project
jq -r '.components[] | .key' /tmp/sonar_projects.json | while read key; do
  count=$(curl -s -u "$SONAR_TOKEN:" "$SONAR_HOST_URL/api/hotspots/search?projectKey=$key&status=TO_REVIEW" | jq '.paging.total')
  if [ "$count" != "0" ] && [ "$count" != "null" ]; then
    name=$(jq -r --arg k "$key" '.components[] | select(.key == $k) | .name' /tmp/sonar_projects.json)
    echo "$count | $name"
  fi
done | sort -rn
```

### Get hotspots for a single project

```bash
# List hotspots to review for a specific project
curl -s -u "$SONAR_TOKEN:" "$SONAR_HOST_URL/api/hotspots/search?projectKey=PROJECT_KEY&status=TO_REVIEW" | jq -r '.hotspots[] | "[\(.vulnerabilityProbability)] \(.message)\n  File: \(.component):\(.line)\n  Key: \(.key)\n"'
```

## Hotspot Operations (via API)

### Change hotspot status

```bash
# Mark as SAFE
curl -s -X POST -u "$SONAR_TOKEN:" "$SONAR_HOST_URL/api/hotspots/change_status" -d "hotspot=HOTSPOT_KEY&status=REVIEWED&resolution=SAFE"

# Mark as FIXED
curl -s -X POST -u "$SONAR_TOKEN:" "$SONAR_HOST_URL/api/hotspots/change_status" -d "hotspot=HOTSPOT_KEY&status=REVIEWED&resolution=FIXED"

# Reopen (back to TO_REVIEW)
curl -s -X POST -u "$SONAR_TOKEN:" "$SONAR_HOST_URL/api/hotspots/change_status" -d "hotspot=HOTSPOT_KEY&status=TO_REVIEW"
```

### Add comment to hotspot

```bash
curl -s -X POST -u "$SONAR_TOKEN:" "$SONAR_HOST_URL/api/hotspots/add_comment" -d "hotspot=HOTSPOT_KEY" --data-urlencode "text=This is safe because input is validated at the API layer."
```

### Bulk resolve hotspots

```bash
# Get hotspot keys from findings export, then resolve each
jq -r '.[] | select(.type == "SECURITY_HOTSPOT" and .status == "TO_REVIEW") | .key' /tmp/findings.json | while read key; do
  curl -s -X POST -u "$SONAR_TOKEN:" "$SONAR_HOST_URL/api/hotspots/change_status" -d "hotspot=$key&status=REVIEWED&resolution=SAFE"
done
```

## Export Metrics

```bash
# Main metrics for all projects
sonar-measures-export -o "${SONAR_ORGANIZATION}" -m _main -f metrics.csv

# With project names and last analysis date
sonar-measures-export -o "${SONAR_ORGANIZATION}" -m _main -n -a -f metrics.csv
```

## Other Commands

```bash
# Audit
sonar-audit -o "${SONAR_ORGANIZATION}" -f audit_report.json --format json 2>/dev/null

# LOC report
sonar-loc -o "${SONAR_ORGANIZATION}" -f loc_report.csv 2>/dev/null

# Sync findings between branches
sonar-findings-sync -o "${SONAR_ORGANIZATION}" -k PROJECT_KEY --sourceBranch main --targetBranch feature/xyz 2>/dev/null
```

## Filter Reference

### Types
- `BUG` - Reliability issues
- `VULNERABILITY` - Security issues
- `CODE_SMELL` - Maintainability issues
- `SECURITY_HOTSPOT` - Security hotspots

### Statuses
`OPEN`, `CONFIRMED`, `REOPENED`, `RESOLVED`, `CLOSED`, `TO_REVIEW`, `REVIEWED`

### Resolutions
`FALSE-POSITIVE`, `WONTFIX`, `FIXED`, `REMOVED`, `ACCEPTED`, `SAFE`

### Severities
`BLOCKER`, `CRITICAL`, `MAJOR`, `MINOR`, `INFO`

## Pitfalls

1. **`--types` flag unreliable** - Export all findings, filter with jq
2. **`-o` flag required** - All CLI commands need `-o "$SONAR_ORGANIZATION"`
3. **Project keys vs names** - Users say names, API needs keys (e.g., `goodhabitz_55014192`)
4. **Large exports** - Filter by project (`-k`) and use `--threads`
5. **Shell variable `status` is read-only** - Use `qg_status` in scripts
6. **ACKNOWLEDGED not supported** - Use SAFE or FIXED instead
7. **Multi-line curl commands fail** - Always use single-line curl commands with `-u "$SONAR_TOKEN:"` (avoid backslash continuations)
8. **sonar-findings-export logs to stderr** - Use `2>/dev/null` to get clean JSON output
9. **Cross-project queries** - Use REST API directly (`/api/hotspots/search`, `/api/issues/search`) instead of sonar-findings-export for multi-project queries
