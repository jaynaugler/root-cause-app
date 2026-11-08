// POST /browse: the newest records narrowed by filters, for the "Recent records" list before
// the first question. The page loads the list without filters itself (load in
// routes/+page.server.ts); this route answers when a filter changes. Like routes/facets, it
// only passes the request on to search-api, so the API key stays on the server.
// Not under /api: that path belongs to the Python api/ service.
import { error, json } from '@sveltejs/kit';
import { RECENT_LIMIT } from '#lib/search.js';
import { browseArchive } from '#lib/server/search-api.js';
import { browseRequestSchema } from '#lib/server/search-params.js';
import type { RequestHandler } from './$types';

export const POST: RequestHandler = async ({ request, fetch }) => {
	let body: unknown;
	try {
		body = await request.json();
	} catch {
		error(400, 'The request body must be JSON.');
	}
	const parsed = browseRequestSchema.safeParse(body);
	if (!parsed.success) error(400, 'Invalid browse request.');

	try {
		// request.signal: when the page cancels (a newer filter change), stop waiting too
		const { results, total } = await browseArchive(
			fetch,
			parsed.data.filters,
			RECENT_LIMIT,
			AbortSignal.any([request.signal, AbortSignal.timeout(10_000)])
		);
		return json({ results, total });
	} catch (err) {
		// The browser stopped waiting: nobody reads this answer, and it's not an error to log
		if (request.signal.aborted) return new Response(null, { status: 499 });
		console.error('Could not browse the archive:', err);
		error(502, 'Could not load the records. Try again later.');
	}
};
