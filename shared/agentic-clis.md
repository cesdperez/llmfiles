# Agentic CLI registry

These are CLIs used by agents with companion skills. Read this file when asked
to "upgrade all my CLIs", upgrade one of these tools, or maintain its skills.

## Upgrade procedure

1. Check each registered CLI's executable, version, and installation owner.
   Treat the tables as maintenance recipes, not proof that a tool is still installed.
   Skip missing CLIs and report them; retain their skill entries for future use.
2. Upgrade installed tools with their existing package manager and release channel.
   Run `brew update` once before targeted Homebrew upgrades. Limit upgrades to the
   registered tools; project dependencies require a project-specific request.
3. Refresh each CLI's companion skills in the same pass, even if the CLI is already
   current. Run a shared skill update once, such as `cf-cli` for both Cloudflare CLIs.
   Use named Skills CLI updates rather than updating unrelated installed skills.
4. For repository-maintained skills, compare the upgraded CLI's help, changelog,
   and official documentation with the skill. Apply necessary corrections while
   preserving local workflow rules. Report "reviewed, no changes needed" when appropriate.
5. Verify versions and skill sources/links, review repository diffs, and run
   `git diff --check`. Report versions before and after, skill updates, skipped or
   failed entries, and any restart requirement. Keep this registry current if an
   installation owner or skill source changes.

"Upgrade all" authorizes the listed CLI and companion-skill updates, including
necessary edits to local skills. It does not mean deploying projects or running
their migrations. Continue independent entries when one upgrade fails.

## Installed tools

| CLI | Installation and CLI upgrade | Companion skill and ownership | Skill upgrade |
| --- | --- | --- | --- |
| `cf` / `cloudflare` | Global npm package: `npm install -g cf@latest` | Official [Cloudflare `cf-cli`](https://github.com/cloudflare/skills/tree/main/skills/cf-cli), managed outside this repo | `npx --yes skills@latest update cf-cli -g -y` |
| `wrangler` | Global npm package: `npm install -g wrangler@latest` | Same managed `cf-cli` skill covers tool selection and Wrangler fallbacks; use [Wrangler docs](https://developers.cloudflare.com/workers/wrangler/) for project-specific commands | Refresh `cf-cli` once alongside `cf`; review Wrangler-related guidance against current docs |
| `glab` | Homebrew formula: `brew upgrade glab` | [Local `glab-cli`](../skills/glab-cli/SKILL.md), maintained in this repo | Review and update the local skill against [GitLab CLI docs](https://docs.gitlab.com/cli/), especially command/flag changes; preserve writing and review policies |
| `twg` | Standalone binary in `~/.local/bin`: `twg upgrade --yes` | Vendor-bundled `twg` and `twg-*` skills in `~/.agents/skills/` and `~/.claude/skills/` | A binary upgrade refreshes detected installed skills. If the binary is already current, refresh separately: `twg skills install --agent claude --yes`. Verify options with `twg upgrade --help` and `twg skills install --help` |
| `orca` | CLI shipped with the app from the `stablyai/orca` Homebrew tap: `brew upgrade --cask stablyai/orca/orca`. The qualified name distinguishes it from Plotly's unrelated `orca` cask | Managed `orchestration` skill from [stablyai/orca](https://github.com/stablyai/orca); `orca-cli` and other guides are also served by the binary | `orca skills update --all` refreshes already-installed Orca skills. Read version-matched guides with `orca skills get <name>`; verify upgrade options with `orca skills update --help` |
| `skills` (via `npx`) | Run `npx --yes skills@latest ...`; no global installation to upgrade | Managed [`find-skills`](https://github.com/vercel-labs/skills/tree/main/skills/find-skills) in `~/.agents/skills/` | `npx --yes skills@latest update find-skills -g -y` |

The Skills CLI records global sources in `~/.agents/.skill-lock.json`.
`cf-cli` lives in `~/.agents/skills/cf-cli/`; Claude's skill path links there.
To restore it on another machine:

```bash
npx --yes skills@latest add cloudflare/skills --skill cf-cli -g -a codex claude-code -y
```

## Repository skills without a detected global CLI

These skills remain useful for project-local or temporary CLI invocations. Check
availability again during an upgrade; do not install a global CLI just because
its companion skill exists.

| CLI | CLI upgrade when installed | Companion skill and refresh |
| --- | --- | --- |
| `playwright-cli` | Global npm install: `npm install -g @playwright/cli@latest`; preserve another package manager if detected | Microsoft's [official skill](https://github.com/microsoft/playwright-cli/tree/main/skills/playwright-cli) is currently kept as a [repository copy with references](../skills/playwright-cli/). After a CLI upgrade, review/sync the entire skill folder from that exact package version. Generate it in a temporary directory with `playwright-cli install --skills` and preserve the repo symlinks. The skill is also independently installable; see below |
| `supabase` | For the Homebrew installation recorded by the skill: `brew upgrade supabase`; verify the actual owner first | [Local operational skill](../skills/supabase/SKILL.md). Review against [CLI documentation](https://supabase.com/docs/reference/cli/introduction) after a CLI upgrade. The official `supabase/agent-skills` app-building skills serve a different scope and do not replace this operational skill |
| `likec4` | For a global npm installation: `npm install -g likec4@latest`; project-local versions stay with their project | [Local DSL skill](../skills/likec4/SKILL.md). Review against [LikeC4 CLI docs](https://likec4.dev/tooling/cli/) and its [official DSL skill](https://github.com/likec4/likec4/tree/main/skills/likec4-dsl) after a CLI upgrade; preserve local conventions |

### Playwright skill installation options

Playwright documents a [native skill installer](https://playwright.dev/agent-cli/skills):
`playwright-cli install --skills=agents --global` installs into `~/.agents/skills/`,
and `playwright-cli install --skills --global` targets Claude's skill directory.

For a source-tracked installation with a separate update command, use Microsoft's
official repository through the Skills CLI. First reconcile this repository's
existing agent symlinks; these commands apply after migrating the copied skill:

```bash
npx --yes skills@latest add microsoft/playwright-cli --skill playwright-cli -g -a codex claude-code -y
npx --yes skills@latest update playwright-cli -g -y
```

API-only and framework skills such as `intervals-icu`, `zitadel-api`, and `svelte`
are outside this CLI upgrade registry. Agent launchers and unrelated system tools
are also outside its scope.
