// Loads the options of one filter panel from POST /facets/[field] (routes/facets/[facet]).
// One FacetOptionsLoader per open panel. Its fields are $state, so the panel re-renders when
// they change. (A .svelte.ts file may use runes like $state outside a component.)
//
// - Only the newest request counts: a new one cancels the one still running (AbortController),
//   and an answer that arrives anyway for an older request is thrown away.
// - First pages are cached, so a panel that opens again shows its list at once while the
//   fresh one loads.
import type {
	FacetField,
	FacetOption,
	FacetOptionsResponse,
	PanelSearch
} from '#lib/search.js';

// What the panel itself decides: the text typed in its search field, the order, the page size
export interface PanelQuery {
	search: string;
	sort: 'count' | 'alpha';
	limit: number;
}

// First pages, shared by all panels, for as long as the tab is open. The key holds everything
// the counts depend on, so an entry for another question or other filters is simply never hit
// again. Cleared when it gets big. Only the browser fills it: panels load when they're opened.
const cache = new Map<string, FacetOptionsResponse>();
const CACHE_MAX = 50;

export class FacetOptionsLoader {
	options = $state<FacetOption[]>([]); // in the server's order: count or A–Z
	selected = $state<FacetOption[]>([]); // the field's checked values, with counts
	totalOptions = $state(0); // options on all pages
	nextCursor = $state<string | null>(null); // null = everything is loaded
	loading = $state(false);
	failed = $state(false);
	loaded = $state(false); // a list is on screen (from the cache or the server)

	#field: FacetField;
	#controller: AbortController | null = null;
	#body: object = {}; // the request behind the list on screen, for loadMore()

	constructor(field: FacetField) {
		this.#field = field;
	}

	// A new list: the first page for this search and panel state. Replaces what is shown.
	async load(search: PanelSearch, query: PanelQuery) {
		// The counts ignore this field's own checked values (search-api counts every field
		// without its own filter), so they're left out of the key: checking a box here doesn't
		// make the cached list outdated.
		const others = Object.fromEntries(
			Object.entries(search.filters).filter(([field]) => field !== this.#field)
		);
		const key = JSON.stringify([this.#field, search.question, search.history, others, query]);
		const cached = cache.get(key);
		if (cached) this.#show(cached, false);

		this.#body = { ...search, ...query };
		const data = await this.#fetch({ ...this.#body, cursor: null });
		if (!data) return;
		this.#show(data, false);
		if (cache.size >= CACHE_MAX) cache.clear();
		cache.set(key, data);
	}

	// The next page of the same list, added at the end (infinite scroll)
	async loadMore() {
		if (!this.nextCursor || this.loading) return;
		const data = await this.#fetch({ ...this.#body, cursor: this.nextCursor });
		if (data) this.#show(data, true);
	}

	// The panel closed: stop waiting
	abort() {
		this.#controller?.abort();
	}

	#show(data: FacetOptionsResponse, append: boolean) {
		this.options = append ? [...this.options, ...data.options] : data.options;
		// `selected` is kept from the first page: it decides which rows sit in the pinned
		// "Selected" section, and rows must not move there while the user scrolls and clicks.
		// It's renewed with the next new list (panel opened again, other search text).
		if (!append) this.selected = data.selected;
		this.totalOptions = data.total_options;
		this.nextCursor = data.next_cursor;
		this.loaded = true;
	}

	// One request. Returns null when it failed, or when a newer request replaced it.
	async #fetch(body: object): Promise<FacetOptionsResponse | null> {
		this.#controller?.abort(); // cancel the request still running, if any
		const controller = new AbortController();
		this.#controller = controller;
		this.loading = true;
		this.failed = false;
		try {
			const response = await fetch(`/facets/${this.#field}`, {
				method: 'POST',
				headers: { 'Content-Type': 'application/json' },
				body: JSON.stringify(body),
				signal: controller.signal
			});
			if (!response.ok) throw new Error(`status ${response.status}`);
			const data = (await response.json()) as FacetOptionsResponse;
			// The answer can arrive just as a newer request starts: then it's outdated
			return controller === this.#controller ? data : null;
		} catch (error) {
			if (!controller.signal.aborted) {
				console.warn(`Could not load the ${this.#field} options:`, error);
				this.failed = true;
			}
			return null;
		} finally {
			if (controller === this.#controller) this.loading = false;
		}
	}
}
