<script lang="ts">
	import { applyAction, enhance, type SubmitFunction } from '$app/forms';
	import { onMount, tick } from 'svelte';
	import SearchSummary from '#lib/components/search/SearchSummary.svelte';
	import ResultsCard from '#lib/components/resultsCard/ResultsCard.svelte';
	import MagicBorder from '#lib/components/search/MagicBorder.svelte';
	import SearchBox from '#lib/components/search/SearchBox.svelte';
	import { Button } from '#lib/components/ui/button/index.js';
	import { MAX_HISTORY, type ThreadTurn } from '#lib/search.js';

	let { data, form } = $props();
	// Text of the main search box. Starts from `form` so a no-JS submit (full page reload) keeps the
	// question; with JS the box is never cleared, so later `form` changes don't need copying in.
	// svelte-ignore state_referenced_locally
	let newQuestion = $state(form?.question ?? '');

	type Mode = 'new' | 'followup';

	// sessionStorage: survives a refresh, cleared when the tab closes, separate per tab
	const STORAGE_KEY = 'search-thread';
	const MAX_THREAD = 10; // keep only the newest turns so storage can't grow forever

	// The conversation: one entry per answered question
	let thread = $state<ThreadTurn[]>([]);
	// false until the saved thread is loaded, so the save effect can't overwrite it with []
	let restored = $state(false);

	// Load the saved thread. onMount runs only in the browser (the server has no sessionStorage).
	onMount(() => {
		try {
			const saved = JSON.parse(sessionStorage.getItem(STORAGE_KEY) ?? '[]');
			// Ignore anything that doesn't look like a thread (e.g. saved by an older version)
			if (
				Array.isArray(saved) &&
				saved.every((t) => typeof t?.question === 'string' && Array.isArray(t?.results))
			) {
				thread = saved.slice(-MAX_THREAD);
			}
		} catch {
			// Storage blocked (private mode) or corrupt JSON: start empty, like before
		}
		restored = true;
		// The thread is on screen and the list collapsed: drop the marker from the <svelte:head>
		// script so the list shows again (after tick(), so both changes reach the screen together)
		tick().then(() => delete document.documentElement.dataset.savedThread);
	});

	// Runs in the browser while the page is still loading, before anything is drawn. The server
	// can't see sessionStorage, so it always sends "Recent records" open; if a thread is saved,
	// this marks <html> so the CSS below hides the list until onMount has restored the thread.
	// (Same trick sites use to avoid a flash of the wrong dark/light theme.)
	// The closing tag is written with a backslash (<\/script>): the plain form, anywhere in this
	// block (even in a comment), would end this component's own script block early.
	const hideRecentsScript = `<script>try{if(sessionStorage.getItem(${JSON.stringify(STORAGE_KEY)}))document.documentElement.dataset.savedThread=''}catch(e){}<\/script>`;

	// Save whenever the thread changes
	$effect(() => {
		if (!restored) return;
		try {
			if (thread.length) sessionStorage.setItem(STORAGE_KEY, JSON.stringify(thread));
			else sessionStorage.removeItem(STORAGE_KEY);
		} catch {
			// Storage full or blocked: the page still works, it just won't survive a refresh
		}
	});
	// Set while a request is running: which form sent it, and the question (shown as a placeholder turn)
	let pending = $state<{ mode: Mode; question: string } | null>(null);
	// Which form the last error belongs to, so it shows under the right input
	let errorFor = $state<Mode>('new');
	let followUp = $state('');
	let followUpInput = $state<HTMLInputElement | HTMLTextAreaElement | null>(null);

	// The "Recent records" browse list: open only while there are no results. It collapses as
	// soon as a search starts, and when results appear without one (the thread restored after a
	// refresh, or a no-JS answer). Then it's just a triangle the user can toggle (bind:open keeps
	// manual opens/closes sticky while the thread lives).
	// Driven by `turns`, not `visibleTurns`: a new search temporarily hides the
	// thread and must NOT pop this open mid-search.
	// Starts closed when the server already has an answer (no-JS submit), so it never renders open.
	// svelte-ignore state_referenced_locally
	let recentsOpen = $state(!form?.results);
	let threadHasTurns = $state(false); // so open/close only fire on a change, not every render
	$effect(() => {
		if (turns.length && !threadHasTurns) {
			threadHasTurns = true;
			recentsOpen = false;
		} else if (!turns.length && threadHasTurns) {
			threadHasTurns = false;
			recentsOpen = true;
		}
	});

	// Without JavaScript the form does a normal page reload and the answer arrives as `form`
	const turns = $derived<ThreadTurn[]>(
		thread.length ? thread : form?.results ? [form as unknown as ThreadTurn] : []
	);
	// While a NEW search runs, hide the old thread — it is about to be replaced
	const visibleTurns = $derived(pending?.mode === 'new' ? [] : turns);

	// Chat-style spacing: the newest follow-up (or its loading placeholder) is at least one screen
	// tall, so it can always be scrolled to the top even when its answer is short. Not for the
	// first search, which already sits right under the header.
	const FILL_SCREEN = 'min-h-[calc(100dvh-8rem)]'; // minus the sticky follow-up bar
	const padLatestTurn = $derived(visibleTurns.length > 1 && !pending);

	// Sent with each follow-up: the last turns' questions and summaries (records are not needed)
	const historyJson = $derived(
		JSON.stringify(
			turns.slice(-MAX_HISTORY).map(({ question, summary }) => ({ question, summary }))
		)
	);

	// One submit handler for both forms; `mode` decides whether the answer replaces or extends the thread
	// Scroll an element to the top of the screen (scroll-mt-6 on the target leaves a small gap)
	function scrollToTop(id: string) {
		document.getElementById(id)?.scrollIntoView({ behavior: 'smooth', block: 'start' });
	}

	function resetSearch() {
		if (pending) return;
		thread = [];
		form = null;
		newQuestion = '';
		followUp = '';
		recentsOpen = true;
		tick().then(() => window.scrollTo({ top: 0, behavior: 'smooth' }));
	}

	function submitTo(mode: Mode): SubmitFunction {
		return ({ formData }) => {
			pending = { mode, question: formData.get('question')?.toString().trim() ?? '' };
			errorFor = mode;
			recentsOpen = false; // a search starting shouldn't wait for results to reclaim space

			// Follow-up: move the question + loading placeholder to the top right away, so the
			// answer appears where you are looking (not off-screen below the follow-up bar).
			// Not awaited: the request starts immediately.
			if (mode === 'followup') tick().then(() => scrollToTop('turn-pending'));

			return async ({ result }) => {
				pending = null;

				if (result.type === 'success' && result.data?.results) {
					const turn = result.data as unknown as ThreadTurn;
					thread = mode === 'new' ? [turn] : [...thread, turn].slice(-MAX_THREAD);
					if (mode === 'followup') followUp = '';
					form = null; // clear any old error message

					// The answer replaces the placeholder at the same spot; re-align in case the
					// user scrolled while waiting, then put the cursor back for the next question
					await tick();
					if (mode === 'followup') scrollToTop(`turn-${thread.length - 1}`);
					followUpInput?.focus({ preventScroll: true });
				} else {
					// Validation error or API failure: puts it in `form` so the messages below render
					await applyAction(result);
				}
			};
		};
	}
