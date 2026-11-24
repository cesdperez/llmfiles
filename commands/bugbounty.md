---
description: Run a bug bounty on a running app. Parallel hunters attack it from every angle (functionality, look, responsiveness on desktop and mobile, accessibility, races, load, abuse) with playwright-cli, curl and the app's own tools, then workers fix what matters test-first, in cycles, until it meets a stated bar. Ends at a local branch; "ship to main" or "ship to prod" go further.
argument-hint: <local|staging|prod|URL> [focus text] [cycles=N] [ship to main|ship to prod] [unattended]
allowed-tools: Agent, SendMessage, Skill, Read, Grep, Glob, Bash, Edit, Write, AskUserQuestion, Monitor, ToolSearch
---

**Role:** controller of one bug bounty. You own intake, triage, merges, releases and
cleanup. Hunters find, workers fix, and only conclusions come back to you.

The run asks everything up front in one batch, then works unattended until the bar is met,
the cycles run out, or a stage is blocked. Put status notes in the same message as the next
tool call. Waiting on a hunter or worker is not a stop: the stage ends when its last agent
has reported.

A stage is blocked when it cannot proceed for a reason the run cannot fix: a target that
is down, credentials that fail, a denied push, an MR the run may not merge. Record the
reason in the ledger and go to stage 7, which always runs.

## Arguments

`$ARGUMENTS` holds:

- **Target**: where hunters attack. `local` (the stack started from this checkout),
  `staging`, `prod`, or a URL. Several are allowed, for example `local prod`.
- **Focus** (optional): free text that narrows or weights the hunt areas.
- **`cycles=N`**: maximum hunt and fix cycles. Default 2.
- **Endpoint**: default `branch`, fixes committed on a local bounty branch. The phrase
  "ship to main" sets `main`: merge into the base and push. The phrase "ship to prod" sets
  `prod`: also deploy to production, and re-verify there. Only these exact phrases count.
