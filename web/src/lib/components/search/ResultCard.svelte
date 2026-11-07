<script lang="ts">
	import * as Card from '#lib/components/ui/card/index.js';
	import type { SearchResult } from '#lib/search.js';
	// TODO 3: import Badge from '#lib/components/ui/badge/index.js'

	// Props: the parent passes these in, e.g. <ResultCard {result} number={1} anchorId="t0-result-1" />
	let { result, number, anchorId }: { result: SearchResult; number: number; anchorId: string } =
		$props();
</script>

<!-- id lets the summary's [1] link jump here. scroll-mt keeps it from hiding under the top edge. -->
<Card.Root id={anchorId} class="scroll-mt-6">
	<Card.Header>
		<Card.Title>
			{number}. {result.title ?? 'Untitled record'}
			<!-- TODO 1: make the title a link to result.link (only when it exists).
			     Hint: {#if result.link} <a href={result.link} target="_blank" rel="noopener noreferrer">…</a> {:else} … {/if}
			     Style idea: class="hover:underline" -->
		</Card.Title>

		<!-- TODO 2: show result.attribution under the title, if it exists.
		     Hint: <Card.Description>…</Card.Description> -->
	</Card.Header>

	<Card.Content>
		<!-- TODO 4: show result.description in a <p class="text-sm"> -->

		<!-- TODO 3: show result.resourceformat as a <Badge variant="outline">, if it exists -->
	</Card.Content>
</Card.Root>
