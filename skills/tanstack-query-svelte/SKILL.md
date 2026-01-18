---
name: tanstack-query-svelte
description: Server state management with TanStack Query v5 for Svelte. Use when fetching data in Svelte/SvelteKit, using createQuery/createMutation, caching API responses, or when user mentions svelte-query, tanstack query svelte, or server state in Svelte apps.
---

# TanStack Query v5 for Svelte

## Overview

TanStack Query manages server state in Svelte apps—data owned by the server that your app displays as a cached snapshot. It uses Svelte stores for reactivity, integrating seamlessly with runes and the `$` auto-subscription syntax.

## Core Paradigm

**Server state ≠ Client state.** Don't copy fetched data to `$state`. Query IS your server state manager—use the cache directly via store subscriptions.

## Setup (SvelteKit)

```svelte
<!-- +layout.svelte -->
<script lang="ts">
  import { QueryClient } from '@tanstack/svelte-query'
  import { QueryClientProvider } from '@tanstack/svelte-query'
  import { SvelteQueryDevtools } from '@tanstack/svelte-query-devtools'

  let { children } = $props()

  const queryClient = new QueryClient({
    defaultOptions: {
      queries: {
        staleTime: 60 * 1000,
      },
    },
  })
</script>

<QueryClientProvider client={queryClient}>
  {@render children()}
  <SvelteQueryDevtools />
</QueryClientProvider>
```

## v5 Breaking Changes

### Removed: Query callbacks
`onSuccess`, `onError`, `onSettled` removed from `createQuery` (still exist on `createMutation`).

### Other v5 Changes
- `cacheTime` renamed to `gcTime`
- `isLoading` split: `isPending` (no data yet) vs `isFetching` (request in flight)
- Status is now `'pending' | 'error' | 'success'`

## Query Keys

Always arrays. Structure hierarchically for targeted invalidation:

```typescript
const todoKeys = {
  all: ['todos'] as const,
  lists: () => [...todoKeys.all, 'list'] as const,
  list: (filters: Filters) => [...todoKeys.lists(), filters] as const,
  details: () => [...todoKeys.all, 'detail'] as const,
  detail: (id: number) => [...todoKeys.details(), id] as const,
}
```

## createQuery

Returns a **Svelte store**—access properties with `$` prefix:

```svelte
<script lang="ts">
  import { createQuery } from '@tanstack/svelte-query'

  let { filters } = $props()

  const query = createQuery({
    queryKey: ['todos', filters],
    queryFn: ({ signal }) => fetch('/api/todos', { signal }).then(r => r.json()),

    // Timing
    staleTime: 5 * 60 * 1000,      // 5 min fresh (default: 0)
    gcTime: 10 * 60 * 1000,        // 10 min in cache after unmount

    // Refetch triggers
    refetchOnMount: true,
    refetchOnWindowFocus: true,
    refetchOnReconnect: true,

    // Control
    enabled: !!filters,
    retry: 3,
  })
</script>

{#if $query.isPending}
  <p>Loading...</p>
{:else if $query.isError}
  <p>Error: {$query.error.message}</p>
{:else}
  <ul>
    {#each $query.data as todo (todo.id)}
      <li>{todo.title}</li>
    {/each}
  </ul>
{/if}
```

### Store Properties

```typescript
$query.data           // TData | undefined
$query.error          // TError | null
$query.status         // 'pending' | 'error' | 'success'
$query.isPending      // No data yet (first load)
$query.isFetching     // Request in flight (including background)
$query.isError
$query.isSuccess
$query.refetch()      // Manual refetch trigger
```

### staleTime vs gcTime

| Setting | Controls | Default | Adjust when... |
|---------|----------|---------|----------------|
| `staleTime` | How long data is "fresh" (no background refetch) | 0ms | Data rarely changes |
| `gcTime` | How long inactive queries stay in cache | 5 min | Rarely needs changing |

## createMutation

