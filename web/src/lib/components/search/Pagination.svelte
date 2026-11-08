<script lang="ts">
	import ChevronLeftIcon from '@lucide/svelte/icons/chevron-left';
	import ChevronRightIcon from '@lucide/svelte/icons/chevron-right';
	import { Button } from '#lib/components/ui/button/index.js';
	import { pageItems } from '#lib/pagination.js';

	let {
		page,
		total,
		pageSize,
		loading = false,
		label = 'Record pages',
		onPage
	}: {
		page: number;
		total: number;
		pageSize: number;
		loading?: boolean;
		label?: string;
		onPage: (page: number) => void;
	} = $props();

	const pageCount = $derived(Math.max(1, Math.ceil(total / pageSize)));
	const items = $derived(pageItems(page, pageCount));
</script>

<!-- Previous · 1 2 3 … 12 · Next. On phones "Previous"/"Next" shrink to arrows, so the bar
     fits in 320px. The current page is marked (aria-current) and isn't a button you can click. -->
{#if pageCount > 1}
	<nav class="flex items-center justify-center gap-1 pt-2 text-sm" aria-label={label}>
		<Button
			variant="ghost"
			size="sm"
			disabled={loading || page <= 1}
			onclick={() => onPage(page - 1)}
			aria-label="Previous page"
		>
			<ChevronLeftIcon aria-hidden="true" />
			<span class="hidden sm:inline">Previous</span>
		</Button>

		{#each items as item, i (item === 'gap' ? `gap-${i}` : item)}
			{#if item === 'gap'}
				<span class="w-6 text-center text-muted-foreground" aria-hidden="true">…</span>
			{:else if item === page}
				<span
					class="inline-flex h-8 min-w-8 items-center justify-center rounded-md border px-2 font-medium"
					aria-current="page"
				>
					<span class="sr-only">Page</span>
					{item}
				</span>
			{:else}
				<Button
					variant="ghost"
					size="sm"
					class="min-w-8 px-2"
					disabled={loading}
					onclick={() => onPage(item)}
					aria-label="Page {item}"
				>
					{item}
				</Button>
			{/if}
		{/each}

		<Button
			variant="ghost"
			size="sm"
			disabled={loading || page >= pageCount}
			onclick={() => onPage(page + 1)}
			aria-label="Next page"
		>
			<span class="hidden sm:inline">Next</span>
			<ChevronRightIcon aria-hidden="true" />
		</Button>
	</nav>
{/if}