</script>

<svelte:head>
	<!-- eslint-disable-next-line svelte/no-at-html-tags -- our own constant, no user input -->
	{@html hideRecentsScript}
</svelte:head>

{#snippet errors(mode: Mode)}
	{#if errorFor === mode && form?.errors?.question}
		<p class="text-sm font-medium text-red-500">{form.errors.question[0]}</p>
	{/if}
	{#if errorFor === mode && form?.message}
		<p class="text-sm font-medium text-red-500">{form.message}</p>
	{/if}
{/snippet}

<main class="container mx-auto max-w-6xl px-4 pt-12 space-y-8">
	<!-- Narrow, centered column for the title + search box; results below keep the full width -->
	<header class="mx-auto max-w-2xl space-y-4">
		<div class="flex items-center justify-between gap-4">
			<h1 class="text-2xl font-semibold">Search the archive</h1>
			{#if turns.length || newQuestion || followUp || form}
				<Button type="button" variant="outline" size="sm" onclick={resetSearch} disabled={!!pending}>
					Reset search
				</Button>
			{/if}
		</div>

		<!-- New search: starts a fresh thread -->
		<form method="POST" action="?/search" class="w-full space-y-2" use:enhance={submitTo('new')}>
			<MagicBorder active={pending?.mode === 'new'} rounded="rounded-2xl">
				<SearchBox bind:value={newQuestion} disabled={!!pending} />
			</MagicBorder>
			{@render errors('new')}
		</form>
	</header>

	<!-- Browse list: open on a fresh visit; collapses on search, then it's a toggle -->
	<details bind:open={recentsOpen} class="recents space-y-3">
		<summary class="cursor-pointer text-sm font-medium text-muted-foreground select-none">
			Recent records
		</summary>
		<div class="mt-3 space-y-3">
			{#if data.defaultRecords.length}
				<div class="grid grid-cols-1 gap-3 md:grid-cols-3">
					{#each data.defaultRecords as record, i (record.id)}
						<ResultsCard result={record} number={i + 1} anchorId={'default-' + i} />
					{/each}
				</div>
			{:else}
				<p class="text-sm text-muted-foreground">
					No records in the archive yet. You can add one on the
					<a href="/submit" class="underline">submit page</a>.
				</p>
			{/if}
		</div>
	</details>

	<!-- The thread: question → summary → records, oldest first -->
	{#each visibleTurns as turn, t (t)}
		{@const isLatest = t === visibleTurns.length - 1}
		<article
			id="turn-{t}"
			class="scroll-mt-6 space-y-4 {isLatest && padLatestTurn ? FILL_SCREEN : ''}"
		> 
			<h2 class="text-lg font-medium">{turn.question}</h2>

			<SearchSummary summary={turn.summary} provider={turn.provider} anchorPrefix="t{t}-result-" />

			<!-- Records: open for the newest turn, collapsed for older ones -->
			<details open={isLatest} class="group space-y-3">
				<summary class="cursor-pointer text-sm font-medium text-muted-foreground select-none">
					{turn.results.length} record{turn.results.length === 1 ? '' : 's'} found
				</summary>
				<div class="mt-3 grid grid-cols-1 gap-3 md:grid-cols-3">
					{#each turn.results as result, i (result.id)}
						<ResultsCard {result} number={i + 1} anchorId="t{t}-result-{i + 1}" />
					{/each}
				</div>
			</details>
		</article>
	{/each}

	<!-- Placeholder while waiting (Ollama can take several seconds) -->
	{#if pending}
		<article
			id="turn-pending"
			class="scroll-mt-6 space-y-4 {pending.mode === 'followup' ? FILL_SCREEN : ''}"
			aria-live="polite"
		>
			<h2 class="text-lg font-medium">{pending.question}</h2>
			<div class="space-y-2 rounded-xl border p-6">
				<div class="h-4 w-3/4 animate-pulse rounded bg-muted"></div>
				<div class="h-4 w-full animate-pulse rounded bg-muted"></div>
				<div class="h-4 w-2/3 animate-pulse rounded bg-muted"></div>
				<p class="pt-2 text-sm text-muted-foreground">Searching the records and writing a summary…</p>
			</div>
		</article>
	{/if}

	<!-- Follow-up: only once there is something to follow up on. Sticky so it stays in reach. -->
	{#if turns.length > 0}
		<!-- Fades the content out above the bar so it reads as "pinned", not as more page.
		     Fades to the page's cream (bg-[#FBF7F2] in +layout.svelte), not white -->
		<form
			method="POST"
			action="?/search"
			class="sticky bottom-0 bg-linear-to-t from-[#FBF7F2] from-80% to-transparent pt-6 pb-4"
			use:enhance={submitTo('followup')}
		>
			<input type="hidden" name="history" value={historyJson} />
			<!-- Slim pill, same width as the search box at the top. The label is for screen readers. -->
			<div class="mx-auto max-w-2xl space-y-2">
				<MagicBorder active={pending?.mode === 'followup'} rounded="rounded-full">
					<SearchBox
						variant="pill"
						placeholder="Ask a follow-up…"
						label="Follow-up question — uses the answers above as context"
						bind:value={followUp}
						bind:ref={followUpInput}
						disabled={!!pending}
					/>
				</MagicBorder>
				{@render errors('followup')}
			</div>
		</form>
	{:else}
		<div class="pb-12"></div>
	{/if}
</main>

<style>
	/* While a saved thread is being restored after a refresh (see hideRecentsScript) */
	:global(html[data-saved-thread]) .recents {
		display: none;
	}
</style>
