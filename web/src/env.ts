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
	PUBLIC_API_BASE_URL: {
		schema: (value) => value?.trim() || '',
		description:
			'Python API base URL used by the prod /api/* proxy fallback (empty in dev — the Vite proxy handles it).',
		public: true
	}
});