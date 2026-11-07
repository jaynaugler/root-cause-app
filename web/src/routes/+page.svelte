<script lang="ts">
	import ResultsCard from '#lib/components/resultsCard/ResultsCard.svelte';
	import type { SearchResult } from '#lib/search.js';

	// Extract the 'form' prop to access action return data and failures
	let { data, form } = $props();

	// Demo placeholder records (temporary sample data)
	const results: SearchResult[] = [
		{ id: '1', title: 'Test Card', description: 'The test results card', link: 'https://nscc.ca' },
		{ id: '2', title: 'Test Card', description: 'The test results card', link: 'https://nscc.ca' },
		{ id: '3', title: 'Test Card', description: 'The test results card', link: 'https://nscc.ca' }
	];
</script>

<main class="container mx-auto max-w-6xl px-4 py-12">

	<div>
  <!-- <Input placeholder="Enter text" /> -->
	</div>

    <div class="grid grid-cols-1 gap-6 sm:grid-cols-2 lg:grid-cols-3">
		{#each results as result, i (result.id)}
			<ResultsCard result={result} number={i + 1} anchorId={'result-' + i} />
		{/each}
    </div>
</main>