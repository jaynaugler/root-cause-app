import { redirect } from '@sveltejs/kit';
import type { PageServerLoad } from './$types';

// The home page IS the search page; this duplicate route's only content was
// drifted copies of it, which caused exactly the confusion duplicates always do.
export const load: PageServerLoad = () => {
	redirect(308, '/');
};
