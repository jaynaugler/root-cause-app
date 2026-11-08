// /login — the server half: checks email + password and starts a session.
import { fail, redirect } from '@sveltejs/kit';
import { z } from 'zod';
import { findUserByEmail } from '#lib/server/users.js';
import { verifyPassword } from '#lib/server/password.js';
import { createSession, setSessionCookie } from '#lib/server/sessions.js';
import type { Actions, PageServerLoad } from './$types';

// Where to go after logging in.
const AFTER_LOGIN = '/submit';

// Only "is it filled in and roughly the right shape". No min-length on the
// password here: the rules are for choosing a password (register), not typing one.
const loginSchema = z.object({
	email: z
		.string({ error: 'Email is required.' })
		.trim()
		.pipe(z.email({ error: 'Enter a valid email address.' })),
	password: z
		.string({ error: 'Password is required.' })
		.min(1, { error: 'Password is required.' })
		.max(128, { error: 'Password cannot exceed 128 characters.' })
});

type FieldErrors = Partial<Record<keyof z.infer<typeof loginSchema>, string[]>>;

// Same message whether the email doesn't exist or the password is wrong,
// so nobody can use this form to find out who has an account.
const INVALID_LOGIN = 'Invalid email or password.';

// Already logged in? No need to see the login form.
export const load: PageServerLoad = ({ locals }) => {
	if (locals.user) redirect(303, AFTER_LOGIN);
};

export const actions: Actions = {
	default: async ({ request, cookies }) => {
		const formData = await request.formData();
		const raw = { email: formData.get('email'), password: formData.get('password') };
		const email = raw.email?.toString() ?? ''; // refill the field; never the password

		const result = loginSchema.safeParse(raw);
		if (!result.success) {
			const errors: FieldErrors = z.flattenError(result.error).fieldErrors;
			return fail(400, { email, errors });
		}

		const user = await findUserByEmail(result.data.email);
		if (!user || !(await verifyPassword(user.passwordHash, result.data.password))) {
			return fail(400, { email, message: INVALID_LOGIN });
		}

		const { token, expiresAt } = await createSession(user._id);
		setSessionCookie(cookies, token, expiresAt);

		redirect(303, AFTER_LOGIN);
	}
};
