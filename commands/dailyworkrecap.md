---
description: One day of my GoodHabitz work written up as a short async standup update for my team. Defaults to yesterday.
---

# /dailyworkrecap

Write up what I did on a given day as an async daily sync post for my team.

## Usage

```
/dailyworkrecap              # yesterday (rolls back to Friday over a weekend)
/dailyworkrecap 2026-07-30
```

## Audience

Other engineers and my PM, skim-reading an offline daily sync. They want to know what
moved, what is stuck, and what needs them. They do not want the mechanics.

That drives every formatting rule below. When in doubt, cut.

## Step 1 — gather the hard data

```bash
python3 ~/llmfiles/scripts/daily-work-recap.py $ARGUMENTS
```

Runs in under 10 seconds. Emits JSON:

- `day`, `weekday` — the resolved day. Always report against this, never re-derive it.
- `commits[]` — `repo`, `sha`, `subject`, `on_default_branch`. Deduped by subject across
  branches, so one entry means one piece of work regardless of how many rebases it took.
- `mrs_authored[]` — `ref`, `title`, `state`, `draft`, `url`. Any MR of mine touched that day.
- `review_activity` — `approved`, `commented`, `opened`, `merged`, `closed`, each a list of
  MR refs and titles.
- `mrs_reviewed[]` — distinct MRs I reviewed, my own already filtered out. **This is the
  count to report.** Do not recount from `review_activity`, comments inflate it.
- `jira_keys[]` — every key seen in commit subjects and MR titles.
- `sessions[]` — Claude Code transcripts overlapping the day, for step 2.

If `commits`, `mrs_authored` and `review_activity` are all empty, say the day looks like it
had no code or review activity and carry on with step 2. Do not stop; meetings, analysis
and unblocking still count as work.

## Step 2 — spawn agents in parallel

All agents in **one message** so they run concurrently. Never do this work yourself
sequentially.

**Session agents.** Split `sessions[]` across agents, at most 8 transcripts each, capped at
3 agents. Give each its file list verbatim plus:

> Read these Claude Code transcripts and report what work happened in them on `<day>`.
> Files: `<paths>`
>
> They are jsonl, one entry per line, each with a `timestamp` (UTC, ISO8601). Parse with
> python3 and stream, do not grep raw lines and do not load whole files, some are megabytes.
> Keep only entries whose timestamp falls on `<day>` in local time (CEST, UTC+2), so the
> window is `<day-1>T22:00:00Z` to `<day>T22:00:00Z`.
>
> Extract the human `user` messages (`type == "user"` where `message.content` is text, not a
> `tool_result`) to get the ask, and enough assistant text to get the outcome.
>
> Return a flat list. One entry per distinct piece of work, not per session. For each:
> what the work was, the service or product area it touched, any Jira keys verbatim
> (`PE-123`, `CPT-45`, `IS-41`), and its state: shipped, in progress, blocked, or
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
> Skip anything that is not GoodHabitz work. Skip tooling and prompt tinkering unless it
> changed something the team uses. Report facts, no editorialising.

**Slack agent.** One agent, with:

> Report what César Pérez (`U037FVCT98F`) discussed on Slack on `<day>`, for a team standup.
>
> Load the tools first:
> `ToolSearch("select:mcp__claude_ai_Slack__slack_search_public_and_private,mcp__claude_ai_Slack__slack_read_thread,mcp__claude_ai_Slack__slack_read_channel")`
>
> Run these searches, `sort="timestamp"`, `channel_types="public_channel,private_channel,mpim,im"`:
> - `from:<@U037FVCT98F> after:<day-1> before:<day+1>` — everything he said
> - `to:<@U037FVCT98F> after:<day-1> before:<day+1>` — what was asked of him
> - `<@U037FVCT98F> after:<day-1> before:<day+1>` — where he was mentioned or pinged
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
> Skip personal and social chat, and skip anything unrelated to GoodHabitz work.
>
> There is no calendar bot in this workspace, so meetings only exist here if a human
> mentioned one. Do not infer meetings that were not mentioned.

## Step 3 — write the recap

One line per item. Every section optional, drop the ones with nothing in them.

```markdown
## Daily recap — <Weekday> <D Month>

**Shipped**
- <what is now live or merged, and what it means for users or the team> [PE-123]

**In progress**
- <what is underway and what is left>

**Reviews**
- Reviewed N MRs across <repo>, <repo> and <repo>.

**Flagged**
- <bug filed, risk called out, or something the team should know> [PE-124]

**Blocked / needs someone**
- <what is stuck and who or what unblocks it>

**Meetings and discussions**
- <meeting or thread, and the outcome>
```

### Rules

