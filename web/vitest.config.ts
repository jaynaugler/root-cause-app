// Vitest config, separate from vite.config.ts: tests don't need the SvelteKit
// plugin (no pages, no dev server), only our server-side modules.
import { fileURLToPath } from 'node:url';
import { defineConfig } from 'vitest/config';

const stub = (file: string) => fileURLToPath(new URL(`./src/test/stubs/${file}`, import.meta.url));

export default defineConfig({
	resolve: {
		alias: {
			// $app/* only exists inside SvelteKit. Swap in test versions that point
			// mongoose.ts at the in-memory MongoDB instead of Atlas / local.
			// (Order matters: the longer path first.)
			'$app/env/private': stub('app-env-private.ts'),
			'$app/env': stub('app-env.ts')
		}
	},
	test: {
		include: ['src/**/*.test.ts'],
		environment: 'node',
		// Starts one in-memory MongoDB for the whole test run (see the file).
		globalSetup: ['src/test/global-setup.ts'],
		// The first run downloads the MongoDB binary; give it time.
		hookTimeout: 120_000
	}
});
