<script lang="ts">
	// The inside of one filter panel, top to bottom:
	//   search field (Category, Source; Format only with more than 8 options)
	//   "Selected (n)" (Source only: the checked values, pinned on top)
	//   the list: "Most records" / "All …, A–Z" / "Matching “text” (n)"
	//   footer: "Clear (n)" and "Show N records"
	// Shows FilterBar's `panel` snippet; the page decides what a click does.
	//
	// The list loads when the panel opens (it is created then), when the search text changes
	// and when the user switches to A–Z, NOT after every click: the counts ignore this field's
	// own checked values, so a click here can't change them. That's also why rows never jump
	// while you click: a row moves between "Selected" and the list only with the next new list.
	import SearchIcon from '@lucide/svelte/icons/search';
	import XIcon from '@lucide/svelte/icons/x';
	import { onMount } from 'svelte';
	import type { Attachment } from 'svelte/attachments';
	import { FacetOptionsLoader } from './facet-options.svelte.js';
	import {
		ALPHA_PAGE,
		FIRST_PAGE,
		SEARCH_DELAY,
		SEARCH_FROM,
		facetConfig,
		highlightParts,
		valueLabel,
		type FacetField,
		type FacetOption,
		type PanelSearch
	} from '#lib/search.js';

	let {
		field,
		search,
		total,
		onToggle,
		onClear,
		close
	}: {
		field: FacetField;
		search: PanelSearch; // the newest answer's question, context and filters
		total: number; // records matching right now, for "Show N records"
		onToggle: (field: FacetField, value: string) => void;
		onClear: (field: FacetField) => void; // uncheck everything in this field
		close: () => void;
	} = $props();

	// A panel is always created for one field and never switches, so reading `field` once is fine
	// svelte-ignore state_referenced_locally
	const loader = new FacetOptionsLoader(field);
	const facet = $derived(facetConfig(field));
	const checked = $derived(search.filters[field] ?? []);

	// 'count' = "Most records" (the first FIRST_PAGE), 'alpha' = every value A–Z, page by page
	let sort = $state<'count' | 'alpha'>('count');
	let typed = $state(''); // what is in the search field right now
	let searched = $state(''); // the text the list on screen was searched with (after the delay)
	// Format gets a search field only once it turns out to be long (and keeps it then)
	let longList = $state(false);
	const showSearch = $derived(facet.searchable || longList);

	async function load() {
		const limit = facet.plain || sort === 'alpha' || searched ? ALPHA_PAGE : FIRST_PAGE;
		await loader.load(search, { search: searched, sort, limit });
		if (!searched && loader.totalOptions >= SEARCH_FROM) longList = true;
	}

	let searchTimer: ReturnType<typeof setTimeout> | undefined;

	onMount(() => {
		load();
		return () => {
			// The panel closed: cancel a request still running, and a search still waiting
			clearTimeout(searchTimer);
			loader.abort();
		};
	});

	function showAll() {
		sort = 'alpha';
		focusTarget = 'option'; // the link disappears: focus the first option of the new list
		load();
	}

	// ---- The search field ----
	// Typing waits SEARCH_DELAY ms, so "univ" makes one request, not four. The server does the
	// matching (case and accents don't matter). Results are ordered by count; empty = the
	// normal list again.
	function runSearch() {
		clearTimeout(searchTimer);
		const text = typed.trim();
		if (text === searched) return;
		searched = text;
		sort = 'count';
		load();
	}

	function onSearchInput() {
		clearTimeout(searchTimer);
		searchTimer = setTimeout(runSearch, SEARCH_DELAY);
	}

	function onSearchKeydown(event: KeyboardEvent) {
		if (event.key === 'ArrowDown') {
			event.preventDefault(); // don't move the text cursor
			focusFirstOption();
		} else if (event.key === 'Enter') {
			runSearch(); // no need to wait
		}
	}

	function clearSearch() {
		typed = '';
		runSearch();
		searchInput?.focus();
	}

	// ---- What the list shows ----
	// "Selected" (Source only): the checked values when this list was loaded. A value checked
	// or unchecked since then stays where it is until the next new list.
	const pinned = $derived(facet.pinSelected ? loader.selected : []);
	const listed = $derived.by(() => {
		const inPinned = new Set(pinned.map((option) => option.value));
		return loader.options.filter((option) => !inPinned.has(option.value));
	});
	const heading = $derived(
		searched
			? `Matching “${searched}” (${loader.totalOptions})`
			: sort === 'count'
				? 'Most records'
				: `All ${facet.plural}, A–Z`
	);
	// Long lists load page by page while scrolling: A–Z, search results, a plain list
	const pageByPage = $derived(sort === 'alpha' || !!searched || facet.plain);

	// ---- Focus ----
	// FilterBar leaves the focus alone when the panel opens. We move it to the search field,
	// or (no search field) to the first option as soon as there is one: the list may still be
	// loading at that moment.
	let list = $state<HTMLElement | null>(null);
	let searchInput = $state<HTMLInputElement | null>(null);
	// svelte-ignore state_referenced_locally
	let focusTarget: 'search' | 'option' | null = facet.searchable ? 'search' : 'option';

	function focusFirstOption() {
		const first = list?.querySelector<HTMLInputElement>('input[type=checkbox]:not(:disabled)');
		first?.focus();
		return !!first;
	}

	$effect(() => {
		void loader.options; // run again whenever the list changes
		if (focusTarget === 'search' && searchInput) {
			searchInput.focus();
			focusTarget = null;
		} else if (focusTarget === 'option' && focusFirstOption()) {
			focusTarget = null;
		}
	});

	function clear() {
		onClear(field);
		// The Clear button becomes disabled and would drop the focus; keep it in the list
		focusFirstOption();
	}

	// ---- Infinite scroll ----
	// An "attachment" ({@attach ...}) runs code when an element appears and cleans up when it
	// goes. This one loads the next page when the empty marker at the end of the list scrolls
	// into view (80px early). The marker is only there while more pages exist and nothing is
	// loading, so each new page brings a new marker, which checks again.
	function whenVisible(callback: () => void): Attachment<HTMLElement> {
		return (node) => {
			const observer = new IntersectionObserver(
				(entries) => {
					if (entries.some((entry) => entry.isIntersecting)) callback();
				},
				{ root: list, rootMargin: '0px 0px 80px 0px' }
			);
			observer.observe(node);
			return () => observer.disconnect();
		};
	}

	const plural = (n: number, word: string) => `${n} ${word}${n === 1 ? '' : 's'}`;
