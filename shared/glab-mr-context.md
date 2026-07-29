# GitLab MR review context

Shared setup for commands that review a GitLab merge request against the local goodhabitz
mirror. Loaded on demand by `/glabreview` and `/glabcesaraireview`. Covers target
resolution, the batched fetch, the read-only MR-head worktree, the deterministic anchor
map, and the prior-pass marker check.

Pairs with `~/llmfiles/shared/review-lenses.md`, which owns the lens catalog and fan-out
contract. This file owns getting the bytes on disk; that one owns what to do with them.

## Caller contract

The calling command supplies:

- **target**: an MR URL or a bare iid.
- **MARKER**: the command's own marker name, used to find its prior summary note. Each
  command must use its own, so two commands reviewing the same MR do not read each
  other's state.
- **write policy**: whether anything may be posted, and when.

## Hard rule: never mutate the user's clone

It routinely sits on an unrelated feature branch with uncommitted work. No `checkout`,
`switch`, `reset`, `stash`, `pull`, or `merge` in it. The detached MR-head worktree is the
only checkout, and it is removed at the end.

## Resolve the target

Parse the URL into `PROJECT` (e.g. `goodhabitz/newhabitz/account`) and `IID`. For a bare
iid, derive `PROJECT` from `git remote get-url origin`. `ENC` is `PROJECT` url-encoded
(`/` becomes `%2F`), needed for raw API calls.

Map the clone by direct path: `gitlab.com/goodhabitz/<rest>` maps to
`/Users/cesardanielperez/projects/goodhabitz/<rest>`. If it does not exist, fall back to a
diff-only review and say so explicitly in the report: every surrounding-code and
cross-repo lens degrades badly without a checkout.

## Batched setup

One call, backgrounded. Do not serialize these into separate calls, it is the single
biggest avoidable cost in the whole run.

```bash
P=<PROJECT>; I=<IID>
CLONE=/Users/cesardanielperez/projects/goodhabitz/<rest>
OUT=<scratchpad>/mr-$I; WT=$OUT/head; mkdir -p "$OUT"

glab mr view  "$I" -R "$P" --output json      > "$OUT/mr.json"     2>"$OUT/mr.err"    &
glab mr diff  "$I" -R "$P"                    > "$OUT/diff.patch"  2>"$OUT/diff.err"  &
glab mr note list "$I" -R "$P" -F json        > "$OUT/notes.json"  2>"$OUT/notes.err" &
git -C "$CLONE" fetch origin "refs/merge-requests/$I/head" --no-tags -q \
  && git -C "$CLONE" worktree add --detach "$WT" FETCH_HEAD -q &
wait
jq -r '.title, .author.username, .source_branch, .target_branch, .sha, .changes_count, (.labels|join(","))' "$OUT/mr.json"
```

Keep from `mr.json`: `title`, `description`, `author.username`, `source_branch`,
`target_branch`, `sha`, `diff_refs`, `labels`, `draft`, `changes_count`, `web_url`. Call
`sha` the `HEAD_SHA`.

`refs/merge-requests/<iid>/head` resolves for fork-sourced MRs, which
`origin/<source_branch>` does not.

If `worktree add` fails (locked index, stale worktree, disk), fall back to
`git -C "$CLONE" show FETCH_HEAD:<path>` per file and tell the lenses to use that.

## Merge base and anchor map

```bash
git -C "$CLONE" fetch origin <target_branch> --no-tags -q
BASE=$(git -C "$WT" merge-base HEAD FETCH_HEAD)
git -C "$WT" diff --unified=0 "$BASE"..HEAD | awk '
  /^\+\+\+ /{p=substr($0,7); next}
  /^@@ /{match($0,/\+[0-9]+/); n=substr($0,RSTART+1,RLENGTH-1)+0; next}
  /^\+/{ if (p != "dev/null") print p":"n"\t"substr($0,2); n++ }
' > "$OUT/anchors.tsv"
```

`anchors.tsv` is `path:new_line<TAB>content` for every added line, and it is the complete
set of valid new-side comment anchors.

**Anchor every finding by looking up this file, never by counting hunk lines.**
Model-counted line numbers are the main cause of comments landing on unrelated code. Pass
the path to every lens and require each finding to cite a literal line from it, or declare
itself cross-cutting.

## Prior-pass marker check

Read `notes.json`. Each element is a discussion: `.id` (discussion id), `.individual_note`,
and `.notes[]` with `.id` (note id), `.type`, `.resolvable`, `.resolved`, `.body`,
`.author.username`, `.position.new_path`, `.position.new_line`.

Find the calling command's own summary note by its marker line, an HTML comment that is
invisible when rendered:

```
<!-- <MARKER>: sha=<SHA> threshold=<N> -->
```

| State | Meaning |
|---|---|
| No marker found | No prior pass. Review the full diff. |
| Marker sha equals `HEAD_SHA` | Nothing changed since the last pass. |
| Marker sha older than `HEAD_SHA` | Incremental: only `git -C "$WT" diff <marker-sha>..HEAD` is new. |

A thread of yours "needs a response" when its last note is from someone else and either
asks you something, disputes the finding, or shows the author resolved it. The calling
command decides what to do about that.

## Repo-specific lens bindings

The lens catalog in `review-lenses.md` is deliberately organization-agnostic. These are the
goodhabitz bindings to pass along when spawning it here.

- **code-standards** reads, most-specific-wins: the repo's `CLAUDE.md`, its group
  `CLAUDE.md` (`newhabitz/CLAUDE.md`, `backend/CLAUDE.md`, `platform/CLAUDE.md`, ...),
  `/Users/cesardanielperez/projects/goodhabitz/CLAUDE.md`, and the repo's lint and format
  config.
- **reuse** also checks `newhabitz/packages` (`@goodhabitz/nh-*`) for existing helpers.
- **cross-repo-impact** sweeps the local mirror in one batched pass, then maps each hit's
  repo to its owning team via the teams catalog in the root `CLAUDE.md`:
  ```bash
  rg -n --no-heading -g '!**/node_modules/**' -g '!**/.git/**' -g '!**/dist/**' \
     -g '!**/bin/**' -g '!**/obj/**' -g '!**/vendor/**' -g '!**/*.lock' -g '!**/.terraform/**' \
     -e '<symbol1>' -e '<symbol2>' -e '<route>' \
     /Users/cesardanielperez/projects/goodhabitz \
     --glob '!/Users/cesardanielperez/projects/goodhabitz/<rest>/**'
  ```
- **ticket-alignment** uses `twg jira workitem get <KEY>`, keys matching `[A-Z]{2,10}-\d+`,
  capped at 3, preferring keys in the title or branch name.

Every lens also gets `$OUT/diff.patch`, `$WT`, `$BASE`, `$OUT/anchors.tsv`, and the MR
title and description.

## Cleanup

Always, including on failure or abort:

```bash
git -C "$CLONE" worktree remove --force "$WT"
git -C "$CLONE" worktree prune
```
