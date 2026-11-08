<script lang="ts">
	import { Button } from '#lib/components/ui/button/index.js';
	import { Input } from '#lib/components/ui/input/index.js';
	import * as Card from '#lib/components/ui/card/index.js';
	import pattern from '#lib/assets/backgroundPattern.webp';

	type BrokenIssues = {
		link_broken: boolean;
		sitelink_broken: boolean;
	};

	type BrokenRecord = {
		id: string; 
		title: string | null;
		attribution: string | null;
		link: string;
		sitelink: string | null;
		issues: BrokenIssues;
	};

	type APIResponse = {
		success: boolean;
		count: number;
		broken_records: BrokenRecord[]; 
	};

	let loading = $state(false);
	let error = $state<string | null>(null);
	let results = $state<APIResponse | null>(null);

	let editingId = $state<string | null>(null);
	let newLinkValue = $state('');
	let actionLoading = $state<string | null>(null);

	async function runScan() {
		loading = true;
		error = null;
		results = null;
		editingId = null;
		try {
			const res = await fetch('/api/bad-links', {
				method: 'GET',
				headers: { 'content-type': 'application/json' }
			});
			
			if (!res.ok) {
				const body = (await res.json().catch(() => null)) as { detail?: unknown } | null;
				const detail = body?.detail;
				error = typeof detail === 'string' ? detail : `Scan failed with status ${res.status}.`;
			} else {
				results = (await res.json()) as APIResponse;
			}
		} catch {
			error = 'Could not reach the scan API.';
		} finally {
			loading = false;
		}
	}

	function toggleEdit(item: BrokenRecord) {
		if (editingId === item.id) {
			editingId = null;
			newLinkValue = '';
		} else {
			editingId = item.id;
			newLinkValue = item.link;
		}
	}

	async function saveLink(id: string) {
		if (!newLinkValue.trim()) return;
		actionLoading = id;
		try {
			const res = await fetch(`/api/bad-links/${id}`, {
				method: 'PATCH',
				headers: { 'content-type': 'application/json' },
				body: JSON.stringify({ link: newLinkValue })
			});

			if (!res.ok) {
				const body = await res.json().catch(() => null);
				alert(body?.detail || 'Failed to update the link.');
			} else {
				if (results) {
					results.broken_records = results.broken_records.filter(record => record.id !== id);
					results.count = results.broken_records.length;
				}
				editingId = null;
			}
		} catch {
			alert('Network failure processing the link update.');
		} finally {
			actionLoading = null;
		}
	}

	async function deleteRecord(item: BrokenRecord) {
		const targetName = item.title || 'this untitled resource';
		const confirmed = confirm(
			`⚠️ WARNING:\n\nYou are about to permanently delete "${targetName}" from the database.\n\nThis will completely erase the whole resource record, not just the link. This action cannot be undone.\n\nDo you want to proceed?`
		);

		if (!confirmed) return;

		actionLoading = item.id;
		try {
			const res = await fetch(`/api/bad-links/${item.id}`, {
				method: 'DELETE'
			});

			if (!res.ok) {
				const body = await res.json().catch(() => null);
				alert(body?.detail || 'Failed to delete the resource.');
			} else {
				if (results) {
					results.broken_records = results.broken_records.filter(r => r.id !== item.id);
					results.count = results.broken_records.length;
				}
			}
		} catch {
			alert('Network failure processing structural deletion operations.');
		} finally {
			actionLoading = null;
		}
	}
</script>

<svelte:head>
	<title>Bad links · Black History Knowledge Hub</title>
</svelte:head>