- **"unattended"**, or any wording that says nobody will answer ("I am away", "decide on
  your own"). See the next section.

## Worker mode and unattended runs

When the prompt starts with Orca's dispatched-worker preamble, or the run is unattended,
follow the worker mode section of `~/llmfiles/shared/orca-fleet.md`. Its rules for
questions, the items only the user can do, and the final report take precedence over the
rules below. With no coordinator to ask, intake takes its recommended defaults, which keep
load and abuse off prod. When `git worktree list` shows other worktrees of this repo, also
follow its section on sharing a repo with sibling worktrees.

## Ledger

Keep the run state in `$(git rev-parse --git-dir)/bugbounty-ledger.md`, never committed:
intake answers, the bar, the data marker, hunt areas, temporary config changes with their
original values, the data the run created, shared state with its starting values, the
current stage, and one row per finding (`B1`, `B2`, ...) with its status and fixing commit.
The ids carry a finding across cycles and into the report. Update the ledger at each stage
boundary. On start, resume from an existing ledger for the same target; for another
target, ask whether to resume or replace it.

At each stage boundary, also publish progress to the worktree's Orca card as the "Progress
in Orca" section of `~/llmfiles/commands/fullsend.md` says, with the comment
`<cycle>/<max> <stage>, <n> fixed`.

## Agents

Hunters and workers share one pool of at most 5 running agents, because they draw on one
usage window and one machine. Queue the rest. An agent stopped by a usage limit keeps its
context: after the reset, resume it with SendMessage and one line of state.

## Stages

### 0. Intake

Read README, CLAUDE.md and the docs on intended behaviour first, so questions are only the
ones the repo cannot answer. Ask in one batch, each with a recommended default:

- **Credentials** per target, and the file they live in. Agents read values from that file
  and never write them into tracked files, prompts or logs. A missing test account is a
  question: the run does not write users or sessions into a target's database.
- **Write rules**: what the run may create, change or delete on each target. Default: create
  its own marked data and delete it at the end; never touch data the run did not create,
  because other people may be using the target at the same time. Repo CLAUDE.md rules on
  real accounts apply on top.
- **Load and abuse**: which targets the load script and abuse probes may hit. Default:
  local and staging only, because real users share prod.
- **Shipping**: whether fixes may be deployed, and to where, when the endpoint allows it.
  Also whether a fix may change config that lives outside the repo (WAF, DNS, rate-limit
  rules) with the CLIs at hand. Default: no, and the exact change goes under Decide.
- **Temporary changes**: config the user loosened for the run (rate limits, flags) and its
  original values.
- **The bar**: the real use the app must survive: who uses it, how many at once, on which
  devices and browsers, and the look it must reach (a design system, a product it
  replaces, or "consistent and polished"). Propose a default from the docs. Severity is
  judged against it, so the hunt stays sized to real use.

Pick a data marker, `bb-<short-slug>`, and put it in the name of every record the run
creates. Cleanup finds the run's data by that marker, not by guessing. For a write that
cannot carry a name, send the marker in the request's User-Agent.

### 1. Recon

In this session, list the app's surfaces from its routes, domains and docs: pages, API
endpoints, background jobs, emails. The list is complete when every route, endpoint and job
in the code maps to a surface. Then cut the hunt two ways, so every surface is seen from
every angle that applies to it:

- **Functional areas**: 3 to 6 domains. Each hunter drives its domain's flows end to end,
  including edge inputs, permissions, and empty, loading and error states.
- **Angles**: each hunter sweeps every surface from one angle. Pick the angles that apply
  to this app and the bar, and add any it needs beyond these (i18n, SEO, payments):
  - **Look**: alignment, spacing, overflow, truncated text, broken images, inconsistent
    components, unstyled empty, loading and error states, every theme. Compare against
    the reference in the bar, with screenshots side by side.
  - **Responsive**: a phone, a tablet and a desktop viewport at least, plus the narrowest
    and widest devices in the bar. No horizontal scroll, tap targets of at least 44px, no
    iOS zoom on input focus, uploads in the sizes and formats those devices produce.
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

An app without a UI skips the browser angles and hunts through its API or CLI. Angles that
use the same tools on the same surfaces may share one hunter, such as look with responsive,
or races with bad network.

List the shared state hunters could overwrite for each other: a stub or in-memory store,
and the settings of a shared account that cannot carry the marker (language, favourites,
progress). Give each to one hunter, the only one that writes it, and record its starting
value in the ledger so cleanup can restore it.

Record the areas, angles and shared state in the ledger. Create a branch
`bugbounty/<slug>` from the base. In a worktree made for this run, its own branch is the
bounty branch.

If a target is `local`, start the stack from this branch the way `/fullsend` stage 4 does,
with its containers labelled. Start it detached (`nohup <command> > <log> 2>&1 &`): a
background Bash task is stopped at its time limit, and the hunt outlasts it.

The stack and the suites share the machine with other runs, under the machine lock in
`~/llmfiles/commands/fullsend.md`:

- A stack on fixed ports or one shared database: take the lock before starting it and hold
  it to stage 7. Refresh it at every stage boundary, every agent report, and every 30
  minutes of waiting.
- A repo that gives each worktree its own ports and data: take the lock only around the
  full suite and the load script, so sibling runs are not held up for hours.

### 2. Hunt

One `reviewer` agent per hunter in the recon cut. Each hunter brief carries:

- the authorization: the user owns these targets and runs this bounty on them, within the
  write rules and the load and abuse targets from intake
- the area or angle, the surface list, the targets with their URLs, the credentials file,
  the write rules, the data marker and the bar
- for a UI: every viewport and browser engine in the bar (WebKit and Chromium by default),
  whatever the area or angle. An engine named only in the responsive brief is tested only
  there, and exports, uploads and forms break per engine too.
- the tools: for UIs, call the Skill tool with "playwright-cli" first; curl for APIs; and
  whatever database, cloud or deploy CLIs the repo uses
- its own playwright-cli session named `bb-<area>`, run from
  `$(git rev-parse --git-dir)/bugbounty-qa/<area>/`, because the CLI writes logs into its
  working directory. Its scripts and screenshots stay in that directory, and each command
  spells out `playwright-cli -s=bb-<area>`: hunters share the session scratchpad, a
  command without `-s` drives another hunter's browser, and zsh does not split a command
  held in a variable.
- the shared state it owns, and that it leaves all other shared state as it found it
- context rules: filter command output with grep, head or tail; read files in parts;
  report what is left uncovered instead of running until context is short
- edit no files; every record it creates carries the marker and is listed in its report
- report every finding, `minor` included; triage filters later
- the report shape: per finding, title, area or angle, surface, target, viewport and engine,
  repro steps, evidence (a screenshot path for anything visible, a response, file:line),
  severity, and the suspected cause. Then what was tested and passed, in one line each.
- severity against the bar: `blocker` breaks the real use, loses data, or locks a user out,
  including keyboard and screen-reader users; `hurts` works but looks broken, confuses, or
  fails WCAG AA; `minor` is polish a user would barely notice.

In cycle 2 and later, hunt only the areas and angles that had a `fix` finding or left
something uncovered, on the target the last cycle released to. Each of those hunters
re-runs the repro of every fixed finding in its scope first, then goes deeper on the fixed
surfaces and the uncovered ones. Its brief lists the open findings as already reported.

### 3. Triage

In this session, on each hunter report as it arrives. Merge duplicates, including one
cause seen from several angles, such as a layout bug that is both a look and a responsive
finding. A cause that shows on several surfaces or code paths is one finding that lists
them all. Drop `minor` findings unless the fix is a few lines.

Before accepting a finding that fails on only one browser engine or one environment,
confirm the intended behaviour in code or docs: it can be a wrong assumption in a test,
not an app bug. Check a data anomaly against the other hunters' writes before calling it
a bug. Record each finding as `fix`, `accept-risk` (with the reason) or `not-a-bug`. An
accepted `blocker` is a Decide item in the report.

### 4. Fix

Group `fix` findings by the files they touch. One `worker` per group, with
`isolation: "worktree"`. Hunting and fixing overlap: start a group once no running hunter
covers its files. A later finding in files a running worker owns goes to that worker with
SendMessage while it has context to spare, and otherwise to a fresh worker with
`file:line` pointers.

Files that many groups would change belong to you, not to a worker: generated baselines
and images, token tables, shared docs. Workers report the change they need, and you make
it once after the cycle's last merge.

Each brief carries the findings with the hunter's evidence and suspected cause, and a free
port for any server its tests start (`lsof -nP -iTCP:<port> -sTCP:LISTEN`). Each worker:

- merges the bounty branch into its own before it starts and again before it reports, so
  it builds on the fixes already merged and resolves its own conflicts
- writes a test that reproduces the finding and watches it fail, unless the finding is
  config or a layout only a browser shows; then the repro steps are the test
- fixes the cause on every surface and code path it reaches, not only the one in the
  repro. Other problems it notices go in its report, not in the diff
- updates docs the fix makes stale, following `~/llmfiles/shared/agent-docs-bar.md`
- runs only the tests near the change, never a full or browser suite, because workers
  running suites side by side fail each other's tests. Commits granularly
- runs one plain command per Bash call, writes files with Write and Edit, and saves a
  script to a file before running it: the worktree guard refuses heredocs, `git -C`,
  `eval` and commands built from variables
- reports the commits, the tests, the findings it could not fix, and the problems it noticed

Merge each worker branch into the bounty branch. Resolve conflicts here, since you hold
both sides. After the cycle's last merge, run the repo's type check, lint and full test
suite once, end-to-end included, under the machine lock: fixes change behaviour that older
tests assert. Problems the workers noticed go to the next cycle's triage. A trap a hunter
or worker hit running the app that the repo's agent docs did not warn about, or a doc
claim the run proved wrong, is fixed in the file that owns that topic, in its own commit.

### 5. Release

Once per cycle, after its full suite passes. A fix batch shipped on its own skips the
suite and the next hunt.

- Endpoint `branch`: restart the local stack from the bounty branch.
- Endpoint `main`: merge into the base, push, and wait for the pipeline or auto-deploy with
  Monitor. Where the base refuses the push, ship through an MR or PR and merge it yourself
  only if the repo's rules allow that. Otherwise the run is blocked at the open MR.
- Endpoint `prod`: also deploy to production the way the repo does.

Confirm a deploy by the commit or asset hash the target serves. A status word or an older
log can describe a build that is still running.

### 6. Next cycle and last verify

Run stages 2 to 5 again while cycles remain and the last hunt found a `blocker` or
`hurts`. The next cycle's hunters re-run the fixed repros first, so no separate re-verify
runs between cycles.

The last cycle's fixes have no next hunt. `reviewer` agents re-run each of their repros
where they were released. A repro that still fails, or a `blocker` or `hurts` they find
with a named cause, gets one more round of stages 4 and 5 without a new hunt. A fix of a
few lines is yours to make test-first; a larger one goes to a worker. What still fails
after that round is an open item.

### 7. Cleanup and report

Runs on every exit, blocked runs included.

- Delete only records carrying the marker, children before parents (stored files, then
  rows). Check counts before and after, and confirm that nothing else changed.
- Restore shared state to the starting values in the ledger, and every temporary change
  to its original value. If the original value breaks the bar, keep a safe value, prove
  the break with numbers, and put it first in the report.
- Stop the servers and playwright-cli sessions the run started, and release the lock.
- Delete the ledger and `bugbounty-qa/` once the run ends unblocked. A blocked run keeps
  them, so the next start resumes.

An unattended run with no coordinator files its Decide and Still broken items itself, as
"Items for the user" in `~/llmfiles/shared/orca-fleet.md` says, and puts each link in its
line.

Report in plain English, in this shape and under 300 words. Lead with anything the user
must decide. The commits hold the detail of each fix.

```
<app> bounty - <bar met | still broken: n | blocked at <stage>: <reason>>, <cycles run>/<max>
Decide: <kept config, accepted blockers, risks needing a yes, an MR waiting, or "nothing">
Found and fixed: <blocker n of n, hurts n of n, minor n of n>
Fixed: <each blocker in one line with its commit, then one line per area>
Still broken: <id, finding and cause, one line each, or "nothing">
Tested and passed: <area: what, on which targets, devices and engines>
Risks left alone: <id, finding, why it is acceptable against the bar>
Cleanup: <records deleted per target, state and config restored, servers stopped>
Branch: <bugbounty/<slug>, n commits | merged to main | deployed to prod>
```
