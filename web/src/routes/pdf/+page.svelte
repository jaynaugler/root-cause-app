<script lang="ts">
	import { Button } from '#lib/components/ui/button/index.js';
	import { Input } from '#lib/components/ui/input/index.js';
	import * as Card from '#lib/components/ui/card/index.js';

	// Mirrors the response of POST /api/pdf-metadata (api/app/pdf.py)
	type PdfMetadata = {
		title: string | null;
		author: string | null;
		subject: string | null;
		creator: string | null;
		producer: string | null;
		creationDate: string | null;
		modDate: string | null;
		pageCount: number;
		extra: Record<string, string>;
	};

	let url = $state('');
	let loading = $state(false);
	let error = $state<string | null>(null);
	let meta = $state<PdfMetadata | null>(null);

	async function lookup(event: SubmitEvent) {
		event.preventDefault();
		try {
			// Client-side sanity check; type="url" + backend 422 cover the rest
			new URL(url);
		} catch {
			error = 'Enter a valid URL (including https://).';
			meta = null;
			return;
		}
		loading = true;
		error = null;
		meta = null;
		try {
			const res = await fetch('/api/pdf-metadata', {
				method: 'POST',
				headers: { 'content-type': 'application/json' },
				body: JSON.stringify({ url })
			});
			if (!res.ok) {
				// detail is a string for our HTTPExceptions, an array for pydantic 422s
				const body = (await res.json().catch(() => null)) as { detail?: unknown } | null;
				const detail = body?.detail;
				error =
					typeof detail === 'string'
						? detail
						: `Request failed with status ${res.status}.`;
			} else {
				meta = (await res.json()) as PdfMetadata;
			}
		} catch {
			error = 'Could not reach the API.';
		} finally {
			loading = false;
		}
	}
</script>

<main class="container mx-auto max-w-xl py-12 px-4 space-y-6">
	<Card.Root>
		<Card.Header>
			<Card.Title>PDF metadata</Card.Title>
			<Card.Description>Paste a link to a PDF to extract its metadata.</Card.Description>
		</Card.Header>
		<Card.Content class="space-y-4">
			<form onsubmit={lookup} class="space-y-2">
				<div class="flex gap-2">
					<Input type="url" bind:value={url} placeholder="https://example.com/file.pdf" required />
					<Button type="submit" disabled={loading}>{loading ? 'Fetching…' : 'Fetch metadata'}</Button>
				</div>
				{#if error}
					<p class="text-sm font-medium text-red-500">
						{error}
					</p>
				{/if}
			</form>

			{#if meta}
				<dl class="grid grid-cols-[auto_1fr] gap-x-4 gap-y-1 text-sm">
					<dt class="font-medium">Title</dt>
					<dd>{meta.title ?? '—'}</dd>
					<dt class="font-medium">Author</dt>
					<dd>{meta.author ?? '—'}</dd>
					<dt class="font-medium">Subject</dt>
					<dd>{meta.subject ?? '—'}</dd>
					<dt class="font-medium">Creator</dt>
					<dd>{meta.creator ?? '—'}</dd>
					<dt class="font-medium">Producer</dt>
					<dd>{meta.producer ?? '—'}</dd>
					<dt class="font-medium">Created</dt>
					<dd>{meta.creationDate ?? '—'}</dd>
					<dt class="font-medium">Modified</dt>
					<dd>{meta.modDate ?? '—'}</dd>
					<dt class="font-medium">Pages</dt>
					<dd>{meta.pageCount}</dd>
					{#each Object.entries(meta.extra) as [key, value] (key)}
						<dt class="font-medium">{key}</dt>
						<dd>{value}</dd>
					{/each}
				</dl>
			{/if}
		</Card.Content>
	</Card.Root>
</main>
