<script lang="ts">
	import { Button } from '#lib/components/ui/button/index.js';

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
</script>

{#if pageCount > 1}
	<nav class="flex items-center justify-center gap-3 pt-2 text-sm" aria-label={label}>
		<Button variant="outline" disabled={loading || page <= 1} onclick={() => onPage(page - 1)}>
			Previous
		</Button>
		<span aria-live="polite">Page {page} of {pageCount}</span>
		<Button variant="outline" disabled={loading || page >= pageCount} onclick={() => onPage(page + 1)}>
			Next
		</Button>
	</nav>
{/if}
