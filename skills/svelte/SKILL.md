---
name: svelte5-sveltekit
description: Best practices for Svelte 5 and SvelteKit 2.9+ development. Use when writing Svelte components, using runes ($state, $derived, $effect, $props), creating SvelteKit routes, working with load functions, form actions, or when the user mentions Svelte, SvelteKit, .svelte files, or runes.
---

# Svelte 5 & SvelteKit 2.9+ Development

## Overview

Svelte 5 introduces runes—a new reactivity system using `$state`, `$derived`, `$effect`, and `$props`. SvelteKit provides file-based routing, SSR, and full-stack capabilities.

## Runes (Svelte 5 Reactivity)

### $state - Reactive State
```svelte
<script>
  let count = $state(0);
  let todos = $state([{ done: false, text: 'Learn runes' }]);
</script>

<button onclick={() => count++}>{count}</button>
```

**Key points:**
- Arrays/objects become deeply reactive proxies
- Use `$state.raw()` for non-proxied state (requires reassignment)
- Use `$state.snapshot()` to get plain objects for external APIs
- Destructuring breaks reactivity—access properties directly

### $derived - Computed Values
```svelte
<script>
  let count = $state(0);
  let doubled = $derived(count * 2);

  // For complex logic:
  let total = $derived.by(() => {
    let sum = 0;
    for (const n of numbers) sum += n;
    return sum;
  });
</script>
```

**Key points:**
- Must be side-effect free
- Dependencies tracked automatically
- Recalculates only when accessed and dependencies changed

### $effect - Side Effects
```svelte
<script>
  $effect(() => {
    console.log('Count changed:', count);

    // Return cleanup function
    return () => clearInterval(timer);
  });
</script>
```

**When to use:**
- DOM manipulation, canvas drawing
- Third-party library integration
- Network requests based on state

**When NOT to use:**
- State synchronization → use `$derived` instead
- Never update `$state` you're reading (infinite loops)

### $props - Component Properties
```svelte
<script>
  let { name, age = 25, ...rest } = $props();

  // With TypeScript:
  let { name, age = 25 }: { name: string; age?: number } = $props();

  // Bindable props (two-way binding):
  let { value = $bindable() } = $props();
</script>
```

### Snippets (Replaces Slots)
```svelte
{#snippet row(item)}
  <tr><td>{item.name}</td><td>{item.value}</td></tr>
{/snippet}

<table>
  {#each items as item}
    {@render row(item)}
  {/each}
</table>
```

Pass snippets as props:
```svelte
<!-- Parent -->
<DataTable data={items}>
  {#snippet row(item)}
    <CustomRow {item} />
  {/snippet}
</DataTable>

<!-- Child (DataTable.svelte) -->
<script>
  let { data, row } = $props();
</script>

{#each data as item}
  {@render row(item)}
{/each}
```

## SvelteKit File Structure

```
src/
├── lib/                    # Shared code ($lib alias)
│   ├── components/
│   ├── server/             # Server-only ($lib/server)
│   └── utils/
├── routes/
│   ├── +layout.svelte      # Root layout
│   ├── +page.svelte        # Home page
│   ├── +page.server.ts     # Server load/actions
│   ├── api/
│   │   └── [endpoint]/
│   │       └── +server.ts  # API endpoint
│   └── [slug]/
│       ├── +page.svelte
│       └── +page.ts        # Universal load
├── hooks.server.ts
├── hooks.client.ts
└── app.html
```

## Routing Files

| File | Purpose |
|------|---------|
| `+page.svelte` | Page component |
| `+page.ts` | Universal load (runs on server & client) |
| `+page.server.ts` | Server-only load + form actions |
| `+layout.svelte` | Persistent UI wrapper |
| `+layout.ts/+layout.server.ts` | Layout data loading |
| `+server.ts` | API endpoint (GET, POST, etc.) |
| `+error.svelte` | Error boundary |

## Load Functions

### Universal Load (+page.ts)
```typescript
import type { PageLoad } from './$types';

export const load: PageLoad = async ({ params, fetch, url }) => {
  const res = await fetch(`/api/items/${params.id}`);
  return { item: await res.json() };
};
```

### Server Load (+page.server.ts)
```typescript
import type { PageServerLoad } from './$types';
import { db } from '$lib/server/db';

export const load: PageServerLoad = async ({ params, cookies, locals }) => {
  const item = await db.items.find(params.id);
  return { item }; // Must be serializable
};
```

Access data in components:
```svelte
<script>
  let { data } = $props();
</script>

<h1>{data.item.name}</h1>
```

