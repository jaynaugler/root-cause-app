// Tests for hooks.server.ts: the place where cookie, session, user and the
// /admin guard all come together. Real sessions in the in-memory MongoDB.
import { isHttpError, isRedirect } from '@sveltejs/kit';
import { afterAll, beforeEach, describe, expect, it, vi } from 'vitest';
import { handle } from '../hooks.server.js';
import { getConnection } from '#lib/server/mongoose.js';
import { createUser, getUserModel } from '#lib/server/users.js';
import { SESSION_COOKIE, createSession, getSessionModel } from '#lib/server/sessions.js';
import { fakeCookies, thrownBy } from './fakes.js';

type HandleInput = Parameters<typeof handle>[0];

let bobToken: string;
let adaToken: string;

beforeEach(async () => {
	const [User, Session] = [await getUserModel(), await getSessionModel()];
	await Promise.all([User.deleteMany({}), Session.deleteMany({})]);

	const bob = await createUser({ name: 'Bob', email: 'bob@example.com', password: 'password-1' });
	const ada = await createUser({ name: 'Ada', email: 'ada@example.com', password: 'password-2' });
	if (bob === 'email-taken' || ada === 'email-taken') throw new Error('unexpected');
	await User.updateOne({ _id: ada }, { role: 'admin' });

	bobToken = (await createSession(bob)).token;
	adaToken = (await createSession(ada)).token;
});

afterAll(async () => {
	await (await getConnection()).close();
});

// Builds the { event, resolve } that SvelteKit passes to handle().
function request(path: string, token?: string) {
	const cookies = fakeCookies(token ? { [SESSION_COOKIE]: token } : {});
	const event = { cookies, locals: {} as App.Locals, url: new URL(`http://localhost${path}`) };
	// resolve() = "render the page". A spy, so we can check whether it was reached.
	const resolve = vi.fn(async () => new Response('the page'));
	const input = { event, resolve } as unknown as HandleInput;
	return { input, event, cookies, resolve };
}

describe('handle: who is this?', () => {
	it('no cookie → logged out, page still renders', async () => {
		const { input, event, resolve } = request('/');

		await handle(input);

		expect(event.locals.user).toBeNull();
		expect(resolve).toHaveBeenCalled();
	});

	it('valid cookie → locals.user is that user, cookie refreshed', async () => {
		const { input, event, cookies } = request('/', bobToken);

		await handle(input);

		expect(event.locals.user).toMatchObject({ name: 'Bob', role: 'user' });
		expect(cookies.set).toHaveBeenCalledWith(SESSION_COOKIE, bobToken, expect.anything());
	});

	it('invalid cookie → logged out, and the useless cookie is deleted', async () => {
		const { input, event, cookies, resolve } = request('/', 'forged-token');

		await handle(input);

		expect(event.locals.user).toBeNull();
		expect(cookies.delete).toHaveBeenCalledWith(SESSION_COOKIE, expect.anything());
		expect(resolve).toHaveBeenCalled();
	});
});

describe('handle: the /admin guard', () => {
	it('logged out → redirect to /login, page never rendered', async () => {
		const { input, resolve } = request('/admin/bad-links');

		const thrown = await thrownBy(() => handle(input));

		expect(isRedirect(thrown)).toBe(true);
		expect(resolve).not.toHaveBeenCalled();
	});

	it('normal user → 403, page never rendered', async () => {
		const { input, resolve } = request('/admin', bobToken);

		const thrown = await thrownBy(() => handle(input));

		expect(isHttpError(thrown, 403)).toBe(true);
		expect(resolve).not.toHaveBeenCalled();
	});

	it('admin → page renders', async () => {
		const { input, resolve } = request('/admin/bad-links', adaToken);

		await handle(input);

		expect(resolve).toHaveBeenCalled();
	});

	it('only guards /admin itself and below, not paths that merely start with it', async () => {
		const { input, resolve } = request('/administrator');

		await handle(input);

		expect(resolve).toHaveBeenCalled();
	});
});
