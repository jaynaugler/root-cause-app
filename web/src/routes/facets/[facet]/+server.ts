// POST /facets/contentcategory (or /facets/attribution, /facets/resourceformat): the options of
// one filter panel, with counts. The browser can't call search-api itself, because the API key
// must stay on the server, so this route passes the request on, the same way the search action
// in routes/+page.server.ts does.
// Not under /api: that path belongs to the Python api/ service (Vite proxy in dev,
// routes/api/[...path] in production).
// A +server.ts file is a plain endpoint (like an Express route): it answers with data, not a page.
import { SEARCH_API_URL, SEARCH_API_KEY } from '$app/env/private';
import { error, json } from '@sveltejs/kit';
import { FACET_FIELDS, type FacetOptionsResponse } from '#lib/search.js';
import { facetsRequestSchema } from '#lib/server/search-params.js';
import type { RequestHandler } from './$types';

export const POST: RequestHandler = async ({ params, request, fetch }) => {
	// 1. Which panel: the [facet] part of the URL
	const facet = FACET_FIELDS.find((field) => field === params.facet);
	if (!facet) error(404, 'Unknown filter.');

	// 2. Validate the body (see facetsRequestSchema)
	let body: unknown;
	try {
		body = await request.json();
	} catch {
		error(400, 'The request body must be JSON.');
	}
	const parsed = facetsRequestSchema.safeParse(body);
	if (!parsed.success) error(400, 'Invalid filter request.');

	if (!SEARCH_API_URL || !SEARCH_API_KEY) {
		error(500, 'Search is not configured (SEARCH_API_URL / SEARCH_API_KEY).');
	}

	// 3. Ask search-api. request.signal is passed on: when the panel cancels its request (a
	//    newer one replaced it), the call to search-api is cancelled too, where the server
	//    supports it. Counting is fast, so give up after 10 seconds.
	let response: Response;
	try {
		response = await fetch(`${SEARCH_API_URL}/api/facets`, {
			method: 'POST',
			headers: { 'Content-Type': 'application/json', 'X-API-Key': SEARCH_API_KEY },
			body: JSON.stringify({ ...parsed.data, facet }),
			signal: AbortSignal.any([request.signal, AbortSignal.timeout(10_000)])
		});
	} catch (err) {
		// The browser stopped waiting: nobody reads this answer, and it's not an error to log.
		// (499 = "client closed request", as nginx calls it.)
		if (request.signal.aborted) return new Response(null, { status: 499 });
		console.error('Search API unreachable:', err);
		error(502, 'Search service is unreachable. Try again later.');
	}

	if (!response.ok) {
		console.error('Search API error (facets):', response.status, await response.text());
		error(502, `Could not load the filter options (status ${response.status}).`);
	}

	// 4. Pass the answer on as it is
	return json((await response.json()) as FacetOptionsResponse);
};
