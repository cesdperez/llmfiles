---
name: zitadel-api
description: Manage Zitadel IAM via API — orgs, projects, users, and instance configuration. Use when managing Zitadel organizations, projects, users, roles, service accounts, or instance-level settings.
---

# Zitadel API

Internal management only. Use v2 APIs. Auth via PAT for scripts, Private Key JWT for services.

## Auth

All requests need a Bearer token. For management APIs the token **must** include:
```
urn:zitadel:iam:org:project:id:zitadel:aud
```

**PAT (simplest):** `Authorization: Bearer $PAT`

**Client Credentials:**
```bash
curl -X POST "$DOMAIN/oauth/v2/token" \
  -H "Authorization: Basic $(echo -n '$CLIENT_ID:$CLIENT_SECRET' | base64)" \
  -H "Content-Type: application/x-www-form-urlencoded" \
  -d "grant_type=client_credentials&scope=openid+urn:zitadel:iam:org:project:id:zitadel:aud"
```

## Hierarchy

```
Instance (root)
└── Organizations
    ├── Users (humans + machine accounts)
    └── Projects
        ├── Roles
        └── Authorizations (user ↔ role)
```

## Users

```bash
# Create human user
curl -X POST "$DOMAIN/v2/users/new" -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"human": {"profile": {"givenName": "Jane", "familyName": "Doe"}, "email": {"email": "jane@example.com", "isEmailVerified": true}}}'

# Create machine/service account
curl -X POST "$DOMAIN/v2/users/new" -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"machine": {"name": "my-service", "description": "Backend service"}}'

# Search users
curl -X POST "$DOMAIN/v2/users:search" -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"query": {"limit": 100}, "queries": [{"userNameQuery": {"userName": "jane%"}}]}'

# Get user by ID
curl "$DOMAIN/v2/users/$USER_ID" -H "Authorization: Bearer $TOKEN"

# Delete user
curl -X DELETE "$DOMAIN/v2/users/$USER_ID" -H "Authorization: Bearer $TOKEN"
```

## Organizations

```bash
# List orgs (admin API)
curl -X POST "$DOMAIN/admin/v1/orgs:search" -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" -d '{"query": {"limit": 100}}'

# Create org
curl -X POST "$DOMAIN/admin/v1/orgs" -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"name": "My Org"}'

# Get org
curl "$DOMAIN/management/v1/orgs/$ORG_ID" -H "Authorization: Bearer $TOKEN"
```

## Projects

```bash
# Create project (scoped to org via header)
curl -X POST "$DOMAIN/management/v1/projects" \
  -H "Authorization: Bearer $TOKEN" \
  -H "x-zitadel-orgid: $ORG_ID" \
  -H "Content-Type: application/json" \
  -d '{"name": "My Project"}'

# Add role to project
curl -X POST "$DOMAIN/management/v1/projects/$PROJECT_ID/roles" \
  -H "Authorization: Bearer $TOKEN" \
  -H "x-zitadel-orgid: $ORG_ID" \
  -H "Content-Type: application/json" \
  -d '{"roleKey": "admin", "displayName": "Admin"}'

# Assign role to user
curl -X POST "$DOMAIN/v2/organizations/$ORG_ID/authorizations" \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"userId": "$USER_ID", "projectId": "$PROJECT_ID", "roles": ["admin"]}'
```

## Instance / Root Config

```bash
# Get instance settings
curl "$DOMAIN/admin/v1/settings" -H "Authorization: Bearer $TOKEN"

# Set default org
curl -X PUT "$DOMAIN/admin/v1/orgs/default" -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" -d '{"orgId": "$ORG_ID"}'

# List instance admins
curl "$DOMAIN/admin/v1/members" -H "Authorization: Bearer $TOKEN"

# Add instance admin
curl -X POST "$DOMAIN/admin/v1/members" -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" -d '{"userId": "$USER_ID", "roles": ["IAM_OWNER"]}'
```

## Pitfalls

- **Missing audience scope** → silent 401 "invalid audience". Always add `urn:zitadel:iam:org:project:id:zitadel:aud`.
- **Wrong org context** → use `x-zitadel-orgid` header for management v1 calls scoped to an org.
- **Role assignment silently succeeds in wrong scope** → double-check `orgId` + `projectId` combo.
- **PATs shown only once** → copy immediately on creation.
