// Kit 3 environment variables are declared here (https://svelte.dev/docs/kit/environment-variables).
// Private (server-only) by default; values are read from .env / the environment at app start.
import { defineEnvVars } from '@sveltejs/kit/env';

export const variables = defineEnvVars({
	ATLAS_URI: {
		schema: (value) => value?.trim() || undefined,
		description: 'MongoDB Atlas connection string. Takes precedence over MONGODB_URI.'
	},
	ATLAS_DB: {
		schema: (value) => value?.trim() || undefined,
		description: 'Atlas database name (optional; falls back to MONGODB_DB or root-cause_db).'
	},
	MONGODB_URI: {
		schema: (value) => value?.trim() || undefined,
		description: 'Local MongoDB connection string.'
	},
	MONGODB_DB: {
		schema: (value) => value?.trim() || undefined,
		description: 'Local database name (optional; defaults to root-cause_db).'
	},
	SEARCH_API_URL: {
		schema: (value) => value?.trim().replace(/\/+$/, '') || undefined,
		description:
			'Base URL of the search-server search-api (e.g. the Cloudflare tunnel URL), without /api/search.'
	},
	SEARCH_API_KEY: {
		schema: (value) => value?.trim() || undefined,
		description: 'Sent as X-API-Key to the search-api. Server-only — never expose to the browser.'
	},
	PUBLIC_API_BASE_URL: {
		schema: (value) => value?.trim() || '',
		description:
			'Python API base URL used by the prod /api/* proxy fallback (empty in dev — the Vite proxy handles it).',
		public: true
	}
});