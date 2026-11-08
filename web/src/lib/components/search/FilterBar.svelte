<script lang="ts">
	// The filter bar under the latest answer: one pill per field (Category, Format, Source) and
	// "Clear all filters (N)". A pill opens a panel (a popover) under it; only one is open at a
	// time. This component only does the pills and the opening/closing. What a panel shows comes
	// from the page, as the `panel` snippet, and the page decides what a change does.
	import ChevronDownIcon from '@lucide/svelte/icons/chevron-down';
	import type { Snippet } from 'svelte';
	import * as Popover from '#lib/components/ui/popover/index.js';
	import {
		FACETS,
		activeFacetCount,
		facetConfig,
		pillLabel,
		type FacetField,
		type Filters
	} from '#lib/search.js';

	let {
		filters,
		disabled = false,
		onClearAll,
		panel
	}: {
		filters: Filters; // checked values, e.g. { contentcategory: ['people'] }
		disabled?: boolean; // while a new question is running
		onClearAll: () => void;
		// The inside of a panel: gets the field, and a function that closes the panel
		// (for the footer's "Show N records" button)
		panel: Snippet<[FacetField, () => void]>;
	} = $props();

	// Which panel is open. One variable for all pills, so opening one closes the others.
	let openFacet = $state<FacetField | null>(null);
	// The panel starts at the pill's left edge, unless it would stick out on the right
	let align = $state<'start' | 'end'>('start');
	// The pill buttons, to measure them and to move the focus to them. Each starts as null, not
	// missing: the trigger's `ref` has a fallback (null), and Svelte refuses bind:ref={undefined}.
	let pills = $state(
		Object.fromEntries(FACETS.map((facet) => [facet.field, null])) as Record<
			FacetField,
			HTMLElement | null
		>
	);

	const active = $derived(activeFacetCount(filters));

	// The panel's width: its own, but never wider than the screen minus 16px on each side
	function panelWidth(field: FacetField) {
		return Math.min(facetConfig(field).panelWidth, window.innerWidth - 32);
	}

	// Called by the popover when it wants to open (click, Enter, Space on the pill) or close
	// (Esc, a click outside, a second click on the pill), and by the panel's close button.
	function setOpen(field: FacetField, open: boolean) {
		if (open) {
			const left = pills[field]?.getBoundingClientRect().left ?? 0;
			align = left + panelWidth(field) > window.innerWidth - 16 ? 'end' : 'start';
			openFacet = field;
		} else if (openFacet === field) {
			// Clicking pill B while A is open: A reports "close" and B "open", in either order.
			// Only close what is still open, so A's late "close" can't close B again.
			openFacet = null;
		}
	}

	function clearAll() {
		onClearAll();
		// The link disappears with the filters; put the focus somewhere sensible
		pills[FACETS[0].field]?.focus();
	}
</script>

<div class="flex flex-wrap items-center gap-2.5" role="group" aria-label="Filter the records">
	{#each FACETS as facet (facet.field)}
		{@const label = pillLabel(facet.field, filters[facet.field] ?? [])}
		{@const isActive = label.names !== ''}
		<Popover.Root
			open={openFacet === facet.field}
			onOpenChange={(open) => setOpen(facet.field, open)}
		>
			<!-- The pill. bits-ui adds aria-haspopup="dialog", aria-expanded and
			     data-state="open"/"closed". aria-label + title: the full text, because the
			     visible one can be cut off. -->
			<Popover.Trigger
				bind:ref={pills[facet.field]}
				{disabled}
				aria-label={label.full}
				title={label.full}
				class="inline-flex h-9 max-w-80 items-center gap-1.5 rounded-full border px-3 text-sm font-medium transition-colors focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-ink disabled:opacity-50 data-[state=open]:shadow-[0_0_0_1px_var(--ink)] {isActive
					? 'border-filter-active-border bg-filter-active text-filter-active-text'
					: 'border-pill-border bg-white text-ink hover:bg-panel-footer'}"
			>
				<span class="min-w-0 truncate">{facet.label}{#if isActive}: {label.names}{/if}</span>
				{#if label.more}<span class="shrink-0">+{label.more}</span>{/if}
				<ChevronDownIcon class="size-3.5 shrink-0" aria-hidden="true" />
			</Popover.Trigger>

			<!-- The panel. Not modal: no focus trap, the page stays usable.
			     No portal: it stays right after its pill in the page, so Tab goes from the
			     panel's last control on to the next pill.
			     onOpenAutoFocus: bits-ui would focus the first button it finds, but the list may
			     still be loading; the panel moves the focus itself once its options are there.
			     Closing returns the focus to the pill (bits-ui does that). -->
			<Popover.Content
				role="dialog"
				aria-label="{facet.label} filter"
				portalProps={{ disabled: true }}
				trapFocus={false}
				onOpenAutoFocus={(event) => event.preventDefault()}
				side="bottom"
				{align}
				sideOffset={8}
				collisionPadding={16}
				style="width: min({facet.panelWidth}px, calc(100vw - 32px))"
				class="gap-0 overflow-hidden rounded-xl p-0 text-ink motion-reduce:animate-none"
			>
				{@render panel(facet.field, () => setOpen(facet.field, false))}
			</Popover.Content>
		</Popover.Root>
	{/each}

	{#if active > 0}
		<button
			type="button"
			{disabled}
			onclick={clearAll}
			class="h-9 px-1 text-sm font-medium text-ink underline underline-offset-4 hover:text-filter-active-border disabled:opacity-50"
		>
			Clear all filters ({active})
		</button>
	{/if}
</div>
