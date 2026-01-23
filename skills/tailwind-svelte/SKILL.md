---
name: tailwind-svelte
description: Tailwind CSS v4 patterns for Svelte 5 and SvelteKit. Use when styling Svelte components with Tailwind, configuring Tailwind in SvelteKit, using @apply in Svelte style blocks, creating variant-based components, or when the user mentions Tailwind with Svelte, SvelteKit styling, or utility-first CSS in .svelte files.
---

# Tailwind CSS v4 + Svelte 5

## Overview

Tailwind v4 (released Jan 2025) is a ground-up rewrite with CSS-first configuration, automatic content detection, and native CSS features. This skill covers v4-specific patterns for Svelte/SvelteKit projects.

## SvelteKit Setup (v4)

```bash
# New project with Tailwind
pnpm dlx sv create my-app --add tailwindcss

# Or manual setup
npm install tailwindcss @tailwindcss/vite
```

```ts
// vite.config.ts
import { sveltekit } from '@sveltejs/kit/vite';
import tailwindcss from '@tailwindcss/vite';
import { defineConfig } from 'vite';

export default defineConfig({
  plugins: [tailwindcss(), sveltekit()]
});
```

```css
/* src/app.css */
@import "tailwindcss";

@theme {
  --color-brand: oklch(0.7 0.15 250);
  --font-display: "Inter", sans-serif;
}
```

```svelte
<!-- src/routes/+layout.svelte -->
<script>
  import '../app.css';
  let { children } = $props();
</script>

{@render children()}
```

## Using @apply in Svelte Style Blocks

Svelte's scoped `<style>` blocks don't have access to Tailwind's theme by default. Use `@reference`:

```svelte
<style>
  @reference "tailwindcss";

  h1 {
    @apply text-2xl font-bold text-brand;
  }

  .card {
    @apply rounded-lg bg-white p-4 shadow-sm;
  }
</style>
```

Or reference your app's CSS for custom theme values:

```svelte
<style>
  @reference "../app.css";

  .highlight {
    @apply bg-brand/20 text-brand;
  }
</style>
```

**Prefer utility classes in markup over @apply** — use `@apply` only for third-party component overrides or unavoidable CSS.

## Component Patterns

### Utility Classes in Markup (Preferred)

```svelte
<script>
  let { variant = 'primary', size = 'md' } = $props();
</script>

<button
  class="rounded-sm font-medium transition-colors
    {variant === 'primary' ? 'bg-blue-500 text-white hover:bg-blue-600' : ''}
    {variant === 'secondary' ? 'bg-gray-200 text-gray-800 hover:bg-gray-300' : ''}
    {size === 'sm' ? 'px-2 py-1 text-sm' : ''}
    {size === 'md' ? 'px-4 py-2' : ''}
    {size === 'lg' ? 'px-6 py-3 text-lg' : ''}"
>
  <slot />
</button>
```

### Class Variance Authority (CVA) for Complex Variants

```bash
npm install class-variance-authority clsx tailwind-merge
```

```ts
// lib/utils.ts
import { clsx, type ClassValue } from 'clsx';
import { twMerge } from 'tailwind-merge';

export function cn(...inputs: ClassValue[]) {
  return twMerge(clsx(inputs));
}
```

```svelte
<!-- lib/components/Button.svelte -->
<script lang="ts">
  import { cva, type VariantProps } from 'class-variance-authority';
  import { cn } from '$lib/utils';

  const buttonVariants = cva(
    'inline-flex items-center justify-center rounded-sm font-medium transition-colors disabled:opacity-50',
    {
      variants: {
        variant: {
          primary: 'bg-blue-500 text-white hover:bg-blue-600',
          secondary: 'bg-gray-200 text-gray-800 hover:bg-gray-300',
          ghost: 'hover:bg-gray-100'
        },
        size: {
          sm: 'h-8 px-3 text-sm',
          md: 'h-10 px-4',
          lg: 'h-12 px-6 text-lg'
        }
      },
      defaultVariants: {
        variant: 'primary',
        size: 'md'
      }
    }
  );

  type ButtonProps = VariantProps<typeof buttonVariants> & {
    class?: string;
  };

  let { variant, size, class: className, ...rest }: ButtonProps = $props();
</script>

<button class={cn(buttonVariants({ variant, size }), className)} {...rest}>
  {@render children?.()}
</button>
```

### Accepting Class Overrides

