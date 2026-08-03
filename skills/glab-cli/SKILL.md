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

### Writing MR Text

Applies to every comment, thread reply, and description, whether written by a command or
ad-hoc. Comments and descriptions get read by busy people, often on a phone. Concise,
direct, human.

- Lead with the point. First sentence says what is wrong or what changed, not how you
  found it.
- No preamble, no restating the question, no closing summary of what you just said.
- Comments: 1 to 3 sentences, one finding each. Hard ceiling of 4 lines. Past that, split
  it or move it to the summary comment. Never paste the code the comment is anchored to.
- Severity once, up front, as a tag: `Blocking:`, `Nit:`, or nothing. Do not re-argue it
  in the body.
- No softeners bolted onto a finding: "Happy to be wrong", "happy either way", "just a
  thought", "not a blocker but". If a claim has a condition, write the condition:
  "Unless something outside the repo reads these keys, this path is dead."
- Name mechanics plainly. Not "the config knob that used to drive them is now inert" but
  "`WebSessionRefreshRate` no longer does anything." Avoid inert, knob, lever, rides
  along, cuts against.
- Descriptions: what changed, then why. Bullets over paragraphs. Link the ticket, do not
  retell it. No Testing section unless there is something non-obvious to run.
- No filler adjectives (comprehensive, robust, seamless), no hedge stacks (might
  possibly), no emoji, no em dashes.
- Plain words: "use" not "utilize", "so" not "in order to".
- Say it once. If the diff shows it, do not narrate it.
- End every comment and thread reply with this signature after a blank line:
  `_🤖 Comment made by Claude <model> (<thinking level>)_`. Infer both at runtime: the
  model name from the session's environment context, the thinking level from session
  context if stated, else `effortLevel` in `~/.claude/settings.json` (the saved default;
  a per-session override wins when known). Drop the parenthetical if undeterminable.
  This signature is the one place an emoji is allowed.

```
Bad:  "I was reviewing and noticed that it looks like there might potentially be an
      issue where the email parameter could possibly be concatenated directly..."
Good: "`email` goes straight into the command text, so a quote breaks the query.
      Parameterize it."
```

Length is where this goes wrong most often. A comment that verifies a claim does not have
to show the verification:

```
Bad:  "Expiry semantics change here, and the config knob that used to drive them is now
      inert. Old behaviour was a sliding expiration of RefreshRate (WebSessionRefreshRate
      / MobileSessionRefreshRate = 60s in appsettings) with GetOrCreate. New behaviour is
      an absolute ShortDuration (5 min, Startup.cs:520-521) with SetAsync, i.e. always
      overwrite. Those two settings no longer influence cache retention at all. Impact is
      near-zero because these caches are write-only [...] Happy to be wrong if there's an
      out-of-repo consumer reading these keys."
Good: "Sliding 60s (`WebSessionRefreshRate`) becomes absolute 5 min, and that setting now
      does nothing. Nothing reads these keys, so unless something outside the repo does,
      delete these writers instead of porting them."
```

### MR Creation Defaults

Always include these flags when creating MRs:
- `--remove-source-branch` - Delete branch when merged
- `--squash-before-merge` - Squash commits when merged
- `--yes` - Skip confirmation prompts
- `--assignee @me` - Assign to the current user

**MR Title Format**: Conventional Commits, with the Jira code as the scope:
`type(PROJ-123): description`, e.g. `fix(PE-209): correct OTLP receiver hostname`.
Applies to commit titles too.

Not `PROJ-123 fix: description` and not a bare `PROJ-123` prefix. Confirmed by
Sajad Hashemian on 2026-06-30.

If the user does not give a Jira code, ask. If there is none, omit the scope:
`fix: correct OTLP receiver hostname`.

### Create MR

```bash
# Standard MR creation
glab mr create \
    --title "<title>" \
    --description "<description>" \
    --assignee @me \
    --remove-source-branch \
    --squash-before-merge \
    --yes

# Auto-fill from commits
glab mr create --fill \
    --assignee @me \
    --remove-source-branch \
    --squash-before-merge \
    --yes

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
glab mr note create <mr_id> -m "Comment"  # Add comment (new discussion thread)
```

### Comments & Discussion Threads

