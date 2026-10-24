# SvelteKit Reference

## File Structure

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

## SvelteKit Imports
```typescript
import { goto, invalidate, invalidateAll } from '$app/navigation';
import { page, navigating } from '$app/state';
import { enhance } from '$app/forms';
import { json, error, redirect, fail } from '@sveltejs/kit';
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