<main>
	<!-- Orange band with the pattern (same as the other pages) -->
	<section class="relative overflow-hidden bg-[#FF8C4B] px-4 pb-28 pt-8 text-center md:pb-32 md:pt-12">
		<div
			class="absolute inset-0 opacity-40 mix-blend-multiply"
			style="background-image: url({pattern}); background-size: auto 180px; background-repeat: repeat;"
		></div>
		<div class="relative">
			<h1 class="font-heading text-2xl tracking-wide text-[#2A1A10] sm:text-3xl md:text-5xl">
				BAD LINKS
			</h1>
			<p
				class="mt-4 inline-block rounded-lg bg-[#FFC49B] px-3 py-1.5 text-sm font-semibold text-[#2A1A10] md:px-4 md:py-2 md:text-base"
			>
				Find records whose links no longer work
			</p>
		</div>
	</section>

	<!-- The existing card, overlapping the bottom of the band -->
	<div class="relative mx-auto -mt-20 max-w-2xl space-y-6 px-3 pb-16 sm:px-4 md:-mt-24">
	<Card.Root>
		<Card.Header>
			<Card.Title>Link Integrity Checker</Card.Title>
			<Card.Description>Scan all collection records to identify broken file links or source sitelinks.</Card.Description>
		</Card.Header>
		<Card.Content class="space-y-4">
			<div class="flex flex-col gap-2">
				<Button type="button" class="self-center bg-[#3F6B41] px-10 text-white hover:bg-[#335A35]" onclick={runScan} disabled={loading}>
					{loading ? 'Scanning entire database…' : 'Start Integrity Scan'}
				</Button>
				{#if error}
					<p class="text-sm font-medium text-red-500 mt-1">
						{error}
					</p>
				{/if}
			</div>

			{#if results}
				<div class="space-y-4 pt-2 border-t border-border">
					<div class="flex justify-between items-center bg-muted/50 p-3 rounded-lg border border-border">
						<span class="text-sm font-medium">Scan Result Summary</span>
						<span class={`text-sm font-bold px-2 py-0.5 rounded ${results.count > 0 ? 'bg-red-500/10 text-red-500' : 'bg-green-500/10 text-green-500'}`}>
							{results.count} broken {results.count === 1 ? 'link' : 'links'} found
						</span>
					</div>

					{#if results.broken_records.length === 0}
						<p class="text-sm text-center text-muted-foreground py-4">
							🎉 Excellent! All system links and sitelinks are fully operational.
						</p>
					{/if}

					<div class="space-y-3 max-h-[500px] overflow-y-auto pr-1">
						{#each results.broken_records as item (item.id)}
							<div class="p-3 border border-border rounded-lg space-y-3 bg-card text-card-foreground shadow-sm">
								
								<div class="flex justify-between items-start gap-4">
									<div class="space-y-1">
										<h4 class="font-semibold text-sm leading-tight">{item.title ?? 'Untitled Resource'}</h4>
										{#if item.attribution}
											<p class="text-xs font-medium text-muted-foreground block">
												via {item.attribution}
											</p>
										{/if}
									</div>
									
									<div class="flex items-center gap-1.5 shrink-0">
										<Button 
											type="button" 
											variant="outline" 
											size="sm" 
											class="h-7 text-xs px-2.5" 
											disabled={actionLoading !== null}
											onclick={() => toggleEdit(item)}
										>
											{editingId === item.id ? 'Cancel' : 'Edit'}
										</Button>
										<Button 
											type="button" 
											variant="destructive" 
											size="sm" 
											class="h-7 text-xs px-2.5"
											disabled={actionLoading !== null}
											onclick={() => deleteRecord(item)}
										>
											Delete
										</Button>
									</div>
								</div>
								
								<div class="space-y-1 text-xs border-t border-border/40 pt-2">
									<div class="flex items-start gap-2">
										<span class={`font-mono text-[10px] uppercase px-1 rounded ${item.issues.link_broken ? 'bg-red-500/10 text-red-500 font-bold' : 'bg-green-500/10 text-green-500'}`}>
											Link
										</span>
										<p class={`break-all ${item.issues.link_broken ? 'text-red-500 underline decoration-wavy' : 'text-muted-foreground'}`}>
											{item.link}
										</p>
									</div>

									{#if item.sitelink}
										<div class="flex items-start gap-2 pt-1">
											<span class={`font-mono text-[10px] uppercase px-1 rounded ${item.issues.sitelink_broken ? 'bg-red-500/10 text-red-500 font-bold' : 'bg-green-500/10 text-green-500'}`}>
												Site
											</span>
											<p class={`break-all ${item.issues.sitelink_broken ? 'text-red-500 underline decoration-wavy' : 'text-muted-foreground'}`}>
												{item.sitelink}
											</p>
										</div>
									{/if}
								</div>

								{#if editingId === item.id}
									<div class="bg-muted/40 p-2.5 border border-dashed rounded-md space-y-2 mt-2">
										<label for={`input-${item.id}`} class="text-[11px] font-medium block text-muted-foreground">
											Update destination file link address:
										</label>
										<div class="flex gap-2">
											<Input 
												id={`input-${item.id}`}
												type="url" 
												class="h-8 text-xs bg-background" 
												bind:value={newLinkValue} 
												placeholder="https://"
											/>
											<Button 
												type="button" 
												size="sm" 
												class="h-8 text-xs px-3"
												disabled={actionLoading === item.id}
												onclick={() => saveLink(item.id)}
											>
												{actionLoading === item.id ? 'Saving…' : 'Save'}
											</Button>
										</div>
									</div>
								{/if}

							</div>
						{/each}
					</div>
				</div>
			{/if}
		</Card.Content>
	</Card.Root>
	</div>
</main>