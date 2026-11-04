<script lang="ts">
	import { enhance } from '$app/forms';
	import { Button } from '#lib/components/ui/button/index.js';
	import { Input } from '#lib/components/ui/input/index.js';
	import * as Card from '#lib/components/ui/card/index.js';

	let { data } = $props();
</script>

<main class="container mx-auto max-w-xl py-12 px-4 space-y-6">
	<Card.Root>
		<Card.Header>
			<Card.Title>Hackathon Stack Ready</Card.Title>
			<Card.Description>SvelteKit 5 + MongoDB + shadcn-svelte</Card.Description>
		</Card.Header>
		<Card.Content class="space-y-4">
			<form method="POST" action="?/create" use:enhance class="flex gap-2">
				<Input name="name" placeholder="Add a test document..." required />
				<Button type="submit">Save</Button>
			</form>

			<div class="space-y-2 pt-4">
				{#each data.items as item (item._id)}
					<div class="flex items-center justify-between rounded-md border p-3 text-sm">
						<span class="font-medium">{item.name}</span>
						<span class="text-xs text-muted-foreground">
							{new Date(item.createdAt).toLocaleTimeString()}
						</span>
					</div>
				{:else}
					<p class="text-sm text-muted-foreground">Connected to DB. No items yet.</p>
				{/each}
			</div>
		</Card.Content>
	</Card.Root>
</main>
