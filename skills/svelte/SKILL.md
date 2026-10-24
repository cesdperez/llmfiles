---
name: svelte
description: Best practices for Svelte 5 and SvelteKit 2.9+ development. Use when writing Svelte components, using runes ($state, $derived, $effect, $props), creating SvelteKit routes, working with load functions, form actions, or when the user mentions Svelte, SvelteKit, .svelte files, or runes.
---

# Svelte 5 & SvelteKit 2.9+ Development

## Overview

Svelte 5 introduces runes, a reactivity system using `$state`, `$derived`, `$effect`, and `$props`. SvelteKit provides file-based routing, SSR, and full-stack capabilities.

## References

- Read `~/llmfiles/skills/svelte/references/sveltekit.md` when writing routes, load functions, form actions, API endpoints or hooks, importing from `$app/*` or `@sveltejs/kit`, or running dev/build/check commands.
- Read `~/llmfiles/skills/svelte/references/components.md` when passing snippets as props or typing component props with TypeScript.

## Runes (Svelte 5 Reactivity)

### $state - Reactive State
```svelte
<script>
  let count = $state(0);
  let todos = $state([{ done: false, text: 'Learn runes' }]);
</script>

<button onclick={() => count++}>{count}</button>
```

- Arrays/objects become deeply reactive proxies
- Use `$state.raw()` for non-proxied state (requires reassignment)
- Use `$state.snapshot()` to get plain objects for external APIs
- Destructuring breaks reactivity: `let { name } = person;` loses it, read `person.name` directly

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

Use for DOM manipulation, canvas drawing, third-party library integration, and network requests based on state.

Not for state synchronization: use `$derived` instead. Never update `$state` you're reading, it loops forever:
```svelte
// BAD - infinite loop
$effect(() => {
  count = count + 1;
});
```

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

### Rune Quick Reference
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

## Svelte 4 Patterns to Avoid

| Svelte 4 (BAD) | Svelte 5 (GOOD) |
|----------------|-----------------|
| `<button on:click={handler}>` | `<button onclick={handler}>` |
| `on:click\|preventDefault\|stopPropagation` | Call `e.preventDefault()` and `e.stopPropagation()` inside the handler |
| `<slot />` (deprecated) | `{@render children?.()}` |

## SvelteKit Pitfalls

- Server load return values must be JSON-serializable. Can't return functions, class instances, or Svelte components. Use universal loads (+page.ts) for non-serializable data.
- Don't mix server-only code in universal files. Use `$lib/server/` for DB connections, secrets. These will error if accidentally imported client-side.
