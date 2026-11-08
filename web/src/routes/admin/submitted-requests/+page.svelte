<script lang="ts">
	import { onMount } from 'svelte';
	import * as Card from '#lib/components/ui/card/index.js';
	import { Button } from '#lib/components/ui/button/index.js';
	import { Input } from '#lib/components/ui/input/index.js';
	import { Label } from '#lib/components/ui/label/index.js';
	import { Badge } from '#lib/components/ui/badge/index.js';
	import FileTextIcon from '@lucide/svelte/icons/file-text';
	import PaperclipIcon from '@lucide/svelte/icons/paperclip';
	import EyeIcon from '@lucide/svelte/icons/eye';
	import EyeOffIcon from '@lucide/svelte/icons/eye-off';
	import ExternalLinkIcon from '@lucide/svelte/icons/external-link';
	import CheckIcon from '@lucide/svelte/icons/check';
	import Trash2Icon from '@lucide/svelte/icons/trash-2';
	import PencilIcon from '@lucide/svelte/icons/pencil';
	import RefreshCwIcon from '@lucide/svelte/icons/refresh-cw';
	import UserIcon from '@lucide/svelte/icons/user';
	import MailIcon from '@lucide/svelte/icons/mail';

	type Feed = { id: string; title: string; url: string };

	type PendingSubmission = {
		id: string;
		name: string | null;
		email: string | null;
		description: string | null;
		generatedDescription: string | null;
		submittedSummary: string | null;
		summary: string | null;
		resourceformat: string | null;
		link: string | null;
		sitelink: string | null;
		attachmentName: string | null;
		attachmentUrl: string | null;
		status: string;
		createdAt: string | null;
	};

	let loading = $state(true);
	let error = $state<string | null>(null);
	let queue = $state<PendingSubmission[]>([]);

	// Previews toggled per submission ID
	let previewOpen = $state<Record<string, boolean>>({});

	// Editing states
	let editingId = $state<string | null>(null);
	let editName = $state('');
	let editEmail = $state('');
	let editLink = $state('');
	let editSitelink = $state('');
	let editDescription = $state('');
	let editSubmittedSummary = $state('');
	let editGeneratedDescription = $state('');
	let editSummary = $state('');
	let editAttachmentName = $state('');
	let editAttachmentUrl = $state('');

	let actionLoading = $state<string | null>(null);
	const URL_PATTERN = /^https?:\/\/\S+$/;

	let feeds = $state<Feed[]>([]);
	let feedUrl = $state('');
	let feedAdding = $state(false);
	let feedChecking = $state(false);
	let feedMessage = $state('');

	function getDocumentUrl(item: PendingSubmission): string | null {
		if (item.attachmentUrl) return item.attachmentUrl;
		if (item.link && (item.link.toLowerCase().endsWith('.pdf') || item.link.includes('/download/'))) {
			return item.link;
		}
		return null;
	}

	function getDocumentName(item: PendingSubmission): string {
		if (item.attachmentName) return item.attachmentName;
		if (item.link) {
			try {
				const pathname = new URL(item.link).pathname;
				const parts = pathname.split('/').filter(Boolean);
				if (parts.length > 0 && parts[parts.length - 1].includes('.')) {
					return decodeURIComponent(parts[parts.length - 1]);
				}
			} catch {
				// Fall through
			}
		}
		return 'Attached Document';
	}

	function isPdf(url: string | null): boolean {
		if (!url) return false;
		return url.toLowerCase().includes('.pdf');
	}

	function isImage(url: string | null): boolean {
		if (!url) return false;
		return /\.(png|jpe?g|webp|gif|svg)(\?.*)?$/i.test(url);
	}

	function togglePreview(id: string) {
		previewOpen[id] = !previewOpen[id];
	}

	async function fetchQueue() {
		loading = true;
		error = null;
		editingId = null;
		try {
			const res = await fetch('/api/moderate/pending');
			if (!res.ok) {
				error = `Failed to load moderation queue (${res.status}).`;
			} else {
				const body = await res.json();
				queue = body.records ?? [];
			}
		} catch {
			error = 'Could not connect to the moderation service.';
		} finally {
			loading = false;
		}
	}

	function startEditing(item: PendingSubmission) {
		editingId = item.id;
		editName = item.name ?? '';
		editEmail = item.email ?? '';
		editLink = item.link ?? '';
		editSitelink = item.sitelink ?? '';
		editDescription = item.description ?? '';
		editSubmittedSummary = item.submittedSummary ?? '';
		editGeneratedDescription = item.generatedDescription ?? '';
		editSummary = item.summary ?? '';
		editAttachmentName = item.attachmentName ?? '';
		editAttachmentUrl = item.attachmentUrl ?? '';
	}

	function cancelEditing() {
		editingId = null;
	}

	async function approveItem(id: string) {
		actionLoading = id;
		try {
			const res = await fetch(`/api/moderate/approve/${id}`, { method: 'POST' });
			if (!res.ok) {
				const err = await res.json().catch(() => null);
				alert(err?.detail ?? 'Failed to approve submission.');
			} else {
				queue = queue.filter((item) => item.id !== id);
			}
		} catch {
			alert('Network failure while approving submission.');
		} finally {
			actionLoading = null;
		}
	}

	async function saveModifications(id: string) {
		if (!editLink.trim() && !editAttachmentUrl.trim() && !editAttachmentName.trim()) {
			alert('Submission must have either a resource link or an attached document.');
			return;
		}
		if (editLink.trim() && !URL_PATTERN.test(editLink.trim())) {
			alert('Resource link must be a full URL starting with http:// or https://.');
			return;
		}
		if (editSitelink.trim() && !URL_PATTERN.test(editSitelink.trim())) {
			alert('Site link must be a full URL starting with http:// or https://.');
			return;
		}
		if (editSubmittedSummary.trim() && editSubmittedSummary.trim().length < 250) {
			alert('The submitter summary must contain at least 250 characters, or be left blank.');
			return;
		}
		if (editSummary.trim() && editSummary.trim().length < 250) {
			alert('The summary must contain at least 250 characters, or be left blank.');
			return;
		}

		actionLoading = id;
		try {
			const payload = {
				name: editName.trim() || null,
				email: editEmail.trim() || null,
				link: editLink.trim() || null,
				sitelink: editSitelink.trim() || null,
				description: editDescription.trim() || null,
				submitted_summary: editSubmittedSummary.trim() || null,
				generated_description: editGeneratedDescription.trim() || null,
				summary: editSummary.trim() || null,
				attachment_name: editAttachmentName.trim() || null,
				attachment_url: editAttachmentUrl.trim() || null
			};

			const res = await fetch(`/api/moderate/modify/${id}`, {
				method: 'PATCH',
				headers: { 'content-type': 'application/json' },
				body: JSON.stringify(payload)
			});

			if (!res.ok) {
				const err = await res.json().catch(() => null);
				alert(err?.detail ?? 'Failed to update submission details.');
			} else {
				queue = queue.map((item) => {
					if (item.id === id) {
						return {
							...item,
							name: payload.name,
							email: payload.email,
							link: payload.link,
							sitelink: payload.sitelink,
							description: payload.description,
								submittedSummary: payload.submitted_summary,
								generatedDescription: payload.generated_description,
								summary: payload.summary,
							attachmentName: payload.attachment_name,
							attachmentUrl: payload.attachment_url
						};
					}
					return item;
				});
				editingId = null;
			}
		} catch {
			alert('Network exception updating submission.');
		} finally {
			actionLoading = null;
		}
	}

	async function rejectItem(item: PendingSubmission) {
		const label = item.attachmentName || item.name || 'this submission';
		const isFeedEntry = item.resourceformat === 'article' || item.resourceformat === 'podcast';
		const confirmed = confirm(
			isFeedEntry
				? `Reject "${label}" and exclude it from future feed checks?`
				: `Are you sure you want to permanently reject and remove "${label}" from the submission queue?`
		);
		if (!confirmed) return;

		actionLoading = item.id;
		try {
			const res = await fetch(`/api/moderate/reject/${item.id}`, { method: 'DELETE' });
			if (!res.ok) {
				const err = await res.json().catch(() => null);
				alert(err?.detail ?? 'Server rejected deletion request.');
			} else {
				queue = queue.filter((i) => i.id !== item.id);
			}
		} catch {
			alert('Network error while deleting submission.');
		} finally {
			actionLoading = null;
		}
	}

	async function fetchFeeds() {
		try {
			const res = await fetch('/api/feeds');
			if (res.ok) feeds = (await res.json()).feeds ?? [];
		} catch {
			feedMessage = 'Could not load RSS feeds.';
		}
	}

	async function addFeed(event: SubmitEvent) {
		event.preventDefault();
		feedMessage = '';
		if (!URL_PATTERN.test(feedUrl.trim())) {
			feedMessage = 'Enter a full feed URL starting with http:// or https://.';
			return;
		}
		feedAdding = true;
		try {
			const res = await fetch('/api/feeds', {
				method: 'POST',
				headers: { 'content-type': 'application/json' },
				body: JSON.stringify({ url: feedUrl.trim() })
			});
			const body = await res.json().catch(() => null);
			if (!res.ok) throw new Error(body?.detail ?? 'Could not add that feed.');
			feedUrl = '';
			feedMessage = body.added ? 'Feed added.' : 'That feed is already listed.';
			await fetchFeeds();
		} catch (error) {
			feedMessage = error instanceof Error ? error.message : 'Could not add that feed.';
		} finally {
			feedAdding = false;
		}
	}

	async function checkFeeds() {
		feedChecking = true;
		feedMessage = '';
		try {
			const res = await fetch('/api/feeds/check', { method: 'POST' });
			const body = await res.json().catch(() => null);
			if (!res.ok) throw new Error(body?.detail ?? 'Feed check failed.');
			feedMessage = `${body.inserted} added, ${body.duplicates} duplicates skipped across ${body.feedsChecked} feeds.`;
			if (body.failed?.length) feedMessage += ` ${body.failed.length} entries or feeds failed.`;
			await Promise.all([fetchQueue(), fetchFeeds()]);
		} catch (error) {
			feedMessage = error instanceof Error ? error.message : 'Feed check failed.';
		} finally {
			feedChecking = false;
		}
	}

	function formatDate(dateStr: string | null): string {
		if (!dateStr) return '—';
		try {
			return new Date(dateStr).toLocaleDateString('en-CA', {
				year: 'numeric',
				month: 'short',
				day: 'numeric'
			});
		} catch {
			return dateStr;
		}
	}

	onMount(() => {
		fetchQueue();
		fetchFeeds();
	});
