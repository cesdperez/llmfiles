---
name: cf-cli
description: Cloudflare CLI (`cf`) — manage DNS, zones, accounts, registrar, and the full Cloudflare API surface from the terminal. Use when managing Cloudflare DNS records, zones, domains, account members, or any Cloudflare resource via the `cf` command. Currently v0.0.5 technical preview.
---

# Cloudflare `cf` CLI

The `cf` CLI is Cloudflare's unified CLI (technical preview, v0.0.5), designed to eventually cover all ~3000 Cloudflare API operations across 100+ products. It is schema-driven and optimized for both humans and AI agents. The user is always already logged in.

## Global Flags

Available on every command:

```
-a, --account-id   Cloudflare account ID (or set CLOUDFLARE_ACCOUNT_ID)
-z, --zone         Zone ID or domain name (or set CLOUDFLARE_ZONE_ID)
-q, --quiet        Suppress non-essential output
--json             Structured JSON output (use for scripting/parsing)
--ndjson           Newline-delimited JSON (one object per line)
--fields           Comma-separated fields to include in output
--dryRun           Validate and show what would happen without executing
```

## Context Management

Avoid repeating `-a`/`-z` on every command by setting a default context:

```bash
cf context show                          # show current defaults
cf context set account-id <id-or-name>  # set default account
cf context set zone <domain-or-id>      # set default zone
cf context clear account-id             # clear default

# Save context to project .cfrc instead of user config
cf context set zone example.com -p
```

## Available Top-Level Commands

```
cf accounts    Account settings, members, roles, subscriptions, API tokens
cf dns         DNS records, DNSSEC, analytics, zone transfers
cf zones       Zone list, settings, hold, environments, cache
cf registrar   Domain registration, contacts, auto-renewal, WHOIS privacy
cf context     Manage default account/zone (see above)
cf schema      Inspect API schema for any command
cf agent-context  Output agent context + tool definitions for a product
```

## DNS Records

```bash
# List records for a zone
cf dns records list -z example.com
cf dns records list -z example.com --type A
cf dns records list -z example.com --name-contains api

# Get a specific record
cf dns records get -z example.com --id <record-id>

# Create a record (use --dryRun to preview)
cf dns records create -z example.com --body '{"type":"A","name":"api","content":"1.2.3.4","ttl":300,"proxied":false}'

# Update a record
cf dns records update -z example.com --id <record-id> --body '{"content":"5.6.7.8"}'

# Delete a record
cf dns records delete -z example.com --id <record-id>

# Export zone as BIND file
cf dns records export -z example.com

# Import BIND zone file
cf dns records import -z example.com --body @zone.txt
```

## Zones

```bash
cf zones list                          # list all zones
cf zones get-zones -z example.com      # get zone details
cf zones get-zone-settings -z example.com
cf zones edit-single-setting -z example.com --setting-id ssl --body '{"value":"full"}'
```

## Accounts

```bash
cf accounts list                       # list accounts
cf accounts get -a <account-id>        # get account details
cf accounts members list -a <id>       # list members
cf accounts tokens list -a <id>        # list API tokens
cf accounts logs list -a <id>          # audit log entries
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
- Use `--json` for scripting, plain output for human review
- Prefer `cf context set` over repeating `-z`/`-a` in every command
- Use `--dryRun` before destructive or complex write operations
- Use `cf schema <command path>` to discover flags when unsure

## Common Workflows

### Find and update a DNS record

```bash
# Find the record ID
cf dns records list -z example.com --name api.example.com --json

# Update it
cf dns records update -z example.com --id <id> --body '{"content":"1.2.3.4","proxied":true}'
```

### Inspect zone settings

```bash
cf zones get-zone-settings -z example.com --json | jq '.result[] | select(.id == "ssl")'
```

### Set up project-scoped context

```bash
cf context set zone example.com -p       # saves to .cfrc in project root
cf context set account-id abc123 -p
cf context show
```

## Limitations (v0.0.5)

- Technical preview — not all Cloudflare products have dedicated subcommands yet
- Use `cf agent-context <product>` to get tool definitions for products not yet in the top-level CLI
- Listing zones across more than 500 accounts is not allowed
- Products like Workers, KV, R2, D1 are accessible via `cf agent-context` but may not have standalone subcommands yet — check `cf --help` for current state