```svelte
<script lang="ts">
  import { createMutation, useQueryClient } from '@tanstack/svelte-query'

  const queryClient = useQueryClient()

  const mutation = createMutation({
    mutationFn: (newTodo: Todo) =>
      fetch('/api/todos', {
        method: 'POST',
        body: JSON.stringify(newTodo),
      }).then(r => r.json()),

    // Callbacks (still supported on mutations!)
    onMutate: async (newTodo) => {
      await queryClient.cancelQueries({ queryKey: ['todos'] })
      const previous = queryClient.getQueryData(['todos'])
      queryClient.setQueryData(['todos'], old => [...old, newTodo])
      return { previous }
    },
    onError: (err, newTodo, context) => {
      queryClient.setQueryData(['todos'], context.previous)
    },
    onSettled: () => {
      queryClient.invalidateQueries({ queryKey: ['todos'] })
    },
  })

  function handleSubmit(todo: Todo) {
    $mutation.mutate(todo)
  }
</script>

<button onclick={() => handleSubmit({ title: 'New' })} disabled={$mutation.isPending}>
  {$mutation.isPending ? 'Adding...' : 'Add Todo'}
</button>

{#if $mutation.isError}
  <p>Error: {$mutation.error.message}</p>
{/if}
```

### Mutation State

```typescript
$mutation.isPending   // In flight
$mutation.isSuccess   // Completed successfully
$mutation.isError     // Failed
$mutation.data        // Response data
$mutation.error       // Error object
$mutation.reset()     // Reset to idle state
$mutation.mutate(variables)      // Fire and forget
$mutation.mutateAsync(variables) // Returns promise
```

## Integration with Svelte 5 Runes

### With $derived

```svelte
<script lang="ts">
  import { createQuery } from '@tanstack/svelte-query'

  let { userId } = $props()

  const query = createQuery({
    queryKey: ['user', userId],
    queryFn: () => fetchUser(userId),
    enabled: !!userId,
  })

  let userName = $derived($query.data?.name ?? 'Unknown')
  let isAdmin = $derived($query.data?.role === 'admin')
</script>

<h1>Welcome, {userName}</h1>
```

### With $effect

```svelte
<script lang="ts">
  const query = createQuery({ ... })

  $effect(() => {
    if ($query.isSuccess) {
      console.log('Data loaded:', $query.data)
    }
  })
</script>
```

## Dependent Queries

```svelte
<script lang="ts">
  let { userId } = $props()

  const user = createQuery({
    queryKey: ['user', userId],
    queryFn: () => fetchUser(userId),
    enabled: !!userId,
  })

  const projects = createQuery({
    queryKey: ['projects', $user.data?.id],
    queryFn: () => fetchProjects($user.data!.id),
    enabled: !!$user.data?.id,
  })
</script>

{#if $user.isPending}
  <p>Loading user...</p>
{:else if $projects.isPending}
  <p>Loading projects...</p>
{:else}
  <h1>{$user.data.name}'s Projects</h1>
  {#each $projects.data as project}
    <p>{project.name}</p>
  {/each}
{/if}
```

## Custom Query Functions

Colocate fetching logic with configuration:

```typescript
// lib/queries/todos.ts
import { createQuery, createMutation, useQueryClient } from '@tanstack/svelte-query'
import * as api from '$lib/api/todos'

const todoKeys = {
  all: ['todos'] as const,
  lists: () => [...todoKeys.all, 'list'] as const,
  list: (filters: Filters) => [...todoKeys.lists(), filters] as const,
  detail: (id: number) => [...todoKeys.all, 'detail', id] as const,
}

export function useTodos(filters: Filters) {
  return createQuery({
    queryKey: todoKeys.list(filters),
    queryFn: () => api.getTodos(filters),
    staleTime: 5 * 60 * 1000,
  })
}

export function useTodo(id: number) {
  return createQuery({
    queryKey: todoKeys.detail(id),
    queryFn: () => api.getTodo(id),
    enabled: !!id,
  })
}

export function useCreateTodo() {
  const queryClient = useQueryClient()

  return createMutation({
    mutationFn: api.createTodo,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: todoKeys.lists() })
    },
  })
}

export function useUpdateTodo() {
  const queryClient = useQueryClient()

  return createMutation({
    mutationFn: api.updateTodo,
    onSuccess: (data, variables) => {
      queryClient.setQueryData(todoKeys.detail(variables.id), data)
      queryClient.invalidateQueries({ queryKey: todoKeys.lists() })
    },
  })
}
```

Usage:

```svelte
<script lang="ts">
  import { useTodos, useCreateTodo } from '$lib/queries/todos'

  const todos = useTodos({ status: 'active' })
  const createTodo = useCreateTodo()
</script>
```

## Cache Invalidation

