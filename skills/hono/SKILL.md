---
name: hono
description: Fast, lightweight web framework for Edge runtimes. Use when writing Hono routes, middleware, handlers, or when the user mentions Hono, edge functions, Cloudflare Workers with Hono, or building APIs with hono/client RPC.
---

# Hono 4 Web Framework

## Overview

Hono is an ultrafast, lightweight web framework built on Web Standards. Zero dependencies, works across Cloudflare Workers, Deno, Bun, Node.js, Vercel, and AWS Lambda.

## Project Setup

```bash
# Cloudflare Workers
npm create hono@latest my-app -- --template cloudflare-workers

# Bun
bun create hono@latest my-app

# Node.js
npm create hono@latest my-app -- --template nodejs
```

**tsconfig.json for JSX:**
```json
{
  "compilerOptions": {
    "jsx": "react-jsx",
    "jsxImportSource": "hono/jsx"
  }
}
```

## Core Patterns

### App Creation with Typed Bindings

```typescript
import { Hono } from 'hono'

// Simple app
const app = new Hono()

// With Cloudflare bindings
type Bindings = {
  DB: D1Database
  KV: KVNamespace
  BUCKET: R2Bucket
  API_KEY: string
}

type Variables = {
  user: { id: string; name: string }
}

const app = new Hono<{ Bindings: Bindings; Variables: Variables }>()
```

### Routing

```typescript
// Method chaining preserves types (required for RPC client)
const app = new Hono()
  .get('/users', (c) => c.json([]))
  .get('/users/:id', (c) => {
    const id = c.req.param('id') // typed
    return c.json({ id })
  })
  .post('/users', async (c) => {
    const body = await c.req.json()
    return c.json(body, 201)
  })

// Route grouping
const users = new Hono()
  .get('/', (c) => c.json([]))
  .get('/:id', (c) => c.json({ id: c.req.param('id') }))

app.route('/users', users)
```

### Context Object (c)

```typescript
app.get('/example', async (c) => {
  // Request access
  const id = c.req.param('id')
  const query = c.req.query('page')
  const header = c.req.header('Authorization')
  const body = await c.req.json()

  // Response helpers
  return c.text('Hello')           // text/plain
  return c.json({ ok: true })      // application/json
  return c.html(<Page />)          // text/html
  return c.redirect('/login')      // 302 redirect
  return c.redirect('/login', 301) // 301 redirect
  return c.notFound()              // 404

  // Headers and status
  c.status(201)
  c.header('X-Custom', 'value')
  return c.json({ created: true })

  // Request-scoped state
  c.set('user', { id: '123' })
  const user = c.get('user')       // or c.var.user

  // Cloudflare bindings
  const db = c.env.DB
  const kv = c.env.KV
})
```

### Middleware

```typescript
import { createMiddleware } from 'hono/factory'

// Inline middleware
app.use('*', async (c, next) => {
  console.log(`${c.req.method} ${c.req.url}`)
  await next()
})

// Typed reusable middleware
const authMiddleware = createMiddleware<{
  Variables: { userId: string }
}>(async (c, next) => {
  const token = c.req.header('Authorization')
  if (!token) throw new HTTPException(401, { message: 'Unauthorized' })
  c.set('userId', 'extracted-id')
  await next()
})

// Path-specific middleware
app.use('/admin/*', authMiddleware)
```

**Execution order:** Middleware runs in registration order. Code before `next()` runs forward, code after `next()` runs backward (onion model).

### Validation with Zod

```typescript
import { zValidator } from '@hono/zod-validator'
import { z } from 'zod'

const createUserSchema = z.object({
  name: z.string().min(1),
  email: z.string().email(),
})

app.post(
  '/users',
  zValidator('json', createUserSchema),
  (c) => {
    const data = c.req.valid('json') // fully typed
    return c.json(data, 201)
  }
)

// Validate multiple targets
app.get(
  '/users/:id',
  zValidator('param', z.object({ id: z.string() })),
  zValidator('query', z.object({ include: z.string().optional() })),
  (c) => {
    const { id } = c.req.valid('param')
    const { include } = c.req.valid('query')
    return c.json({ id, include })
  }
)
```

### Error Handling

```typescript
import { HTTPException } from 'hono/http-exception'

// Throw HTTP errors
app.get('/protected', (c) => {
  throw new HTTPException(401, { message: 'Unauthorized' })
})

// With cause for debugging
throw new HTTPException(500, {
  message: 'Database error',
  cause: originalError,
})

// Global error handler
app.onError((err, c) => {
  if (err instanceof HTTPException) {
    return err.getResponse()
  }
  console.error(err)
  return c.json({ error: 'Internal Server Error' }, 500)
})

// Custom 404
app.notFound((c) => c.json({ error: 'Not Found' }, 404))
```

### RPC Client (Type-Safe API Calls)

```typescript
// server.ts
const app = new Hono()
  .get('/users', (c) => c.json([{ id: '1', name: 'Alice' }]))
  .post('/users', zValidator('json', createUserSchema), async (c) => {
    const data = c.req.valid('json')
    return c.json(data, 201)
  })

export type AppType = typeof app
export default app

// client.ts
import { hc } from 'hono/client'
import type { AppType } from './server'

const client = hc<AppType>('http://localhost:8787')

// Fully typed requests
const res = await client.users.$get()
const users = await res.json()

const res = await client.users.$post({
  json: { name: 'Bob', email: 'bob@example.com' },
})
```

