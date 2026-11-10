---
description: Everything a team merged since a date (default 7 days ago) as one short Slack message, one line per change, flagging what is not in prod yet. Optionally publishes it to a Slack channel.
argument-hint: "[team] [since <date>] [publish to slack <channel>]"
disable-model-invocation: true
---

# /teamdigest

Write up what a team merged as one Slack message the whole team reads weekly: engineers, EM
and PM. Readers skim it to see what changed and what is still not in prod, and click through
to the MR or Jira ticket for detail. Keep repo names and technical nouns: the readers are
the team.

Read `~/llmfiles/shared/digest-message.md` for the draft format and the steps after it.

## Arguments

`$ARGUMENTS` may hold any of these, in any order:

- A team: its Jira key (`PE`, `LI`), its id, or part of its name. Default: `team_id` from
  `~/llmfiles/local/work.json`.
- `since <date>`, or a bare date. Default: 7 days ago.
- `publish to slack <channel>`: publish after printing, without asking.

## Draft

```bash
python3 ~/llmfiles/scripts/merge-digest.py --team <team> [--since YYYY-MM-DD]
```

The repos are those only this team owns in the platform directory, plus any repo a member
merged into.

Then write, print and publish as `digest-message.md` says.
