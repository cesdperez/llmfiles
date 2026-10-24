# MR Comments, Threads, and Suggestions

Mechanics for posting, replying to, resolving, editing, and deleting MR comments. The text
itself follows **Writing MR Text** in `~/llmfiles/skills/glab-cli/SKILL.md`.

## Comments & Discussion Threads

As of glab 1.107.0 (`mr note` is currently EXPERIMENTAL) you can reply into an
existing thread and comment directly on diff lines, not just post root-level
notes. `mr note create` starts a new resolvable discussion by default.

```bash
# Add comment (new discussion thread)
glab mr note create <mr_id> -m "Comment"

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

## Thread Management (glab >= 1.109)

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

## Suggestions (one-click fixes)

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

## Posting Diff Comments Reliably

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