### Testing

```typescript
import { testClient } from 'hono/testing'
import app from './app'

const client = testClient(app)

test('GET /users returns array', async () => {
  const res = await client.users.$get()
  expect(res.status).toBe(200)
  const data = await res.json()
  expect(Array.isArray(data)).toBe(true)
})

test('POST /users creates user', async () => {
  const res = await client.users.$post({
    json: { name: 'Test', email: 'test@example.com' },
  })
  expect(res.status).toBe(201)
})

// With headers
const res = await client.users.$get({}, {
  headers: { Authorization: 'Bearer token' },
})
```

## Built-in Middleware

```typescript
import { cors } from 'hono/cors'
import { secureHeaders } from 'hono/secure-headers'
import { logger } from 'hono/logger'
import { compress } from 'hono/compress'
import { jwt } from 'hono/jwt'
import { basicAuth } from 'hono/basic-auth'
import { bearerAuth } from 'hono/bearer-auth'
import { csrf } from 'hono/csrf'
import { etag } from 'hono/etag'

app.use(logger())
app.use(secureHeaders())
app.use(compress())
app.use('/api/*', cors({ origin: 'https://example.com' }))

// JWT (must specify algorithm explicitly for security)
app.use('/api/*', jwt({ secret: 'key', alg: 'HS256' }))

// Basic auth
app.use('/admin/*', basicAuth({ username: 'admin', password: 'secret' }))
```

## Runtime-Specific Patterns

### Cloudflare Workers

```typescript
// Access bindings via c.env
app.get('/data', async (c) => {
  const value = await c.env.KV.get('key')
  const obj = await c.env.BUCKET.get('file.txt')
  const result = await c.env.DB.prepare('SELECT * FROM users').all()
  return c.json({ value, result })
})

// waitUntil for background work
app.post('/log', async (c) => {
  c.executionCtx.waitUntil(
    fetch('https://analytics.example.com', { method: 'POST', body: '...' })
  )
  return c.text('OK')
})

export default app
```

### Bun

```typescript
import { serveStatic } from 'hono/bun'

app.use('/static/*', serveStatic({ root: './' }))

export default {
  port: 3000,
  fetch: app.fetch,
}
```

### Node.js

```typescript
import { serve } from '@hono/node-server'
import { serveStatic } from '@hono/node-server/serve-static'

app.use('/static/*', serveStatic({ root: './' }))

serve({ fetch: app.fetch, port: 3000 })
```

## JSX Components

```tsx
import type { FC } from 'hono/jsx'

const Layout: FC = ({ children }) => (
  <html>
    <head><title>App</title></head>
    <body>{children}</body>
  </html>
)

const Page: FC<{ name: string }> = ({ name }) => (
  <Layout>
    <h1>Hello, {name}!</h1>
  </Layout>
)

app.get('/', (c) => c.html(<Page name="World" />))

// Async components
const AsyncData: FC = async () => {
  const data = await fetchData()
  return <div>{data}</div>
}
```

## OpenAPI with Zod

```typescript
import { OpenAPIHono, createRoute, z } from '@hono/zod-openapi'

const app = new OpenAPIHono()

const route = createRoute({
  method: 'get',
  path: '/users/{id}',
  request: {
    params: z.object({ id: z.string() }),
  },
  responses: {
    200: {
      content: { 'application/json': { schema: z.object({ id: z.string(), name: z.string() }) } },
      description: 'User found',
    },
  },
})

app.openapi(route, (c) => {
  const { id } = c.req.valid('param')
  return c.json({ id, name: 'Alice' })
})

app.doc('/doc', { openapi: '3.0.0', info: { title: 'API', version: '1' } })
```

## Pitfalls to Avoid

1. **Don't create controller files** - Write handlers inline with routes to preserve type inference. Use `app.route()` for organization, not separate handler files.

2. **Chain methods for RPC types** - `const app = new Hono().get(...).post(...)` preserves types. Separate `app.get(); app.post()` calls break RPC client inference.

3. **Always specify JWT algorithm** - `jwt({ secret, alg: 'HS256' })`. Omitting `alg` is a security vulnerability (algorithm confusion attack).

4. **Headers must be lowercase** - `c.req.header('content-type')` not `c.req.header('Content-Type')`.

5. **Content-Type required for validation** - JSON validation requires `Content-Type: application/json` header in requests.

6. **c.env not process.env** - On Cloudflare Workers, use `c.env.VAR` not `process.env.VAR`. Use `env()` helper for cross-runtime compatibility.

7. **HTTPException.getResponse() ignores context** - If you need context headers in error responses, manually create a new Response.

## Quick Reference

| Task | Code |
|------|------|
| Get param | `c.req.param('id')` |
| Get query | `c.req.query('page')` |
| Get header | `c.req.header('authorization')` |
| Get body | `await c.req.json()` |
| JSON response | `c.json({ data }, 200)` |
| Set header | `c.header('X-Key', 'value')` |
| Set state | `c.set('key', value)` |
| Get state | `c.get('key')` or `c.var.key` |
| Validated data | `c.req.valid('json')` |
| Cloudflare binding | `c.env.KV` |
| Runtime detection | `getRuntimeKey()` |
| Cross-runtime env | `env(c).VAR` |
