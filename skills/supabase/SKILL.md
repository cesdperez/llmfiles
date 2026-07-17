---
name: supabase
description: Run operational tasks against Supabase Postgres databases in your own account using the Supabase CLI alone (no MCP server). Use when connecting to a Supabase project, running SQL queries against a remote/local database, inspecting DB health/performance, checking security & performance advisors, or when the user mentions Supabase, `supabase db query`, or their Supabase project.
---

# Supabase CLI Skill (operational / query-focused)

CLI-only workflow for connecting to Supabase projects and running queries. No MCP
server required. For *building app code* against Supabase (Auth, Edge Functions,
client libs), prefer the official skills instead (see Related resources).

## Local Setup
- Version: 2.109.1 (stable channel, via `supabase/tap`)
- Install path: `/opt/homebrew/bin/supabase`
- Upgrade: `brew upgrade supabase`
- Auth token stored globally after `supabase login` (persists across directories)

## Your Context
- Account is already authenticated (`supabase login` done).
- Known project: **Sleepscore app** — ref `rsthwlwnsudfgpjjpuxv`, Postgres 17.6,
  region `eu-central-1`, org `kzaiqmmlpzlyghkrfhyj`.
- List current projects anytime: `supabase projects list`

## Core Workflow: connect + query (CLI only)

The recommended path uses a **linked project** so queries run through the
Management API — no DB password or connection string needed.

```bash
# 1. One-time auth (browser OAuth). Skip if already logged in.
supabase login

# 2. See your projects and grab a ref
supabase projects list
supabase projects list --output-format json   # machine-readable

# 3. Link a project to the current directory (creates supabase/.temp/project-ref)
supabase link --project-ref rsthwlwnsudfgpjjpuxv

# 4. Run SQL against the linked remote DB via Management API
supabase db query --linked "select now();"
supabase db query --linked -f ./report.sql
supabase db query --linked --output-format json "select id, email from auth.users limit 5;"
```

### Query without linking
```bash
# Direct Postgres connection string (pooler or direct). URL must be percent-encoded.
supabase db query --db-url "$DATABASE_URL" "select count(*) from public.foo;"

# Local dev stack (after `supabase start`)
supabase db query --local "select 1;"
```

### Query targets (pick one flag)
| Flag | Target | Needs |
|------|--------|-------|
| `--linked` | Linked remote project | `supabase link` + login |
| `--db-url <url>` | Any Postgres via connection string | percent-encoded URL |
| `--local` | Local stack | `supabase start` running |

## Inspecting the database (read-only diagnostics)

`supabase inspect db <tool>` runs curated diagnostic queries. Works with the same
target flags (`--linked` / `--db-url` / `--local`).

```bash
supabase inspect db table-stats --linked      # row counts, sizes per table
supabase inspect db outliers --linked         # slowest queries by total time
supabase inspect db calls --linked            # most-called queries
supabase inspect db long-running-queries --linked
supabase inspect db blocking --linked         # queries blocking others
supabase inspect db locks --linked
supabase inspect db index-stats --linked      # index usage / efficiency
supabase inspect db bloat --linked            # table/index bloat
supabase inspect db cache-hit --linked        # buffer cache hit rate
supabase inspect db vacuum-stats --linked

# Dump every inspect metric to CSV
supabase inspect report --output-dir ./inspect --linked
```

## Security & performance advisors
```bash
supabase db advisors --linked                        # all issues (RLS gaps, missing indexes, etc.)
supabase db advisors --linked --type security        # security only
supabase db advisors --linked --type performance     # performance only
supabase db advisors --linked --level error          # minimum severity to show
supabase db advisors --linked --fail-on error        # non-zero exit for CI gating
```

## Schema & data dumps (read-only)
```bash
supabase db dump --linked -f schema.sql            # schema only (default)
supabase db dump --linked --data-only -f data.sql  # data only
supabase db dump --linked --role-only -f roles.sql # roles/grants
```

## Output formats
- Global `--output-format text|json|stream-json` on most commands (text default).
- Use `--output-format json` when you need to parse results programmatically.
- `--yes` skips interactive confirmation prompts (useful in scripts/agents).

## Gotchas
- **"Cannot find project ref. Have you run supabase link?"** — you ran a `--linked`
  command in a directory with no linked project. Run `supabase link --project-ref <ref>`
  first, or use `--db-url` / `--local` instead.
- `--linked` state is **per-directory** (stored in `supabase/.temp/project-ref`),
  but the auth token is **global**. Different repos → link each once.
- `db query --linked` executes through the **Management API**, so it does NOT need
  the DB password — only login + link. `--db-url` DOES need credentials in the URL.
- `--db-url` connection strings must be **percent-encoded** (escape special chars
  in the password).
- Many `inspect db` subcommands are marked **deprecated** (e.g. `table-sizes`,
  `unused-indexes`); prefer the non-deprecated equivalents (`table-stats`,
  `index-stats`) shown above.
- Writes (INSERT/UPDATE/DELETE/DDL) via `db query` run for real against the target —
  double-check you're pointed at the intended env before mutating. Prefer migrations
  (`supabase migration`) for schema changes you want tracked.

## Quick Reference
```bash
supabase login                                     # authenticate
supabase projects list                             # list projects + refs
supabase link --project-ref <ref>                  # link current dir
supabase db query --linked "<sql>"                 # run SQL (remote, via Mgmt API)
supabase db query --linked -f file.sql             # run SQL file
supabase db query --db-url "<url>" "<sql>"          # run SQL (connection string)
supabase db query --local "<sql>"                  # run SQL (local stack)
supabase inspect db table-stats --linked           # DB diagnostics
supabase db advisors --linked                      # security/perf advisors
supabase db dump --linked -f schema.sql            # dump schema
```

## Related resources (for app-building, not covered here)
- Official agent skills: `github.com/supabase/agent-skills`
  (`npx skills add supabase/agent-skills`) — covers Auth, Edge Functions, Realtime,
  Storage, client libs, and Postgres best practices.
- Official MCP server + Claude Code plugin: `supabase.com/docs/guides/ai-tools/mcp`
  (`claude plugin install supabase@claude-plugins-official`).
