---
description: Multi-angle code audit of local changes. Fans out parallel read-only lens agents (correctness, tests, standards, reuse, and security or performance when the change calls for them), then synthesizes one scored report.
argument-hint: '[branch|codebase] [low|medium|high|max] [--only a,b] [--skip a,b] [--verify] [--autofix] [--base ref] [--intent file] [--compact]'
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
- **`--autofix`**: after synthesis, fix the findings at the [fix bar](#fix-bar) and commit.
  Off by default.
- **`--base <ref>`**: the branch the change was cut from. Without it, the default branch.
  Workflow step 1 resolves both.
- **`--intent <file>`**: the caller's record of the intent: its sources, acceptance criteria
  and the decisions the user made.
- **`--compact`**: a calling command reads the report, so print the
  [compact output](#compact-output).

Default lens set: `correctness`, `test-health`, `code-standards`, `reuse`, plus:

- `security` when the diff touches authentication, authorization, request or input
  handling, queries, file paths, secrets, tokens, CORS or exposed config. When in doubt, it
  runs.
- `performance` when the diff holds a schema or data migration. Otherwise it runs only with
  `--only`.

The two MR-specific lenses (`cross-repo-impact`, `ticket-alignment`) are not
part of this command's default, but `--only cross-repo-impact` works when you want a
blast-radius check on uncommitted work.

## Workflow

1. **Resolve the target.** Codebase scope reads the tree and goes to step 2. For branch
   scope, run `git fetch origin` when there is a remote, then resolve the base:
   - `--base` becomes `origin/<base>` when it is a bare branch name and that ref exists,
     because a stale local branch pulls upstream commits into the diff.
   - Without `--base`, the default branch: `origin/HEAD`, else `origin/main`, else
     `origin/master`. With no remote, local `main`, else `master`.

   Write the diff and the anchor map to `OUT=<scratchpad>/review-<repo>-<branch>`, with `/`
   replaced by `-`, from the checkout:
   `python3 ~/llmfiles/scripts/review-diff.py --base <base> --out "$OUT"`. The diff includes
   uncommitted work and untracked files, which `git diff` alone leaves out.
   If its summary says `empty`, say so and stop.

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
   `brief.md` and, except for `correctness`, the time signal. The uncertainty policy is to
   report: a finding the lens cannot settle is reported as unconfirmed, with its check,
   because a dropped finding here ships as a bug. The `codex-reviewer` brief also asks for
   every finding, and the rule-lens bundle keeps its per-lens sections and count lines.

   `correctness` runs as the built-in `/code-review high` in place of the `reviewer` lens
   agent, because on past misses it caught bugs the lens agent dropped. Start it in the same
   message, as a background Bash command from the checkout, so it gets a fresh context:
   `claude -p "/code-review high" --permission-mode auto --output-format json`. It reviews
   the branch against the default branch plus uncommitted work, unsharded. It does not see
   the intent, so synthesis drops its findings that contradict a stated decision. When
   `--base` names another branch, or `/code-review` is unavailable (Codex, opencode),
   `correctness` runs as the lens agent. The `codex-reviewer` read keeps the lens brief.

5. **Synthesize** per the shared rules: dedupe by lens ownership, score, keep findings at or
   above the threshold for the chosen depth. At `low` and `medium`, additionally drop anything
   below high confidence, except an unconfirmed finding, which stays with its check.

6. **Report** in the [output format](#output-format), or the
   [compact output](#compact-output) with `--compact`. Group survivors by lens, most
   impactful first. Zero findings for a lens is a valid result.

7. **Fix mode** (only with `--autofix`): fix every finding at the [fix bar](#fix-bar)
   **sequentially**, never in parallel, to avoid edit conflicts. If on the base or the
   default branch, create a branch first. Commit with a message summarizing what was fixed
   by lens. Print the report afterwards regardless, so the reader sees what changed.

## Fix bar

A finding is fixed only at or above the threshold, and a `test-health`, `code-standards` or
`reuse` finding only at 7 or above. The rest are reported, not fixed. The bar holds for
`--autofix` and for a calling command that has the fixes made elsewhere.

An unconfirmed finding is never fixed blind: whoever fixes it runs its check first, and
fixes it only if it holds.

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

### unconfirmed
- 7/10 correctness | `src/cache.ts:18` : A write in another tab may leave this entry stale. Check: read whether `onStorage` clears it.

### summary
<total findings by lens; what the self-refutation dropped; note anything applied via --autofix>
```

Confirmed findings fill the table. Unconfirmed findings go only under `### unconfirmed`, one
line each with the check that settles it.

Descriptions are two sentences maximum: what is wrong, then what to do instead. No pasted
code, no emoji.

### Compact output

With `--compact`, print one line per finding in the shared finding format (the unconfirmed
form for an unconfirmed one), most impactful first, then one line per lens that ran: `<lens>: <n> findings` or `<lens>: none`. No table
and no per-finding sections.
