import { SEARCH_API_URL, SEARCH_API_KEY } from '$app/env/private';
import { fail } from '@sveltejs/kit';
import { z } from 'zod';
import {
	MAX_HISTORY,
	MAX_SUMMARY_CHARS,
	type HistoryTurn,
	type SearchResponse,
	type ThreadTurn
} from '#lib/search.js';
import type { Actions } from './$types';

// Same limits as SearchRequest in search-api/main.py
const searchSchema = z.object({
	question: z
		.string()
		.trim()
		.min(1, { message: 'Type a question.' })
		.max(500, { message: 'Question cannot exceed 500 characters.' })
});

// Earlier turns sent by the follow-up form (hidden field, JSON). Same limits as Turn in main.py.
const historySchema = z
	.array(
		z.object({
			question: z.string().trim().min(1).max(500),
			summary: z
				.string()
				.nullable()
				.transform((s) => s?.slice(0, MAX_SUMMARY_CHARS) ?? null)
		})
	)
	.transform((turns) => turns.slice(-MAX_HISTORY));

// Missing or malformed history → no context (a plain new search), never an error
function parseHistory(raw: FormDataEntryValue | null): HistoryTurn[] {
	if (typeof raw !== 'string' || !raw) return [];
	try {
		const parsed = historySchema.safeParse(JSON.parse(raw));
		return parsed.success ? parsed.data : [];
	} catch {
		return [];
	}
}

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

		if (!SEARCH_API_URL || !SEARCH_API_KEY) {
			return fail(500, { question, message: 'Search is not configured (SEARCH_API_URL / SEARCH_API_KEY).' });
		}

		// 2. Call the search API — the key stays on the server
		let response: Response;
		try {
			response = await fetch(`${SEARCH_API_URL}/api/search`, {
				method: 'POST',
				headers: { 'Content-Type': 'application/json', 'X-API-Key': SEARCH_API_KEY },
				body: JSON.stringify({ question, history }),
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
		const result = (await response.json()) as SearchResponse;
		const turn: ThreadTurn = { question, ...result };
		return turn;
	}
};