As of glab 1.107.0 (`mr note` is currently EXPERIMENTAL) you can reply into an
existing thread and comment directly on diff lines, not just post root-level
notes. `mr note create` starts a new resolvable discussion by default.

```bash
# List discussions to get their IDs (needed for --reply)
glab mr note list <mr_id>                  # human-readable (same as `mr view --comments`)
glab mr note list <mr_id> -F json | jq '.[] | {id, body: .notes[0].body}'
glab mr note list <mr_id> --state unresolved   # only unresolved threads
glab mr note list <mr_id> --type diff          # only diff comments
glab mr note list <mr_id> --file src/main.go   # threads on one file

# `note list` includes activity events as discussions ("assigned to @x", "requested
# review from @y", "changed the description"). They have no `position` and are not
# review feedback. Filter them out before acting on "the comments on this MR":
glab mr note list <mr_id> -F json \
  | jq -r '.[] | select(.notes[0].system != true)
           | "\(.id) \(.notes[0].position.new_path // "-"):\(.notes[0].position.new_line // "-")\n\(.notes[0].body)"'

# Reply into an existing thread (discussion ID, or a prefix of >=8 chars)
glab mr note create <mr_id> --reply abc12345 -m "I agree!"

# Diff comments: anchor to a file/line in the latest diff version
glab mr note create <mr_id> --file main.go --line 42 -m "Needs refactoring"
glab mr note create <mr_id> --file main.go --line 10:15 -m "Extract this block"  # multiline range
glab mr note create <mr_id> --file main.go --old-line 7 -m "Why removed?"        # removed (old) side
glab mr note create <mr_id> --file main.go -m "File-level comment"               # no line

# Non-resolvable note for bots/CI status (won't block "all threads resolved")
glab mr note create <mr_id> -m "Build: green" --resolvable=false
glab mr note create <mr_id> -m "LGTM" --unique   # skip if identical note exists
```

Flag rules: `--line`/`--old-line` require `--file` and can't combine; `--file`,
`--reply`, and `--unique` are mutually exclusive; `--resolvable=false` can't
combine with `--reply` or `--file`.

Consequence worth internalizing: since `--resolvable=false` can't combine with
`--file`, **every diff comment is a resolvable thread**, so it can gate merge in
projects requiring "all threads resolved". Only root-level notes can be made
non-resolvable.

### Thread Management (glab >= 1.109)

```bash
glab mr note resolve <mr_id> <discussion_id>       # resolve a thread
glab mr note reopen  <mr_id> <discussion_id>       # un-resolve
glab mr note update  <mr_id> <note_id> -m "..."    # edit a note body
```

**`resolve`/`reopen` take the MR id FIRST.** Their `--help` USAGE line claims
`<discussion-id> [<id>|<branch>]`, but that order fails with
`No open merge request available for "<discussion_id>"`. Their own EXAMPLES show
the working order, MR id first. Verified on glab 1.109.0. Do not trust the USAGE
line, and do not assume shape-based disambiguation.

`resolve`/`reopen` also accept an integer **note** id in the discussion slot and
resolve its parent discussion, so a note id returned by `note create` is enough to
resolve the thread it started. Discussion ids accept an 8+ character prefix.

`update` and `delete` do **not** disambiguate safely either. `glab mr note delete` USAGE
says `<note-id> [<id>|<branch>]` while its own examples say the opposite, and both
arguments are numeric. Use the raw API for deletion, and verify with `note list`
after any update:

```bash
glab api --method DELETE "projects/<url_encoded_path>/merge_requests/<mr_id>/notes/<note_id>"
glab api --method PUT    "projects/<url_encoded_path>/merge_requests/<mr_id>/notes/<note_id>" -f body="..."
```

### Suggestions (one-click fixes)

A diff comment containing a `suggestion` block renders an Apply button, letting the
author commit the fix without leaving the MR. New-side anchors only, not
`--old-line`.

````bash
glab mr note create <mr_id> --file src/db.cs --line 45 -m "Parameterize this query.

