// Types for search-server/search-api responses (POST /api/search).
// Shared by the /search route and the components in #lib/components/search/.

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
}

// One question + its answer in the follow-up thread (what the action returns)
export interface ThreadTurn extends SearchResponse {
	question: string;
}

// Earlier turn sent back to the API as context. Same limits as Turn in search-api/main.py.
export interface HistoryTurn {
	question: string;
	summary: string | null;
}

// Longest question the search API accepts (max_length in search-server/search-api/main.py).
// Mirrored in the zod schema in routes/+page.server.ts.
export const MAX_QUESTION_CHARS = 500;
export const MAX_HISTORY = 3;
export const MAX_SUMMARY_CHARS = 2000;
