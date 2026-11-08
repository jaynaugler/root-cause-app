// Test stand-in for SvelteKit's `$app/env/private` (see vitest.config.ts).
// mongoose.ts reads these four values; we point it at the in-memory MongoDB.
import { randomUUID } from 'node:crypto';
import { inject } from 'vitest';

export const ATLAS_URI: string | undefined = undefined; // never Atlas in tests
export const ATLAS_DB: string | undefined = undefined;
export const MONGODB_URI: string | undefined = inject('mongoUri');
// A fresh database per test file: files run in parallel, so they must not share data.
export const MONGODB_DB: string | undefined = `test-${randomUUID()}`;
