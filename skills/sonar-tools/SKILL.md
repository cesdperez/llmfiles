---
name: sonar-tools
description: Manage and query SonarQube/SonarCloud projects, issues, and hotspots using the Web API. Use when the user wants to list failing projects, find security vulnerabilities, or handle hotspots from the CLI.
---

# Sonar Tools (API Wrapper)

## Overview
This skill provides command patterns to interact with the SonarQube/SonarCloud Web API using `curl` and `jq`. Since there is no official CLI for these management tasks, direct API access is the standard approach.

## Prerequisites
- **curl**: For making API requests.
- **jq**: For parsing and filtering JSON output.
- **Sonar Token**: A user token with appropriate permissions.
- **Env Vars**: Set `SONAR_TOKEN` and `SONAR_HOST` (e.g., `https://sonarcloud.io` or `http://localhost:9000`) for easier commands.

## Key Patterns
- **Authentication**: Usage of `-u $SONAR_TOKEN:` (note the trailing colon).
- **Pagination**: Most list endpoints default to minimal page size. Add `&ps=500` to fetch more items.
- **Filtering**: Heavy use of `jq` to transform raw JSON into readable tables.

## Commands

### 1. Projects & Quality Gates

#### List Projects Failing Quality Gate
Finds all projects (TRK) where the Quality Gate status (`alert_status`) is ERROR.

```bash
curl -s -u "${SONAR_TOKEN}:" "${SONAR_HOST}/api/measures/search?metricKeys=alert_status&qualifiers=TRK&ps=500" | \
  jq -r '.components[] | select(.measures[0].value == "ERROR") | "\(.key) - \(.name)"'
```

#### Get Specific Project Status
```bash
curl -s -u "${SONAR_TOKEN}:" "${SONAR_HOST}/api/qualitygates/project_status?projectKey=MY_PROJECT_KEY" | \
  jq -r .projectStatus.status
```

### 2. Issues (Vulnerabilities, Bugs, Code Smells)

#### List Security Issues (Vulnerabilities)
Lists all open vulnerabilities for a project.

```bash
# Types: VULNERABILITY, BUG, CODE_SMELL
curl -s -u "${SONAR_TOKEN}:" "${SONAR_HOST}/api/issues/search?componentKeys=MY_PROJECT_KEY&types=VULNERABILITY&resolved=false" | \
  jq -r '.issues[] | "\(.key) | \(.message) | \(.severity) | File: \(.component)"'
```

#### List Maintainability Issues (Code Smells)
```bash
curl -s -u "${SONAR_TOKEN}:" "${SONAR_HOST}/api/issues/search?componentKeys=MY_PROJECT_KEY&types=CODE_SMELL&resolved=false&ps=100" | \
  jq -r '.issues[] | "\(.key) | \(.message) | \(.severity)"'
```

### 3. Security Hotspots

#### List Hotspots to Review
Hotspots are separate from Issues. This finds all hotspots in `TO_REVIEW` status.

```bash
curl -s -u "${SONAR_TOKEN}:" "${SONAR_HOST}/api/hotspots/search?projectKey=MY_PROJECT_KEY&status=TO_REVIEW&ps=500" | \
  jq -r '.hotspots[] | "\(.key) | \(.message) | \(.component)"'
```

#### Show Hotspot Details
Get full details including the code snippet (if available).
```bash
curl -s -u "${SONAR_TOKEN}:" "${SONAR_HOST}/api/hotspots/show?hotspot=HOTSPOT_KEY" | jq .
```

### 4. Resolving & Commenting

#### Review a Hotspot (Resolve)
Change status to `REVIEWED` and set resolution (e.g., `FIXED`, `SAFE`).

```bash
# Mark as Fixed
curl -s -u "${SONAR_TOKEN}:" -X POST "${SONAR_HOST}/api/hotspots/change_status" \
  -d "hotspot=HOTSPOT_KEY" \
  -d "status=REVIEWED" \
  -d "resolution=FIXED" \
  -d "comment=Fixed in commit xyz"

# Mark as Safe (False Positive/Accepted Risk)
curl -s -u "${SONAR_TOKEN}:" -X POST "${SONAR_HOST}/api/hotspots/change_status" \
  -d "hotspot=HOTSPOT_KEY" \
  -d "status=REVIEWED" \
  -d "resolution=SAFE" \
  -d "comment=Investigated and determined safe because X"
```

## Common Workflows

### Audit Workflow
1. **Find failing projects**: Run the "List Projects Failing Quality Gate" command.
2. **Pick a project**: Export `PROJECT_KEY=...`.
3. **Check Critical Vulnerabilities**:
   ```bash
   curl -s -u "${SONAR_TOKEN}:" "${SONAR_HOST}/api/issues/search?componentKeys=${PROJECT_KEY}&types=VULNERABILITY&severities=CRITICAL,BLOCKER&resolved=false" | \
   jq -r '.issues[] | "\(.message) (\(.key))"'
   ```

### Review Workflow
1. **List open hotspots**: Run the hotspot list command.
2. **Review one**: Take a key and mark it as safe.
   ```bash
   curl -s -u "${SONAR_TOKEN}:" -X POST "${SONAR_HOST}/api/hotspots/change_status" \
     -d "hotspot=HOTSPOT_KEY" -d "status=REVIEWED" -d "resolution=SAFE"
   ```

## Pitfalls to Avoid
1. **Pagination Limits**: The API defaults to 100 items usually. Always check `paging.total` in the JSON response. Use `&p=2` to get subsequent pages if total > ps.
2. **Token Scope**: Ensure your token has 'Browse' permissions on the projects and 'Administer Issues' if you are resolving them.
3. **Host URL**: Don't forget the scheme (`https://`). For SonarCloud, use `https://sonarcloud.io`.
4. **Hotspots vs Issues**: Remember `api/issues/search` does **not** return hotspots. You must use `api/hotspots/search`.
