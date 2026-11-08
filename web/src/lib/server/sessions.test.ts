// Tests for sessions.ts + session-schema.ts, against the in-memory MongoDB.
import { createHash } from 'node:crypto';
import { afterAll, afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import type { Types } from 'mongoose';
import { getConnection } from './mongoose.js';
import { createUser, getUserModel } from './users.js';
import { createSession, deleteSession, getSessionModel, validateSession } from './sessions.js';

const DAY_MS = 24 * 60 * 60 * 1000;

let userId: Types.ObjectId;

beforeEach(async () => {
	const [User, Session] = [await getUserModel(), await getSessionModel()];
	await Promise.all([User.deleteMany({}), Session.deleteMany({})]);

	const id = await createUser({ name: 'Bob', email: 'bob@example.com', password: 'bobs-password' });
	if (id === 'email-taken') throw new Error('unexpected: empty collection');
	userId = id;
});

afterEach(() => {
	// Put the clock back after the "time travel" tests.
	vi.useRealTimers();
});

afterAll(async () => {
	await (await getConnection()).close();
});

// "Time travel": fake ONLY Date (Date.now / new Date), so session expiry can be
// tested without waiting 30 days. Real timers stay real, so MongoDB keeps working.
function travelForward(ms: number) {
	const now = Date.now();
	vi.useFakeTimers({ toFake: ['Date'] });
	vi.setSystemTime(now + ms);
}

describe('createSession', () => {
	it('stores only a hash of the token, never the token itself', async () => {
		const { token } = await createSession(userId);
		const Session = await getSessionModel();
		const stored = await Session.findOne({ userId }).lean();

		expect(stored!.tokenHash).not.toBe(token);
		expect(stored!.tokenHash).toBe(createHash('sha256').update(token).digest('hex'));
	});

	it('creates a long random token, different every time', async () => {
		const first = await createSession(userId);
		const second = await createSession(userId);

		expect(first.token.length).toBeGreaterThanOrEqual(40);
		expect(first.token).not.toBe(second.token);
	});

	it('expires in 30 days', async () => {
		const { expiresAt } = await createSession(userId);

		expect(expiresAt.getTime() - Date.now()).toBeGreaterThan(29.9 * DAY_MS);
		expect(expiresAt.getTime() - Date.now()).toBeLessThanOrEqual(30 * DAY_MS);
	});
});

describe('validateSession', () => {
	it('returns the user for a valid token, without the password hash', async () => {
		const { token } = await createSession(userId);
		const result = await validateSession(token);

		expect(result!.user).toEqual({
			id: String(userId),
			name: 'Bob',
			email: 'bob@example.com',
			role: 'user'
		});
		expect(result!.user).not.toHaveProperty('passwordHash');
	});

	it('returns null for an unknown token', async () => {
		await createSession(userId);

		expect(await validateSession('made-up-token')).toBeNull();
	});

	it('sees role changes right away (e.g. after pnpm make-admin)', async () => {
		const { token } = await createSession(userId);
		const User = await getUserModel();
		await User.updateOne({ _id: userId }, { role: 'admin' });

		expect((await validateSession(token))!.user.role).toBe('admin');
	});

	it('returns null and removes the session once it has expired', async () => {
		const { token } = await createSession(userId);

		travelForward(31 * DAY_MS);

		expect(await validateSession(token)).toBeNull();
		const Session = await getSessionModel();
		expect(await Session.countDocuments()).toBe(0);
	});

	it('does not extend a session that still has more than 15 days left', async () => {
		const { token, expiresAt } = await createSession(userId);

		travelForward(5 * DAY_MS); // 25 days left

		expect((await validateSession(token))!.expiresAt).toEqual(expiresAt);
	});

	it('extends an active session back to 30 days when less than 15 are left', async () => {
		const { token, expiresAt } = await createSession(userId);

		travelForward(20 * DAY_MS); // 10 days left
		const result = await validateSession(token);

		expect(result!.expiresAt.getTime()).toBeGreaterThan(expiresAt.getTime());
		expect(result!.expiresAt.getTime() - Date.now()).toBe(30 * DAY_MS);
		// ...and saved in the DB, not only returned
		const Session = await getSessionModel();
		const stored = await Session.findOne({ userId }).lean();
		expect(stored!.expiresAt).toEqual(result!.expiresAt);
	});

	it('returns null and removes the session if the user was deleted', async () => {
		const { token } = await createSession(userId);
		const User = await getUserModel();
		await User.deleteOne({ _id: userId });

		expect(await validateSession(token)).toBeNull();
		const Session = await getSessionModel();
		expect(await Session.countDocuments()).toBe(0);
	});
});

describe('deleteSession (logout)', () => {
	it('makes the token useless', async () => {
		const { token } = await createSession(userId);

		await deleteSession(token);

		expect(await validateSession(token)).toBeNull();
	});

	it('only logs out that one device', async () => {
		const laptop = await createSession(userId);
		const phone = await createSession(userId);

		await deleteSession(phone.token);

		expect(await validateSession(phone.token)).toBeNull();
		expect(await validateSession(laptop.token)).not.toBeNull();
	});
});

describe('sessionSchema indexes', () => {
	it('has a TTL index so MongoDB deletes expired sessions by itself', async () => {
		const Session = await getSessionModel();
		const indexes = await Session.collection.indexes();
		const ttl = indexes.find((index) => index.key.expiresAt === 1);

		expect(ttl?.expireAfterSeconds).toBe(0);
	});

	it('has a unique index on tokenHash', async () => {
		const Session = await getSessionModel();
		const indexes = await Session.collection.indexes();

		expect(indexes.find((index) => index.key.tokenHash === 1)?.unique).toBe(true);
	});
});
