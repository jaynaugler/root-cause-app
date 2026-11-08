// Tests for password.ts: pure functions, no database needed.
import { describe, expect, it } from 'vitest';
import { hashPassword, verifyPassword } from './password.js';

describe('hashPassword', () => {
	it('never returns the plain password', async () => {
		const hash = await hashPassword('correct horse battery');

		expect(hash).not.toContain('correct horse battery');
		// argon2id, with its settings stored inside the string
		expect(hash).toMatch(/^\$argon2id\$v=19\$m=19456,t=2,p=1\$/);
	});

	it('gives a different hash each time for the same password (random salt)', async () => {
		const first = await hashPassword('same-password');
		const second = await hashPassword('same-password');

		expect(first).not.toBe(second);
	});
});

describe('verifyPassword', () => {
	it('accepts the right password', async () => {
		const hash = await hashPassword('s3cret-pass');

		expect(await verifyPassword(hash, 's3cret-pass')).toBe(true);
	});

	it('rejects a wrong password', async () => {
		const hash = await hashPassword('s3cret-pass');

		expect(await verifyPassword(hash, 's3cret-pasS')).toBe(false);
		expect(await verifyPassword(hash, '')).toBe(false);
	});
});
