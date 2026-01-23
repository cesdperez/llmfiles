---
name: drizzle-postgresql
description: TypeScript ORM patterns for PostgreSQL databases. Use when writing Drizzle schemas, queries, migrations, or when working with PostgreSQL 16+ features, database schema design, or TypeScript database code.
---

# Drizzle ORM with PostgreSQL 16+

## Overview

Drizzle is a headless TypeScript ORM that maps closely to SQL. It generates exactly 1 SQL query per operation, making it ideal for serverless and edge environments.

## Core Principles

- **Favor Core API**: Use `db.select().from()` over Relational Query API (`db.query`) for better control and performance in complex joins/aggregations.
- **Strict Typing**: Leverage `sql<type>` for raw fragments and subqueries to maintain type safety.
- **Explicit Schema**: Define all constraints, defaults, and indexes in schema files.

## Project Structure

```
src/
├── db/
│   ├── index.ts          # Database connection
│   ├── schema.ts         # All table definitions (or split by domain)
│   └── relations.ts      # Relational definitions
├── drizzle/              # Generated migrations
└── drizzle.config.ts     # Drizzle Kit configuration
```

## Schema Definition

```typescript
import { pgTable, serial, varchar, integer, timestamp, text, boolean, pgEnum } from 'drizzle-orm/pg-core';

// Enums first
export const roleEnum = pgEnum('role', ['user', 'admin', 'moderator']);

// Tables with snake_case DB columns, camelCase TS
export const users = pgTable('users', {
  id: serial('id').primaryKey(),
  email: varchar('email', { length: 256 }).notNull().unique(),
  role: roleEnum('role').default('user'),
  createdAt: timestamp('created_at').defaultNow().notNull(),
  updatedAt: timestamp('updated_at').defaultNow().notNull(),
});

export const posts = pgTable('posts', {
  id: serial('id').primaryKey(),
  title: varchar('title', { length: 256 }).notNull(),
  content: text('content'),
  authorId: integer('author_id').references(() => users.id).notNull(),
  published: boolean('published').default(false),
});
```

**Key rules:**
- Always export tables (required for migration generation)
- Use snake_case for DB columns: `createdAt: timestamp('created_at')`
- Or enable auto-casing in config: `casing: 'snake_case'`

## Relations (for nested queries)

```typescript
import { relations } from 'drizzle-orm';

export const usersRelations = relations(users, ({ many }) => ({
  posts: many(posts),
}));

export const postsRelations = relations(posts, ({ one }) => ({
  author: one(users, {
    fields: [posts.authorId],
    references: [users.id],
  }),
}));
```

## Database Connection

```typescript
// node-postgres (traditional)
import { drizzle } from 'drizzle-orm/node-postgres';
import * as schema from './schema';

export const db = drizzle(process.env.DATABASE_URL, { schema });

// postgres.js (modern, prepared statements by default)
import { drizzle } from 'drizzle-orm/postgres-js';
export const db = drizzle(process.env.DATABASE_URL, { schema });
```

## drizzle.config.ts

```typescript
import { defineConfig } from 'drizzle-kit';

export default defineConfig({
  dialect: 'postgresql',
  schema: './src/db/schema.ts',
  out: './drizzle',
  dbCredentials: {
    url: process.env.DATABASE_URL!,
  },
  casing: 'snake_case', // Auto-convert camelCase to snake_case
});
```

## Essential Commands

```bash
# Generate migration from schema changes
npx drizzle-kit generate

# Apply migrations to database
npx drizzle-kit migrate

# Push schema directly (dev only, no migration files)
npx drizzle-kit push

# Pull existing DB schema to TypeScript
npx drizzle-kit pull

# Open Drizzle Studio (visual DB browser)
npx drizzle-kit studio
```

## Query Patterns

### CRUD Operations

```typescript
import { eq, and, or, like, gt, inArray } from 'drizzle-orm';

// Insert
const [newUser] = await db.insert(users)
  .values({ email: 'user@example.com' })
  .returning();

// Batch insert
await db.insert(users).values([
  { email: 'user1@example.com' },
  { email: 'user2@example.com' },
]);

// Select with conditions
const activeAdmins = await db.select()
  .from(users)
  .where(and(
    eq(users.role, 'admin'),
    eq(users.active, true)
  ));

// Select specific fields
const emails = await db.select({ email: users.email })
  .from(users);

// Update
await db.update(users)
  .set({ role: 'admin', updatedAt: new Date() })
  .where(eq(users.id, userId));

// Delete
await db.delete(users).where(eq(users.id, userId));
```

### Relational Queries (nested data)

```typescript
// Fetch users with their posts
const usersWithPosts = await db.query.users.findMany({
  with: {
    posts: true,
  },
});

// With filtering and limits
const result = await db.query.users.findFirst({
  where: eq(users.id, userId),
  with: {
    posts: {
      where: eq(posts.published, true),
      limit: 10,
    },
  },
});
```

### Joins

