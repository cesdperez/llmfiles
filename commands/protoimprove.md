---
description: Multi-angle code audit of local changes. Fans out parallel read-only lens agents (correctness, tests, standards, reuse, security, performance), then synthesizes one scored report.
allowed-tools: Task, Read, Grep, Glob, Bash
---

**Role:** Orchestrator of a multi-angle code audit over local changes, with no GitLab
involvement. You spawn one specialist agent per selected lens, run them in parallel, then
synthesize their findings into a single scored report.

**Load the shared protocol first:** `Read ~/llmfiles/shared/review-lenses.md`. It defines the
fan-out contract, the lens catalog, the synthesis rules, and the finding format. This command
supplies only the target, the lens selection, the output shape, and the fix policy. Where the
two conflict, this file wins.

## Arguments

Parse `$ARGUMENTS` (all optional, any order):

- **scope**: `branch` (default) or `codebase`.
  - `branch`: analyze only changes in the current branch vs `main`.
  - `codebase`: analyze all files.
- **depth**: `low` | `medium` (default) | `high` | `max`.
  - `low` / `medium`: fewer, high-confidence findings only, threshold 5.
  - `high` / `max`: broader coverage, may include lower-confidence findings, threshold 4.
- **`--only a,b,...`**: run only the listed lenses.
- **`--skip a,b,...`**: run all default lenses except the listed ones.
- **`--verify`**: add the `verify` lens from the catalog. Heavier, and it runs the code
  rather than reading it.
- **`--autofix`**: after synthesis, apply every surviving finding and commit. Off by default.

Default lens set: `correctness`, `test-health`, `code-standards`, `reuse`, `security`,
`performance`. The two MR-specific lenses (`cross-repo-impact`, `ticket-alignment`) are not
part of this command's default, but `--only cross-repo-impact` works when you want a
blast-radius check on uncommitted work.

## Workflow

1. **Resolve the target.** `git diff --name-only main...` for branch scope, or the relevant
   tree for codebase scope. If branch scope has no diff, say so and stop.

2. **Build the anchor map** so findings cite real line numbers rather than counted ones:
   ```bash
   git diff --unified=0 main... | awk '
     /^\+\+\+ /{p=substr($0,7); next}
     /^@@ /{match($0,/\+[0-9]+/); n=substr($0,RSTART+1,RLENGTH-1)+0; next}
     /^\+/{ if (p != "dev/null") print p":"n"\t"substr($0,2); n++ }
   '
   ```
   Skip this for codebase scope, where lenses read files directly.

3. **Fan out** per the shared contract: single message, read-only (except `verify`), strict
   boundaries, self-refute, model tiering, sharding caps. Give each agent its mandate and NOT
   list, the scope, the depth, the target file list, and the finding format.

4. **Synthesize** per the shared rules: dedupe by lens ownership, score, keep findings at or
   above the threshold for the chosen depth. At `low` and `medium`, additionally drop anything
   below high confidence.

5. **Report.** Group survivors by lens, most impactful first. Zero findings for a lens is a
   valid result.

6. **Fix mode** (only with `--autofix`): apply every surviving finding across all lenses
   **sequentially**, never in parallel, to avoid edit conflicts. If on `main`, create a branch
   first. Commit with a message summarizing what was fixed by lens. Print the full report
   afterwards regardless, so the user sees what changed.

## Output format

```
## protoimprove - <scope>, depth <depth>

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
