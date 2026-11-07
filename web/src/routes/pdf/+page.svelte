<script lang="ts">
	import { Button } from '#lib/components/ui/button/index.js';
	import { Input } from '#lib/components/ui/input/index.js';
	import * as Card from '#lib/components/ui/card/index.js';

	// Mirrors the response of POST /api/pdf-metadata (api/app/pdf.py) —
	// the shape of the eventual `resources` record (details are UI-only).
	type Details = {
		author: string | null;
		subject: string | null;
		creator: string | null;
		producer: string | null;
		creationDate: string | null;
		modDate: string | null;
		pageCount: number;
		extra: Record<string, string>;
	};
	type ResourceRecord = {
		title: string | null;
		link: string;
		description: string | null;
		attribution: string | null;
		resourceformat: string;
		contentcategory: string | null;
		imgurl: string | null;
		status: string | null;
		details: Details;
		raw?: Omit<ResourceRecord, 'raw'>;
	};

	let url = $state('');
	let loading = $state(false);
	let error = $state<string | null>(null);
	let meta = $state<ResourceRecord | null>(null);

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
				meta = (await res.json()) as ResourceRecord;
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
			<Card.Description>Paste a link to a PDF to extract a resource record.</Card.Description>
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
				<div class="space-y-3">
					<div class="space-y-1">
						<h3 class="text-lg font-semibold leading-none">{meta.title ?? 'Untitled'}</h3>
						<p class="break-all text-xs text-muted-foreground">{meta.link}</p>
					</div>

					{#if meta.description}
						<p class="text-sm leading-relaxed">{meta.description}</p>
					{:else}
						<p class="text-sm text-muted-foreground">No text layer found (scanned PDF?).</p>
					{/if}

					<dl class="grid grid-cols-[auto_1fr] gap-x-4 gap-y-1 text-sm">
						<dt class="font-medium">Attribution</dt>
						<dd>{meta.attribution ?? '—'}</dd>
						<dt class="font-medium">Format</dt>
						<dd>{meta.resourceformat}</dd>
						<dt class="font-medium">Category</dt>
						<dd>{meta.contentcategory ?? '—'}</dd>
						<dt class="font-medium">Status</dt>
						<dd>{meta.status ?? '—'}</dd>
						<dt class="font-medium">Author</dt>
						<dd>{meta.details.author ?? '—'}</dd>
						<dt class="font-medium">Creator</dt>
						<dd>{meta.details.creator ?? '—'}</dd>
						<dt class="font-medium">Producer</dt>
						<dd>{meta.details.producer ?? '—'}</dd>
						<dt class="font-medium">Created</dt>
						<dd>{meta.details.creationDate ?? '—'}</dd>
						<dt class="font-medium">Modified</dt>
						<dd>{meta.details.modDate ?? '—'}</dd>
						<dt class="font-medium">Pages</dt>
						<dd>{meta.details.pageCount}</dd>
						{#each Object.entries(meta.details.extra) as [key, value] (key)}
							<dt class="font-medium">{key}</dt>
							<dd>{value}</dd>
						{/each}
					</dl>

					<!-- Debug: strip before Mongo insert, like `details` -->
					<details class="mt-4">
						<summary class="cursor-pointer text-sm font-medium">Cleaned record (API response)</summary>
						<pre class="mt-2 max-h-96 overflow-auto rounded bg-muted p-3 text-xs">{JSON.stringify(
							{ ...meta, raw: undefined },
							null,
							2
						)}</pre>
					</details>
					{#if meta.raw}
						<details class="mt-2">
							<summary class="cursor-pointer text-sm font-medium">Original scrape (raw extractor output)</summary>
							<pre class="mt-2 max-h-96 overflow-auto rounded bg-muted p-3 text-xs">{JSON.stringify(
								meta.raw,
								null,
								2
							)}</pre>
						</details>
					{/if}
				</div>
			{/if}
		</Card.Content>
	</Card.Root>
</main>
