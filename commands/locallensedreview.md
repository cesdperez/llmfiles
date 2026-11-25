---
description: Multi-angle code audit of local changes. Fans out parallel read-only lens agents (correctness, tests, standards, reuse, security, performance), then synthesizes one scored report.
argument-hint: '[branch|codebase] [low|medium|high|max] [--only a,b] [--skip a,b] [--verify] [--autofix] [--base ref] [--intent file]'
allowed-tools: Agent, Read, Grep, Glob, Bash, Edit, Write
---

**Role:** Orchestrator of a multi-angle code audit over local changes, with no GitLab
involvement. You spawn the selected lenses as parallel agents per the shared contract, then
synthesize their findings into a single scored report.

**Load the shared protocol first:** `Read ~/llmfiles/shared/review-lenses.md`. It defines the
fan-out contract, the lens catalog, the synthesis rules, and the finding format. This command
supplies only the target, the lens selection, the output shape, and the fix policy. Where the
two conflict, this file wins.

## Arguments

Parse `$ARGUMENTS` (all optional, any order):

- **scope**: `branch` (default) or `codebase`.
  - `branch`: analyze only this branch's changes against the base.
  - `codebase`: analyze all files.
- **depth**: `low` | `medium` (default) | `high` | `max`.
  - `low` / `medium`: fewer, high-confidence findings only, threshold 5.
  - `high` / `max`: broader coverage, may include lower-confidence findings, threshold 4.
- **`--only a,b,...`**: run only the listed lenses.
- **`--skip a,b,...`**: run all default lenses except the listed ones.
- **`--verify`**: add the `verify` lens from the catalog. Heavier, and it runs the code
  rather than reading it.
- **`--autofix`**: after synthesis, apply every surviving finding and commit. Off by default.
- **`--base <ref>`**: the branch the change was cut from. Without it, the default branch.
  Workflow step 1 resolves both.
- **`--intent <file>`**: the caller's record of the intent: its sources, acceptance criteria
  and the decisions the user made.

Default lens set: `correctness`, `test-health`, `code-standards`, `reuse`, `security`,
`performance`. The two MR-specific lenses (`cross-repo-impact`, `ticket-alignment`) are not
part of this command's default, but `--only cross-repo-impact` works when you want a
blast-radius check on uncommitted work.

## Workflow

1. **Resolve the target.** Codebase scope reads the tree and goes to step 2. For branch
   scope, run `git fetch origin` when there is a remote, then resolve the base:
   - `--base` becomes `origin/<base>` when it is a bare branch name and that ref exists,
     because a stale local branch pulls upstream commits into the diff.
   - Without `--base`, the default branch: `origin/HEAD`, else `origin/main`, else
     `origin/master`. With no remote, local `main`, else `master`.

   Write the diff to `OUT=<scratchpad>/review-<repo>-<branch>`, with `/` replaced by `-`.
   It includes uncommitted work and untracked files, which `git diff` alone leaves out.
   ```bash
   BASE=$(git merge-base HEAD <base>)
   changes() {
     git diff "$@" "$BASE"
     git ls-files -z --others --exclude-standard |
       xargs -0 -I{} git diff --no-index "$@" /dev/null {}
   }
   mkdir -p "$OUT"
   changes > "$OUT/diff.patch"
   changes --unified=0 | awk '
     /^\+\+\+ /{p=substr($0,7); sub(/\t$/,"",p); next}
     /^@@ /{match($0,/\+[0-9]+/); n=substr($0,RSTART+1,RLENGTH-1)+0; next}
     /^\+/{ if (p != "dev/null") print p":"n"\t"substr($0,2); n++ }
   ' > "$OUT/anchors.tsv"
   ```
   If `diff.patch` is empty, say so and stop.

2. **Gather the intent**: the acceptance criteria and the decisions the user made. Take it
   from `--intent` when given. Otherwise take it from this conversation, the branch's commit
   messages and any ticket they name.

3. **Write the shared brief** once, to `$OUT/brief.md`: the absolute checkout path, the
   scope and depth, the paths of `diff.patch` and `anchors.tsv`, the intent, and the finding
   format. For branch scope it tells each lens to read the change from `diff.patch` rather
   than running `git diff`. A finding anchors on a line from `anchors.tsv`, never a counted
   one. A finding about removed code cites the old-side range from its hunk header, and a
   whole file or cross-cutting is also valid.

4. **Fan out** per the shared contract: single message, read-only, strict
   boundaries, self-refute, executor tiering, the rule-lens bundle, sharding caps. Each lens
   brief holds its mandate, its NOT list, its shard if sharded, the absolute path of
   `brief.md` and, except for `correctness`, the time signal. The `codex-reviewer` brief
   also asks for every finding, and the rule-lens bundle keeps its per-lens sections and
   count lines.

5. **Synthesize** per the shared rules: dedupe by lens ownership, score, keep findings at or
   above the threshold for the chosen depth. At `low` and `medium`, additionally drop anything
   below high confidence.

6. **Report.** Group survivors by lens, most impactful first. Zero findings for a lens is a
   valid result.

7. **Fix mode** (only with `--autofix`): apply every surviving finding across all lenses
   **sequentially**, never in parallel, to avoid edit conflicts. If on `main`, create a branch
   first. Commit with a message summarizing what was fixed by lens. Print the full report
   afterwards regardless, so the user sees what changed.

## Output format

```
## locallensedreview - <scope>, depth <depth>

| # | Score | Lens | Location | Issue |
|---|-------|------|----------|-------|
| 1 | 8/10  | correctness | src/loop.ts:42 | Off-by-one skips the last element |
| 2 | 6/10  | test-health | user.test.ts | Mocks the DB it exists to exercise |

### 1. Off-by-one skips the last element (correctness, 8/10)
`src/loop.ts:42`
The bound is `< len - 1`, so the final item never runs. Use `< len`.

### 2. Mocks the DB it exists to exercise (test-health, 6/10)
`user.test.ts`
Every query is stubbed, so the test passes even when the SQL is wrong. Convert it to an integration test against a real DB.

### summary
<total findings by lens; what the self-refutation dropped; note anything applied via --autofix>
```

Descriptions are two sentences maximum: what is wrong, then what to do instead. No pasted
code, no emoji.
