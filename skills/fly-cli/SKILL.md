---
name: fly-cli
description: Fly.io CLI for deploying and managing applications. Use when deploying to Fly.io, configuring fly.toml, managing secrets, scaling apps, viewing logs, setting up CI/CD with GitHub Actions, or when the user mentions fly, flyctl, or Fly.io.
---

# Fly.io CLI (flyctl)

## Core Workflow

```bash
fly launch              # Initialize new app (creates fly.toml)
fly deploy              # Deploy changes
fly status              # Check deployment status
fly logs                # Stream application logs
```

## fly.toml Configuration

Minimal working config:

```toml
app = 'my-app'
primary_region = 'iad'

[build]

[http_service]
  internal_port = 3000
  force_https = true
  auto_stop_machines = 'stop'
  auto_start_machines = true
  min_machines_running = 0

[[vm]]
  memory = '512mb'
  cpu_kind = 'shared'
  cpus = 1
```

### Key Sections

**Build options** (mutually exclusive):
```toml
[build]
  dockerfile = "Dockerfile"           # Custom Dockerfile path
  # OR
  image = "flyio/hellofly:latest"     # Pre-built image
  # OR
  builder = "paketobuildpacks/builder:base"  # Buildpack

[build.args]
  NODE_ENV = "production"
```

**Deploy settings**:
```toml
[deploy]
  release_command = "node db/migrate.js"   # Runs before deployment
  strategy = "rolling"                      # rolling|immediate|canary|bluegreen
```

**Environment variables** (non-secret):
```toml
[env]
  NODE_ENV = "production"
  LOG_LEVEL = "info"
```

**Health checks**:
```toml
[[http_service.checks]]
  grace_period = "10s"
  interval = "30s"
  method = "GET"
  path = "/api/health"
  timeout = "5s"
```

**Volumes** (persistent storage):
```toml
[[mounts]]
  source = "data"
  destination = "/app/data"
  initial_size = "1gb"
```

**Multi-process apps**:
```toml
[processes]
  web = "bun run start"
  worker = "bun run worker"
```

## Secrets Management

```bash
# Set secrets (triggers redeploy)
fly secrets set DATABASE_URL="postgres://..." ENCRYPTION_KEY="abc123"

# Set without redeploying
fly secrets set KEY=value --stage
fly deploy  # Deploy when ready

# Import from file
cat .env.production | fly secrets import

# List (shows names only, not values)
fly secrets list

# Remove
fly secrets unset SECRET_NAME
```

## Deployment

```bash
# Standard deploy
fly deploy

# Deploy specific app
fly deploy -a my-app

# Deploy with strategy
fly deploy --strategy canary
fly deploy --strategy bluegreen

# Deploy pre-built image
fly deploy --image ghcr.io/org/app:latest

# Remote build (useful in CI)
fly deploy --remote-only
```

### Deployment Strategies

| Strategy | Behavior |
|----------|----------|
| `rolling` (default) | Update machines one at a time |
| `immediate` | Stop all, then start all (downtime) |
| `canary` | Deploy 1 machine first, verify, then roll out |
| `bluegreen` | Spin up new machines alongside old, switch traffic |

## Scaling

```bash
# View current config
fly scale show

# Horizontal: change machine count
fly scale count 2
fly scale count web=3 worker=1  # Per process group

# Vertical: change VM size
fly scale vm shared-cpu-1x
fly scale vm performance-1x

# Memory
fly scale memory 512
fly scale memory 1024
```

### VM Sizes

| Size | CPU | Memory | Use Case |
|------|-----|--------|----------|
| `shared-cpu-1x` | Shared | 256MB | Dev, low traffic |
| `shared-cpu-2x` | Shared | 512MB | Light production |
| `performance-1x` | 1 dedicated | 2GB | Production |
| `performance-2x` | 2 dedicated | 4GB | High load |

## Logs & Debugging

```bash
# Stream logs
fly logs

# Filter by region
fly logs -r iad

# Filter by machine
fly logs --machine 1234abcd

# Get logs snapshot (no streaming)
fly logs --no-tail

# JSON format (for parsing)
fly logs --json
```

## SSH & Console

```bash
# SSH into running machine
fly ssh console

# Run one-off command
fly ssh console -C "node scripts/seed.js"

# Interactive console (uses console_command from fly.toml)
fly console
```

## Postgres Database

```bash
# Create Postgres cluster
fly postgres create

# Attach to your app (sets DATABASE_URL secret)
fly postgres attach my-postgres-db -a my-app

# Connect directly
fly postgres connect -a my-postgres-db

# Proxy for local access
fly proxy 5432 -a my-postgres-db
# Then connect: psql postgres://postgres:PASSWORD@localhost:5432
```

## GitHub Actions CI/CD

1. Generate deploy token:
```bash
fly tokens create deploy -x 999999h
```

2. Add `FLY_API_TOKEN` secret to GitHub repo settings

3. Create `.github/workflows/fly.yml`:
```yaml
name: Fly Deploy
on:
  push:
    branches: [main]

jobs:
  deploy:
    runs-on: ubuntu-latest
    concurrency: deploy-group
    steps:
      - uses: actions/checkout@v4
      - uses: superfly/flyctl-actions/setup-flyctl@master
      - run: flyctl deploy --remote-only
        env:
          FLY_API_TOKEN: ${{ secrets.FLY_API_TOKEN }}
```

## Common Tasks

### Initial Setup

```bash
fly launch                    # Interactive setup
# Or non-interactive:
fly launch --name my-app --region iad --no-deploy
```

### View App Info

```bash
fly status                    # Machines, health, deployment
fly apps list                 # All your apps
fly releases                  # Deployment history
fly ips list                  # Allocated IPs
```

### Manage Machines

```bash
fly machine list              # List all machines
fly machine start MACHINE_ID  # Start stopped machine
fly machine stop MACHINE_ID   # Stop running machine
fly machine destroy MACHINE_ID # Delete machine
```

### Volumes

```bash
fly volumes create data --size 10 --region iad
fly volumes list
fly volumes extend VOLUME_ID --size 20
```

### Certificates

```bash
fly certs list
fly certs add custom.domain.com
fly certs check custom.domain.com
```

## Pitfalls to Avoid

1. **Secrets trigger redeploy**: `fly secrets set` redeploys immediately. Use `--stage` to batch multiple secrets before deploying.

2. **Volume machine affinity**: Machines with volumes are pinned to specific hosts. You can't move them between regions.

3. **First deploy creates 2 machines**: By default, Fly creates 2 machines for redundancy. Set `min_machines_running = 1` in fly.toml or scale down after.

4. **Release command runs on every deploy**: The `release_command` runs before each deployment, not just the first. Make it idempotent.

5. **Auto-stop needs health checks**: `auto_stop_machines` only works if health checks are configured properly.

## Quick Reference

| Task | Command |
|------|---------|
| Deploy | `fly deploy` |
| Logs | `fly logs` |
| Status | `fly status` |
| SSH | `fly ssh console` |
| Set secret | `fly secrets set KEY=value` |
| Scale horizontally | `fly scale count N` |
| Scale vertically | `fly scale vm SIZE` |
| Restart | `fly apps restart` |
| Open in browser | `fly open` |
| Proxy local port | `fly proxy LOCAL:REMOTE` |
