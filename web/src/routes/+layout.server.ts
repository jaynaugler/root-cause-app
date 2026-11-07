// Root layout load: runs for every page, so `data.user` is available in
// +layout.svelte and every page below it. This is how the user found by
// hooks.server.ts (event.locals, server-only) reaches the components.
import type { LayoutServerLoad } from './$types';

export const load: LayoutServerLoad = ({ locals }) => {
	// { id, name, email, role } or null. Never add passwordHash or session data here:
	// everything returned from a load is sent to the browser.
	return { user: locals.user };
};
