import { SEARCH_API_URL, SEARCH_API_KEY } from '$app/env/private';
import { fail } from '@sveltejs/kit';
import { type SearchResponse, type ThreadTurn } from '#lib/search.js';
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

		if (!SEARCH_API_URL || !SEARCH_API_KEY) {
			return fail(500, { question, message: 'Search is not configured (SEARCH_API_URL / SEARCH_API_KEY).' });
		}

		// 2. Call the search API — the key stays on the server
		let response: Response;
		try {
			response = await fetch(`${SEARCH_API_URL}/api/search`, {
				method: 'POST',
				headers: { 'Content-Type': 'application/json', 'X-API-Key': SEARCH_API_KEY },
				body: JSON.stringify({ question, history, filters, summary }),
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
		const turn: ThreadTurn = { question, filters, ...result };
		return turn;
	}
};

import { getResourceModel } from '#lib/server/resources.js';

// Landing state: recent approved records so the page has content before the
// first search. A database failure must not take the whole page down — an
// empty list just means the browse section falls back to the "no records" note.
export const load: PageServerLoad = async () => {
	try {
		const Resource = await getResourceModel();
		const docs = await Resource.find(
			{ status: 'approved' },
			{
				title: 1,
				description: 1,
				summary: 1,
				attribution: 1,
				link: 1,
				sitelink: 1,
				resourceformat: 1,
				contentcategory: 1,
				createdAt: 1
			}
		)
			.sort({ createdAt: -1 })
			.limit(12)
			.lean();
		return {
			defaultRecords: docs.map((doc) => ({
				id: String(doc._id),
				title: doc.title ?? undefined,
				description: doc.description ?? undefined,
				summary: doc.summary ?? undefined,
				attribution: doc.attribution ?? undefined,
				link: doc.link,
				sitelink: doc.sitelink ?? undefined,
				resourceformat: doc.resourceformat,
				contentcategory: doc.contentcategory ?? undefined,
				createdAt: doc.createdAt.toISOString()
			}))
		};
	} catch (error) {
		console.error('Could not load default records:', error);
		return { defaultRecords: [] };
	}
};
