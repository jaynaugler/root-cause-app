// /admin — only reachable by admins (hooks.server.ts checks every /admin request).
import { requireAdmin } from '#lib/server/guards.js';
import type { PageServerLoad } from './$types';

export const load: PageServerLoad = async (event) => {
	// The hook already let only admins through. Calling the guard again costs
	// nothing and gives us `admin` typed as a user (not `SessionUser | null`).
	const admin = requireAdmin(event);
	return { admin: { name: admin.name, email: admin.email } };
};
