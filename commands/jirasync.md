---
description: Sync a Jira epic with what merged to main. Moves merged tickets to Done, assigns me where I wrote the merged work, flags Done tickets with nothing merged and tickets with no assignee, then drafts a release recap. Say "dry run" to only list what it would change.
argument-hint: <EPIC-KEY> [dry run]
disable-model-invocation: true
---

# /jirasync

Bring an epic's child tickets in line with the code that merged, then draft a recap of what
shipped. The scope is the one epic named in `$ARGUMENTS`: never touch the epic itself, its
siblings or other projects.

## Step 1: gather the diff

```bash
python3 ~/llmfiles/scripts/jira-sync.py <EPIC-KEY>
```

It takes about a minute, because GitLab's group MR search is slow. Org values come from
`~/llmfiles/local/work.json`. It prints JSON:

- `epic`, `me` (my GitLab username, git email and Jira account ID).
- `tickets`: per key, `summary`, `status`, `done`, `assignee` (`name`, `email`, `account_id`),
  `url`, and `merged[]`: MRs merged to main that name the key, with `ref`, `title`, `url`,
  `author`, `author_username`, `merged_at` and `matched_in` (`title`, `source_branch`,
  `description`). GitLab searches only titles and descriptions, so an MR that names the key
  only in its branch is missing.
- `merged_not_done`, `done_nothing_merged`, `missing_assignee`, `assign_to_me`: key lists.
- `errors`: tickets whose MR lookup failed. Their merged state is unknown, so report them and
  leave them alone.

## Step 2: update the tickets

Call the Skill tool with "twg-jira" for the mechanics, and with "jira-writing" before writing
any comment. With "dry run" in `$ARGUMENTS`, list the changes below and make none.

- **`merged_not_done`**: move to Done when an MR names the key in its title or source branch.
  A key found only in a description is a mention, not proof, so flag that ticket instead.
  Discover the transitions first. When the Done transition needs a field such as Resolution,
  ask me for the value once for all such tickets rather than picking one.
- **`assign_to_me`**: assign the ticket to me. These are tickets where I authored a merged MR
  naming the key in its title or source branch, and someone else or nobody holds the ticket. When someone else holds it, flag it instead,
  since they may have done the rest of the work.
- **`done_nothing_merged`**: flag only. The work may have shipped in an MR that names the key
  only in its branch or not at all, or not needed code.
- **`missing_assignee`** not covered above: flag only, with the MR authors if any merged.

Do not comment on tickets, change other fields or reopen anything.

## Step 3: report and recap

Print one line per change made, then the flags, each with the ticket link:

```
jirasync <EPIC-KEY> - <n> moved to Done, <n> assigned to me, <n> flagged[ (dry run)]
Done: <KEY> <summary>, <MR ref>
Assigned: <KEY> <summary>
Flag: <KEY> <summary>, <why>
```

Then draft a release recap from the merged MRs, for a Slack post or release note: a one-line
headline of what the epic delivered, then one bullet per ticket with merged work, written as
the user-visible result in plain words, with the ticket link. Group by repo only when more than
three repos are involved. Keep it under 15 lines. Print it in a ` ```text ` fence and post it
nowhere.
