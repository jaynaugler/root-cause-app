// /admin/submitted-requests — admins only (also enforced by hooks.server.ts).
import { requireAdmin } from '#lib/server/guards.js';
import type { PageServerLoad } from './$types';

export const load: PageServerLoad = (event) => {
	const admin = requireAdmin(event);
	return { admin: { name: admin.name, email: admin.email } };
};
