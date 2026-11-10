---
description: Everything the current repo merged into its default branch since a date (default 7 days ago) as one short Slack message, one line per change, flagging what is not in prod yet. Optionally publishes it to a Slack channel.
argument-hint: "[since <date>] [publish to slack <channel>]"
disable-model-invocation: true
---

# /repodigest

Write up what the current repo merged into its default branch as one Slack message for
engineers in other teams. Readers skim it to see what changed and what is still not in prod,
and click through to the MR or Jira ticket for detail. Say the effect a user of the service
sees, and in the header use the name engineers know the service by (the README usually says).

Read `~/llmfiles/shared/digest-message.md` for the draft format and the steps after it.

## Arguments

`$ARGUMENTS` may hold either part, in any order:

- `since <date>`, or a bare date. Default: 7 days ago.
- `publish to slack <channel>`: publish after printing, without asking.

## Draft

Read the host and project path from `git remote get-url origin`.

GitLab:

```bash
python3 ~/llmfiles/scripts/merge-digest.py --repo <project path> [--since YYYY-MM-DD]
```

GitHub has no prod check. Build the draft in the same format from the list below, without
`:waiting:` marks:

```bash
gh pr list --state merged --search "merged:>=<since>" --limit 200 --json number,title,url
```

Then write, print and publish as `digest-message.md` says.
