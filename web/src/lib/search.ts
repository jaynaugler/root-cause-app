// Types and helpers for search-server/search-api (POST /api/search, POST /api/facets).
// Shared by the search on the home page (routes/+page.*), the filter panels' route
// (routes/facets/[facet]) and the components in #lib/components/search/.

// Fields the search can be filtered by (the checkboxes). Same list as FacetField in search-api/main.py.
export const FACET_FIELDS = ['contentcategory', 'attribution', 'resourceformat'] as const;
export type FacetField = (typeof FACET_FIELDS)[number];

// Checked values per field, e.g. { contentcategory: ['people', 'events'] }
export type Filters = Partial<Record<FacetField, string[]>>;

// How many matching records have each value, e.g. { contentcategory: { people: 12, history: 7 } }.
// Values with 0 matches are left out by Meilisearch.
export type Facets = Partial<Record<FacetField, Record<string, number>>>;

// One record (a Meilisearch hit). Fields can be missing or null on some records.
export interface SearchResult {
	id: string;
	title?: string;
	description?: string;
	summary?: string;
	attribution?: string;
	link?: string;
	sitelink?: string;
	resourceformat?: string; // e.g. "pdf", "website"
	contentcategory?: string; // e.g. "history"
	imgurl?: string | null;
	createdAt?: string;
	_rankingScore?: number; // 0–1, how well it matches the question
}

export interface SearchResponse {
	summary: string | null; // null when nothing was found or the model failed
	provider: 'ollama' | 'gemini' | null;
	results: SearchResult[];
	// How many records match the question and the filters (results holds only the best few).
	// Exact up to 1000. Missing from older search-api versions.
	total?: number;
	facets?: Facets; // missing from older search-api versions
}

// The newest records without a question (POST /api/browse): the "Recent records" list
export interface BrowseResponse {
	results: SearchResult[]; // newest first
	total: number; // records passing the filters (all records without filters)
	facets?: Facets;
}
export const RECENT_LIMIT = 12; // records per page in the "Recent records" list
export const SEARCH_LIMIT = 8; // records per page in a search answer

// One question + its answer in the follow-up thread (what the action returns)
export interface ThreadTurn extends SearchResponse {
	question: string;
	filters?: Filters; // the filters this answer was searched with (missing in older saved threads)
	offset?: number; // zero-based record offset for this page
	// true after a filter click: the records changed, the summary was written for the old ones
	summaryStale?: boolean;
}

// Earlier turn sent back to the API as context. Same limits as Turn in search-api/main.py.
export interface HistoryTurn {
	question: string;
	summary: string | null;
}

// Longest question the search API accepts (max_length in search-server/search-api/main.py).
// Mirrored in the zod schema in #lib/server/search-params.ts.
export const MAX_QUESTION_CHARS = 500;
export const MAX_HISTORY = 3;
export const MAX_SUMMARY_CHARS = 2000;

// ---- Filter panels (the pills under the latest answer) ----

// One pill per field, in this order. (Date comes later: records don't have a year yet.)
export interface FacetConfig {
	field: FacetField;
	label: string; // the pill's name: "Category"
	plural: string; // for "Search categories", "Show all categories, A–Z"
	panelWidth: number; // px; the panel is never wider than the screen minus 32px
	// Search field in the panel. false = only when the field has more than SEARCH_FROM options.
	searchable: boolean;
	// A short list (Format): every option at once, no "Most records" section, no A–Z link
	plain: boolean;
	// Checked values in their own "Selected (n)" section on top (Source: a long list, where a
	// checked value could otherwise be far down or hidden by the search text). false = they
	// stay checked in their normal place (Category).
	pinSelected: boolean;
}
export const FACETS: FacetConfig[] = [
	{ field: 'contentcategory', label: 'Category', plural: 'categories', panelWidth: 380, searchable: true, plain: false, pinSelected: false },
	{ field: 'resourceformat', label: 'Format', plural: 'formats', panelWidth: 380, searchable: false, plain: true, pinSelected: false },
	{ field: 'attribution', label: 'Source', plural: 'sources', panelWidth: 400, searchable: true, plain: false, pinSelected: true }
];
export const SEARCH_DELAY = 200; // ms of no typing before the panel's search runs
export const SEARCH_FROM = 9; // a non-searchable panel gets a search field from 9 options
export const FIRST_PAGE = 8; // options in a panel when it opens ("Most records")
export const ALPHA_PAGE = 50; // options per page in the A–Z list

export function facetConfig(field: FacetField): FacetConfig {
	return FACETS.find((facet) => facet.field === field)!;
}

