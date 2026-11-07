// Tests for users.ts + user-schema.ts, against the in-memory MongoDB.
import { afterAll, beforeEach, describe, expect, it } from 'vitest';
import { getConnection } from './mongoose.js';
import { verifyPassword } from './password.js';
import { createUser, findUserByEmail, getUserModel } from './users.js';

const bob = { name: 'Bob', email: 'bob@example.com', password: 'bobs-password' };

// Each test starts with an empty users collection, so tests can't affect each other.
beforeEach(async () => {
	const User = await getUserModel();
	await User.deleteMany({});
});

afterAll(async () => {
	await (await getConnection()).close();
});

describe('createUser', () => {
	it('saves the user with a hashed password, never the plain one', async () => {
		await createUser(bob);
		const saved = await findUserByEmail(bob.email);

		expect(saved).not.toBeNull();
		expect(saved!.passwordHash).not.toBe(bob.password);
		expect(await verifyPassword(saved!.passwordHash, bob.password)).toBe(true);
	});

	it('lets MongoDB create the _id and fills role + createdAt from the schema', async () => {
		const id = await createUser(bob);
		const saved = await findUserByEmail(bob.email);

		expect(String(saved!._id)).toBe(String(id));
		expect(saved!.role).toBe('user');
		expect(saved!.createdAt).toBeInstanceOf(Date);
	});

	it('stores the email lowercase and trimmed, and trims the name', async () => {
		await createUser({ ...bob, name: '  Bob  ', email: '  Bob@Example.COM ' });
		const saved = await findUserByEmail('bob@example.com');

		expect(saved!.email).toBe('bob@example.com');
		expect(saved!.name).toBe('Bob');
	});

	it("returns 'email-taken' for an existing email, even with other capitals", async () => {
		await createUser(bob);

		expect(await createUser({ ...bob, email: 'BOB@example.com' })).toBe('email-taken');

		const User = await getUserModel();
		expect(await User.countDocuments()).toBe(1);
	});

	it('cannot be used to create an admin', async () => {
		// Someone sneaks an extra field into the input (e.g. a tampered form).
		const sneaky = { ...bob, role: 'admin' } as typeof bob;
		await createUser(sneaky);

		expect((await findUserByEmail(bob.email))!.role).toBe('user');
	});
});

describe('findUserByEmail', () => {
	it('finds the user regardless of capitals and spaces', async () => {
		await createUser(bob);

		expect((await findUserByEmail('  BOB@example.com '))?.name).toBe('Bob');
	});

	it('returns null for an unknown email', async () => {
		expect(await findUserByEmail('nobody@example.com')).toBeNull();
	});
});

describe('userSchema (the last safety net)', () => {
	it('rejects an invalid email', async () => {
		const User = await getUserModel();

		await expect(
			User.create({ name: 'X', email: 'not-an-email', passwordHash: 'x' })
		).rejects.toThrow(/email/);
	});

	it('rejects unknown fields (strict: throw)', async () => {
		const User = await getUserModel();

		await expect(
			// @ts-expect-error TypeScript already blocks this; the test checks the runtime too
			User.create({ name: 'X', email: 'x@example.com', passwordHash: 'x', isAdmin: true })
		).rejects.toThrow(/isAdmin/);
	});

	it('rejects a role that is not user or admin', async () => {
		const User = await getUserModel();

		await expect(
			// @ts-expect-error TypeScript already blocks this; the test checks the runtime too
			User.create({ name: 'X', email: 'x@example.com', passwordHash: 'x', role: 'superuser' })
		).rejects.toThrow(/role/);
	});
});
