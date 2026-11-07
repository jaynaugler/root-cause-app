// Tests for guards.ts. No database: the guards only look at event.locals.user,
// so we hand them a fake event with exactly that.
import { isHttpError, isRedirect } from '@sveltejs/kit';
import { describe, expect, it } from 'vitest';
import { requireAdmin, requireUser, requireUserApi } from './guards.js';
import type { SessionUser } from './sessions.js';

const user: SessionUser = { id: '1', name: 'Bob', email: 'bob@example.com', role: 'user' };
const admin: SessionUser = { id: '2', name: 'Ada', email: 'ada@example.com', role: 'admin' };

function eventFor(who: SessionUser | null) {
	return { locals: { user: who } };
}

// The guards stop a request by THROWING a redirect or an error.
// This runs the guard and returns what it threw.
function thrownBy(guard: () => unknown): unknown {
	try {
		guard();
	} catch (thrown) {
		return thrown;
	}
	throw new Error('expected the guard to throw, but it let the request through');
}

describe('requireUser (pages)', () => {
	it('redirects a logged-out visitor to /login', () => {
		const thrown = thrownBy(() => requireUser(eventFor(null)));

		expect(isRedirect(thrown)).toBe(true);
		expect(thrown).toMatchObject({ status: 303, location: '/login' });
	});

	it('lets any logged-in user through and returns them', () => {
		expect(requireUser(eventFor(user))).toBe(user);
		expect(requireUser(eventFor(admin))).toBe(admin);
	});
});

describe('requireUserApi (endpoints)', () => {
	it('answers 401 instead of redirecting, so fetch() gets a clear error', () => {
		const thrown = thrownBy(() => requireUserApi(eventFor(null)));

		expect(isRedirect(thrown)).toBe(false);
		expect(isHttpError(thrown, 401)).toBe(true);
	});

	it('lets a logged-in user through', () => {
		expect(requireUserApi(eventFor(user))).toBe(user);
	});
});

describe('requireAdmin', () => {
	it('redirects a logged-out visitor to /login (not 403: they might be an admin)', () => {
		const thrown = thrownBy(() => requireAdmin(eventFor(null)));

		expect(isRedirect(thrown)).toBe(true);
	});

	it('answers 403 to a logged-in normal user', () => {
		const thrown = thrownBy(() => requireAdmin(eventFor(user)));

		expect(isHttpError(thrown, 403)).toBe(true);
	});

	it('lets an admin through', () => {
		expect(requireAdmin(eventFor(admin))).toBe(admin);
	});
});
