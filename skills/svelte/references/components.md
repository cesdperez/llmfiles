# Component API Reference

## Snippets as Props

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

## TypeScript Props
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
