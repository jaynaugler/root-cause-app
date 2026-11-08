// Smoke test for the test setup itself: does mongoose.ts reach the in-memory DB?
import { afterAll, describe, expect, it } from 'vitest';
import { getConnection } from '#lib/server/mongoose.js';

describe('test setup', () => {
	afterAll(async () => {
		await (await getConnection()).close();
	});

	it('connects mongoose.ts to the in-memory MongoDB, not Atlas', async () => {
		const connection = await getConnection();

		expect(connection.host).toBe('127.0.0.1');
		expect(connection.name).toMatch(/^test-/);

		const ping = await connection.db!.admin().ping();
		expect(ping.ok).toBe(1);
	});
});
