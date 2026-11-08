import { SEARCH_API_KEY, SEARCH_API_URL } from '$app/env/private';
import type { RequestHandler } from './$types';

export const GET: RequestHandler = async ({ fetch }) => {
	if (!SEARCH_API_URL || !SEARCH_API_KEY) {
		return Response.json(
			{
				status: 'unavailable',
				providers: {},
				error: 'Search AI health is not configured (SEARCH_API_URL / SEARCH_API_KEY).'
			},
			{ status: 503 }
		);
	}

	let response: Response;
	try {
		response = await fetch(`${SEARCH_API_URL}/health/ai`, {
			headers: { 'X-API-Key': SEARCH_API_KEY, Accept: 'application/json' },
			cache: 'no-store',
			signal: AbortSignal.timeout(25_000)
		});
	} catch (error) {
		console.error('Search AI health check proxy failed:', error);
		const timedOut = error instanceof DOMException && error.name === 'TimeoutError';
		return Response.json(
			{
				status: 'unavailable',
				providers: {},
				error: timedOut
					? 'The search AI health check timed out. Check that the search service and its tunnel are running.'
					: 'Could not connect to the search AI service. Check SEARCH_API_URL and that the search service is running.'
			},
			{ status: 503 }
		);
	}

	if (response.status === 404) {
		return Response.json(
			{
				status: 'unavailable',
				providers: {},
				error:
					'The search service does not have the /health/ai endpoint yet (HTTP 404). Rebuild and redeploy search-server/search-api, then refresh.'
			},
			{ status: 503, headers: { 'Cache-Control': 'no-store' } }
		);
	}

	if (response.status === 401 || response.status === 403) {
		return Response.json(
			{
				status: 'unavailable',
				providers: {},
				error: `The search service rejected its health-check credentials (HTTP ${response.status}). Verify SEARCH_API_KEY matches the search service API_KEY.`
			},
			{ status: 503, headers: { 'Cache-Control': 'no-store' } }
		);
	}

	let payload: unknown;
	try {
		payload = await response.json();
	} catch {
		return Response.json(
			{
				status: 'unavailable',
				providers: {},
				error: `The search service returned a non-JSON health response (HTTP ${response.status}).`
			},
			{ status: 502, headers: { 'Cache-Control': 'no-store' } }
		);
	}

	if (!response.ok) {
		return Response.json(
			{
				status: 'unavailable',
				providers: {},
				error: `The search service health check failed (HTTP ${response.status}).`
			},
			{ status: 503, headers: { 'Cache-Control': 'no-store' } }
		);
	}

	return Response.json(payload, {
		status: response.status,
		headers: { 'Cache-Control': 'no-store' }
	});
};
