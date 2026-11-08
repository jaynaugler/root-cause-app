import { SEARCH_API_URL, SEARCH_API_KEY } from '$app/env/private';
import { fail } from '@sveltejs/kit';
import { z } from 'zod';
import { RECENT_LIMIT, type SearchResponse, type SearchResult, type ThreadTurn } from '#lib/search.js';
import { browseArchive } from '#lib/server/search-api.js';
// The question / history / filter checks are shared with the filter panels' route
import { parseFilters, parseHistory, searchSchema } from '#lib/server/search-params.js';
import type { Actions, PageServerLoad } from './$types';

export const actions: Actions = {
	search: async ({ request, fetch }) => {
		const data = await request.formData();
		const rawQuestion = data.get('question')?.toString() ?? '';

		// 1. Validate
		const parsed = searchSchema.safeParse({ question: rawQuestion });
		if (!parsed.success) {
			return fail(400, {
				question: rawQuestion,
				errors: parsed.error.flatten().fieldErrors
			});
		}
		const { question } = parsed.data;
		const history = parseHistory(data.get('history'));
		const filters = parseFilters(data);
		// summary=off: records and counts only (a filter click). Anything else: with AI summary.
		const summary = data.get('summary') !== 'off';
		const parsedOffset = z.coerce.number().int().nonnegative().safeParse(data.get('offset') ?? 0);
		const offset = parsedOffset.success ? parsedOffset.data : 0;

		if (!SEARCH_API_URL || !SEARCH_API_KEY) {
			return fail(500, { question, message: 'Search is not configured (SEARCH_API_URL / SEARCH_API_KEY).' });
		}

		// 2. Call the search API — the key stays on the server
		let response: Response;
		try {
			response = await fetch(`${SEARCH_API_URL}/api/search`, {
				method: 'POST',
				headers: { 'Content-Type': 'application/json', 'X-API-Key': SEARCH_API_KEY },
				body: JSON.stringify({ question, history, filters, summary, offset }),
				// Summaries from Ollama can take a while
				signal: AbortSignal.timeout(90_000)
			});
		} catch (error) {
			console.error('Search API unreachable:', error);
			return fail(502, { question, message: 'Search service is unreachable. Try again later.' });
		}

		if (!response.ok) {
			console.error('Search API error:', response.status, await response.text());
			return fail(502, { question, message: `Search failed (status ${response.status}).` });
		}

		// 3. Return to the page (available as the `form` prop)
		// The answer includes `facets` (the counts for the checkboxes)
		const result = (await response.json()) as SearchResponse;
		const turn: ThreadTurn = { question, filters, offset, ...result };
		return turn;
	}
};

// Landing state: the newest records, so the page has content before the first question.
// They come from search-api (/api/browse), the same index the search and the filter counts
// use, so the list and the counts always agree (MongoDB could hold records that aren't
// indexed yet). A failure must not take the whole page down: the list then says it couldn't
// load. 5 seconds at most, so a slow search server can't hold up the page for long.
export const load: PageServerLoad = async ({ fetch }) => {
	try {
		const { results, total } = await browseArchive(fetch, {}, RECENT_LIMIT, 0, AbortSignal.timeout(5_000));
		return { recent: { results, total, failed: false } };
	} catch (error) {
		console.error('Could not load the recent records:', error);
		return { recent: { results: [] as SearchResult[], total: 0, failed: true } };
	}
};
