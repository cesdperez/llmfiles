---
description: One day of my work as a short Slack-ready standup post, split into team and no-team work, plus private notes. Defaults to yesterday.
disable-model-invocation: true
---

# /dailyworkrecap

Write up what I did on a given day as a Slack post for my team's async daily sync, plus private notes for me.

## Usage

```
/dailyworkrecap              # yesterday (rolls back to Friday over a weekend)
/dailyworkrecap thursday     # most recent past Thursday
/dailyworkrecap 2026-07-30
```

## Audience

Other engineers and my PM, skim-reading an offline daily sync. They want to know what
moved, what is stuck, and what needs them. They do not want the mechanics.

That drives every formatting rule below. When in doubt, cut.

## Org settings

Read `~/llmfiles/local/work.json` (shape in `~/llmfiles/local.example/work.json`). The
`<key>` placeholders below are its values. Also read `~/llmfiles/local/dailyworkrecap-style.md`
if it exists: its sample post replaces the one in step 3, and its gotchas join the list at
the end. Pass the resolved values, never the placeholders, into agent prompts.

## Step 1: gather the hard data

```bash
python3 ~/llmfiles/scripts/daily-work-recap.py $ARGUMENTS
```

Runs in under 10 seconds. Emits JSON:

- `day`, `weekday`: the resolved day. Always report against this, never re-derive it.
- `commits[]`: `repo`, `sha`, `subject`, `on_default_branch`. Deduped by subject across
  branches, so one entry means one piece of work regardless of how many rebases it took.
- `mrs_authored[]`: `ref`, `title`, `state`, `draft`, `url`. Any MR of mine touched that day.
- `review_activity`: `approved`, `commented`, `opened`, `merged`, `closed`, each a list of
  MR refs and titles.
- `mrs_reviewed[]`: distinct MRs I reviewed, my own already filtered out. **This is the
  count to report.** Do not recount from `review_activity`, comments inflate it.
- `jira_keys[]`: every key seen in commit subjects and MR titles.
- `sessions[]`: Claude Code transcripts overlapping the day, for step 2.

If `commits`, `mrs_authored` and `review_activity` are all empty, say the day looks like it
had no code or review activity and carry on with step 2. Do not stop; meetings, analysis
and unblocking still count as work.

## Step 2: spawn agents in parallel

All agents in **one message** so they run concurrently, each a named executor so model and
effort stay pinned. Never do this work yourself sequentially.

**Session agents.** Split `sessions[]` across agents, at most 8 transcripts each, capped at
3 agents. Give each its file list and the script's `window` verbatim plus:

> Read these Claude Code transcripts and report what work happened in them on `<day>`.
> Files: `<paths>`
>
> They are jsonl, one entry per line, each with a `timestamp` (UTC, ISO8601). Parse with
> python3 and stream, do not grep raw lines and do not load whole files, some are megabytes.
> Keep only entries whose timestamp falls on `<day>` in local time, so the window is
> `<window.start>` to `<window.end>`.
>
> Extract the human `user` messages (`type == "user"` where `message.content` is text, not a
> `tool_result`) to get the ask, and enough assistant text to get the outcome.
>
> Return a flat list. One entry per distinct piece of work, not per session. For each:
> what the work was, the service or product area it touched, any Jira keys verbatim
> (`<team_jira_project>-123`, `<other_jira_examples>`), and its state: shipped, in progress, blocked, or
> investigation only. Note explicitly anything that was handed to someone else, anything
> waiting on a decision, and any meeting or discussion that was prepared for.
>
> Then return a second list, `loose_ends`, of work that was started and left hanging.
> Only from evidence in the transcript, never inferred. Look for:
> - a task the session set out to do that has no closing evidence, no passing test, no
>   commit, no MR
> - something deferred out loud: "leave that for later", "I'll do X after", "TODO", a
>   follow-up ticket that was discussed but never created
> - a test, check or pipeline left failing or skipped at the end of the session
> - a question the session raised that was never answered, or a decision it needed and
>   did not get
> - a temporary change meant to be reverted: a hardcoded value, a disabled guard, a
>   commented-out block, debug logging
> - the last session on a piece of work ending mid-task rather than at a clean stop
>
> For each loose end: what is unfinished, which repo or area, any Jira key, and quote or
> paraphrase the transcript evidence. If a later session in your batch picked it back up
> and finished it, drop it. If you are not sure it is still open, say so rather than
> dropping it.
>
> Skip anything that is not `<org_name>` work. Skip tooling and prompt tinkering unless it
> changed something the team uses. Report facts, no editorialising.

