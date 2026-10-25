---
name: glab-cli
description: GitLab CLI for merge requests and CI/CD pipelines. Use when creating MRs, reviewing merge requests, checking pipeline status, or when the user mentions glab, GitLab CLI, or merge request operations.
---

# GitLab CLI (glab)

glab brings GitLab to your terminal. Manage merge requests, pipelines, and repositories
without leaving the command line. CLI is already authenticated. Check with `glab auth status`.

## Merge Request Commands

### Writing MR Text

Applies to every comment, thread reply, and description, whether written by a command or
ad-hoc. Comments and descriptions get read by busy people, often on a phone. Concise,
direct, human.

Load the `plainenglish` skill before writing any MR text. The rules below are the
GitLab-specific additions on top of it.

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
- Name mechanics with the literal phrase. Not "the config knob that used to drive them is
  now inert" but "`WebSessionRefreshRate` no longer does anything." Metaphor drags in
  connotations you did not choose, and the reader has to translate it back.
- Descriptions: what changed, then why. Bullets over paragraphs. Link the ticket, do not
  retell it. No Testing section unless there is something non-obvious to run.
- No filler adjectives (comprehensive, robust, seamless), no hedge stacks (might
  possibly), no emoji, no em dashes.
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
`type(PROJ-123): description`, e.g. `fix(PROJ-209): correct OTLP receiver hostname`.
Applies to commit titles too.

Not `PROJ-123 fix: description` and not a bare `PROJ-123` prefix.

If the user does not give a Jira code, ask. If there is none, omit the scope:
`fix: correct OTLP receiver hostname`.

**Branch naming**: include the Jira code, `type/PROJ-123-description`, e.g.
`feat/PROJ-209-otlp-receiver-hostname`. Never commit MR work directly on main: branch
first, then commit, push, and create the MR.

### Create MR

For multiline descriptions, write the text to a file and pass
`--description-file <path>` to `mr create` or `mr update`.

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
```

### Common Commands

```bash
glab mr view <mr_id>                      # View MR details
glab mr view <mr_id> --output json        # JSON output for parsing
glab mr diff <mr_id>                      # View diff
glab mr list --assignee=@me               # Assigned to me
glab mr list --reviewer=@me               # I'm reviewing
glab mr checkout <mr_id>                  # Checkout branch locally
glab mr checkout <mr_id> --worktree ../<repo>-mr-<mr_id>  # Separate worktree, current checkout untouched
glab mr merge <mr_id>                     # Merge MR
glab mr merge <mr_id> --squash            # Squash and merge
glab ci status                            # Current pipeline status
```

`mr merge` during a running pipeline enables auto-merge (merge-when-pipeline-succeeds).
Pass `--auto-merge=false` to merge immediately.

## References

- Read `~/llmfiles/skills/glab-cli/references/mr-comments.md` before posting, replying to,
  resolving, editing, or deleting any MR comment or suggestion. It holds the anchor flags
  and the guards against duplicate and misplaced diff comments.
- Read `~/llmfiles/skills/glab-cli/references/merge-requests.md` for MR commands beyond
  the ones above: drafts, reviewers, updates, labels, approvals, closing, the flag table.
- Read `~/llmfiles/skills/glab-cli/references/pipelines.md` when checking, polling, or
  debugging CI pipelines and jobs.
- Read `~/llmfiles/skills/glab-cli/references/api.md` when outside a git repo or working
  across projects: global MR queries, group project enumeration, environment variables.

## Pitfalls to Avoid

1. **Forgetting `--yes` in scripts** - Without it, commands prompt for confirmation
2. **Not pushing before MR** - Use `--fill` which auto-pushes (unless `--push=false`), or push manually first
3. **Squash flag timing** - `--squash-before-merge` is on create/update, `--squash` is on merge
4. **Assignee modification** - Use `+` to add, `-` to remove, or plain to replace all
5. **JSON parsing** - Use `--output json` not `--json`
6. **GitHub CLI flag confusion** - Use `--description` for MR body, not `--body` (which is gh's syntax)
