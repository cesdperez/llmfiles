---
description: Everything the current repo merged into its default branch since a date (default 7 days ago) as an Artifact page, the work grouped by Jira epic with unplanned work apart, a TL;DR per group of changes with prod stats, flagging what is not in prod yet. Optionally publishes the Slack message too.
argument-hint: "[since <date>] [publish to slack <channel>]"
disable-model-invocation: true
---

# /repodigest

Write up what the current repo merged into its default branch as one Artifact page for
engineers in other teams. Readers skim it to see what changed and what is still not in prod,
and click through to the MR or Jira ticket for detail. Say the effect a user of the service
sees, and in the header use the name engineers know the service by (the README usually says).

Read `~/llmfiles/shared/digest-message.md` for the draft format and how to write its lines.

## Arguments

`$ARGUMENTS` may hold either part, in any order:

- `since <date>`, or a bare date. Default: 7 days ago.
- `publish to slack <channel>`: also post the Slack message, without asking.

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

Then write the change lines as `digest-message.md` says, and save the written digest, the
note below `---` included, to `message.md` in the scratchpad.

## Page

Before writing `notes.json`, see which epic each change belongs to:

```bash
python3 ~/llmfiles/scripts/digest-page.py message.md notes.json --list-epics --title x -o /dev/null
```

It reads each ticket's epic through `twg`, and puts lines with no ticket, or whose ticket has
no epic, under unplanned. Write `notes.json` with `{}` first if it does not exist yet.

Write `notes.json` next to it:

- `groups`: `{group: {"tldr": line, "mrs": ["!12", ...]}}`, three to seven groups named by
  the part of the service a user knows (`Licences`, `Login`, `Change data capture`), ordered
  by how much merged in them. A change line joins the group that lists its first MR, so
  list one MR of every line. The `tldr` is one or two plain sentences on what changed for
  the service's users. Housekeeping lines get their own group.
- `epics`: `{epic key: line}`, one or two plain sentences per epic from `--list-epics`
  on what moved this period, so a reader connects it to what was planned. Name what is not
  in prod yet or blocked.
- `unplanned`: one or two sentences on what the unplanned work was mostly about.

```bash
python3 ~/llmfiles/scripts/digest-page.py message.md notes.json [--no-prod-check] \
  --title "<Service> Merge Digest <d>-<d> <Mon>" -o <service>-digest.html
```

Pass `--no-prod-check` for a GitHub draft. The script fails when a change line lands in no
group. Publish the page as a new Artifact with icon `list`, and a description naming the
service and the period. Reply with the link, the totals, and the note from below `---`.

## Slack

Only with `publish to slack <channel>`, or when asked after the page: print and publish the
message as `digest-message.md` says, with the page link as its last line.
