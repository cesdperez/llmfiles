---
description: Report every MR waiting on my review, with difficulty and quality ratings, a suggested action, findings, and open comment threads.
---

# /glabsummary

Report every MR waiting on my review, with a difficulty and quality rating, a suggested action, findings, and open comment threads.

## Usage

```
/glabsummary
```

## Scope

Include an MR only if **all** of these hold:
- state is `opened`
- I am a requested **reviewer**
- it is **not** a draft / WIP
- I have **not** already approved it
- it has had **activity in the last 30 days**

Deliberately out of scope:
- **Merge conflicts.** GitLab blocks the merge regardless, so assume the author will rebase. Do not report `has_conflicts` or `need_rebase` and never downgrade quality for it.
- **Stale MRs**, measured on `updated_at`, not `created_at`. An MR opened months ago but discussed this week is live work and stays in the report; one nobody has touched in a month is dead weight and drops out. Do not substitute creation date for this.
- MRs I authored.

## Step 1 — Build the queue

```bash
python3 ~/.claude/scripts/glab-review-queue.py
```

Pass `--max-idle-days N` to widen or tighten the staleness window (`0` disables it) when I ask for a full sweep or a tighter one.

Emits JSON: `{user, max_idle_days, total_assigned, skipped: {draft, idle, already_approved_by_me}, stale: [...], queue: [...]}`. Each queue entry carries `iid`, `project`, `title`, `url`, `author`, `created`, `updated`, `branch`, `description`, `approvals` ("given/required"), `approved_by`, `merge_status`, `pipeline`, `diff` (file count, +/-, per-path breakdown sorted by churn), `open_threads`, and `local_repo` (absolute path to the local clone, or `null`).

The script already applies every scope rule above, so **do not re-filter**. If `queue` is empty, report the empty queue with the skip counts and stop.

The `skipped` counts are non-overlapping and applied in order (draft → idle → already approved), so an MR that is both stale and already approved counts only as idle. That makes `already_approved_by_me` shift when the window changes; it is not a bug.

If an entry has a non-null `degraded`, an API call failed and that MR is in the queue with unverified approval state. Surface it in the report rather than presenting the numbers as solid.

## Step 2 — Analyse each MR with parallel agents

Spawn **one `general-purpose` agent per queue entry, all in a single message** so they run concurrently. Cap at 8 per batch; if the queue is larger, run further batches. Never analyse them yourself sequentially.

Give each agent the entry's JSON verbatim plus this brief:

> Analyse GitLab MR `<project>!<iid>` (`<url>`) and return a rating. You are one of several agents each covering one MR; return data, not prose.
>
> Read the diff:
> ```bash
> glab api "/projects/<project_id>/merge_requests/<iid>/changes"
> ```
> On a large diff, pull the full text per file rather than truncating the JSON blob.
>
> **Use the local clone at `<local_repo>`** to get context the diff alone cannot give: how the changed functions are called elsewhere, whether a cited path or command actually exists, existing conventions in neighbouring files, the repo's `CLAUDE.md`. Verify claims against the checked-out code instead of assuming. Note that the clone sits on its default branch, not the MR branch, so treat it as the "before" state.
>
> Also read the discussion for review points already raised and whether they were addressed:
> ```bash
> glab api "/projects/<project_id>/merge_requests/<iid>/notes?per_page=100&sort=asc"
> ```
> Ignore bot notes (Sonar, etc.) beyond their pass/fail verdict.
>
> Return exactly:
> - **difficulty 0-10**: effort for a human to review *well*. Drive it off blast radius and required context, not line count. A 5-line CI change in a deploy path can outrank a 500-line mechanical rename. Flag when a diff is big but mechanical.
> - **quality 0-10**: is this good to merge? 8+ approve as-is, 6-7 approve with a note, ≤5 something needs changing first.
> - **findings**: only what changes my decision or is worth saying in a comment. Each one concrete, with `file:line`. Distinguish blocking from non-blocking. Explicitly call out behaviour changes riding along inside an otherwise mechanical diff, and unrelated scope inflating a large diff. Say "nothing worth flagging" when that's true rather than padding.
> - **suggested action**: one of approve / approve with comment / request change / ping author / close, plus a one-line reason.
> - **verified**: what you actually checked against the local clone, so I can gauge confidence.

## Step 3 — Report

Lead with a table sorted by suggested action (approvals first, blocked last):

| MR | Author | Diff | Difficulty | Quality | Approvals | Open threads | Action |
|---|---|---|---|---|---|---|---|

- MR column: markdown link on `project!iid`, then a short subject.
- Approvals: `given/required`, naming who approved when non-zero. This tells me whether my review is actually gating.
- Note the pipeline only when it is not `success`.

Then one short section per MR: the findings, plus **open comment threads** rendered as:

> `author` on `file:line` (`date`, N replies) — quoted gist. **Waiting on me** / **waiting on `last_author`**.

`waiting_on_me` in the JSON is true when the last reply is not mine. Threads where the ball is in my court are the point of this report, so surface them prominently. An MR whose only blocker is an unresolved thread of my own is a "resolve or reply" action, not a review.

Close with a one-line footer: total assigned, drafts skipped, idle skipped, already-approved skipped.

When `stale` is non-empty, add **one line** naming those MRs with their idle days, so dropped work is visible without cluttering the report, e.g. *"Hidden as stale: `platform/aws/Gitlab-Base-Images-In-ECR!1` (322d idle). Re-run with `--max-idle-days 0` to include."* Never analyse them; they are excluded on purpose.

## Then

Ask whether I want to approve any of them, or to see a deeper review of a specific one. Do not approve, comment, or merge anything unless I ask.

## Gotchas

These are all things that produced wrong output before. Keep them.

- **`user_has_approved` from `/approvals` is the only reliable "did I approve this" signal.** Matching my username against `approved_by` returned stale data and put an already-approved MR back on the list. The script handles this; don't second-guess it with a username match.
- **A 401 from `POST /approve` means "already approved", not a permission problem.** Read back `user_has_approved` before reporting a failure.
- **Inline comments need `glab mr note create --file <path> --line <n>`**, or the raw API with `--input body.json -H "Content-Type: application/json"`. The `-f "position[new_line]=17"` bracket form is silently accepted and degrades to an unanchored `DiscussionNote`; `--input` without the explicit content-type returns HTTP 415.
- **A quality score is not a diff-size score.** A one-line dependency bump can be a 9; a green 125-file diff in the authorization path is still worth real scrutiny.
- Never read the token out of `~/.config/glab-cli/config.yml`. It is OAuth2 with a refresh cycle, so it breaks on expiry and leaks a live credential into context. Always go through `glab api`.