</script>

{#snippet sectionLabel(text: string)}
	<p class="px-4 pt-2 pb-1 text-xs font-semibold tracking-[0.06em] text-ink-muted uppercase">
		{text}
	</p>
{/snippet}

{#snippet option(item: FacetOption)}
	{@const isChecked = checked.includes(item.value)}
	{@const label = valueLabel(field, item.value)}
	<!-- A real checkbox inside a <label>: clicking the text toggles it, Space toggles it.
	     0 matches: disabled (a real `disabled`, not just grey), unless it's checked, so it can
	     always be unchecked. The count is part of the name screen readers say. -->
	<label
		class="flex min-h-10 cursor-pointer items-center gap-3 px-4 py-2 text-sm hover:bg-panel-footer has-[:disabled]:cursor-not-allowed has-[:disabled]:opacity-50"
	>
		<input
			type="checkbox"
			class="size-4 shrink-0 accent-filter-active-border"
			checked={isChecked}
			disabled={item.count === 0 && !isChecked}
			aria-label="{label}, {plural(item.count, 'result')}"
			onchange={() => onToggle(field, item.value)}
		/>
		<!-- The letters matching the search text are marked. One line on purpose: line breaks
		     between the pieces would show up as spaces inside the name. -->
		<span class="min-w-0 flex-1 truncate" title={label}
			>{#each highlightParts(label, searched) as part, i (i)}{#if part.match}<mark class="rounded-sm bg-filter-active font-semibold text-inherit">{part.text}</mark>{:else}{part.text}{/if}{/each}</span
		>
		<span class="shrink-0 text-[13px] text-ink-muted tabular-nums" aria-hidden="true">
			{item.count}
		</span>
	</label>
{/snippet}

{#if showSearch}
	<div class="relative m-3">
		<SearchIcon
			class="pointer-events-none absolute top-1/2 left-3 size-4 -translate-y-1/2 text-ink-muted"
			aria-hidden="true"
		/>
		<!-- type="text", not "search": in a search field Esc clears the text, but here Esc
		     closes the panel -->
		<input
			bind:this={searchInput}
			bind:value={typed}
			type="text"
			enterkeyhint="search"
			autocomplete="off"
			spellcheck="false"
			aria-label="Search {facet.plural}"
			placeholder="Search {facet.plural}"
			oninput={onSearchInput}
			onkeydown={onSearchKeydown}
			class="h-10 w-full rounded-[10px] border border-field-border bg-white px-9 text-sm text-ink placeholder:text-ink-muted focus-visible:outline-2 focus-visible:outline-offset-0 focus-visible:outline-ink"
		/>
		{#if typed}
			<button
				type="button"
				aria-label="Clear the search"
				onclick={clearSearch}
				class="absolute top-1/2 right-1.5 flex size-7 -translate-y-1/2 items-center justify-center rounded-md text-ink-muted hover:text-ink"
			>
				<XIcon class="size-4" aria-hidden="true" />
			</button>
		{/if}
	</div>
{/if}

<!-- While a new list loads, the old one stays visible, dimmed -->
<div
	bind:this={list}
	class="max-h-80 overflow-y-auto py-1 transition-opacity {loader.loading && loader.loaded
		? 'opacity-60'
		: ''} {showSearch ? 'border-t' : ''}"
>
	{#if !loader.loaded}
		<p class="px-4 py-3 text-sm text-ink-muted">
			{loader.failed ? 'Could not load the options. Close and open the panel to try again.' : 'Loading…'}
		</p>
	{:else}
		{#if pinned.length}
			{@render sectionLabel(`Selected (${pinned.length})`)}
			{#each pinned as item (item.value)}
				{@render option(item)}
			{/each}
		{/if}

		{#if !facet.plain || searched}
			{@render sectionLabel(heading)}
		{/if}

		{#each listed as item (item.value)}
			{@render option(item)}
		{:else}
			{@const other = pinned.length ? 'other ' : ''}
			<p class="px-4 py-3 text-sm text-ink-muted">
				{searched
					? `No ${other}${facet.plural} match “${searched}”.`
					: other
						? `No other ${facet.plural}.`
						: `No ${facet.plural} for this search.`}
			</p>
		{/each}

		<!-- "Most records" shows only the first few: offer the rest, A–Z -->
		{#if !facet.plain && !searched && sort === 'count' && loader.nextCursor}
			<button
				type="button"
				onclick={showAll}
				class="mx-4 my-2 text-sm font-medium text-ink underline underline-offset-4 hover:text-filter-active-border"
			>
				Show all {facet.plural}, A–Z
			</button>
		{/if}

		{#if pageByPage && loader.nextCursor}
			{#if loader.loading}
				<p class="px-4 py-2 text-sm text-ink-muted">Loading more…</p>
			{:else}
				<div class="h-px" {@attach whenVisible(() => loader.loadMore())}></div>
			{/if}
		{/if}
	{/if}
</div>

<!-- Footer. "Show N records" only closes the panel: the filters are already applied. -->
<div class="flex items-center justify-between gap-3 border-t bg-panel-footer p-3">
	<button
		type="button"
		disabled={!checked.length}
		onclick={clear}
		class="text-sm font-medium text-ink underline underline-offset-4 disabled:cursor-not-allowed disabled:text-ink-muted disabled:no-underline"
	>
		Clear{checked.length ? ` (${checked.length})` : ''}
	</button>
	<button
		type="button"
		onclick={close}
		class="rounded-lg bg-ink px-4 py-2 text-sm font-medium text-white hover:bg-ink/85"
	>
		Show {plural(total, 'record')}
	</button>
</div>