## Form Actions

```typescript
// +page.server.ts
import type { Actions } from './$types';
import { fail, redirect } from '@sveltejs/kit';

export const actions: Actions = {
  default: async ({ request, cookies }) => {
    const data = await request.formData();
    const email = data.get('email');

    if (!email) {
      return fail(400, { email, missing: true });
    }

    // Process form...
    redirect(303, '/success');
  },

  // Named action: action="?/login"
  login: async ({ request }) => { /* ... */ }
};
```

```svelte
<script>
  import { enhance } from '$app/forms';
  let { form } = $props();
</script>

<form method="POST" use:enhance>
  <input name="email" value={form?.email ?? ''}>
  {#if form?.missing}
    <p class="error">Email is required</p>
  {/if}
  <button>Submit</button>
</form>
```

## API Endpoints (+server.ts)

```typescript
import type { RequestHandler } from './$types';
import { json, error } from '@sveltejs/kit';

export const GET: RequestHandler = async ({ params, url }) => {
  const item = await db.items.find(params.id);
  if (!item) error(404, 'Not found');
  return json(item);
};

export const POST: RequestHandler = async ({ request }) => {
  const data = await request.json();
  const item = await db.items.create(data);
  return json(item, { status: 201 });
};
```

## Hooks

### Server Hooks (hooks.server.ts)
```typescript
import type { Handle } from '@sveltejs/kit';

export const handle: Handle = async ({ event, resolve }) => {
  // Add to event.locals (accessible in load/actions)
  event.locals.user = await getUser(event.cookies.get('session'));

  const response = await resolve(event);
  response.headers.set('x-custom-header', 'value');
  return response;
};
```

## Commands

```bash
# Development
npm run dev              # Start dev server
npm run dev -- --open    # Open in browser

# Build & Preview
npm run build            # Production build
npm run preview          # Preview production build

# Type checking
npm run check            # Run svelte-check
npm run check:watch      # Watch mode
```

## Pitfalls to Avoid

1. **Don't destructure reactive state**
   ```svelte
   // BAD - loses reactivity
   let { name } = person;

   // GOOD - maintains reactivity
   person.name
   ```

2. **Don't update $state inside $effect that reads it**
   ```svelte
   // BAD - infinite loop
   $effect(() => {
     count = count + 1;
   });

   // GOOD - use $derived for computed values
   let doubled = $derived(count * 2);
   ```

3. **Don't use old event syntax**
   ```svelte
   <!-- BAD (Svelte 4) -->
   <button on:click={handler}>

   <!-- GOOD (Svelte 5) -->
   <button onclick={handler}>
   ```

4. **Don't use slots (deprecated)**
   ```svelte
   <!-- BAD (Svelte 4) -->
   <slot />

   <!-- GOOD (Svelte 5) -->
   {@render children?.()}
   ```

5. **Don't forget serialization in server loads**
   - Server load return values must be JSON-serializable
   - Can't return functions, class instances, or Svelte components
   - Use universal loads (+page.ts) for non-serializable data

6. **Don't mix server-only code in universal files**
   - Use `$lib/server/` for DB connections, secrets
   - These will error if accidentally imported client-side

## Quick Reference

### Runes
| Rune | Purpose |
|------|---------|
| `$state(value)` | Reactive state |
| `$state.raw(value)` | Non-proxy state |
| `$derived(expr)` | Computed value |
| `$derived.by(fn)` | Complex computed |
| `$effect(() => {})` | Side effects |
| `$effect.pre(() => {})` | Before DOM update |
| `$props()` | Component props |
| `$bindable()` | Two-way binding |
| `$inspect(value)` | Debug logging |

### SvelteKit Imports
```typescript
import { goto, invalidate, invalidateAll } from '$app/navigation';
import { page, navigating } from '$app/state';
import { enhance } from '$app/forms';
import { json, error, redirect, fail } from '@sveltejs/kit';
```

### Event Modifiers (Svelte 5)
```svelte
<!-- Old: on:click|preventDefault|stopPropagation -->
<!-- New: handle in function -->
<button onclick={(e) => {
  e.preventDefault();
  e.stopPropagation();
  handler();
}}>
```

### TypeScript Props
```svelte
<script lang="ts">
  import type { Snippet } from 'svelte';

  interface Props {
    name: string;
    count?: number;
    children?: Snippet;
    row?: Snippet<[Item]>;
  }

  let { name, count = 0, children, row }: Props = $props();
</script>
```
