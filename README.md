# llmfiles

This repo is to LLM coding assistants what [dotfiles](https://wiki.archlinux.org/title/Dotfiles) are to your shell, a single place to manage your configuration, symlinked wherever tools expect it. The name comes from there.

Manages Claude Code skills, commands, agents, and global instructions in one place.
Claude Code is the primary setup. Codex adaptations live under `codex/` and opencode
adaptations under `opencode/`. Both reuse the existing command bodies, agent instructions,
skills, and shared protocols.

[Agentic CLI registry](shared/agentic-clis.md) tracks CLI and companion-skill
upgrade recipes. Ask "upgrade all my CLIs" to run its maintenance procedure.

## Structure

```
llmfiles/
├── agents/
│   └── <agent-name>.md
├── skills/
│   └── <skill-name>/
│       ├── SKILL.md
│       └── references/
│           └── <topic>.md
├── commands/
│   └── <command-name>.md
├── claude-hooks/
│   └── subagent-context-budget.py
├── hooks/
│   ├── pre-commit
│   └── check-repo.py
├── scripts/
│   └── <script-name>.py
├── local.example/
│   └── <settings file>
├── shared/
│   ├── CLAUDE.md
│   ├── agent-docs-bar.md
│   ├── agentic-clis.md
│   ├── digest-message.md
│   ├── digest-page.html
│   ├── glab-mr-context.md
│   ├── meta-hub.md
│   ├── orca-fleet.md
│   └── review-lenses.md
├── codex/
│   ├── AGENTS.md
│   ├── compatibility.md
│   ├── agents/
│   │   └── <agent-name>.toml
│   └── skills/
│       └── <command-name>/
│           ├── SKILL.md
│           └── agents/openai.yaml
├── opencode/
│   ├── opencode.json
│   ├── compatibility.md
│   ├── builders.md
│   ├── builder-contract.md
│   ├── fullconduct.md
│   └── agents/
│       └── <agent-name>.md
├── CLAUDE.md
└── README.md
```

## File Formats

### Skills (`skills/<name>/SKILL.md`)

Reusable knowledge modules that AI assistants auto-activate based on context.

An activated skill loads in full, so SKILL.md holds only what most invocations need: the
core workflow, the policies, and the pitfalls. Reference material goes in
`references/<topic>.md`, and SKILL.md names the condition under which to read each file.

```markdown
---
name: skill-name
description: When to use this skill (max 1024 chars)
---

Instructions and knowledge go here.
```

Companion CLI skills may be maintained here, bundled with their CLI, or managed
from upstream outside this repo. Their sources and refresh steps live in the
[Agentic CLI registry](shared/agentic-clis.md). The official `cf-cli` and
`playwright-cli` skills are managed outside this repo and shared by Claude Code and Codex.

### Commands (`commands/<name>.md`)

Slash commands triggered with `/command-name`.

```markdown
---
description: Brief description
allowed-tools: Read, Grep, Glob
---

Prompt content here. Use $ARGUMENTS for user input.
```

### Agents (`agents/<name>.md`)

Named subagents the orchestrator delegates to. Each pins a model alias and an effort so the
session's own model and effort never leak into delegated work. The session and every agent
whose output needs judgment run `opus`. Agents whose tasks have known steps (`Explore`,
`gitlab`, `worker-fast`) run `sonnet`, where speed matters more than the quality gap on hard
reasoning. Effort is the dial within each model, and it is re-tuned on every release: a level
name does not mean the same amount of thinking across models (Sonnet `medium` is not Opus
`medium`), so pick a level from an effort sweep on your own tasks, not from its name.

`codex-worker` and `codex-reviewer` run `sonnet` at `low` because they only forward the task to
`codex exec`, which does the work on the ChatGPT plan. Codex follows the matching
`worker.md` or `reviewer.md` body, and the `codex` CLI must be logged in.

```markdown
---
name: agent-name
description: When the orchestrator should pick this agent
model: opus
effort: high
disallowedTools: Edit, Write, NotebookEdit
---

Standing instructions for the agent.
```

Model aliases (`opus`, `fable`, `sonnet`) resolve to the newest model of that family, so the
files need no edit when a new version ships. Files named after a built-in agent (`Explore`,
`general-purpose`) replace it.

### Scripts (`scripts/<name>.py`)

Deterministic data gathering a command would otherwise re-derive from scratch every run.
Emit JSON on stdout so the command can reason over the result instead of over shell quoting.

Commands call them by absolute path (`python3 ~/llmfiles/scripts/<name>.py`), so no symlink
is needed.

- `daily-work-recap.py`, one day of git commits, merge requests, GitLab review activity and
  matching Claude Code transcripts, used by `/dailyworkrecap`.
- `glab-review-queue.py`, assigned GitLab merge requests with approval state, diffs,
  pipelines, and unresolved threads, used by `/glabsummary`.
- `merge-digest.py`, the draft Slack message for `/teamdigest` and `/repodigest`: what a team
  or a repo merged, grouped by Jira key, flagged when not yet in prod. It prints text rather
  than JSON, so the command only rewords titles. For a team it reads ownership from
  `platform_directory` in `local/work.json`, and parses that YAML with Ruby.
- `digest-page.py`, renders the written `/teamdigest` or `/repodigest` digest and a notes JSON (areas, a TL;DR
  per repo, a line per epic) into the filterable Artifact page from `shared/digest-page.html`, with changes grouped
  under their tickets' Jira epics through `twg` and the rest as unplanned work. For
  `/repodigest` the notes group one repo's changes instead of areas of repos.
- `orca-add-repo.py`, registers a repo in Orca under the project group of the closest
  registered repo that contains it, used by `/fleet` and `/fullsend`. The CLI cannot move a
  repo into a group, so it calls the app's `projectGroup.moveProject` through the CLI's
  client library, and an Orca update can break that call.
- `builder-evals.py`, the ledger of the opencode conductor's builder runs and A/B comparisons
  (see [Conductor](#conductor)). It reads model and wall time from the opencode session API.

### Local org settings (`local/`)

Employer-specific values stay out of this public repo. `local/` is gitignored, and
`local.example/` holds a template for each file:

- `work.json`: repo root, GitLab group, git author, Jira URL and project, Slack IDs, timezone,
  and the platform directory and team that `/fullsend` picks reviewers from and `/teamdigest`
  reads team repos and members from.
  The scripts load it through `scripts/work_config.py`, and `LLMFILES_WORK_CONFIG` overrides
  its path. Commands read it directly.
- `glab-lens-bindings.md`: org-specific lens bindings for the GitLab review commands.
- `dailyworkrecap-style.md`: the sample post and team-specific gotchas for `/dailyworkrecap`.
- `meta-hub-verify.md`: how `/fullsend` runs the hub's shared local stack on a worktree.

```bash
mkdir -p ~/llmfiles/local && cp -n ~/llmfiles/local.example/* ~/llmfiles/local/
```

### Git hooks (`hooks/`)

`pre-commit` rejects em dashes in staged lines, so the writing rule in `shared/CLAUDE.md` holds
without a model remembering it. It then lints the whole tracked tree and blocks the commit on
any finding:

- `yamllint --strict`, configured in `.yamllint`.
- `shellcheck` on the shell scripts.
- `ruff check`, configured in `ruff.toml`.
- `check-repo.py`, for what the agent CLIs load but no linter sees: frontmatter that parses as
  YAML, required keys, skill and agent names that match their file, model aliases and effort
  levels, Codex agent TOML, opencode agents and config, example JSON, and every `~/llmfiles/`
  path and relative Markdown link pointing at a file that exists.

### Claude Code hooks (`claude-hooks/`)

`subagent-context-budget.py` is a `PostToolUse` hook. When a subagent's context passes 300k
tokens, it tells that subagent once to finish its step and report a handoff. When the main
session passes 120k, it tells it once to hand the remaining reading and editing to agents.
Neither can see its own token count, so the delegation rule in `shared/CLAUDE.md` needs this to
hold. `SUBAGENT_CONTEXT_WARN_TOKENS` and `MAIN_CONTEXT_WARN_TOKENS` override the limits.

### Global instructions (`shared/CLAUDE.md`)

User-level instructions for every Claude Code session, linked to `~/.claude/CLAUDE.md`.

### Shared protocols (`shared/<name>.md`)

Content reused by several commands, extracted so it lives in one place. Commands load it with an explicit read, for example `Read ~/llmfiles/shared/review-lenses.md`.

Deliberately not skills: a skill is auto-listed with its description and can activate in unrelated sessions, whereas a shared protocol should load only when a command asks for it. Use a skill when the knowledge should surface on its own (`glab-cli`), a shared protocol when it should not (`review-lenses`).

Current protocols:
- `agent-docs-bar.md`, the quality bar for files an agent reads, used by `/curatemds` and `/skillbuilder`, and by `/fullsend`, `/bugbounty` and the `code-standards` lens for the docs they touch. It targets Opus 5.5, so update it when a new model ships.
- `orca-fleet.md`, the Orca orchestration commands, worker mode and shipping rules for runs that share a repo, used by `/fleet` and by `/fullsend` and `/bugbounty` when they run as its workers or with "unattended".
- `meta-hub.md`, checkouts, task ordering and verify for runs whose session sits in a
  checkout that holds other repos, such as a `meta` repo, used by `/fleet` and `/fullsend`.
- `review-lenses.md`, the lens catalog and parallel fan-out contract, used by `/glablensedreview`, `/locallensedreview`.
- `digest-message.md`, the draft format, wording, print and publish steps shared by `/teamdigest` and `/repodigest`.
- `digest-page.html`, the Artifact page template `scripts/digest-page.py` fills for `/teamdigest` and `/repodigest`.
- `glab-mr-context.md`, GitLab MR setup (batched fetch, read-only MR-head worktree, diff anchor map, prior-pass marker check) plus the org-specific lens bindings from `local/`, used by `/glablensedreview` and the per-MR agents of `/glabsummary`.

## Installation

Clone to `~/llmfiles`. Commands, adapters, and settings reference files by that path.

```bash
git clone git@github.com:cesdperez/llmfiles.git ~/llmfiles
```

Prerequisites: `python3` (3.11 or later) for the scripts and hooks, `yamllint`, `shellcheck` and
`ruff` for the git hook (`brew install yamllint shellcheck ruff`), `jq` for the GitLab and
Orca commands, and an authenticated `glab` for the GitLab commands. The GitLab and recap commands also need
`local/work.json` (see [Local org settings](#local-org-settings-local)), and the review
commands expect the GitLab group cloned under its `repo_root`. Other CLIs with companion skills are
listed in the [Agentic CLI registry](shared/agentic-clis.md).

### Claude Code

```bash
# Global instructions
ln -sf ~/llmfiles/shared/CLAUDE.md ~/.claude/CLAUDE.md
```

Commands and agents are whole-directory symlinks. Skills are linked one by one, because
Claude Code writes its own synced Anthropic skills into `~/.claude/skills/synced/`, and a
directory symlink would land those inside this repo.

```bash
ln -sf ~/llmfiles/commands ~/.claude/commands
ln -sf ~/llmfiles/agents ~/.claude/agents

mkdir -p ~/.claude/skills
for skill in ~/llmfiles/skills/*/; do
  ln -sf "${skill%/}" ~/.claude/skills/
done
```

Re-run the skills loop after adding a skill here.

Git hooks, once per clone:

```bash
git -C ~/llmfiles config core.hooksPath hooks
```

Claude Code hooks are referenced by absolute path from the `hooks` block of
`~/.claude/settings.json`. Append the entry to an existing `PostToolUse` array rather than
replacing it:

```json
"PostToolUse": [
  { "matcher": "*", "hooks": [{ "type": "command", "command": "python3 ~/llmfiles/claude-hooks/subagent-context-budget.py", "timeout": 5 }] }
]
```

Agents without a `model` of their own follow `CLAUDE_CODE_SUBAGENT_MODEL`, except the built-in
Plan, which inherits the session model unless `CLAUDE_CODE_SUBAGENT_MODEL_FORCE` is set. Set it in the
`env` block of `~/.claude/settings.json` so ad hoc delegation, whose task shape is unknown, also runs on Opus:

```json
"env": { "CLAUDE_CODE_SUBAGENT_MODEL": "opus" }
```

### Codex

Codex uses global instructions in `$CODEX_HOME/AGENTS.md` (default `~/.codex/AGENTS.md`),
personal agents in `$CODEX_HOME/agents/`, and shared skills in `~/.agents/skills/`.
See the official documentation for [instructions](https://learn.chatgpt.com/docs/agent-configuration/agents-md),
[skills](https://learn.chatgpt.com/docs/build-skills), and
[custom agents](https://learn.chatgpt.com/docs/agent-configuration/subagents).

Link skills and agents individually to preserve anything already installed in the global
directories. The following commands leave existing matching links alone and report other collisions.
Move a conflicting file aside or merge its contents before rerunning; an existing empty
`AGENTS.md` also counts as a collision. An `AGENTS.override.md` in Codex home takes precedence
over `AGENTS.md`, so check it if your global instructions do not load.

```bash
llmfiles_repo="$HOME/llmfiles"
llmfiles_codex_home="${CODEX_HOME:-$HOME/.codex}"
llmfiles_skills_home="$HOME/.agents/skills"

mkdir -p "$llmfiles_codex_home/agents" "$llmfiles_skills_home"

link_llmfile() {
  local source_path="$1" target_path="$2"
  if [ -L "$target_path" ] && [ "$(readlink "$target_path")" = "$source_path" ]; then
    return 0
  fi
  if [ -e "$target_path" ] || [ -L "$target_path" ]; then
    echo "Skipped existing path: $target_path" >&2
    return 1
  fi
  ln -s "$source_path" "$target_path"
}

link_llmfile "$llmfiles_repo/codex/AGENTS.md" "$llmfiles_codex_home/AGENTS.md"

for agent in "$llmfiles_repo"/codex/agents/*.toml; do
  link_llmfile "$agent" "$llmfiles_codex_home/agents/${agent##*/}"
done

for skill in "$llmfiles_repo"/skills/*/ "$llmfiles_repo"/codex/skills/*/; do
  skill="${skill%/}"
  link_llmfile "$skill" "$llmfiles_skills_home/${skill##*/}"
done
```

Resolve every reported collision before considering the installation complete. Re-run
the loops after adding an agent or skill. No `config.toml` replacement is needed.
Start a fresh Codex session to load global instructions and custom agents. In the CLI,
use `/skills` to check discovery, then invoke a command adapter with `$name`, for example:

```text
$waitwhat
$locallensedreview branch high
$glablensedreview <mr-url> --dry-run
```

All eleven command adapters are explicit-only skills. `agents/openai.yaml` sets
`allow_implicit_invocation: false`; shared knowledge skills retain their own policies.

`codex/compatibility.md` owns argument handling, delegation, tool substitutions, and Codex
attribution for GitLab text. Each adapter loads its existing `commands/<name>.md` body and
supplies any further differences. Codex agent definitions load the corresponding
`agents/<name>.md` body; `explorer` maps to Claude's `Explore`.

Codex agents use `gpt-6.1-sol` at high effort for `worker`, `reviewer`, and
`general-purpose`, and medium effort for `reviewer-fast`. `worker-fast` and `gitlab` use
`gpt-6.1-terra` at medium effort, which needs Codex CLI 0.165.0 or later. `explorer` uses
`gpt-6-luna` at high effort, whose usage limits suit high-volume search. These are explicit model IDs,
not Claude aliases or equivalent effort levels. Choose available models in the TOML files
if your account does not support them; `$whichmodels` proposes changes to Codex settings.

Adaptation boundaries:

- Review workflows preserve their posting policies. Use `--dry-run` with
  `$glablensedreview` to inspect findings before posting.
- Review agents' read-only behavior is instructed, not a separate sandbox. Agents inherit
  the parent session's permissions and schedule within its available concurrency limit.
- `$dailyworkrecap` reads the existing collector's Claude transcripts. Codex session
  history is not collected. Slack coverage depends on available connected tools.
- Claude's `PushNotification`, Workflow, agent-team settings, and
  `claude-hooks/` are not installed as Codex features. The adapters use available Codex capabilities and report
  missing coverage where it affects the result.

### opencode

opencode reads `~/.config/opencode/`. Its `claude-agent` provider runs the local Claude Code on
the Claude subscription, and its `openai` provider runs on the ChatGPT plan; `opencode auth list`
shows both once logged in. `opencode/opencode.json` defaults to `openai/gpt-6.1-sol#high` and loads
`shared/CLAUDE.md` and `opencode/compatibility.md` as instructions on every model.

Commands link as one directory, since opencode accepts their Claude frontmatter. Agents link
one by one, so other agent files there stay. Move an existing `opencode.json` or `commands`
aside first.

```bash
mkdir -p ~/.config/opencode/agents
ln -sf ~/llmfiles/opencode/opencode.json ~/.config/opencode/opencode.json
ln -sfn ~/llmfiles/commands ~/.config/opencode/commands
for agent in ~/llmfiles/opencode/agents/*.md; do
  ln -sf "$agent" ~/.config/opencode/agents/
done
opencode service restart
```

`opencode reload` picks up config changes. A new or relinked agent or command file needs
`opencode service restart`, because per-directory agent lists stay cached until then. Skills need no links: opencode discovers `~/.claude/skills` and
`~/.agents/skills`. The Codex adapters in `~/.agents/skills` are hidden by the `skill` deny rules in
`opencode.json`, because the linked commands cover them. `check-repo.py` keeps the rules in
step with `codex/skills/`.

Run a command as `/name` in the TUI. `opencode run "/name"` sends the text as a plain message, so
script a command with `opencode api POST /api/session/<id>/command -d '{"name": "<name>", "text": "<arguments>"}'`.

Each `opencode/agents/<name>.md`, except the [conductor](#conductor) and its builders, loads the body of `agents/<name>.md`. `explore` is Claude's
`Explore`, and `codex-worker` and `codex-reviewer` load the `worker` and `reviewer` bodies and run
them on GPT directly, with no `codex exec` step. The `#variant` in a model ID is its effort level:

| Agent | Model |
| --- | --- |
| `worker`, `reviewer`, `general-purpose` | `openai/gpt-6.1-sol#high` |
| `reviewer-fast` | `openai/gpt-6.1-sol#medium` |
| `worker-fast`, `gitlab` | `openai/gpt-6.1-terra#medium` |
| `explore` | `openai/gpt-6-luna#medium` |
| `codex-worker`, `codex-reviewer` | `openai/gpt-6.1-sol#high` |

`opencode models` lists model IDs, and `opencode api GET /api/model` lists each model's variants.
Read-only agents deny the `edit` permission, which removes the write, edit and patch tools. The
shell tool stays, so read-only shell use is instructed, as with Claude's `disallowedTools`.

Adaptation boundaries:

- `opencode/compatibility.md` maps Claude tools to opencode's. `Workflow`, `Artifact`,
  `PushNotification`, `Monitor`, worktree isolation and forks have no equivalent, and it names
  the substitute for each.
- A subagent cannot start its own subagents (`subagent_depth` defaults to 1), so every fan-out
  runs from the main session.
- GitLab comments are signed `_Comment made by opencode <model> (<effort>)_`.
- `claude-hooks/subagent-context-budget.py` is not covered. A plugin could port it, since the
  server reports token counts per session.
- `/dailyworkrecap` reads Claude transcripts only. opencode sessions are not collected.

#### Conductor

`conductor` is an opencode-only primary agent on `claude-agent/opus#medium`. Switch to
it with Tab in the TUI, or run `opencode run --agent conductor "<task>"`. It splits a task into
narrow briefs, sends each to a builder subagent, and reviews every diff. Its edit tools are
denied, so builders make every change. Its shell still runs tests, git and worktrees, and can
write files, so that part is instructed, not enforced.

[`opencode/builders.md`](opencode/builders.md) routes each task kind to a builder, names the
escalation target, and holds the measurements behind each choice. `builder-luna` and `builder-terra` share
[`opencode/builder-contract.md`](opencode/builder-contract.md). Retry, escalation and the A/B
procedure live in [`opencode/agents/conductor.md`](opencode/agents/conductor.md). Say "ab" or
"a/b" in the message to A/B a brief. `ab-judge` scores the two diffs without knowing which builder made them.

A global `subagent` deny on `builder-*` and `ab-judge` in `opencode.json` keeps `build`, `plan`
and `general` from calling them. The conductor allows them again, plus `worker`, `codex-worker`,
`explore`, `reviewer`, `reviewer-fast` and `codex-reviewer`, and nothing else. All of those
subagents run on OpenAI; Opus is reserved for the conductor.

`/fullconduct` is `/fullsend` on the conductor. It is defined under `commands` in
`opencode.json`, not in `commands/`, so Claude Code never sees it. It loads `commands/fullsend.md`
unchanged with [`opencode/fullconduct.md`](opencode/fullconduct.md), which holds what differs:
builders implement and fix, and the conductor runs the review lenses itself. `/fullsend` stays as
it is in both tools.

Every settled brief and every A/B adds a row to `local/builder-evals.jsonl`
(`LLMFILES_BUILDER_EVALS` overrides the path). To tune `builders.md`, read
`python3 ~/llmfiles/scripts/builder-evals.py summary`:

- `provider_split` is the real split of runs. Move task kinds between builders when it drifts
  from the target in `builders.md`.
- Per model and `by_kind`: a low `pass_rate` or a high `escalation_rate` means that builder is
  wrong for that kind. Compare `avg_wall_s` only between builders that pass.
- `ab_win_rate` and `ab_avg_score` compare builders on the same brief, so they are the fairest
  signal. Run an A/B on a kind before moving it.

`check-repo.py` checks that each builder reads the contract, that `builders.md` and the builder
files name the same builders, that every agent the conductor allows or `builders.md` escalates to
exists, that the global deny rules are in place, and that each `opencode.json` command runs on an
existing agent and shadows no file in `commands/`. `/whichmodels` does not cover the conductor or
the builders. The other commands (`/fleet`, `/bugbounty`, the review commands and the rest) are not
adapted to the conductor: run them from `build`.