</script>

<svelte:head>
	<title>Submitted Requests · Black History Knowledge Hub</title>
</svelte:head>

<main class="container mx-auto max-w-4xl px-4 py-12 space-y-6">
	<Card.Root class="border-orange-200/80 shadow-md">
		<Card.Header>
			<Card.Title class="text-lg font-bold text-[#2A1A10]">RSS & Atom feeds</Card.Title>
			<Card.Description class="text-xs text-muted-foreground">
				Add recent stories and podcast episodes to the pending queue. Existing links are skipped.
			</Card.Description>
		</Card.Header>
		<Card.Content class="space-y-4">
			<form class="flex flex-col gap-2 sm:flex-row" onsubmit={addFeed}>
				<Input
					type="url"
					bind:value={feedUrl}
					placeholder="https://example.com/feed.xml"
					aria-label="RSS or Atom feed URL"
					disabled={feedAdding}
				/>
				<Button type="submit" class="shrink-0 bg-orange-700 text-white hover:bg-orange-800" disabled={feedAdding}>
					{feedAdding ? 'Adding…' : 'Add feed'}
				</Button>
			</form>
			{#if feeds.length}
				<ul class="space-y-2 rounded-lg border border-orange-100 bg-orange-50/30 p-3 text-xs">
					{#each feeds as feed (feed.id)}
						<li>
							<p class="font-semibold text-foreground">{feed.title}</p>
							<p class="break-all text-muted-foreground">{feed.url}</p>
						</li>
					{/each}
				</ul>
			{/if}
			<div class="flex flex-wrap items-center gap-3">
				<Button
					type="button"
					variant="outline"
					class="border-orange-200 text-xs hover:bg-orange-50"
					onclick={checkFeeds}
					disabled={feedChecking || !feeds.length}
				>
					<RefreshCwIcon class="size-3.5 {feedChecking ? 'animate-spin' : ''}" />
					{feedChecking ? 'Checking feeds…' : 'Check recent stories'}
				</Button>
				{#if feedMessage}
					<p class="text-xs text-muted-foreground" role="status">{feedMessage}</p>
				{/if}
			</div>
		</Card.Content>
	</Card.Root>

	<Card.Root class="border-orange-200/80 shadow-md">
		<Card.Header class="flex flex-row items-center justify-between border-b border-orange-100 pb-4">
			<div class="space-y-1">
				<Card.Title class="text-xl font-bold tracking-tight text-[#2A1A10]">
					Submitted Requests (Moderation Queue)
				</Card.Title>
				<Card.Description class="text-xs text-muted-foreground">
					Review raw user contributions (uploaded documents and links) before sending them to the processing pipeline.
				</Card.Description>
			</div>
			<div class="flex items-center gap-2">
				<Button
					type="button"
					variant="outline"
					size="sm"
					class="h-8 gap-1.5 text-xs border-orange-200 hover:bg-orange-50"
					onclick={fetchQueue}
					disabled={loading}
				>
					<RefreshCwIcon class="size-3.5 {loading ? 'animate-spin' : ''}" />
					Refresh
				</Button>
				<Badge
					variant="secondary"
					class="font-semibold {queue.length > 0 ? 'bg-amber-100 text-amber-900 border-amber-300' : ''}"
				>
					{queue.length} Pending
				</Badge>
			</div>
		</Card.Header>

		<Card.Content class="space-y-5 pt-5">
			{#if loading}
				<div class="py-12 text-center text-sm text-muted-foreground animate-pulse space-y-2">
					<p>Loading submission queue…</p>
				</div>
			{:else if error}
				<div class="rounded-lg border border-red-200 bg-red-50 p-4 text-center text-sm font-medium text-red-700">
					⚠️ {error}
				</div>
			{:else if queue.length === 0}
				<div class="rounded-xl border border-dashed border-orange-200 bg-orange-50/30 py-14 text-center space-y-2">
					<p class="text-base font-semibold text-[#2A1A10]">📥 Moderation inbox clear</p>
					<p class="text-xs text-muted-foreground">No pending user submissions waiting for review right now.</p>
					<Button
						type="button"
						size="sm"
						variant="outline"
						class="mt-3 text-xs border-orange-200"
						onclick={fetchQueue}
					>
						Check Again
					</Button>
				</div>
			{/if}

			<div class="space-y-4">
				{#each queue as item (item.id)}
					{@const docUrl = getDocumentUrl(item)}
					{@const docName = getDocumentName(item)}
					{@const hasDoc = !!item.attachmentUrl || !!item.attachmentName || (!!item.link && isPdf(item.link))}

					<article class="rounded-xl border border-orange-200/70 bg-card p-5 shadow-xs space-y-4 transition-all">
						<!-- VIEW MODE -->
						{#if editingId !== item.id}
							<!-- Header: Submitter Name, Email, Date, Badges & Actions -->
							<div class="flex flex-col gap-3 sm:flex-row sm:items-start sm:justify-between">
								<div class="space-y-1.5">
									<div class="flex flex-wrap items-center gap-2">
										<h3 class="text-base font-bold text-foreground inline-flex items-center gap-1.5">
											<UserIcon class="size-4 text-orange-700" />
											{item.name || 'Anonymous Contributor'}
										</h3>
										{#if item.email}
											<Badge variant="outline" class="text-[11px] gap-1 font-normal border-orange-200 bg-orange-50/50">
												<MailIcon class="size-3 text-muted-foreground" />
												<a href={`mailto:${item.email}`} class="hover:underline">{item.email}</a>
											</Badge>
										{/if}
										{#if hasDoc}
											<Badge variant="secondary" class="font-mono text-[10px] tracking-wider uppercase bg-amber-100 text-amber-900 border-amber-300">
												📎 Document Attached
											</Badge>
										{:else if item.link}
											<Badge variant="secondary" class="font-mono text-[10px] tracking-wider uppercase">
												🔗 Link Submission
											</Badge>
										{/if}
									</div>

									<p class="text-[11px] text-muted-foreground">
										Submitted on {formatDate(item.createdAt)}
									</p>
								</div>

								<!-- Action buttons -->
								<div class="flex items-center gap-1.5 shrink-0 self-end sm:self-start">
									<Button
										type="button"
										variant="outline"
										size="sm"
										class="h-8 text-xs gap-1 border-orange-200 hover:bg-orange-50"
										disabled={actionLoading !== null}
										onclick={() => startEditing(item)}
									>
										<PencilIcon class="size-3.5" />
										Edit
									</Button>
									<Button
										type="button"
										variant="destructive"
										size="sm"
										class="h-8 text-xs gap-1"
										disabled={actionLoading !== null}
										onclick={() => rejectItem(item)}
									>
										<Trash2Icon class="size-3.5" />
										Reject
									</Button>
									<Button
										type="button"
										size="sm"
										class="h-8 text-xs gap-1 bg-emerald-600 hover:bg-emerald-700 text-white font-medium"
										disabled={actionLoading !== null}
										onclick={() => approveItem(item.id)}
									>
										<CheckIcon class="size-3.5" />
										{actionLoading === item.id ? 'Approving…' : 'Approve'}
									</Button>
								</div>
							</div>

							<!-- ATTACHED DOCUMENT PREVIEW SECTION -->
							{#if hasDoc}
								<div class="rounded-xl border border-orange-200/90 bg-orange-50/40 p-3.5 space-y-3">
									<div class="flex flex-col gap-2 sm:flex-row sm:items-center sm:justify-between">
										<div class="flex items-center gap-2.5 min-w-0">
											<div class="p-2 bg-orange-100 rounded-lg text-orange-800 shrink-0">
												<FileTextIcon class="size-5" />
											</div>
											<div class="min-w-0">
												<p class="text-xs font-bold text-[#2A1A10] truncate">
													{docName}
												</p>
												<p class="text-[10px] uppercase font-mono text-muted-foreground">
													{isPdf(docUrl) ? 'PDF Document' : 'Attached File'}
												</p>
											</div>
										</div>

										<!-- Document preview & open actions -->
										<div class="flex items-center gap-1.5 shrink-0">
											{#if docUrl}
												<Button
													type="button"
													variant="outline"
													size="sm"
													class="h-7 text-xs gap-1 border-orange-200 bg-white hover:bg-orange-50"
													onclick={() => togglePreview(item.id)}
												>
													{#if previewOpen[item.id]}
														<EyeOffIcon class="size-3" />
														Hide Viewer
													{:else}
														<EyeIcon class="size-3" />
														Inline Preview
													{/if}
												</Button>
												<Button
													type="button"
													variant="outline"
													size="sm"
													class="h-7 text-xs gap-1 border-orange-200 bg-white hover:bg-orange-50"
													href={docUrl}
													target="_blank"
													rel="noopener noreferrer"
												>
													<ExternalLinkIcon class="size-3" />
													Open File
												</Button>
											{/if}
										</div>
									</div>

									<!-- Collapsible Inline Document Viewer -->
									{#if previewOpen[item.id] && docUrl}
										<div class="pt-2 border-t border-orange-200/60">
											{#if isPdf(docUrl)}
												<iframe
													src={docUrl}
													title="Document PDF Preview"
													class="w-full h-96 rounded-lg border border-border bg-white shadow-inner"
												></iframe>
											{:else if isImage(docUrl)}
												<div class="flex justify-center bg-muted/20 p-2 rounded-lg border">
													<img src={docUrl} alt="Uploaded attachment" class="max-h-80 object-contain rounded" />
												</div>
											{:else}
												<div class="p-4 text-center text-xs text-muted-foreground bg-muted/20 rounded-lg">
													<span>Inline rendering not supported for this file type. Click "Open File" above.</span>
												</div>
											{/if}
										</div>
									{/if}
								</div>
							{/if}

							<!-- GENERATED PUBLIC METADATA -->
							<div class="space-y-3 rounded-lg border border-orange-200/70 bg-orange-50/30 p-3 text-xs leading-relaxed">
								<div>
									<span class="mb-1 block text-[10px] font-bold uppercase text-muted-foreground">
										Generated Description:
									</span>
									<p class="whitespace-pre-wrap text-foreground">
										{item.generatedDescription || 'No generated description. Use Edit to add one.'}
									</p>
								</div>
								<div>
									<span class="mb-1 block text-[10px] font-bold uppercase text-muted-foreground">
										Generated Summary:
									</span>
									<p class="whitespace-pre-wrap text-foreground">
										{item.summary || 'No generated summary. Use Edit to add one before approving.'}
									</p>
								</div>
							</div>

							<!-- SUBMITTER NOTES / DESCRIPTION -->
							{#if item.description || item.submittedSummary}
								<div class="space-y-3 rounded-lg border border-border/50 bg-muted/30 p-3 text-xs leading-relaxed">
									{#if item.description}
										<div>
											<span class="mb-1 block text-[10px] font-bold uppercase text-muted-foreground">
												Submitter Notes & Description:
											</span>
											<p class="whitespace-pre-wrap text-foreground">{item.description}</p>
										</div>
									{/if}
									{#if item.submittedSummary}
										<div>
											<span class="mb-1 block text-[10px] font-bold uppercase text-muted-foreground">
												Submitter Summary:
											</span>
											<p class="whitespace-pre-wrap text-foreground">{item.submittedSummary}</p>
										</div>
									{/if}
								</div>
							{/if}

							<!-- WEB LINKS SECTION (IF PROVIDED) -->
							<div class="grid grid-cols-1 sm:grid-cols-2 gap-x-4 gap-y-2 border-t border-border/50 pt-3 text-xs">
								{#if item.link}
									<div class="space-y-0.5">
										<span class="text-[10px] uppercase font-bold text-muted-foreground tracking-wider">
											Resource Web Link
										</span>
										<div class="truncate">
											<a
												href={item.link}
												target="_blank"
												rel="noopener noreferrer"
												class="text-orange-700 hover:underline inline-flex items-center gap-1 font-medium max-w-full"
											>
												<span class="truncate">{item.link}</span>
												<ExternalLinkIcon class="size-3 shrink-0" />
											</a>
										</div>
									</div>
								{/if}

								{#if item.sitelink}
									<div class="space-y-0.5">
										<span class="text-[10px] uppercase font-bold text-muted-foreground tracking-wider">
											Host Site Link
										</span>
										<div class="truncate">
											<a
												href={item.sitelink}
												target="_blank"
												rel="noopener noreferrer"
												class="text-orange-700 hover:underline inline-flex items-center gap-1 font-medium max-w-full"
											>
												<span class="truncate">{item.sitelink}</span>
												<ExternalLinkIcon class="size-3 shrink-0" />
											</a>
										</div>
									</div>
								{/if}
							</div>

						<!-- EDITING MODE -->
						{:else}
							<div class="space-y-4 rounded-xl border border-orange-300 bg-orange-50/40 p-4">
								<div class="flex items-center justify-between border-b border-orange-200 pb-2">
									<h4 class="text-xs font-bold uppercase tracking-wider text-[#2A1A10]">
										Curator Editor — Edit Raw Submission
									</h4>
									<span class="text-[11px] font-mono text-muted-foreground">ID: {item.id}</span>
								</div>

								<div class="grid grid-cols-1 md:grid-cols-2 gap-4">
									<!-- Submitter Name -->
									<div class="space-y-1">
										<Label for={`name-${item.id}`} class="text-xs font-semibold">Submitter Name</Label>
										<Input
											id={`name-${item.id}`}
											type="text"
											class="bg-background text-xs"
											bind:value={editName}
											placeholder="e.g. Jane Doe"
										/>
									</div>

									<!-- Submitter Email -->
									<div class="space-y-1">
										<Label for={`email-${item.id}`} class="text-xs font-semibold">Contact Email</Label>
										<Input
											id={`email-${item.id}`}
											type="email"
											class="bg-background text-xs"
											bind:value={editEmail}
											placeholder="name@example.com"
										/>
									</div>

									<!-- Attached Document Name -->
									<div class="space-y-1">
										<Label for={`attname-${item.id}`} class="text-xs font-semibold">Attached File Name</Label>
										<Input
											id={`attname-${item.id}`}
											type="text"
											class="bg-background text-xs"
											bind:value={editAttachmentName}
											placeholder="e.g. document-1956.pdf"
										/>
									</div>

									<!-- Attached Document URL/Path -->
									<div class="space-y-1">
										<Label for={`atturl-${item.id}`} class="text-xs font-semibold">Document URL / Path</Label>
										<Input
											id={`atturl-${item.id}`}
											type="url"
											class="bg-background text-xs"
											bind:value={editAttachmentUrl}
											placeholder="https://..."
										/>
									</div>

									<!-- Resource Link -->
									<div class="space-y-1">
										<Label for={`link-${item.id}`} class="text-xs font-semibold">Resource link (optional if a document is attached)</Label>
										<Input
											id={`link-${item.id}`}
											type="url"
											class="bg-background text-xs"
											bind:value={editLink}
											placeholder="Direct link to the PDF, e.g. https://bccns.com/download/2468/"
										/>
									</div>

									<!-- Site Link -->
									<div class="space-y-1">
										<Label for={`site-${item.id}`} class="text-xs font-semibold">Site link (optional)</Label>
										<Input
											id={`site-${item.id}`}
											type="url"
											class="bg-background text-xs"
											bind:value={editSitelink}
											placeholder="e.g. https://bccns.com/resources/"
										/>
									</div>

									<!-- Submitter Description -->
									<div class="space-y-1 md:col-span-2">
										<Label for={`desc-${item.id}`} class="text-xs font-semibold">
											Submitter Notes / Description
										</Label>
										<textarea
											id={`desc-${item.id}`}
											rows={3}
											class="flex w-full rounded-md border border-input bg-background p-2 text-xs shadow-xs focus-visible:outline-hidden focus-visible:ring-1 focus-visible:ring-ring"
											bind:value={editDescription}
											placeholder="User's explanation of what this record is..."
										></textarea>
									</div>

									<!-- Submitter Summary -->
									<div class="space-y-1 md:col-span-2">
										<Label for={`submitted-summary-${item.id}`} class="text-xs font-semibold">
											Submitter Summary
										</Label>
										<textarea
											id={`submitted-summary-${item.id}`}
											rows={5}
											minlength={250}
											maxlength={2000}
											class="flex w-full rounded-md border border-input bg-background p-2 text-xs shadow-xs focus-visible:outline-hidden focus-visible:ring-1 focus-visible:ring-ring"
											bind:value={editSubmittedSummary}
											placeholder="Summary supplied by the submitter, if any..."
										></textarea>
									</div>

									<!-- Generated Public Description -->
									<div class="space-y-1 md:col-span-2">
										<Label for={`generated-desc-${item.id}`} class="text-xs font-semibold">
											Generated Description (Public)
										</Label>
										<textarea
											id={`generated-desc-${item.id}`}
											rows={2}
											maxlength={150}
											class="flex w-full rounded-md border border-input bg-background p-2 text-xs shadow-xs focus-visible:outline-hidden focus-visible:ring-1 focus-visible:ring-ring"
											bind:value={editGeneratedDescription}
											placeholder="Short description shown on the public resource card..."
										></textarea>
									</div>

									<!-- Generated Public Summary -->
									<div class="space-y-1 md:col-span-2">
										<Label for={`summary-${item.id}`} class="text-xs font-semibold">
											Generated Summary (Public)
										</Label>
										<textarea
											id={`summary-${item.id}`}
											rows={7}
											minlength={250}
											maxlength={2000}
											class="flex w-full rounded-md border border-input bg-background p-2 text-xs shadow-xs focus-visible:outline-hidden focus-visible:ring-1 focus-visible:ring-ring"
											bind:value={editSummary}
											placeholder="At least 250 characters, or leave blank if the source cannot support a summary..."
										></textarea>
									</div>
								</div>

								<div class="flex justify-end items-center gap-2 pt-3 border-t border-orange-200">
									<Button
										type="button"
										size="sm"
										variant="ghost"
										class="text-xs"
										onclick={cancelEditing}
										disabled={actionLoading !== null}
									>
										Discard
									</Button>
									<Button
										type="button"
										size="sm"
										class="text-xs bg-orange-700 hover:bg-orange-800 text-white"
										disabled={actionLoading === item.id}
										onclick={() => saveModifications(item.id)}
									>
										{actionLoading === item.id ? 'Saving…' : 'Apply Changes'}
									</Button>
								</div>
							</div>
						{/if}
					</article>
				{/each}
			</div>
		</Card.Content>
	</Card.Root>
</main>