```typescript
const result = await db.select({
  userName: users.email,
  postTitle: posts.title,
})
.from(users)
.leftJoin(posts, eq(users.id, posts.authorId))
.where(eq(posts.published, true));
```

### Transactions

```typescript
await db.transaction(async (tx) => {
  const [user] = await tx.insert(users)
    .values({ email: 'new@example.com' })
    .returning();

  await tx.insert(posts).values({
    title: 'Welcome',
    authorId: user.id,
  });
});
```

### Parallel DB + External API Calls

When needing DB data and external API data, use `Promise.all`:

```typescript
const [dbData, apiData] = await Promise.all([
  db.select().from(users).where(eq(users.id, userId)),
  fetchFromExternalApi(userId)
]);
```

### Prepared Statements (performance)

```typescript
import { placeholder } from 'drizzle-orm';

const getUserById = db.select()
  .from(users)
  .where(eq(users.id, placeholder('id')))
  .prepare('get_user_by_id');

const user = await getUserById.execute({ id: 1 });
```

## PostgreSQL 16+ Features

### JSON Functions (SQL standard)

```typescript
// Use raw SQL for PG16 JSON constructors
import { sql } from 'drizzle-orm';

// JSON_OBJECT, JSON_ARRAY (PG16+)
const result = await db.execute(sql`
  SELECT JSON_OBJECT('id': id, 'email': email) as user_json
  FROM users
  WHERE id = ${userId}
`);

// IS JSON check
const validJson = await db.execute(sql`
  SELECT * FROM documents
  WHERE data IS JSON
`);
```

### Numeric Literals (PG16+)

```sql
-- Hex, octal, binary literals now supported
SELECT 0x42F, 0o273, 0b100101;
-- Underscores for readability
SELECT 1_000_000;
```

### New Array Functions (PG16+)

```typescript
// array_sample and array_shuffle
const shuffled = await db.execute(sql`
  SELECT array_shuffle(ARRAY[1, 2, 3, 4, 5])
`);

const sampled = await db.execute(sql`
  SELECT array_sample(ARRAY[1, 2, 3, 4, 5], 3)
`);
```

### Performance Monitoring

```typescript
// pg_stat_io view (PG16+) for I/O stats
const ioStats = await db.execute(sql`
  SELECT * FROM pg_stat_io
  WHERE backend_type = 'client backend'
`);
```

## Column Types Reference

```typescript
import {
  serial, bigserial, smallserial,
  integer, bigint, smallint,
  real, doublePrecision, numeric,
  varchar, char, text,
  boolean,
  timestamp, timestamptz, date, time, interval,
  json, jsonb,
  uuid,
  pgEnum,
} from 'drizzle-orm/pg-core';

// JSONB with TypeScript typing
const users = pgTable('users', {
  metadata: jsonb('metadata').$type<{ preferences: string[] }>(),
});

// UUID with default
const items = pgTable('items', {
  id: uuid('id').defaultRandom().primaryKey(),
});

// Timestamp modes
const events = pgTable('events', {
  // Returns Date object
  createdAt: timestamp('created_at', { mode: 'date' }),
  // Returns ISO string
  scheduledAt: timestamp('scheduled_at', { mode: 'string' }),
});
```

## Pitfalls to Avoid

1. **Forgetting to export tables** - Drizzle Kit won't detect unexported schemas for migrations

2. **Using `push` in production** - Only use `push` for development; use `generate` + `migrate` for production deployments

3. **N+1 queries** - Use relational queries (`db.query.*.findMany({ with: {...} })`) instead of manual loops

4. **Missing relations definition** - Relational queries require explicit `relations()` setup, they don't auto-detect from foreign keys

5. **postgres.js in AWS Lambda** - Disable prepared statements: `postgres(url, { prepare: false })`

6. **Forgetting `returning()`** - Insert/update don't return data by default; add `.returning()` to get inserted/updated rows

7. **Type mismatches with bigint** - Use `mode: 'number'` for JS numbers or `mode: 'bigint'` for BigInt

8. **COUNT(*) returns BIGINT** - Postgres `COUNT(*)` returns BIGINT (string in JS); cast in SQL: `sql<number>\`COUNT(*)::int\``

9. **Numeric vs Number** - Postgres `numeric` returns a string; cast in SQL or parse in JS

## Quick Reference

| Task | Command/Code |
|------|--------------|
| Generate migration | `npx drizzle-kit generate` |
| Apply migration | `npx drizzle-kit migrate` |
| Push (dev) | `npx drizzle-kit push` |
| Pull schema | `npx drizzle-kit pull` |
| Visual studio | `npx drizzle-kit studio` |
| Select all | `db.select().from(table)` |
| Select where | `db.select().from(t).where(eq(t.col, val))` |
| Insert | `db.insert(t).values({...}).returning()` |
| Update | `db.update(t).set({...}).where(eq(...))` |
| Delete | `db.delete(t).where(eq(...))` |
| With relations | `db.query.table.findMany({ with: {...} })` |
| Transaction | `db.transaction(async (tx) => {...})` |
| Raw SQL | `db.execute(sql`...`)` |