**Slack agent.** One agent, with:

> Report what `<slack_user_name>` (`<slack_user_id>`) discussed on Slack on `<day>`, for a team standup.
>
> Load the tools first:
> `ToolSearch("select:mcp__claude_ai_Slack__slack_search_public_and_private,mcp__claude_ai_Slack__slack_read_thread,mcp__claude_ai_Slack__slack_read_channel")`
>
> Run these searches, `sort="timestamp"`, `channel_types="public_channel,private_channel,mpim,im"`:
> - `from:<@<slack_user_id>> after:<day-1> before:<day+1>` returns everything I said
> - `to:<@<slack_user_id>> after:<day-1> before:<day+1>` returns what was asked of me
> - `<@<slack_user_id>> after:<day-1> before:<day+1>` returns where I was mentioned or pinged
> - the same window plus each Jira key in this list: `<jira_keys>`
>
> Slack's `after`/`before` are exclusive, hence the day either side. Drop anything outside
> `<day>`. Read the parent thread when a reply needs context.
>
> Return, grouped by topic not by channel: what he reported as done, what he committed to
> doing, what he flagged as a risk or blocked, what he asked others for and who owes him,
> and any meeting he attended, prepped for or scheduled. Jira keys and MR refs verbatim.
>
> Then return a second list, `unattended`, of things still sitting on him. For each of the
> `to:` and mention hits, read the full thread and check whether he replied at all, before
> or after `<day>`. Report it as unattended when:
> - someone asked him a direct question and he never replied in that thread
> - he was pinged or assigned something and did not acknowledge it
> - he was the last person asked in a thread and the thread stops there
> - he committed to something that day ("I'll look at it", "I'll send it over") with no
>   later message showing he did
>
> For each: who asked, which channel, one line on what they want, the message permalink,
> and how long it has been sitting. Drop it if a reaction emoji from him or a later message
> in the thread shows it was handled. A reply from someone else is not him replying.
>
> Skip personal and social chat, and skip anything unrelated to `<org_name>` work.
>
> Report only meetings a message names. Do not infer others.

**Calendar agent.** One `worker-fast` agent, since attendee lists run to hundreds of addresses:

> Load `ToolSearch("select:mcp__claude_ai_Microsoft_365__outlook_calendar_search")` and call
> it with `query="*"`, `afterDateTime="<day>T00:00:00"`, `beforeDateTime="<day+1>T00:00:00"`,
> `order="oldest"`, `limit=25`, `offset=0`. Page with `nextOffset` if present.
>
> Times come back in the `timeZone` each event names, usually UTC. Convert to `<timezone>`.
> Return one line per event: local start and end, subject, organizer, `isOrganizer`, and the
> attendee count. Drop cancelled events. Mark company-wide ones, where the attendees include
> an all-staff list such as `<all_staff_list>`.

## Step 3: write the Slack post

My team owns the `<team_jira_project>` Jira project. Split the work on that:

- **Team:** anything tied to a `<team_jira_project>-` key, or with no key but clearly the
  same work as a `<team_jira_project>-` item that day.
- **No team:** anything tied to another project's key, keyless work for another
  team, and department-wide work such as preparing or running an Engineering meeting.

Print the post inside a ` ```text ` fence, so the terminal does not render the markup and I
copy the raw characters. Use only the syntax the Slack composer converts on paste:

| Want | Write |
| --- | --- |
| Bold | `*text*` |
| Link | `[text](url)` |
| List | `- item` |

Everything else stays literal in Slack, so no `#` headings, no `**`, no tables, no nested
lists. Write people as plain names: a pasted `@name` does not become a mention.

This is the length and tone I write myself:

```text
Team:
- Password import: identity provider now accepts legacy passwords, tested locally, MRs up [PROJ-493](<jira_base_url>PROJ-493)
- Deployed orders-api to prod, token exchange included

No team:
- Prepared and organized the platform status meeting

Reviews: 5 MRs
```

### Rules

- **Two to six bullets in total.** Cut the least useful item before squeezing two into one.
- **One short line each, about 12 words.** Lead with the topic, not a status word. Drop a
  section or the Reviews line when it is empty.
- **Say the effect, not the mechanism.** "Admin panel changes now reach the identity
  system", not "added a nullable unique column and a set endpoint".
- **No file paths, line numbers, SHAs, branch names, config keys or library versions.**
  The one exception is when the mechanism *is* the news, for example a dependency floating
  across five apps with no test coverage.
