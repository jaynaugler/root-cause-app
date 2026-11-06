// Prod fallback for the same-origin /api/* path used in dev by Vite's server.proxy
// (web/vite.config.ts). In dev, Vite intercepts /api before SvelteKit sees it; in
// production, this catch-all handler forwards /api/* to the Python API.
import { PUBLIC_API_BASE_URL } from '$app/env/public';

import type { RequestHandler } from './$types';

// Hop-by-hop / app-local headers that must not be forwarded upstream.
const SKIP_REQUEST_HEADERS = new Set([
	'host',
	'cookie',
	'connection',
	'keep-alive',
	'transfer-encoding',
	'upgrade',
	'content-length'
]);

const SKIP_RESPONSE_HEADERS = new Set([
	'connection',
	'keep-alive',
	'transfer-encoding',
	'content-encoding',
	'content-length'
]);

const proxy: RequestHandler = async ({ request, url }) => {
	if (!PUBLIC_API_BASE_URL) {
		return new Response(
			'/api proxy target is not configured — set PUBLIC_API_BASE_URL (e.g. your Render API URL)',
			{ status: 500 }
		);
	}

	// The FastAPI router serves under the /api prefix itself, so the path is
	// forwarded as-is: https://<render-app>.onrender.com/api/items
	let target: URL;
	try {
		target = new URL(url.pathname + url.search, PUBLIC_API_BASE_URL);
	} catch {
		return new Response(
			`PUBLIC_API_BASE_URL is not a valid URL: ${JSON.stringify(PUBLIC_API_BASE_URL)}`,
			{ status: 500 }
		);
	}

	const headers = new Headers();
	for (const [name, value] of request.headers) {
		if (!SKIP_REQUEST_HEADERS.has(name.toLowerCase())) {
			headers.set(name, value);
		}
	}

	const body = ['GET', 'HEAD'].includes(request.method) ? undefined : request.body;

	let upstream: Response;
	try {
		upstream = await fetch(target, {
			method: request.method,
			headers,
			body,
			duplex: 'half'
		} as RequestInit);
	} catch (err) {
		// Upstream unreachable (e.g. Render free-tier cold start failing, DNS) —
		// report a 502 with context instead of SvelteKit's generic 500.
		console.error('API proxy fetch failed:', err);
		return new Response('API proxy failed to reach the upstream service', { status: 502 });
	}

	// Pass status, body, and headers through — the browser sees the API's response as-is.
	const responseHeaders = new Headers();
	for (const [name, value] of upstream.headers) {
		if (!SKIP_RESPONSE_HEADERS.has(name.toLowerCase())) {
			responseHeaders.set(name, value);
		}
	}

	return new Response(upstream.body, {
		status: upstream.status,
		headers: responseHeaders
	});
};

export const GET: RequestHandler = proxy;
export const POST: RequestHandler = proxy;
export const PUT: RequestHandler = proxy;
export const PATCH: RequestHandler = proxy;
export const DELETE: RequestHandler = proxy;
