// "Is the guard actually used?" guards.test.ts proves requireUser works; these
// prove the protected routes call it. If someone deletes that one line, these fail.
import { isHttpError, isRedirect } from '@sveltejs/kit';
import { afterAll, beforeEach, describe, expect, it } from 'vitest';
import { load as submitLoad } from '../routes/submit/+page.server.js';
import { POST as saveResource } from '../routes/resources/+server.js';
import { getConnection } from '#lib/server/mongoose.js';
import { getResourceModel } from '#lib/server/resources.js';
import type { SessionUser } from '#lib/server/sessions.js';
import { thrownBy } from './fakes.js';

const bob: SessionUser = { id: '1', name: 'Bob', email: 'bob@example.com', role: 'user' };

afterAll(async () => {
	await (await getConnection()).close();
});

// Route functions expect the full SvelteKit event; they only use these parts.
// eslint-disable-next-line @typescript-eslint/no-explicit-any
type AnyEvent = any;

describe('/submit', () => {
	it('redirects a logged-out visitor to /login', async () => {
		const thrown = await thrownBy(() => submitLoad({ locals: { user: null } } as AnyEvent));

		expect(isRedirect(thrown)).toBe(true);
		expect(thrown).toMatchObject({ location: '/login' });
	});

	it('loads for a logged-in user', async () => {
		const data = await submitLoad({ locals: { user: bob } } as AnyEvent);

		expect(data).toEqual({ user: { name: 'Bob', email: 'bob@example.com' } });
	});
});

describe('POST /resources', () => {
	const record = {
		title: 'A test PDF',
		link: 'https://example.com/test.pdf',
		resourceformat: 'pdf'
	};

	// Start every test with an empty collection, so one test can't affect the next.
	beforeEach(async () => {
		await (await getResourceModel()).deleteMany({});
	});

	function postAs(user: SessionUser | null, overrides: Record<string, unknown> = {}) {
		const request = new Request('http://localhost/resources', {
			method: 'POST',
			headers: { 'content-type': 'application/json' },
			body: JSON.stringify({ ...record, ...overrides })
		});
		return saveResource({ locals: { user }, request } as AnyEvent);
	}

	it('answers 401 to a logged-out caller and saves nothing', async () => {
		const thrown = await thrownBy(() => postAs(null));

		expect(isHttpError(thrown, 401)).toBe(true);
		const Resource = await getResourceModel();
		expect(await Resource.countDocuments()).toBe(0);
	});

	it('saves the record for a logged-in user', async () => {
		const response = await postAs(bob);

		expect(response.status).toBe(201);
		const Resource = await getResourceModel();
		expect(await Resource.countDocuments({ link: record.link })).toBe(1);
	});

	it('keeps optional submitter notes separate from the generated description', async () => {
		const response = await postAs(bob, {
			description: 'Generated resource description',
			submittedDescription: 'Context for the review team',
			status: 'pending'
		});

		expect(response.status).toBe(201);
		const Resource = await getResourceModel();
		const saved = await Resource.findOne({ link: record.link }).lean();
		expect(saved?.description).toBe('Generated resource description');
		expect(saved?.submittedDescription).toBe('Context for the review team');
	});
});
