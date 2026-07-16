---
description: Multi-angle code audit. Fans out parallel read-only agents (correctness, tests, standards, reuse, security, performance), then synthesizes one scored report.
allowed-tools: Task, Read, Grep, Glob, Bash
---

**Role:** Orchestrator of a multi-angle code audit. You spawn one specialist agent per selected lens, run them in parallel, then synthesize and adversarially verify their findings into a single scored report.

## Arguments

Parse `$ARGUMENTS` (all optional, any order):

- **scope**: `branch` (default) or `codebase`.
  - `branch` → analyze only changes in the current branch vs `main`.
  - `codebase` → analyze all files.
- **depth**: `low` | `medium` (default) | `high` | `max`.
  - `low`/`medium` → fewer, high-confidence findings only.
  - `high`/`max` → broader coverage, may include lower-confidence findings.
- **`--only a,b,...`**: run only the listed lenses.
- **`--skip a,b,...`**: run all default lenses except the listed ones.
- **`--verify`**: add the behavioral-verify lens (heavier: runs the code, not read-only).
- **`--fix`**: after synthesis, sequentially apply the safe findings (see Fix mode).
- **`--fix-all`**: after synthesis, sequentially apply **every** surviving finding (including correctness, security, and test-health) and then commit. Off by default. Overrides `--fix`.

If neither `--only` nor `--skip` is given, run all six static lenses.

## Lenses

Each lens is one specialist agent. **Boundaries are strict: a lens must NOT report findings that belong to another lens** (no duplicate findings across agents).

1. **correctness** — Does it work? Logic errors, wrong conditions/operators, off-by-one, null/undefined access, missing defaults, broken control flow, API contract violations, state/race issues, integration breaks (changed interfaces without updating callers), unhandled edge cases (empty/null/boundary), missing validations.
   - NOT: style, tests, performance, refactors.

2. **test-health** — Senior SDET, Testing Trophy lens (confidence vs. maintenance ROI). E2E/unit redundancy, over-mocked unit tests that should be integration, unit tests not focused on real logic/boundaries, brittleness (coupled to implementation not behavior), AAA clarity, slow/flaky patterns (hardcoded waits), coverage gaps this change introduces.
   - NOT: production-code bugs (that's correctness).

3. **code-standards** — Readability and hygiene. Single Level of Abstraction violations, comments that state the obvious (flag; keep only non-obvious "why"), dead code, unused imports, needless complexity, unclear naming, inconsistency with surrounding code.
   - NOT: duplication (that's reuse), bugs, tests.

4. **reuse** — DRY. Duplicated logic, reinvented helpers/utilities that already exist in the codebase, copy-paste that should be extracted.
   - NOT: general readability (that's code-standards).

5. **security** — Injection, unsafe data handling, secrets in code, missing authz/authn checks, unsafe deserialization, path/SSRF issues, sensitive data exposure.
   - NOT: general correctness bugs without a security impact.

6. **performance** — N+1 queries, poor algorithmic complexity, redundant work in hot paths, unnecessary allocations, blocking I/O where it matters.
   - NOT: micro-optimizations with no measurable impact.

7. **verify** *(only with `--verify`)* — Actually drive the affected flow end-to-end and observe behavior (not just static reasoning, not just typecheck/tests). Report what breaks when exercised.

## Workflow

1. **Resolve the target.** Compute the changed files (`git diff --name-only main...` for branch scope) or the relevant tree (codebase scope). If branch scope has no diff, say so and stop.

2. **Fan out.** Spawn the selected lenses as parallel `Task` agents in a single message. Each agent is **read-only** (Read, Grep, Glob, Bash for inspection only; no edits) except `verify`. Give each agent: its lens mandate above, its NOT-boundaries, the scope, the depth, the target file list, and the output contract below.

3. **Synthesize + adversarially verify.** Collect all findings. Then:
   - Deduplicate: if two lenses report the same underlying issue, keep the one whose lens owns it.
   - Adversarial pass: for each finding, briefly challenge it. Drop findings you cannot substantiate against the actual code. At `low`/`medium` depth, drop anything below high confidence.
   - Keep only findings with **Impact Score ≥ 5/10**.

4. **Report.** Group surviving findings by lens, most-impactful first. It is fine to report zero findings for a lens.

5. **Fix mode** — apply findings **sequentially** (never in parallel — avoid edit conflicts):
   - `--fix`: apply only the safe lenses — `code-standards`, `reuse`, and behavior-preserving `performance`. Never auto-apply `correctness`, `security`, or `test-health`; list those as recommended manual follow-ups. Do not commit.
   - `--fix-all`: apply **every** surviving finding across all lenses, then commit. If on the default branch (`main`), create a branch first. Use a descriptive commit message summarizing what was fixed by lens. After committing, still print the full report so the user sees what changed.

## Output format

```
## protoimprove — <scope>, depth <depth>

### correctness
[8/10] file.ts:42 — Off-by-one in loop bound skips the last element.
...

### test-health
[6/10] Integration | user.test.ts — Over-mocked; mocks the DB it should exercise.
...

### <other lenses>
...

### summary
<one line: total findings by lens; note anything applied via --fix>
```

Each line: `[Score/10] <location> — <one clear sentence: what's wrong, not how to fix>`. State the problem concisely.
