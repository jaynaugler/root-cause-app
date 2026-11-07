// /register — the server half of the page: validates the form and creates the user.
import { fail, redirect } from '@sveltejs/kit';
import { z } from 'zod';
import { createUser } from '#lib/server/users.js';
import { createSession, setSessionCookie } from '#lib/server/sessions.js';
import type { Actions } from './$types';

// What the user typed. Friendly messages per field; the Mongoose schema is the
// last safety net behind this, and the only place uniqueness can be checked.
const registerSchema = z.object({
	name: z
		.string({ error: 'Name is required.' })
		.trim()
		.min(1, { error: 'Name is required.' })
		.max(100, { error: 'Name cannot exceed 100 characters.' }),
	email: z
		.string({ error: 'Email is required.' })
		.trim()
		.pipe(z.email({ error: 'Enter a valid email address.' })),
	password: z
		.string({ error: 'Password is required.' })
		.min(8, { error: 'Password must be at least 8 characters.' })
		// Cap the length: hashing a huge "password" would waste server time.
		.max(128, { error: 'Password cannot exceed 128 characters.' })
});

// { name?: string[], email?: string[], password?: string[] }. One shape for every
// fail() below, so the page can always read form.errors.name / .email / .password.
type FieldErrors = Partial<Record<keyof z.infer<typeof registerSchema>, string[]>>;

export const actions: Actions = {
	// A <form method="POST"> without an `action` attribute posts here.
	default: async ({ request, cookies }) => {
		const formData = await request.formData();
		const raw = {
			name: formData.get('name'),
			email: formData.get('email'),
			password: formData.get('password')
		};

		// Values we send back to refill the form. Never the password.
		const keep = { name: raw.name?.toString() ?? '', email: raw.email?.toString() ?? '' };

		const result = registerSchema.safeParse(raw);
		if (!result.success) {
			// e.g. { email: ['Enter a valid email address.'] }
			const errors: FieldErrors = z.flattenError(result.error).fieldErrors;
			return fail(400, { ...keep, errors });
		}

		const userId = await createUser(result.data);
		if (userId === 'email-taken') {
			const errors: FieldErrors = { email: ['An account with this email already exists.'] };
			return fail(400, { ...keep, errors });
		}

		// Log the new user in right away: new session in the DB, token in the cookie.
		const { token, expiresAt } = await createSession(userId);
		setSessionCookie(cookies, token, expiresAt);

		// 303 = "see other": the browser follows it with a GET.
		redirect(303, '/submit'); // same place the login page sends you
	}
};
