// /submit — logged-in users only.
import { requireUser } from '#lib/server/guards.js';
import type { PageServerLoad } from './$types';

export const load: PageServerLoad = (event) => {
	// Not logged in → redirect to /login (which sends them back to /submit after logging in).
	// The guard must be in THIS file, not in +page.svelte: a .svelte check runs in the
	// browser, where anyone can skip it. A server load can't be skipped.
	const user = requireUser(event);
	return { user: { name: user.name, email: user.email } };
};
