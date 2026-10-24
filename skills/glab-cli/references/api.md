# Working Outside a Git Repository (glab api)

Most `glab` commands require being inside a git repository. Use the API directly for
cross-project operations.

## Environment Variables

| Variable | Purpose |
|----------|---------|
| `GITLAB_TOKEN` | API authentication token |
| `GITLAB_HOST` | Self-hosted GitLab URL |
| `BROWSER` | Browser for `--web` |

## List All Your Open MRs (Global)

```bash
# List all open MRs you created across all projects
glab api "merge_requests?scope=created_by_me&state=opened" --paginate

# Format nicely with jq
glab api "merge_requests?scope=created_by_me&state=opened" --paginate | \
    jq -r '.[] | "\(.iid)\t\(.title)\t\(.web_url)"'
```

### Common API Scopes for MRs

| Scope | Description |
|-------|-------------|
| `created_by_me` | MRs you authored |
| `assigned_to_me` | MRs assigned to you |
| `review_requests_for_me` | MRs awaiting your review |

## Close/Update MR via API

Project paths must be URL-encoded (slashes become `%2F`):

```bash
# Close an MR
glab api --method PUT "projects/acme%2Fbackend%2Fmy-project/merge_requests/123" \
    -f state_event=close

# Reopen an MR
glab api --method PUT "projects/acme%2Fbackend%2Fmy-project/merge_requests/123" \
    -f state_event=reopen
```

## Enumerating a Group's Projects

`glab repo list -g <group>` only lists projects directly in the group; nested subgroups are
skipped unless you pass `-G`. For anything that must be complete, go through the API:

```bash
# Every active project in a group, subgroups included, one JSON object per line
glab api "groups/<group>/projects?per_page=100&include_subgroups=true&active=true" \
    --paginate --output ndjson

# Just the clone URLs, keyed by path
glab api "groups/<group>/projects?per_page=100&include_subgroups=true&active=true" \
    --paginate --output ndjson | jq -r '"\(.path_with_namespace)\t\(.ssh_url_to_repo)"'
```

Key parameters:

| Parameter | Effect |
|-----------|--------|
| `include_subgroups=true` | Recurse into nested subgroups (otherwise top level only) |
| `active=true` | Exclude archived **and** pending-deletion projects in one query |
| `archived=false` | Excludes archived but still returns pending-deletion projects |
| `per_page=100` | Max page size; pair with `--paginate` |

Prefer `active=true` over `archived=false`. Projects marked for deletion keep a
`-deletion_scheduled-<id>` suffix on their path and are not archived, so `archived=false`
still returns them and they end up in clone lists as stale duplicates.

`--output ndjson` emits one object per line across all pages, which is what you want for
streaming into `jq` or a script. Plain `--paginate` concatenates separate JSON arrays.
