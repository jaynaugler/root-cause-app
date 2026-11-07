<script lang="ts">
	import { enhance } from '$app/forms';
	import { Button } from '#lib/components/ui/button/index.js';
	import * as Card from '#lib/components/ui/card/index.js';
	import ResultsCard from '#lib/components/resultsCard/ResultsCard.svelte';

	// Extract the 'form' prop to access action return data and failures
	let { data, form } = $props();
</script>

<main class="container mx-auto max-w-6xl px-4 py-12">

	<div>
  <!-- <Input placeholder="Enter text" /> -->
	</div>

    <div class="grid grid-cols-1 gap-6 sm:grid-cols-2 lg:grid-cols-3">
        <ResultsCard 
			title="Test Card" 
			description="The test results card"
			href="https://nscc.ca"
		/>

		<ResultsCard 
			title="Test Card" 
			description="The test results card"
			href="https://nscc.ca"
		/>

		<ResultsCard 
			title="Test Card" 
			description="The test results card"
			href="https://nscc.ca"
		/>
    </div>
</main>