```typescript
const queryClient = useQueryClient()

// Invalidate and refetch
queryClient.invalidateQueries({ queryKey: ['todos'] })

// Invalidate without immediate refetch
queryClient.invalidateQueries({ queryKey: ['todos'], refetchType: 'none' })

// Remove from cache entirely
queryClient.removeQueries({ queryKey: ['todos'] })

// Update cache directly
queryClient.setQueryData(['todo', id], updatedTodo)
```

## Prefetching

```typescript
// In load functions or event handlers
await queryClient.prefetchQuery({
  queryKey: ['todo', id],
  queryFn: () => fetchTodo(id),
  staleTime: 5 * 60 * 1000,
})
```

## SvelteKit SSR

```typescript
// +page.ts
import type { PageLoad } from './$types'
import { QueryClient } from '@tanstack/svelte-query'

export const load: PageLoad = async ({ fetch }) => {
  const queryClient = new QueryClient()

  await queryClient.prefetchQuery({
    queryKey: ['todos'],
    queryFn: () => fetch('/api/todos').then(r => r.json()),
  })

  return { queryClient }
}
```

```svelte
<!-- +page.svelte -->
<script lang="ts">
  import { HydrationBoundary } from '@tanstack/svelte-query'
  import { useTodos } from '$lib/queries/todos'

  let { data } = $props()
  const todos = useTodos()
</script>

<HydrationBoundary state={data.queryClient}>
  {#if $todos.data}
    {#each $todos.data as todo}
      <p>{todo.title}</p>
    {/each}
  {/if}
</HydrationBoundary>
```

## Pitfalls to Avoid

### 1. Copying query data to $state
```svelte
<!-- ❌ Creates stale data, breaks background updates -->
<script>
  let todos = $state([])
  const query = useTodos()
  $effect(() => { if ($query.data) todos = $query.data })
</script>

<!-- ✅ Use query data directly -->
<script>
  const query = useTodos()
</script>
{#each $query.data ?? [] as todo}...{/each}
```

### 2. Forgetting the $ prefix
```svelte
<!-- ❌ Won't be reactive -->
{#if query.isPending}

<!-- ✅ Subscribe to store -->
{#if $query.isPending}
```

### 3. Using string query keys
```typescript
// ❌ Can't do partial invalidation
createQuery({ queryKey: 'todos-list-active' })

// ✅ Use arrays for hierarchy
createQuery({ queryKey: ['todos', 'list', { status: 'active' }] })
```

### 4. Forgetting enabled for dependent queries
```svelte
<!-- ❌ Fires with undefined, causes errors -->
<script>
  const projects = createQuery({
    queryKey: ['projects', $user.data?.id],
    queryFn: () => fetchProjects($user.data.id),
  })
</script>

<!-- ✅ Wait for dependency -->
<script>
  const projects = createQuery({
    queryKey: ['projects', $user.data?.id],
    queryFn: () => fetchProjects($user.data!.id),
    enabled: !!$user.data?.id,
  })
</script>
```

### 5. Not using signal for cancellation
```typescript
// ❌ No cancellation support
queryFn: () => fetch('/api/todos').then(r => r.json())

// ✅ Pass abort signal
queryFn: ({ signal }) => fetch('/api/todos', { signal }).then(r => r.json())
```

## Quick Reference

| Task | Method |
|------|--------|
| Fetch data | `createQuery({ queryKey, queryFn })` |
| Mutate data | `createMutation({ mutationFn })` |
| Access query client | `useQueryClient()` |
| Invalidate cache | `queryClient.invalidateQueries({ queryKey })` |
| Update cache directly | `queryClient.setQueryData(queryKey, data)` |
| Prefetch | `queryClient.prefetchQuery({ queryKey, queryFn })` |
| Get cached data | `queryClient.getQueryData(queryKey)` |
| Cancel queries | `queryClient.cancelQueries({ queryKey })` |
| Check if fetching | `useIsFetching({ queryKey })` |

## Svelte Query Exports

```typescript
import {
  // Core
  createQuery,
  createQueries,
  createInfiniteQuery,
  createMutation,

  // Utilities
  useQueryClient,
  useIsFetching,
  useIsMutating,
  queryOptions,
  infiniteQueryOptions,

  // Components
  QueryClientProvider,
  HydrationBoundary,
} from '@tanstack/svelte-query'

import { SvelteQueryDevtools } from '@tanstack/svelte-query-devtools'
```
