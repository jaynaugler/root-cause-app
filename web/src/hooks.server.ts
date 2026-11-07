// src/hooks.server.ts
// Runs on EVERY request before any page, form action or +server.ts endpoint,
// like an Express middleware. Its job: cookie → session → user → event.locals.user.
// Kit 3: hook types live in '@sveltejs/kit/hooks' (Kit 2 had them in '@sveltejs/kit').
import type { Handle } from '@sveltejs/kit/hooks';
import {
	SESSION_COOKIE,
	deleteSessionCookie,
	setSessionCookie,
	validateSession
} from '#lib/server/sessions.js';
import { requireAdmin } from '#lib/server/guards.js';

// '/admin' and everything below it, but not e.g. '/administrator'.
function isAdminPath(pathname: string): boolean {
	return pathname === '/admin' || pathname.startsWith('/admin/');
}

export const handle: Handle = async ({ event, resolve }) => {
	const token = event.cookies.get(SESSION_COOKIE);

	if (!token) {
		event.locals.user = null;
	} else {
		const result = await validateSession(token);
		if (result) {
			event.locals.user = result.user;
			// Re-send the cookie so its browser-side expiry matches the (maybe extended) session.
			setSessionCookie(event.cookies, token, result.expiresAt);
		} else {
			// Invalid or expired token: remove the useless cookie.
			event.locals.user = null;
			deleteSessionCookie(event.cookies);
		}
	}

	// Guard the whole /admin area here, not in a +layout.server.ts: a layout load
	// does NOT run for form actions or +server.ts endpoints, the hook runs for all.
	// requireAdmin throws a redirect (→ /login) or a 403, and SvelteKit turns that
	// into the response, so resolve() below is never reached.
	if (isAdminPath(event.url.pathname)) requireAdmin(event);

	// resolve() = "continue to the page/action", like next() in Express.
	return resolve(event);
};
