// src/lib/server/guards.ts
// Access checks for load functions, form actions and +server.ts endpoints.
// Call one at the TOP of the function: if the check fails it throws, and nothing
// after it runs. If it passes you get the user back, already typed as non-null.
//
//   const user = requireUser(event);   // any logged-in user
//   const admin = requireAdmin(event); // admins only
//
// Everything under /admin is also checked in hooks.server.ts, so admin pages
// can't be forgotten. Use these for single actions elsewhere (e.g. a delete
// button on /resources) and for "must be logged in" pages.
import { error, redirect } from '@sveltejs/kit';
import type { SessionUser } from './sessions.js';

// The only part of the request event the guards need. Every load, action,
// endpoint and the hook gets an event with `locals`, so they can all pass it.
type HasLocals = { locals: App.Locals };

// Not logged in → send them to /login (303: the browser follows it with a GET).
export function requireUser(event: HasLocals): SessionUser {
	const user = event.locals.user;
	if (!user) redirect(303, '/login');
	return user;
}

// For +server.ts endpoints called with fetch(): a redirect would make fetch silently
// follow it and get the /login page's HTML back. 401 Unauthorized tells the caller
// clearly "you're not logged in" (SvelteKit sends it as JSON: { message }).
export function requireUserApi(event: HasLocals): SessionUser {
	const user = event.locals.user;
	if (!user) error(401, 'You must be logged in.');
	return user;
}

// Not logged in → /login. Logged in but not an admin → 403 Forbidden.
// 403, not a redirect: they ARE logged in, they just aren't allowed in.
export function requireAdmin(event: HasLocals): SessionUser {
	const user = requireUser(event);
	if (user.role !== 'admin') error(403, 'Admins only.');
	return user;
}
