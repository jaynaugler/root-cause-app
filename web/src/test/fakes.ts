// Small stand-ins for the SvelteKit objects our hooks/routes receive, for tests.
import { vi } from 'vitest';

// A cookie jar that behaves like event.cookies, with spies to check calls.
export function fakeCookies(initial: Record<string, string> = {}) {
	const jar = new Map(Object.entries(initial));
	return {
		get: vi.fn((name: string) => jar.get(name)),
		set: vi.fn((name: string, value: string) => void jar.set(name, value)),
		delete: vi.fn((name: string) => void jar.delete(name))
	};
}

// Runs `fn` and returns what it threw (SvelteKit's redirect()/error() throw).
export async function thrownBy(fn: () => unknown): Promise<unknown> {
	try {
		await fn();
	} catch (thrown) {
		return thrown;
	}
	throw new Error('expected it to throw, but it let the request through');
}
