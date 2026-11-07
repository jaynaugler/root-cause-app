// See https://svelte.dev/docs/kit/types#app.d.ts
// for information about these interfaces
import type { SessionUser } from '#lib/server/sessions.js';

declare global {
	namespace App {
		// interface Error {}
		interface Locals {
			// Set by hooks.server.ts on every request. null = not logged in.
			user: SessionUser | null;
		}
		// interface PageData {}
		// interface PageState {}
		// interface Platform {}
	}
}

export {};
