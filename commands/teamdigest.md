---
description: Everything a team merged since a date (default 7 days ago) as an Artifact page, the work grouped by Jira epic with unplanned work apart, a TL;DR per repo with prod stats and the changes behind it, flagging what is not in prod yet. Optionally publishes the Slack message too.
argument-hint: "[team] [since <date>] [publish to slack <channel>]"
disable-model-invocation: true
---

# /teamdigest

Write up what a team merged as one Artifact page the whole team reads weekly: engineers, EM
and PM. Readers skim it to see what changed and what is still not in prod, and click through
to the MR or Jira ticket for detail. Keep repo names and technical nouns: the readers are
the team.

Read `~/llmfiles/shared/digest-message.md` for the draft format and how to write its lines.

## Arguments

`$ARGUMENTS` may hold any of these, in any order:

- A team: its Jira key (`PE`, `LI`), its id, or part of its name. Default: `team_id` from
  `~/llmfiles/local/work.json`.
- `since <date>`, or a bare date. Default: 7 days ago.
- `publish to slack <channel>`: also post the Slack message, without asking.

## Draft

```bash
python3 ~/llmfiles/scripts/merge-digest.py --team <team> [--since YYYY-MM-DD]
```

The repos are those only this team owns in the platform directory, plus any repo a member
merged into.

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

- `areas`: `{area: [repo, ...]}`, five to seven areas named by what the work is about
  (`Account and Experts`, `Change data capture`, `Developer tools`), ordered by how much
  merged in them. A repo left out lands in `Other`.
- `tldr`: `{repo: line}`, one or two plain sentences per repo saying what changed for its
  users. Every repo with a change line needs one; repos with only Housekeeping get a default.
- `epics`: `{epic key: line}`, one or two plain sentences per epic from `--list-epics`
  on what moved this period, so a reader connects it to what was planned. Name what is not
  in prod yet or blocked.
- `unplanned`: one or two sentences on what the unplanned work was mostly about.

```bash
python3 ~/llmfiles/scripts/digest-page.py message.md notes.json \
  --title "<KEY> Merge Digest <d>-<d> <Mon>" -o <KEY>-digest.html
```

The script fails on a repo missing its `tldr`. Publish the page as a new Artifact with icon
`list`, and a description naming the team and the period. Reply with the link, the totals,
and the note from below `---`.

## Slack

Only with `publish to slack <channel>`, or when asked after the page: print and publish the
message as `digest-message.md` says, with the page link as its last line.
