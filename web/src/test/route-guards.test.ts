// "Is the guard actually used?" guards.test.ts proves requireUser works; these
// prove the protected routes call it. If someone deletes that one line, these fail.
import { isHttpError, isRedirect } from '@sveltejs/kit';
import { afterAll, beforeEach, describe, expect, it } from 'vitest';
import { load as homeLoad } from '../routes/+page.server.js';
import { load as submitLoad } from '../routes/submit/+page.server.js';
import { load as submittedRequestsLoad } from '../routes/admin/submitted-requests/+page.server.js';
import { POST as saveResource } from '../routes/resources/+server.js';
import { getConnection } from '#lib/server/mongoose.js';
import { getResourceModel } from '#lib/server/resources.js';
import type { SessionUser } from '#lib/server/sessions.js';
import { thrownBy } from './fakes.js';

const bob: SessionUser = { id: '1', name: 'Bob', email: 'bob@example.com', role: 'user' };
const admin: SessionUser = { id: '2', name: 'Admin', email: 'admin@example.com', role: 'admin' };

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

describe('/admin/submitted-requests', () => {
	it('redirects a logged-out visitor to /login', async () => {
		const thrown = await thrownBy(() => submittedRequestsLoad({ locals: { user: null } } as AnyEvent));
		expect(isRedirect(thrown)).toBe(true);
		expect(thrown).toMatchObject({ location: '/login' });
	});

	it('rejects a logged-in non-admin', async () => {
		const thrown = await thrownBy(() => submittedRequestsLoad({ locals: { user: bob } } as AnyEvent));
		expect(isHttpError(thrown, 403)).toBe(true);
	});

	it('loads for an admin', async () => {
		const data = await submittedRequestsLoad({ locals: { user: admin } } as AnyEvent);
		expect(data).toEqual({ admin: { name: 'Admin', email: 'admin@example.com' } });
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
			name: bob.name,
			email: bob.email,
			description: 'Generated resource description',
			submittedDescription: 'Context for the review team',
			submittedSummary: 'S'.repeat(250),
			status: 'pending'
		});

		expect(response.status).toBe(201);
		const Resource = await getResourceModel();
		const saved = await Resource.findOne({ link: record.link }).lean();
		expect(saved?.name).toBe(bob.name);
		expect(saved?.email).toBe(bob.email);
		expect(saved?.description).toBe('Generated resource description');
		expect(saved?.submittedDescription).toBe('Context for the review team');
		expect(saved?.submittedSummary).toBe('S'.repeat(250));
	});
});

describe('MongoDB card wall', () => {
	beforeEach(async () => {
		const Resource = await getResourceModel();
		await Resource.deleteMany({});
		await Resource.insertMany(
			Array.from({ length: 13 }, (_, i) => ({
				title: `Record ${i}`,
				link: `https://example.com/${i}`,
				resourceformat: i < 3 ? 'article' : 'pdf',
				contentcategory: i < 3 ? 'history' : 'people',
				attribution: i < 3 ? 'Archive' : 'Other',
				status: 'approved',
				createdAt: new Date(2026, 0, i + 1)
			}))
		);
	});

	async function loadWall(query = '') {
		const result = await homeLoad({ url: new URL(`http://localhost/${query}`) } as AnyEvent);
		if (!result) throw new Error('Expected card wall data');
		return result;
	}

	it('paginates the newest records through MongoDB', async () => {
		const first = await loadWall();
		expect(first.wall).toMatchObject({ total: 13, page: 1, pageCount: 2 });
		expect(first.defaultRecords).toHaveLength(12);
		expect(first.defaultRecords[0].title).toBe('Record 12');

		const second = await loadWall('?page=2');
		expect(second.defaultRecords).toHaveLength(1);
		expect(second.defaultRecords[0].title).toBe('Record 0');
	});

	it('combines MongoDB filters and title sorting', async () => {
		const result = await loadWall('?resourceformat=article&contentcategory=history&attribution=Archive&sort=title');
		expect(result.wall.total).toBe(3);
		expect(result.defaultRecords.map((record: { title?: string }) => record.title)).toEqual(['Record 0', 'Record 1', 'Record 2']);
	});
});
