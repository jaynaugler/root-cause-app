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
import type { Actions, PageServerLoad } from './$types';

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

import { getResourceModel } from '#lib/server/resources.js';

const WALL_PAGE_SIZE = 12;
const wallSortSchema = z.enum(['newest', 'oldest', 'title']);

function wallFilter(url: URL, key: string): string {
	const value = url.searchParams.get(key)?.trim() ?? '';
	return value.length <= 200 ? value : '';
}

// MongoDB-backed card wall. Search actions never use these filters or sorting.
export const load: PageServerLoad = async ({ url }) => {
	const filters = {
		resourceformat: wallFilter(url, 'resourceformat'),
		contentcategory: wallFilter(url, 'contentcategory'),
		attribution: wallFilter(url, 'attribution')
	};
	const parsedSort = wallSortSchema.safeParse(url.searchParams.get('sort'));
	const sort = parsedSort.success ? parsedSort.data : 'newest';
	const requestedPage = Number.parseInt(url.searchParams.get('page') ?? '1', 10);
	let page = Number.isInteger(requestedPage) && requestedPage > 0 ? requestedPage : 1;
	const emptyWall = {
		page: 1,
		pageCount: 1,
		total: 0,
		sort,
		filters,
		options: { resourceformat: [], contentcategory: [], attribution: [] }
	};

	try {
		const Resource = await getResourceModel();
		const query: Record<string, unknown> = { status: 'approved' };
		if (filters.resourceformat) query.resourceformat = filters.resourceformat;
		if (filters.contentcategory) {
			query.contentcategory = filters.contentcategory === 'uncategorized' ? null : filters.contentcategory;
		}
		if (filters.attribution) query.attribution = filters.attribution;

		const [total, resourceformat, contentcategory, attribution] = await Promise.all([
			Resource.countDocuments(query),
			Resource.distinct('resourceformat', { status: 'approved' }),
			Resource.distinct('contentcategory', { status: 'approved' }),
			Resource.distinct('attribution', { status: 'approved' })
		]);
		const pageCount = Math.max(1, Math.ceil(total / WALL_PAGE_SIZE));
		page = Math.min(page, pageCount);
		const order: Record<string, 1 | -1> = sort === 'oldest' ? { createdAt: 1, _id: 1 } : sort === 'title' ? { title: 1, _id: 1 } : { createdAt: -1, _id: -1 };
		const docs = await Resource.find(
			query,
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
			.sort(order)
			.skip((page - 1) * WALL_PAGE_SIZE)
			.limit(WALL_PAGE_SIZE)
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
			})),
			wall: {
				page,
				pageCount,
				total,
				sort,
				filters,
				options: {
					resourceformat: resourceformat.filter(Boolean).sort(),
					contentcategory: [...new Set(contentcategory.map((value) => value || 'uncategorized'))].sort(),
					attribution: attribution.filter(Boolean).sort()
				}
			}
		};
	} catch (error) {
		console.error('Could not load default records:', error);
		return { defaultRecords: [], wall: emptyWall };
	}
};
