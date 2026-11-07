<script lang="ts">
	import * as Card from '#lib/components/ui/card/index.js';
	import type { PageProps } from './$types';

	let { data }: PageProps = $props();
</script>

<svelte:head>
	<title>Admin</title>
</svelte:head>

<main class="container mx-auto max-w-2xl px-4 py-12">
	<Card.Root>
		<Card.Header>
			<Card.Title>Admin</Card.Title>
			<Card.Description>Logged in as {data.admin.name} ({data.admin.email}).</Card.Description>
		</Card.Header>
		<Card.Content class="text-sm text-muted-foreground">
			Only admins can see this page. Admin tools will go here.
		</Card.Content>
	</Card.Root>
</main>
