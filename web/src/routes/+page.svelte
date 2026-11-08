<script lang="ts">
	import { applyAction, deserialize, enhance, type SubmitFunction } from '$app/forms';
	import { onMount, tick } from 'svelte';
	import SearchSummary from '#lib/components/search/SearchSummary.svelte';
	import ResultsCard from '#lib/components/resultsCard/ResultsCard.svelte';
	import MagicBorder from '#lib/components/search/MagicBorder.svelte';
	import SearchBox from '#lib/components/search/SearchBox.svelte';
	import FilterBar from '#lib/components/search/FilterBar.svelte';
	import FacetPanel from '#lib/components/search/FacetPanel.svelte';
	import Pagination from '#lib/components/search/Pagination.svelte';
	import { Button } from '#lib/components/ui/button/index.js';
	import {
		FACET_FIELDS,
		MAX_HISTORY,
		RECENT_LIMIT,
		SEARCH_LIMIT,
		activeFacetCount,
		type BrowseResponse,
		type FacetField,
		type Filters,
		type HistoryTurn,
		type PanelSearch,
		type ThreadTurn
	} from '#lib/search.js';

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
		// Refreshed in the middle of a filter change: the summary still needs rewriting
		if (thread.at(-1)?.summaryStale) scheduleSummary(refineId);
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

	// ---- Filters (the bar under the search box) ----
	// The filters in use are the ones the latest answer was searched with. They are also sent
	// with new questions and follow-ups (hidden fields in both forms), so they stay active.
	// A filter change re-runs the latest question in two steps:
	//   1. FILTER_DELAY after the last change, WITHOUT the AI summary: new records, counts and
	//      total in a few milliseconds. Quick clicks in a row make one search, not one each.
	//   2. once the clicking has stopped for SUMMARY_DELAY: once more WITH the summary
	// Every change (and every new search) cancels whatever is still running for the previous
	// one (AbortController) and bumps refineId; an answer that arrives anyway for an older id is
	// ignored, so a slow old answer can never overwrite a newer one.
	const FILTER_DELAY = 300; // ms
	const SUMMARY_DELAY = 1000; // ms
	const activeFilters = $derived<Filters>(thread.at(-1)?.filters ?? {});
	const activeOffset = $derived(thread.at(-1)?.offset ?? 0);
	let refining = $state(false); // a filter changed; its records haven't arrived yet
	let summaryUpdating = $state(false); // the new summary is being written
	let refineError = $state('');
	// Set once a filter update has fully arrived, shown in the newest summary's subtitle
	// ("… · updated for 2 filters") and read out by screen readers. null = nothing to say.
	let refineStatus = $state<{ shown: string; spoken: string } | null>(null);
	let refineId = 0;
	let filterTimer: ReturnType<typeof setTimeout> | undefined;
	let summaryTimer: ReturnType<typeof setTimeout> | undefined;
	let refineController: AbortController | null = null; // the request running for the latest change
	// The filters the records on screen were searched with: restored if an update fails
	let lastGoodFilters: Filters = {};

	const plural = (n: number, word: string) => `${n} ${word}${n === 1 ? '' : 's'}`;

	// Change only the newest turn of the thread
	function replaceLatest(changes: Partial<ThreadTurn>) {
		thread = [...thread.slice(0, -1), { ...thread[thread.length - 1], ...changes }];
	}

	// Context for re-running the latest question = the turns BEFORE it (the latest is the one
	// being re-run). Used by askLatest() and the filter panels, so their counts match the records.
	function historyBefore(turns: ThreadTurn[]): HistoryTurn[] {
		return turns
			.slice(0, -1)
			.slice(-MAX_HISTORY)
			.map(({ question, summary }) => ({ question, summary }));
	}

	// Call the search action from code instead of a form submit (what use:enhance does inside).
	// Returns the new turn, or null if the search failed or was cancelled through `signal`.
	async function askLatest(
		filters: Filters,
		withSummary: boolean,
		signal: AbortSignal,
		offset = 0
	): Promise<ThreadTurn | null> {
		const body = new FormData();
		body.set('question', thread[thread.length - 1].question);
		body.set('history', JSON.stringify(historyBefore(thread)));
		body.set('offset', String(offset));
		for (const field of FACET_FIELDS) {
			for (const value of filters[field] ?? []) body.append(field, value);
		}
		if (!withSummary) body.set('summary', 'off');
		try {
			const response = await fetch('?/search', {
				method: 'POST',
				body,
				headers: { 'x-sveltekit-action': 'true' },
				signal
			});
			const result = deserialize(await response.text());
			return result.type === 'success' ? (result.data as unknown as ThreadTurn) : null;
		} catch {
			return null; // network error, or cancelled by a newer change
		}
	}

	// Stop everything still running or waiting for the previous change: the timers, and the
	// request in flight (its fetch() rejects, askLatest returns null, and the refineId check
	// then ignores it). Returns the new id.
	function cancelRefine(): number {
		clearTimeout(filterTimer);
		clearTimeout(summaryTimer);
		refineController?.abort();
		refineController = null;
		return ++refineId;
	}

	// A new request for the latest change, cancelled by the next cancelRefine()
	function newSignal(): AbortSignal {
		refineController = new AbortController();
		return refineController.signal;
	}

	// The status once an update has fully arrived. No filters left = nothing to say.
	function setStatus(withAnswer: boolean) {
		const n = activeFacetCount(activeFilters);
		const filters = plural(n, 'filter');
		refineStatus = n
			? {
					shown: withAnswer ? `updated for ${filters}` : `records updated for ${filters}`,
					spoken: `${plural(latestTotal, 'record')}. ${withAnswer ? 'Answer and records' : 'Records'} updated for ${filters}.`
				}
			: null;
	}

	// Step 1: the pills change at once; the records are fetched FILTER_DELAY after the last change
	function applyFilters(filters: Filters) {
		// First change of a burst of clicks: remember what the records on screen were searched with
		if (!refining) lastGoodFilters = activeFilters;
		const id = cancelRefine();
		summaryUpdating = false;
		refineError = '';
		refineStatus = null; // hidden until this change has arrived
		replaceLatest({ filters }); // the pill changes colour immediately
		refining = true;
		filterTimer = setTimeout(() => fetchRecords(id, filters), FILTER_DELAY);
	}

	async function fetchRecords(id: number, filters: Filters, offset = 0, notify = true) {
		const answer = await askLatest(filters, false, newSignal(), offset);
		if (id !== refineId) return; // a newer change or a new search took over
		refining = false;

		if (!answer) {
			replaceLatest({ filters: lastGoodFilters }); // undo, the records didn't change
			refineError = 'Could not apply the filter. Try again.';
		} else if (!answer.results.length) {
			// Nothing matches: nothing to summarise either
			replaceLatest({ results: [], total: 0, offset: answer.offset, facets: answer.facets, summary: null, provider: null, summaryStale: false });
			if (notify) setStatus(false);
		} else {
			// The old summary stays visible but is marked stale: its [1], [2] meant other records
			replaceLatest({ results: answer.results, total: answer.total, offset: answer.offset, facets: answer.facets, summaryStale: true });
			scheduleSummary(id, notify);
		}
	}

	function changeSearchPage(page: number) {
		lastGoodFilters = activeFilters;
		const id = cancelRefine();
		summaryUpdating = false;
		refineError = '';
		refineStatus = null;
		refining = true;
		fetchRecords(id, activeFilters, (page - 1) * SEARCH_LIMIT, false);
		scrollToTop(`turn-${thread.length - 1}`);
	}

	// Step 2: rewrite the summary once the clicking has stopped
	function scheduleSummary(id: number, notify = true) {
		clearTimeout(summaryTimer);
		summaryUpdating = true;
		summaryTimer = setTimeout(async () => {
			const answer = await askLatest(activeFilters, true, newSignal(), activeOffset);
			if (id !== refineId) return;
			summaryUpdating = false;
			// Take the whole answer: records and summary come from the same search, so [n] match.
			// If it failed, show "no summary" rather than one about other records.
			replaceLatest(
				answer
					? { ...answer, summaryStale: false }
					: { summary: null, provider: null, summaryStale: false }
			);
			if (notify) setStatus(!!answer?.summary);
		}, SUMMARY_DELAY);
	}

	// A new question or follow-up: stop any filter update still running for the old answer
	function stopRefining() {
		cancelRefine();
		refining = false;
		summaryUpdating = false;
		refineError = '';
		refineStatus = null;
	}

	// ---- Browsing: filters before the first question ----
	// Until there is an answer, the filter bar narrows the "Recent records" list instead. Those
	// filters live here (browseFilters); the first question takes them along (hidden fields),
	// and from then on they live on the thread like above. Same rhythm as a filter change on
	// an answer: the pills change at once, the list FILTER_DELAY after the last change, and a
	// newer change cancels the request still running.
	let browseFilters = $state<Filters>({});
	// The list after a filter change; null = still the one the page was loaded with (data.recent)
	let browseResult = $state<BrowseResponse | null>(null);
	let browseOffset = $state(0);
	let browseLoading = $state(false);
	let browseError = $state('');
	let browseStatus = $state(''); // read out by screen readers once the list has changed
	let browseTimer: ReturnType<typeof setTimeout> | undefined;
	let browseController: AbortController | null = null;
	let lastGoodBrowseFilters: Filters = {};

	const recent = $derived(
		browseResult ? { ...browseResult, failed: false } : data.recent
	);
	const browseFiltered = $derived(activeFacetCount(browseFilters) > 0);

	function applyBrowseFilters(filters: Filters) {
		if (!browseLoading) lastGoodBrowseFilters = browseFilters; // first change of a burst
		clearTimeout(browseTimer);
		browseController?.abort();
		browseFilters = filters;
		browseError = '';
		browseStatus = '';
		browseLoading = true;
		browseTimer = setTimeout(() => fetchBrowse(filters, 0), FILTER_DELAY);
	}

	async function fetchBrowse(filters: Filters, offset: number) {
		const controller = new AbortController();
		browseController = controller;
		browseLoading = true;
		browseError = '';
		try {
			const response = await fetch('/browse', {
				method: 'POST',
				headers: { 'Content-Type': 'application/json' },
				body: JSON.stringify({ filters, offset }),
				signal: controller.signal
			});
			if (!response.ok) throw new Error(`status ${response.status}`);
			const result = (await response.json()) as BrowseResponse;
			if (controller !== browseController) return; // a newer change took over
			browseResult = result;
			browseOffset = offset;
			const n = activeFacetCount(filters);
			browseStatus = n
				? `${plural(result.total, 'record')} match ${plural(n, 'filter')}.`
				: `${plural(result.total, 'record')} in the archive.`;
		} catch {
			if (controller.signal.aborted) return; // cancelled by a newer change
			browseFilters = lastGoodBrowseFilters; // undo, the list didn't change
			browseError = 'Could not apply the filter. Try again.';
		} finally {
			if (controller === browseController) browseLoading = false;
		}
	}

	function changeBrowsePage(page: number) {
		fetchBrowse(browseFilters, (page - 1) * RECENT_LIMIT);
		scrollToTop('recent-records');
	}

	// ---- Changes from the filter bar: to the newest answer, or (no answer yet) to the list ----
	const currentFilters = $derived(thread.length ? activeFilters : browseFilters);

	function changeFilters(filters: Filters) {
		if (thread.length) applyFilters(filters);
		else applyBrowseFilters(filters);
	}

	function toggleFilter(field: FacetField, value: string) {
		const current = currentFilters[field] ?? [];
		const values = current.includes(value)
			? current.filter((v) => v !== value)
			: [...current, value];
		const next: Filters = { ...currentFilters, [field]: values };
		if (!values.length) delete next[field];
		changeFilters(next);
	}

	// A panel's "Clear": uncheck every value of one field, keep the others
	function clearFacet(field: FacetField) {
		const next: Filters = { ...currentFilters };
		delete next[field];
		changeFilters(next);
	}

	// What the filter panels count against (see PanelSearch): the newest answer's search, or
	// no question at all while browsing (search-api then counts the whole archive)
	const panelSearch = $derived<PanelSearch>(
		thread.length
			? { question: thread[thread.length - 1].question, history: historyBefore(thread), filters: activeFilters }
			: { question: '', history: [], filters: browseFilters }
	);
	// The number for "Show N records". Older saved threads have no total: then the number of
	// records shown is the best we know.
	const latestTotal = $derived(
		thread.length ? (thread.at(-1)?.total ?? thread.at(-1)?.results.length ?? 0) : recent.total
	);

	// One submit handler for both forms; `mode` decides whether the answer replaces or extends the thread
	// Scroll an element to the top of the screen (scroll-mt-6 on the target leaves a small gap)
	function scrollToTop(id: string) {
		document.getElementById(id)?.scrollIntoView({ behavior: 'smooth', block: 'start' });
	}

	// "Reset search": start over, as on a fresh visit. The filters go too: otherwise the pills
	// would jump back to whatever was set before the first question.
	function resetSearch() {
		if (pending) return;
		stopRefining(); // a filter update still running for the answer
		clearTimeout(browseTimer); // a browse update still waiting or running
		browseController?.abort();
		browseLoading = false;
		browseError = '';
		browseStatus = '';
		browseFilters = {};
		browseResult = null; // back to the list the page was loaded with
		browseOffset = 0;
		thread = [];
		form = null;
		newQuestion = '';
		followUp = '';
		recentsOpen = true;
		tick().then(() => window.scrollTo({ top: 0, behavior: 'smooth' }));
	}

	function submitTo(mode: Mode): SubmitFunction {
		return ({ formData }) => {
			stopRefining();
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

<!-- The active filters as hidden fields, so new questions and follow-ups use them too -->
{#snippet filterInputs()}
	{#each FACET_FIELDS as field (field)}
		{#each currentFilters[field] ?? [] as value (value)}
			<input type="hidden" name={field} {value} />
		{/each}
	{/each}
{/snippet}

<!-- Inside of a filter panel (FilterBar shows it when a pill is clicked) -->
{#snippet filterPanel(field: FacetField, close: () => void)}
	<FacetPanel
		{field}
		search={panelSearch}
		total={latestTotal}
		onToggle={toggleFilter}
		onClear={clearFacet}
		{close}
	/>
{/snippet}

{#snippet errors(mode: Mode)}
	{#if errorFor === mode && form?.errors?.question}
		<p class="text-sm font-medium text-red-500">{form.errors.question[0]}</p>
	{/if}
	{#if errorFor === mode && form?.message}
		<p class="text-sm font-medium text-red-500">{form.message}</p>
	{/if}
{/snippet}

<main class="container mx-auto max-w-6xl px-4 pt-12 space-y-8">
	<!-- Title + search box, as wide as the answers below -->
	<header class="space-y-4">
		<div class="flex items-center justify-between gap-4">
			<h1 class="text-2xl font-semibold">Search the archive</h1>
			{#if turns.length || newQuestion || followUp || form || browseFiltered}
				<Button type="button" variant="outline" size="sm" onclick={resetSearch} disabled={!!pending}>
					Reset search
				</Button>
			{/if}
		</div>

		<!-- New search: starts a fresh thread -->
		<form method="POST" action="?/search" class="w-full space-y-2" use:enhance={submitTo('new')}>
			{@render filterInputs()}
			<MagicBorder active={pending?.mode === 'new'} rounded="rounded-2xl">
				<SearchBox bind:value={newQuestion} disabled={!!pending} />
			</MagicBorder>
			{@render errors('new')}
		</form>

		<!-- The filter bar, right under the search box. Before the first question it narrows
		     "Recent records"; once there is an answer, its filters are the newest answer's: a
		     change re-runs the newest question (also a follow-up further down). New questions
		     use the filters too. Outside the <form>, so its buttons and checkboxes never submit it. -->
		<FilterBar
			filters={currentFilters}
			disabled={!!pending}
			onClearAll={() => changeFilters({})}
			panel={filterPanel}
		/>
		{#if refineError || browseError}
			<p class="text-sm font-medium text-red-500">{refineError || browseError}</p>
		{/if}
	</header>

	<!-- Browse list: the newest records (from search-api /api/browse, see +page.server.ts).
	     Open on a fresh visit; collapses on search, then it's a toggle. -->
	<details id="recent-records" bind:open={recentsOpen} class="recents space-y-3">
		<summary class="cursor-pointer text-sm font-medium text-muted-foreground select-none">
			Recent records
			{#if recent.total > recent.results.length}
				<span class="font-normal">
					· {recent.results.length} shown of {recent.total}{browseFiltered ? ' matching' : ''}
				</span>
			{:else if browseFiltered && recent.total}
				<span class="font-normal">· {recent.total} matching</span>
			{/if}
		</summary>
		<Pagination
			page={Math.floor(browseOffset / RECENT_LIMIT) + 1}
			total={recent.total}
			pageSize={RECENT_LIMIT}
			loading={browseLoading}
			label="Recent record pages"
			onPage={changeBrowsePage}
		/>
		<!-- Read out by screen readers once the list has changed after a filter change -->
		<p role="status" class="sr-only">{browseStatus}</p>
		<!-- While the list is being narrowed: dimmed, and marked busy for screen readers -->
		<div
			class="mt-3 space-y-3 transition-opacity {browseLoading ? 'opacity-60' : ''}"
			aria-busy={browseLoading}
		>
			{#if recent.results.length}
				<div class="grid grid-cols-1 gap-3 md:grid-cols-3">
					{#each recent.results as record, i (record.id)}
						<ResultsCard result={record} number={i + 1} anchorId={'recent-' + i} />
					{/each}
				</div>
				{:else if recent.failed}
				<p class="text-sm text-muted-foreground">
					Could not load the recent records. Searching may still work; try reloading the page
					later.
				</p>
			{:else if browseFiltered}
				<p class="text-sm text-muted-foreground">
					No records match these filters.
					<button type="button" class="underline" onclick={() => changeFilters({})}>
						Clear all filters
					</button>
				</p>
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
		{@const found = turn.total ?? turn.results.length}
		<!-- aria-busy: tells screen readers this part is being updated (after a filter change) -->
		<article
			id="turn-{t}"
			class="scroll-mt-6 space-y-4 {isLatest && padLatestTurn ? FILL_SCREEN : ''}"
			aria-busy={isLatest && refining}
		>
			<h2 class="text-lg font-medium">{turn.question}</h2>

			<SearchSummary
				summary={turn.summary}
				provider={turn.provider}
				anchorPrefix="t{t}-result-"
				stale={turn.summaryStale}
				updating={isLatest && summaryUpdating}
				status={isLatest ? refineStatus : null}
			/>

			<!-- Records: open for the newest turn, collapsed for older ones -->
			<details
				open={isLatest}
				class="group space-y-3 transition-opacity {isLatest && refining ? 'opacity-60' : ''}"
			>
				<summary class="cursor-pointer text-sm font-medium text-muted-foreground select-none">
					{#if found > turn.results.length}
						{turn.results.length} shown of {plural(found, 'record')}
					{:else}
						{plural(turn.results.length, 'record')} found
					{/if}
				</summary>
				{#if isLatest}
					<Pagination
						page={Math.floor((turn.offset ?? 0) / SEARCH_LIMIT) + 1}
						total={found}
						pageSize={SEARCH_LIMIT}
						loading={refining}
						label="Search result pages"
						onPage={changeSearchPage}
					/>
				{/if}
				<div class="mt-3 grid grid-cols-1 gap-3">
					{#each turn.results as result, i (result.id)}
						<ResultsCard {result} number={i + 1} anchorId="t{t}-result-{i + 1}" searchMode />
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
			{#if pending.mode === 'followup'}
				<h2 class="text-lg font-medium">{pending.question}</h2>
			{/if}
			<div class="space-y-2 rounded-xl border bg-white p-6">
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
			{@render filterInputs()}
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
