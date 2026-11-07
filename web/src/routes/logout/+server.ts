// POST /logout — ends the current session. Use it from a form:
//   <form method="POST" action="/logout"><button>Log out</button></form>
// POST, not a GET link: a link could be triggered by any page (an <img src="/logout">
// would log you out), and SvelteKit's CSRF check only covers form POSTs.
import { redirect } from '@sveltejs/kit';
import { SESSION_COOKIE, deleteSession, deleteSessionCookie } from '#lib/server/sessions.js';
import type { RequestHandler } from './$types';

export const POST: RequestHandler = async ({ cookies }) => {
	const token = cookies.get(SESSION_COOKIE);
	// Delete the session in the DB first: then the token is useless even if
	// the browser somehow kept the cookie.
	if (token) await deleteSession(token);
	deleteSessionCookie(cookies);

	redirect(303, '/login');
};