\`\`\`suggestion:-0+0
        cmd.CommandText = \"SELECT * FROM Users WHERE Email = @email\";
\`\`\`"
````

`suggestion:-0+0` replaces only the anchored line. The offsets extend the replaced
range above and below, so `-1+2` replaces the preceding line, the anchor, and the
two following. **The block must contain the complete replacement for every line in
that range at the file's real indentation**: a block that omits a covered line
silently deletes it on apply. Read the actual lines before writing the block.

### Posting Diff Comments Reliably

**Derive line numbers mechanically, never by counting hunk lines by eye.** This
emits `path:new_line<TAB>content` for every added line, which is the anchor set:

```bash
git diff --unified=0 <base>..<head> | awk '
  /^\+\+\+ /{p=substr($0,7); next}
  /^@@ /{match($0,/\+[0-9]+/); n=substr($0,RSTART+1,RLENGTH-1)+0; next}
  /^\+/{ if (p != "dev/null") print p":"n"\t"substr($0,2); n++ }
'
```

**Diff comments are not idempotent**, because `--file` excludes `--unique`. Before
posting a batch, list what already exists and skip anchors already covered:

```bash
glab mr note list <mr_id> --type diff -F json \
  | jq -r '.[].notes[] | select(.author.username=="<me>")
           | "\(.position.new_path):\(.position.new_line)\t\(.body[0:80])"'
```

**`ok noted !create` is cosmetic** and does not confirm the anchor resolved. An
anchor that fails to match the latest diff version silently degrades to a
file-level or root-level note. Verify placement:

```bash
glab mr note list <mr_id> --type diff -F json \
  | jq -r '.[].notes[] | "\(.position.new_path):\(.position.new_line // "-")"'
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

`glab ci status` streams and waits by default. Pass `--live=false` for a single
snapshot, which is what you want when polling from a script. Its last line is
`Pipeline state: <running|success|failed|canceled>`:

```bash
for i in $(seq 1 60); do
  case "$(glab ci status --live=false 2>/dev/null | awk '/Pipeline state:/{print $3}')" in
    success|failed|canceled) break;;
  esac
  sleep 20
done
glab ci status --live=false | tail -25
```

Bound the loop. `glab ci status` fails outside a git repo (and on any auth or network
error), which prints nothing, matches no state, and turns an `until` into an infinite
spin. The failure mode is a hung command, not an error.

**A "failed" pipeline is not always a blocking failure.** Jobs with
`allow_failure: true` show as failed without gating the merge, so read the job list
before reporting a break. `allow_failure` is not in `ci status` output, so get it
from the API:

```bash
glab api "projects/<url_encoded_path>/pipelines/<pipeline_id>/jobs?per_page=100" \
  --paginate --output ndjson | jq -r 'select(.status=="failed") | "\(.name)\tallow_failure=\(.allow_failure)\t\(.id)"'
```

Note the pipeline SHA in `ci status` will not match your pushed commit when merged
results pipelines are enabled: it is the simulated merge commit, not your HEAD.

## Common Workflows

### Create MR for Current Branch

```bash
# Push and create MR in one step
glab mr create \
    --fill \
    --assignee @me \
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
# When a pipeline is running, auto-merge is enabled by default (merge-when-pipeline-succeeds).
# Pass --auto-merge=false to merge immediately.
```

### Check Pipeline Before Merge

```bash
glab ci status
glab mr view <mr_id> --output json | jq '.pipeline'
# mr list/view also accept a built-in --jq to filter JSON without piping:
glab mr view <mr_id> --output json --jq '.pipeline'
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

### Enumerating a Group's Projects

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

## Pitfalls to Avoid

1. **Forgetting `--yes` in scripts** - Without it, commands prompt for confirmation
2. **Not pushing before MR** - Use `--fill` which auto-pushes, or push manually first
3. **Squash flag timing** - `--squash-before-merge` is on create/update, `--squash` is on merge
4. **Assignee modification** - Use `+` to add, `-` to remove, or plain to replace all
5. **JSON parsing** - Use `--output json` not `--json`
6. **GitHub CLI flag confusion** - Use `--description` for MR body, not `--body` (which is gh's syntax)
7. **Not in a git repo** - Use `glab api` for cross-project operations when outside a repo
8. **Missing subgroup projects** - `glab repo list -g` needs `-G` to recurse; use `glab api groups/<g>/projects?include_subgroups=true` when completeness matters
9. **Stale pending-deletion repos** - Filter with `active=true`, not `archived=false`