// How a stored value is shown: people → People, pdf → PDF. Sources are names: shown as stored.
// One label per format in RESOURCE_FORMATS (#lib/server/resource-schema.ts; not imported here,
// because that file is server-only). A new format without a label shows capitalized.
const FORMAT_LABELS: Record<string, string> = {
	pdf: 'PDF',
	book: 'Books',
	video: 'Videos',
	article: 'Articles',
	podcast: 'Podcasts'
};

export function valueLabel(field: FacetField, value: string): string {
	if (field === 'attribution') return value;
	if (field === 'resourceformat' && FORMAT_LABELS[value]) return FORMAT_LABELS[value];
	return value.charAt(0).toUpperCase() + value.slice(1);
}

// The pill's text. Nothing checked: "Category". One: "Category: People". Several: the names in
// the order they were checked if they stay under PILL_NAMES_MAX characters ("People,
// Publications"), otherwise the first one and "+N" ("Black Cultural Centre for Nova Scotia +1").
export const PILL_NAMES_MAX = 28;

export interface PillLabel {
	full: string; // everything, never shortened: the tooltip and what screen readers say
	names: string; // after "Category: "; the pill may cut it with an ellipsis ("…")
	more: number; // shown as "+N" after the names, never cut off. 0 = none.
}

export function pillLabel(field: FacetField, selected: string[]): PillLabel {
	const { label } = facetConfig(field);
	const labels = selected.map((value) => valueLabel(field, value));
	const all = labels.join(', ');
	const full = labels.length ? `${label}: ${all}` : label;
	if (labels.length <= 1 || all.length < PILL_NAMES_MAX) return { full, names: all, more: 0 };
	return { full, names: labels[0], more: labels.length - 1 };
}

// "Clear all filters (N)" and the status line count fields with a filter, not checked values
export function activeFacetCount(filters: Filters): number {
	return FACET_FIELDS.filter((field) => (filters[field]?.length ?? 0) > 0).length;
}

// Text for matching, without case and accents: "Université" → "universite". Same as fold() in
// search-api/main.py: NFKD splits "é" into "e" + an accent mark (\p{M}), which is then dropped.
// (Python's casefold() also turns "ß" into "ss"; toLowerCase() doesn't. Rare enough to ignore.)
export function fold(text: string): string {
	return text.normalize('NFKD').replace(/\p{M}/gu, '').toLowerCase();
}

// Splits a label into pieces, marking the ones that match the panel's search text, so the panel
// can highlight them: highlightParts("Université Sainte-Anne", "univ") →
// [{ text: "Univ", match: true }, { text: "ersité Sainte-Anne", match: false }]
export function highlightParts(label: string, search: string): { text: string; match: boolean }[] {
	const needle = fold(search.trim());
	if (!needle) return [{ text: label, match: false }];

	// Fold each character on its own, and remember for each folded letter which character it
	// came from. A match found in the folded text can then be mapped back to the label.
	const chars = Array.from(label);
	let folded = '';
	const from: number[] = []; // from[i] = position in `chars` of folded[i]
	chars.forEach((char, i) => {
		const f = fold(char);
		folded += f;
		for (let k = 0; k < f.length; k++) from.push(i);
	});

	const parts: { text: string; match: boolean }[] = [];
	let done = 0; // characters of `chars` already in `parts`
	for (let at = folded.indexOf(needle); at !== -1; at = folded.indexOf(needle, at + needle.length)) {
		const start = Math.max(from[at], done);
		const end = from[at + needle.length - 1] + 1;
		if (start > done) parts.push({ text: chars.slice(done, start).join(''), match: false });
		if (end > start) parts.push({ text: chars.slice(start, end).join(''), match: true });
		done = Math.max(done, end);
	}
	if (done < chars.length) parts.push({ text: chars.slice(done).join(''), match: false });
	return parts;
}

// One value in a filter panel (POST /facets/[field], from search-api's /api/facets)
export interface FacetOption {
	value: string; // as stored, e.g. "people"; valueLabel() makes it readable
	count: number; // matching records if this value were checked (0 = shown disabled)
}

export interface FacetOptionsResponse {
	options: FacetOption[]; // one page, already sorted and matched against `search`
	selected: FacetOption[]; // the field's checked values, whatever `search` says
	total_options: number; // values matching `search`, on all pages
	next_cursor: string | null; // send back as `cursor` for the next page; null = last page
}

// What the page sends to POST /facets/[field]: the latest answer's search, plus the panel's state
export interface FacetOptionsRequest {
	question: string;
	history: HistoryTurn[];
	filters: Filters;
	search?: string;
	sort?: 'count' | 'alpha';
	limit?: number;
	cursor?: string | null;
}

// The search a panel counts against: the newest answer's question, the turns before it as
// context, and its filters. The same as what produced the records on the page, so the counts
// in a panel agree with them.
export type PanelSearch = Pick<FacetOptionsRequest, 'question' | 'history' | 'filters'>;