- **One line each, roughly 15 words.** If it needs two lines it needs to be two items, or
  it does not belong in a standup.
- **Say the effect, not the mechanism.** "Admin panel changes now reach the identity
  system", not "added a nullable unique column and a set endpoint".
- **No file paths, line numbers, SHAs, branch names, config keys or library versions.**
  The one exception is when the mechanism *is* the news, for example a dependency floating
  across five apps with no test coverage.
- **Reviews are a count, not a list.** Number of MRs plus the repos. Never enumerate them,
  never say which I approved or did not approve, never repeat review findings. Findings only
  graduate to **Flagged** if the team needs to act on them.
- **One line per Jira ticket.** The same ticket shows up in commits, MRs, Slack and
  sessions; that is one item, and its state is the furthest it got that day.
- **Link every Jira key** as `[PE-289](https://goodhabitz.atlassian.net/browse/PE-289)`.
  Link an MR only when it is the deliverable and has no Jira key.
- **Name people when something is waiting on them.** That is the point of the blocked
  section.
- **Plain simple language.** Short sentences, no jargon a PM would have to look up, no
  emoji, no em dashes, no softeners.
- Skip personal work, prompt and tooling tinkering, and anything not worth another
  engineer's attention.

Close with a one-line source footer, so gaps are visible:
`Sources: N commits, N MRs authored, N MRs reviewed, N Claude sessions, Slack.`

## Step 4 — loose ends, for me only

Below the footer, separated by a rule, list what the day left open. This is not part of the
post. It is my own follow-up list, so it can name my own sloppiness.

```markdown
---

**Loose ends (not part of the post)**
- Unanswered: <who> asked <what> in <#channel>, no reply from me. <permalink>
- Left open: <what is unfinished and where> [PE-289]
- Said I would, no trace: <what I committed to and to whom>
- Left behind: <hardcoded value, disabled test, debug logging, failing check>
```

### Rules

- Sources are the session agents' `loose_ends` and the Slack agent's `unattended`. Nothing
  else. Do not go looking for extra work to flag.
- **Evidence or nothing.** Every line traces to a transcript quote or a Slack message. No
  "you probably should also". A day with no loose ends prints nothing here, and that is a
  good outcome, not a sign the search failed.
- **Do not repeat the post.** Something already in **In progress** or **Blocked** is not a
  loose end. Loose ends are what I would forget, not what I am tracking.
- **Unanswered Slack goes stale, unfinished code does not.** Put the oldest unanswered
  message first, and say how long it has been waiting. Order the rest by how easy they are
  to lose.
- **Flag uncertainty inline** rather than dropping the item: "may already be handled, thread
  stops at my question".
- One line each, same 15-word budget. Link Jira keys and permalinks.

Then ask if I want the recap adjusted or posted anywhere. Do not post it anywhere unless I
ask, and never post the loose ends block.

## Gotchas

These produced wrong output before. Keep them.

- **There is no calendar source.** Outlook here runs in web mode, its local store has zero
  accounts and zero cached events, and AppleScript against it times out. There is no Outlook
  or calendar bot in Slack either. Meetings come only from what people mentioned in Slack.
  Never guess at a calendar, and never claim a day's meetings are complete.
- **The default day is yesterday, rolled back over a weekend.** The script owns that. Take
  `day` from its output rather than working it out again, or a Monday recap will cover Sunday.
- **Timestamps are UTC, the working day is local.** Transcripts and GitLab events both use
  UTC, so late-afternoon CEST work lands on the same UTC date but early-morning work does
  not. The script handles the GitLab side; the session agents are told the window explicitly.
- **The same commit appears several times under `--all`.** Feature branch, rebase, and the
  copy on the default branch. The script dedupes by subject; do not count raw commits.
- **`review_activity.commented` counts comments, not MRs.** Use `mrs_reviewed` for the count.
- **A merged MR is not automatically shipped.** Check whether the session or Slack evidence
  says it was deployed and verified. When it is merged but unverified, say merged.
- **A fix can be merged and still inert.** Some Experts work does nothing until the Zitadel
  cutover lands. Say so on the same line rather than reporting it as delivered.
- **No Slack reply is not proof of no answer.** I answer in MR comments, in a call, or at a
  desk, and Slack never sees it. Report unanswered messages as "no reply in the thread", and
  let me be the one to say it was handled elsewhere.
- **Loose ends only see one day.** The session agents filter to `<day>`, so work I finished
  the next morning still looks abandoned. Anything whose only evidence is the day ending
  mid-task gets "may already be closed".
- **A loose end that is really a blocker belongs in the post.** If someone else is waiting on
  it, it goes in **Blocked / needs someone**, not in my private list where the team never
  sees it.
