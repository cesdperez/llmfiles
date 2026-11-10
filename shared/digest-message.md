# Digest message

How `/teamdigest` and `/repodigest` turn the draft from `scripts/merge-digest.py` into a
Slack message and publish it.

## The draft

The script prints the message with everything but the wording done:

- MRs sharing a Jira key share a line, with their titles joined by `||`.
- `:waiting:` marks a line whose MRs are not all in the last successful deploy to the repo's
  `prod` or `production` environment. Repos without one get no mark.
- Conventional Commit chores, CI, docs, tests and refactors sit in each repo's `Housekeeping`
  line.
- Below the `---` is a note for me, not part of the message.

## Write

Replace the titles on each change line with one plain-English line saying the effect, not
the mechanism. Where `||` joins several titles, write one line for all of them. Leave the
marks, links, headers, counts and `Housekeeping` lines as they are.

```text
- :waiting: feat(export): stream the CSV export || fix(export): keep the header row on empty exports [ACME-12](url) [!31](url) [!34](url)
```

becomes

```text
- :waiting: CSV exports of any size download without timing out, and empty ones keep their header row. [ACME-12](url) [!31](url) [!34](url)
```

## Print

Print the message inside a ` ```text ` fence, and the note from below the `---` outside it.
If nothing merged, say so and stop.

Without a `publish to slack` argument, end by asking whether to publish it, and to which
channel.

## Publish, on request

1. Find the channel ID with `slack_search_channels` (`channel_types` set to
   `public_channel,private_channel`). When more than one channel matches, ask which.
2. Post it with `slack_send_message`. This tool takes standard Markdown, so write bold as
   `**text**` here.
3. Reply with the link to the post.