- **Reviews are a count only.** Never enumerate MRs or repeat findings. A finding gets its
  own bullet only if the team needs to act on it.
- **One line per Jira ticket.** The same ticket shows up in commits, MRs, Slack and
  sessions; that is one item, and its state is the furthest it got that day.
- **Link every Jira key** as `[PROJ-289](<jira_base_url>PROJ-289)` at
  the end of the line. Link an MR only when it is the deliverable and has no Jira key.
- **Name the person or team when something waits on them.**
- **Plain simple language.** Short sentences, no jargon a PM would have to look up, no
  emoji, no em dashes, no softeners.
- Personal work, prompt and tooling tinkering go to the notes in step 4, not the post.

## Step 4: notes for me

Below the fence, in normal terminal markdown, a block that is never part of the post. It can
name my own sloppiness.

```markdown
**Notes for me**
- Unanswered: <who> asked <what> in <#channel>, no reply in the thread, 2 days. <permalink>
- Left open: <what is unfinished and where> [PROJ-289]
- Said I would, no trace: <what I committed to and to whom>
- Left behind: <hardcoded value, disabled test, debug logging, failing check>
- Also did: <tooling, prompt or personal work cut from the post>

Sources: N commits, N MRs authored, N MRs reviewed, N Claude sessions, Slack, calendar.
```

### Rules

- Loose ends come only from the session agents' `loose_ends` and the Slack agent's
  `unattended`. Do not go looking for extra work to flag.
- **Evidence or nothing.** Every line traces to a transcript quote or a Slack message. No
  "you probably should also". A day with no loose ends prints only the sources line, and that
  is a good outcome, not a sign the search failed.
- **At most four items**, the ones easiest to lose. Drop the rest.
- **Do not repeat the post.** Loose ends are what I would forget, not what I am tracking.
- **Unanswered Slack goes stale, unfinished code does not.** Put the oldest unanswered
  message first, and say how long it has been waiting. Order the rest by how easy they are
  to lose.
- **Flag uncertainty inline** rather than dropping the item: "may already be handled, thread
  stops at my question".
- One line each, about 12 words like the post bullets. Link Jira keys and permalinks.

Then ask whether to draft it in Slack. Never post the notes block.

## Step 5: draft in Slack, on request

Save a draft with `slack_send_message_draft`, never send. It goes as a reply in that day's
async update thread in `<standup_channel.name>` (`<standup_channel.id>`), found by
`<standup_thread_hint>`. Get its `ts` with `slack_read_channel` around
that time, `response_format="detailed"`. The draft tool takes standard markdown, so drop the
Slack-paste `*bold*`. When the recap day is not today, say so before drafting.

## Gotchas

These produced wrong output before. Keep them.

- **The calendar shows invites, not attendance.** The connector has no accepted or declined
  status. A meeting I organized is work and gets a bullet. Others count only when Slack or a
  session shows I took part. Company-wide meetings never make the post.
- **The default day is yesterday, rolled back over a weekend.** The script owns that. Take
  `day` from its output rather than working it out again, or a Monday recap will cover Sunday.
- **Timestamps are UTC, the working day is local.** Transcripts and GitLab events both use
  UTC, so late-afternoon local work lands on the same UTC date but early-morning work does
  not. The script handles the GitLab side; the session agents get the script's `window`.
- **The same commit appears several times under `--all`.** Feature branch, rebase, and the
  copy on the default branch. The script dedupes by subject; do not count raw commits.
- **`review_activity.commented` counts comments, not MRs.** Use `mrs_reviewed` for the count.
- **A merged MR is not automatically shipped.** Check whether the session or Slack evidence
  says it was deployed and verified. When it is merged but unverified, say merged.
- **No Slack reply is not proof of no answer.** I answer in MR comments, in a call, or at a
  desk, and Slack never sees it. Report unanswered messages as "no reply in the thread", and
  let me be the one to say it was handled elsewhere.
- **Loose ends only see one day.** The session agents filter to `<day>`, so work I finished
  the next morning still looks abandoned. Anything whose only evidence is the day ending
  mid-task gets "may already be closed".
- **A loose end that is really a blocker belongs in the post.** If someone else is waiting on
  it, it goes in the post as Blocked, not in my notes where the team never
  sees it.
- **Pasted markup only converts in Slack's default editor.** With "Format messages with
  markup" turned on in Slack preferences, a paste arrives as plain text and the `*` and
  `[text](url)` show literally.
