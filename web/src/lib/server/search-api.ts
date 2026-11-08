// Calling search-server/search-api from the web app's server side. The API key stays here:
// the browser never talks to search-api itself.
import { SEARCH_API_URL, SEARCH_API_KEY } from '$app/env/private';
import type { BrowseResponse, Filters } from '#lib/search.js';

// POST a JSON body to a search-api path, e.g. postSearchApi(fetch, '/api/browse', {...}).
// Pass SvelteKit's `fetch` (from load or a request handler). Throws when search-api isn't
// configured or can't be reached; a non-2xx answer is returned for the caller to check.
export async function postSearchApi(
	fetch: typeof globalThis.fetch,
	path: string,
	body: unknown,
	signal?: AbortSignal
): Promise<Response> {
	if (!SEARCH_API_URL || !SEARCH_API_KEY) {
		throw new Error('Search is not configured (SEARCH_API_URL / SEARCH_API_KEY).');
	}
	return fetch(`${SEARCH_API_URL}${path}`, {
		method: 'POST',
		headers: { 'Content-Type': 'application/json', 'X-API-Key': SEARCH_API_KEY },
		body: JSON.stringify(body),
		signal
	});
}

// The newest records without a question (search-api /api/browse), narrowed by `filters`
export async function browseArchive(
	fetch: typeof globalThis.fetch,
	filters: Filters,
	limit: number,
	signal?: AbortSignal
): Promise<BrowseResponse> {
	const response = await postSearchApi(fetch, '/api/browse', { filters, limit }, signal);
	if (!response.ok) {
		throw new Error(`search-api /api/browse answered ${response.status}: ${await response.text()}`);
	}
	return (await response.json()) as BrowseResponse;
}
