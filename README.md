# llmfiles

This repo is to LLM coding assistants what [dotfiles](https://wiki.archlinux.org/title/Dotfiles) are to your shell, a single place to manage your configuration, symlinked wherever tools expect it. The name comes from there.

Manages Claude Code skills, commands, agents, and global instructions in one place.
Claude Code is the primary setup. Codex adaptations live under `codex/` and reuse the
existing command bodies, agent instructions, skills, and shared protocols.

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
│   └── pre-commit
├── scripts/
│   └── <script-name>.py
├── shared/
│   ├── CLAUDE.md
│   ├── agentic-clis.md
│   ├── glab-mr-context.md
│   └── review-lenses.md
├── statusline/
│   └── statusline-command.sh
├── codex/
│   ├── AGENTS.md
│   ├── compatibility.md
│   ├── agents/
│   │   └── <agent-name>.toml
│   └── skills/
│       └── <command-name>/
│           ├── SKILL.md
│           └── agents/openai.yaml
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

### Git hooks (`hooks/`)

`pre-commit` rejects em dashes in staged lines, so the writing rule in `shared/CLAUDE.md` holds
without a model remembering it.

### Claude Code hooks (`claude-hooks/`)

`subagent-context-budget.py` is a `PostToolUse` hook. When a subagent's context passes 300k
tokens, it tells that subagent once to finish its step and report a handoff. A subagent cannot
see its own token count, so the delegation rule in `shared/CLAUDE.md` needs this to hold.
`SUBAGENT_CONTEXT_WARN_TOKENS` overrides the limit.

### Status line (`statusline/statusline-command.sh`)

Claude Code status line: path, git branch, model and effort, context window usage. It reads
the session JSON on stdin and needs `jq`.

### Global instructions (`shared/CLAUDE.md`)

User-level instructions for every Claude Code session, linked to `~/.claude/CLAUDE.md`.

### Shared protocols (`shared/<name>.md`)

Content reused by several commands, extracted so it lives in one place. Commands load it with an explicit read, for example `Read ~/llmfiles/shared/review-lenses.md`.

Deliberately not skills: a skill is auto-listed with its description and can activate in unrelated sessions, whereas a shared protocol should load only when a command asks for it. Use a skill when the knowledge should surface on its own (`glab-cli`), a shared protocol when it should not (`review-lenses`).

Current protocols:
- `review-lenses.md`, the lens catalog and parallel fan-out contract, used by `/glablensedreview`, `/locallensedreview`.
- `glab-mr-context.md`, GitLab MR setup (batched fetch, read-only MR-head worktree, diff anchor map, prior-pass marker check) plus the acme lens bindings, used by `/glablensedreview` and the per-MR agents of `/glabsummary`.

## Installation

Clone to `~/llmfiles`. Commands, adapters, and settings reference files by that path.

```bash
git clone git@github.com:cesdperez/llmfiles.git ~/llmfiles
```

Prerequisites: `python3` for the scripts and hooks, `jq` for the status line, and an
authenticated `glab` for the GitLab commands. The GitLab review commands also expect the
acme repos cloned under `~/projects/acme/`. Other CLIs with companion skills are
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

The status line is a file symlink, referenced from `~/.claude/settings.json`:

```bash
ln -sf ~/llmfiles/statusline/statusline-command.sh ~/.claude/statusline-command.sh
```

```json
"statusLine": { "type": "command", "command": "bash ~/.claude/statusline-command.sh" }
```

Claude Code hooks are referenced by absolute path from the `hooks` block of
`~/.claude/settings.json`. Append the entry to an existing `PostToolUse` array rather than
replacing it:

```json
"PostToolUse": [
  { "matcher": "*", "hooks": [{ "type": "command", "command": "python3 ~/llmfiles/claude-hooks/subagent-context-budget.py", "timeout": 5 }] }
]
```

Anything spawned without a named agent follows `CLAUDE_CODE_SUBAGENT_MODEL`. Set it in the
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

All eight command adapters are explicit-only skills. `agents/openai.yaml` sets
`allow_implicit_invocation: false`; shared knowledge skills retain their own policies.

`codex/compatibility.md` owns argument handling, delegation, tool substitutions, and Codex
attribution for GitLab text. Each adapter loads its existing `commands/<name>.md` body and
supplies any further differences. Codex agent definitions load the corresponding
`agents/<name>.md` body; `explorer` maps to Claude's `Explore`.

Codex agents use `gpt-6.1-sol` at high effort for `worker`, `reviewer`, and
`general-purpose`, and medium effort for `reviewer-fast`. `explorer`, `worker-fast`, and
`gitlab` use `gpt-6-luna` at high effort for narrower tasks. These are explicit model IDs,
not Claude aliases or equivalent effort levels. Choose available models in the TOML files
if your account does not support them; `$whichmodels` proposes changes to Codex settings.

Adaptation boundaries:

- Review workflows preserve their posting policies. Use `--dry-run` with
  `$glablensedreview` to inspect findings before posting.
- Review agents' read-only behavior is instructed, not a separate sandbox. Agents inherit
  the parent session's permissions and schedule within its available concurrency limit.
- `$dailyworkrecap` reads the existing collector's Claude transcripts. Codex session
  history is not collected. Slack coverage depends on available connected tools.
- Claude's `PushNotification`, Workflow, agent-team settings, status line, and
  `claude-hooks/` are not installed as Codex features. The adapters use available Codex capabilities and report
  missing coverage where it affects the result.
