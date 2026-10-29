---
description: Run a bug bounty on a running app. Parallel hunters attack it from every angle (functionality, look, responsiveness on desktop and mobile, accessibility, races, load, abuse) with playwright-cli, curl and the app's own tools, then workers fix what matters test-first, in cycles, until it meets a stated bar. Ends at a local branch; "ship to main" or "ship to prod" go further.
argument-hint: <local|staging|prod|URL> [focus text] [cycles=N] [ship to main|ship to prod]
allowed-tools: Agent, SendMessage, Skill, Read, Grep, Glob, Bash, Edit, Write, AskUserQuestion, Monitor, ToolSearch
---

**Role:** controller of one bug bounty. You own intake, triage, merges, releases and
cleanup. Hunters find, workers fix, and only conclusions come back to you.

The run asks everything up front in one batch, then works without stopping until the bar is
met, the cycles run out, or a stage is blocked.

## Arguments

`$ARGUMENTS` holds:

- **Target**: where hunters attack. `local` (the stack started from this checkout),
  `staging`, `prod`, or a URL. Several are allowed, for example `local prod`.
- **Focus** (optional): free text that narrows or weights the hunt areas.
- **`cycles=N`**: maximum hunt and fix cycles. Default 2.
- **Endpoint**: default `branch`, fixes committed on a local bounty branch. The phrase
  "ship to main" sets `main`: merge into the base and push. The phrase "ship to prod" sets
  `prod`: also deploy to production, and re-verify there. Only these exact phrases count.

## Ledger

Keep the run state in `$(git rev-parse --git-dir)/bugbounty-ledger.md`, never committed:
intake answers, the bar, the data marker, hunt areas, findings with status, temporary
config changes with their original values, the data the run created, and the current
stage. Update it at each stage boundary. On start, resume from an existing ledger for the
same target; for another target, ask whether to resume or replace it.

## Stages

### 0. Intake

Read README, CLAUDE.md and the docs on intended behaviour first, so questions are only the
ones the repo cannot answer. Ask in one batch, each with a recommended default:

- **Credentials** per target, and the file they live in. Agents read values from that file
  and never write them into tracked files, prompts or logs.
- **Write rules**: what the run may create, change or delete on each target. Default: create
  its own marked data and delete it at the end; never touch data the run did not create,
  because other people may be using the target at the same time. Repo CLAUDE.md rules on
  real accounts apply on top.
- **Shipping**: whether fixes may be deployed, and to where, when the endpoint allows it.
- **Temporary changes**: config the user loosened for the run (rate limits, flags) and its
  original values.
- **The bar**: the real use the app must survive: who uses it, how many at once, on which
  devices and browsers, and the look it must reach (a design system, a product it
  replaces, or "consistent and polished"). Propose a default from the docs. Severity is
  judged against it, so the hunt stays sized to real use.

Pick a data marker, `bb-<short-slug>`, and put it in the name of every record the run
creates. Cleanup finds the run's data by that marker, not by guessing.

### 1. Recon

In this session, list the app's surfaces from its routes, domains and docs: pages, API
endpoints, background jobs, emails. Then cut the hunt two ways, so every surface is seen
from every angle that applies to it:

- **Functional areas**: 3 to 6 domains. Each hunter drives its domain's flows end to end,
  including edge inputs, permissions, and empty, loading and error states.
- **Angles**: each hunter sweeps every surface from one angle. Pick the angles that apply
  to this app and the bar, and add any it needs beyond these (i18n, SEO, payments):
  - **Look**: alignment, spacing, overflow, truncated text, broken images, inconsistent
    components, unstyled empty, loading and error states, every theme. Compare against
    the reference in the bar, with screenshots side by side.
  - **Responsive**: a phone, a tablet and a desktop viewport at least, plus the narrowest
    and widest devices in the bar, on the browser engines in the bar (WebKit and Chromium
    by default). No horizontal scroll, tap targets of at least 44px, no iOS zoom on input
    focus, uploads in the sizes and formats those devices produce.
  - **Accessibility**: an axe-core scan of every page (`npx @axe-core/cli`, or axe injected
    through playwright), then manual checks the scan misses: a keyboard-only pass through
    each flow with visible focus in a sensible order, accessible names and roles in the
    playwright-cli snapshot, contrast in every theme, 200% zoom, reduced motion. Cite the
    WCAG criterion.
  - **Races**: two users acting on the same record, double submits on slow networks,
    writes that must be atomic but run as separate statements.
  - **Load and limits**: a load script sized to the bar, not beyond it. Count requests per
    page view and background refresh, and check rate limits and quotas against the bar,
    including many users behind one IP (an office or event network).
  - **Bad network**: offline mid-action, reconnect, user input kept after a failed submit.
  - **Abuse**: unauthenticated or cross-tenant access, endpoints that hit the database or
    paid quotas without limits.