Use `tailwind-merge` to let consumers override styles without conflicts:

```svelte
<script lang="ts">
  import { cn } from '$lib/utils';

  let { class: className = '' } = $props();
</script>

<div class={cn('rounded-lg bg-white p-4 shadow-sm', className)}>
  {@render children?.()}
</div>
```

## Tailwind v4 Syntax Changes

### Renamed Utilities (Must Update)

| v3 | v4 |
|---|---|
| `shadow-sm` | `shadow-xs` |
| `shadow` | `shadow-sm` |
| `rounded-sm` | `rounded-xs` |
| `rounded` | `rounded-sm` |
| `blur-sm` | `blur-xs` |
| `blur` | `blur-sm` |
| `ring` | `ring-3` (default was 3px) |
| `outline-none` | `outline-hidden` |

### New Syntax

```svelte
<!-- Important modifier (moved to end) -->
<div class="bg-red-500!">

<!-- CSS variables (parentheses, not brackets) -->
<div class="bg-(--brand-color)">

<!-- Arbitrary grid values (underscores for spaces) -->
<div class="grid-cols-[1fr_auto_1fr]">
```

### Removed Utilities

Replace opacity utilities with slash syntax:

```svelte
<!-- v3 -->
<div class="bg-blue-500 bg-opacity-50">

<!-- v4 -->
<div class="bg-blue-500/50">
```

## Dark Mode

```svelte
<div class="bg-white text-gray-900 dark:bg-gray-900 dark:text-white">
  <h1 class="text-2xl dark:text-gray-100">Title</h1>
</div>
```

## Container Queries (Built-in)

```svelte
<div class="@container">
  <div class="grid grid-cols-1 @sm:grid-cols-2 @lg:grid-cols-4">
    {#each items as item}
      <Card {item} />
    {/each}
  </div>
</div>
```

## Responsive Design

```svelte
<div class="px-4 sm:px-6 lg:px-8">
  <div class="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
    <!-- Mobile-first: single column, then 2, then 3 -->
  </div>
</div>
```

## Dynamic Values

Use CSS variables for values from props/state:

```svelte
<script>
  let { color, hoverColor } = $props();
</script>

<button
  style="--btn-bg: {color}; --btn-hover: {hoverColor}"
  class="bg-(--btn-bg) hover:bg-(--btn-hover) px-4 py-2 rounded-sm"
>
  {@render children?.()}
</button>
```

## Pitfalls to Avoid

1. **Don't use @apply without @reference in Svelte style blocks**
   ```svelte
   <!-- BAD - won't find Tailwind classes -->
   <style>
     .foo { @apply text-red-500; }
   </style>

   <!-- GOOD -->
   <style>
     @reference "tailwindcss";
     .foo { @apply text-red-500; }
   </style>
   ```

2. **Don't use Sass/Less/Stylus** — Tailwind v4 is incompatible with CSS preprocessors

3. **Don't forget v4 renames** — `shadow-sm` is now `shadow-xs`, `rounded-sm` is now `rounded-xs`

4. **Don't use old opacity utilities** — `bg-opacity-50` is removed, use `bg-blue-500/50`

5. **Don't stack conflicting classes without tw-merge**
   ```svelte
   <!-- BAD - both bg classes apply unpredictably -->
   <div class="bg-red-500 {conditional ? 'bg-blue-500' : ''}">

   <!-- GOOD - tw-merge resolves conflicts -->
   <div class={cn('bg-red-500', conditional && 'bg-blue-500')}>
   ```

6. **Don't use variant stacking in v3 order** — v4 is left-to-right
   ```svelte
   <!-- v3: first:*:pt-0 → v4: *:first:pt-0 -->
   ```

## Quick Reference

### Theme Configuration (CSS)

```css
@import "tailwindcss";

@theme {
  --color-*: /* colors */
  --font-*: /* font families */
  --spacing-*: /* custom spacing */
  --breakpoint-*: /* custom breakpoints */
}

@source "../components/**/*.svelte"; /* explicit content paths */
```

### Common Imports

```ts
// Utilities
import { cn } from '$lib/utils';           // clsx + tw-merge
import { cva } from 'class-variance-authority';

// Types
import type { VariantProps } from 'class-variance-authority';
import type { ClassValue } from 'clsx';
```

### Browser Support

Tailwind v4 requires: Safari 16.4+, Chrome 111+, Firefox 128+
