// Types for search-server/search-api responses (POST /api/search).
// Shared by the search on the home page (routes/+page.*) and the components in #lib/components/search/.

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
	attribution?: string;
	link?: string;
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
	facets?: Facets; // missing from older search-api versions
}

// One question + its answer in the follow-up thread (what the action returns)
export interface ThreadTurn extends SearchResponse {
	question: string;
	filters?: Filters; // the filters this answer was searched with (missing in older saved threads)
}

// Earlier turn sent back to the API as context. Same limits as Turn in search-api/main.py.
export interface HistoryTurn {
	question: string;
	summary: string | null;
}

export const MAX_HISTORY = 3;
export const MAX_SUMMARY_CHARS = 2000;