An app without a UI skips the browser angles and hunts through its API or CLI.

Record the areas and angles in the ledger. Create a branch `bugbounty/<slug>` from the base.

If a target is `local`, start the stack from this branch under the shared-stack lock from
`/fullsend` stage 4 (`~/.cache/fullsend/qa.lock`), so a concurrent run never serves its code
to these hunters.

### 2. Hunt

One `reviewer` agent per area and per angle, at most 4 at once; queue the rest. Each
hunter brief carries:

- the area or angle, the surface list, the targets with their URLs, the credentials file,
  the write rules, the data marker and the bar
- the tools: `playwright-cli` (load its skill) for UIs, curl for APIs, and whatever
  database, cloud or deploy CLIs the repo uses
- its own playwright-cli session named `bb-<area>`, run from
  `$(git rev-parse --git-dir)/bugbounty-qa/<area>/`, because the CLI writes logs into its
  working directory
- context rules: filter command output with grep, head or tail; read files in parts; finish
  in about 150 turns and report what is left uncovered
- edit no files; every record it creates carries the marker and is listed in its report
- the report shape: per finding, title, area or angle, surface, target, viewport and engine,
  repro steps, evidence (a screenshot path for anything visible, a response, file:line),
  severity, and the suspected cause. Then what was tested and passed, in one line each.
- severity against the bar: `blocker` breaks the real use, loses data, or locks a user out,
  including keyboard and screen-reader users; `hurts` works but looks broken, confuses, or
  fails WCAG AA; `minor` is polish a user would barely notice.

In cycle 2 and later, hunters re-run the repro of each fixed finding first, then go deeper
on the fixed areas and on anything earlier cycles left uncovered.

### 3. Triage

In this session. Merge duplicates, including one cause seen from several angles, such as a
layout bug that is both a look and a responsive finding. Drop `minor` findings unless the
fix is a few lines.
Before accepting a finding that fails on only one browser engine or one environment,
confirm the intended behaviour in code or docs: it can be a wrong assumption in a test,
not an app bug. Record each finding as `fix`, `accept-risk` (with the reason) or `not-a-bug`.

### 4. Fix

Group `fix` findings by the files they touch. One `worker` per group, with
`isolation: "worktree"`, at most 4 at once. Each worker:

- writes a test that reproduces the finding and watches it fail, unless the finding is
  config or a layout only a browser shows; then the repro steps are the test
- fixes it, runs only the tests near the change, and commits granularly
- reports the commits, the tests, and any finding it could not fix

Merge each worker branch into the bounty branch. Resolve conflicts here, since you hold
both sides. Run the repo's type check, lint and the tests touched by the merged fixes.

### 5. Release and re-verify

- Endpoint `branch`: restart the local stack from the bounty branch and re-run each fix's
  repro there.
- Endpoint `main`: merge into the base, push, and wait for the pipeline or auto-deploy with
  Monitor. Re-verify where it deploys.
- Endpoint `prod`: also deploy to production the way the repo does, then re-run each fix's
  repro on prod.

A repro that still fails goes back to stage 4 once. A second failure becomes an open item.

### 6. Next cycle

Run stages 2 to 5 again while cycles remain and the last cycle found a `blocker` or `hurts`.
A cycle with none ends the run early.

### 7. Cleanup and report

- Delete only records carrying the marker, children before parents (stored files, then
  rows). Check counts before and after, and confirm that nothing else changed.
- Restore every temporary change to its original value. If the original value breaks the
  bar, keep a safe value, prove the break with numbers, and put it first in the report.
- Stop the servers and playwright-cli sessions the run started, and release the lock.
- Delete the ledger and `bugbounty-qa/` once the run ends unblocked.

Report in plain English, leading with anything the user must decide:

```
<app> bounty - <bar met | open blockers: n>, <cycles run>/<max>
Decide: <kept config, accepted risks needing a yes, or "nothing">
Fixed: <finding, one line each, with commit>
Tested and passed: <area: what, on which targets and devices>
Risks left alone: <finding, why it is acceptable against the bar>
Cleanup: <records deleted per target, config restored, servers stopped>
Branch: <bugbounty/<slug>, n commits | merged to main | deployed to prod>
```
