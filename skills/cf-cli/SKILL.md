---
name: cf-cli
description: Cloudflare CLI (`cf`), manage DNS, zones, accounts, registrar, and the full Cloudflare API surface from the terminal. Use when managing Cloudflare DNS records, zones, domains, account members, or any Cloudflare resource via the `cf` command. Currently v0.2.0.
---

# Cloudflare `cf` CLI

The `cf` CLI is Cloudflare's unified CLI (v0.2.0), designed to eventually cover all ~3000 Cloudflare API operations across 100+ products. It is schema-driven and optimized for both humans and AI agents. The user is always already logged in.

## Global Flags

Available on every command:

```
-z, --zone           Zone ID or domain name (or set CLOUDFLARE_ZONE_ID)
-q, --quiet          Suppress non-essential output
--local              Route to a local `wrangler dev` / `cf dev` Miniflare session
--local-endpoint     Local Miniflare endpoint URL (required with --local)
-h, --help
-v, --version
```

Account is no longer a global flag. Supply it via `CLOUDFLARE_ACCOUNT_ID` or
`cf context set account-id <id>`. `--dry-run` is now a per-command option (on
both read and write commands) rather than a global flag.

## Context Management

Avoid repeating `-z` (and supplying the account) on every command by setting a
default context:

```bash
cf context show                            # show current defaults
cf context set account-id <id-or-name>    # set default account
cf context set zone <domain-or-id>        # set default zone
cf context set compliance-region <region> # set data-localization region
cf context clear account-id               # clear default (key optional)

# Save context to project .cfrc instead of user config
cf context set zone example.com -p
```

## Available Top-Level Commands

```
cf accounts    Account settings, members, roles, subscriptions, API tokens
cf dns         DNS records, DNSSEC, analytics, settings, zone transfers
cf zones       Zone list/create/delete, settings, hold, environments, cache
cf registrar   Domain registration, contacts, auto-renewal, WHOIS privacy
cf context     Manage default account/zone (see above)
cf schema      Inspect API schema for any command
cf agent-context  Output agent context + tool definitions for a product

# Wrangler-style project/worker toolset (v0.2.0)
cf build       Build a project for Cloudflare
cf deploy      Deploy a project to Cloudflare
cf dev         Run the project's Cloudflare dev server
cf versions    Manage Worker Versions (e.g. versions upload)
cf auth        Authentication (login, logout, whoami) — user is pre-authenticated
cf complete    Generate shell completions
```

## DNS Records

```bash
# List records for a zone
cf dns records list -z example.com
cf dns records list -z example.com --type A
cf dns records list -z example.com --name-contains api

# Get a specific record (record ID is a positional argument)
cf dns records get <record-id> -z example.com

# Create a record (use --dry-run to preview)
cf dns records create -z example.com --body '{"type":"A","name":"api","content":"1.2.3.4","ttl":300,"proxied":false}'

# Partial update = edit (PATCH); update = overwrite the whole record (PUT)
cf dns records edit <record-id> -z example.com --body '{"content":"5.6.7.8"}'

# Delete a record
cf dns records delete <record-id> -z example.com

# Export zone as BIND file
cf dns records export -z example.com

# Import BIND zone file
cf dns records import -z example.com --body @zone.txt
```

## Zones

```bash
cf zones list                                   # list all zones
cf zones get -z example.com                     # get zone details
cf zones settings get ssl -z example.com        # get one setting (no bulk "get all")
cf zones settings edit ssl -z example.com --body '{"value":"full"}'
```

## Accounts

Account comes from `CLOUDFLARE_ACCOUNT_ID` or `cf context set account-id <id>`
(the `-a` flag was removed).

```bash
cf accounts list                       # list accounts
cf accounts get                        # get account details
cf accounts members list               # list members
cf accounts tokens list                # list API tokens
cf accounts logs audit                 # audit log entries
```

## Schema Discovery

Use these to explore what's available before running commands:

```bash
cf schema --list                       # list all available schemas (JSON)
cf schema dns records create           # show schema for a specific command
cf agent-context dns                   # full agent context for DNS product
cf agent-context --list                # list all products with agent context
```

Products with agent context (subset): `d1`, `dns`, `kv`, `r2`, `workers`, `pages`, `zones`, `queues`, `hyperdrive`, `zero-trust`, `email-routing`, `load-balancers`, `rules`, `ssl`, `stream`, `images`, `pipelines`, `secrets-store`, `turnstile`, `vectorize`, `waiting-rooms`, and many more.

## Command Patterns

- Use `get` not `info` (`cf accounts get`, not `cf accounts info`)
- Use `--force` not `--skip-confirmations` for destructive operations
- Prefer `cf context set zone` over repeating `-z`; set the account via
  `cf context set account-id` or `CLOUDFLARE_ACCOUNT_ID`
- Use `--dry-run` before destructive or complex write operations
- Use `cf schema <command path>` to discover flags when unsure

## Common Workflows

### Find and update a DNS record

```bash
# Find the record ID
cf dns records list -z example.com --name api.example.com

# Update it (edit = partial/PATCH; id is positional)
cf dns records edit <id> -z example.com --body '{"content":"1.2.3.4","proxied":true}'
```

### Inspect zone settings

```bash
cf zones settings get ssl -z example.com
```

### Set up project-scoped context

```bash
cf context set zone example.com -p       # saves to .cfrc in project root
cf context set account-id abc123 -p
cf context show
```

## Limitations (v0.2.0)

- Not all Cloudflare products have dedicated subcommands yet
- Use `cf agent-context <product>` to get tool definitions for products not yet in the top-level CLI
- Listing zones across more than 500 accounts is not allowed
- Products like Workers, KV, R2, D1 are accessible via `cf agent-context` but may not have standalone subcommands yet — check `cf --help` for current state
