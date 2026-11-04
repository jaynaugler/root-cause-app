# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Commands

- `pnpm dev` — dev server (Vite)
- `pnpm build` / `pnpm preview` — production build / preview
- `pnpm check` — `svelte-kit sync` + `svelte-check` (type-check; this repo has no test suite or linter)
- `pnpm seed` — clears `items` collection and inserts 3 seed documents via `tsx src/scripts/seed.ts` (loads `.env` standalone, bypassing SvelteKit)

MongoDB runs as a local Docker container on port 27017 (name `mongodb`, restart policy `always`), created manually via `docker run` — there is no compose file in the repo.

## Critical: `#lib`, not `$lib`

This SvelteKit 3 scaffold has **no `$lib` alias** and no `svelte.config.js`. Kit 3 configuration lives in `vite.config.ts` (passed to the `sveltekit()` plugin). The path alias is `#lib`, mapped in `package.json` `imports`, and server-module imports need the `.js` extension:

```ts
import { getDb } from '#lib/server/db.js';        // works
import { getDb } from '#lib/server/db';            // FAILS (extensionless)
import { getDb } from '$lib/server/db.js';         // FAILS (no $lib alias in this scaffold)
```

Root cause: `tsconfig.json` extends `$app/tsconfig` (shim at `node_modules/$app/tsconfig.json`) whose `paths` is `{}`, so TS only resolves `#lib` via the `imports` field (`moduleResolution: "bundler"`). Verify import changes with `pnpm check`.

## Environment variables

Declared in `src/env.ts` via `defineEnvVars` from `@sveltejs/kit/env` (Kit 3 style). Server code reads them from `$app/env/private` — NOT from `process.env` (see `src/lib/server/db.ts`). Values come from `.env` (gitignored; `.env.example` documents the four keys: `ATLAS_URI`, `ATLAS_DB`, `MONGODB_URI`, `MONGODB_DB`). Atlas is used if `ATLAS_URI` is non-empty, otherwise local; missing both throws at module load.

## Architecture

- **DB access** (`src/lib/server/db.ts`): module-load singleton `MongoClient` cached on `globalThis._mongoClientPromise` so the connection survives Vite HMR in dev. `resolveDbConfig()` runs at import time.
- **Data flow** (`src/routes/+page.server.ts`): form actions (`?/create`) validate with zod and return `fail(400, { errors, name })` on failure; the `+page.svelte` `form` prop reads errors to render messages and repopulate the input. `load` queries `items` (latest 10); Mongo `_id` ObjectIds are stringified before returning because SvelteKit cannot serialize them.
- **Item shape**: `{ _id, name, createdAt }` in the `items` collection of `root-cause_db`.
- **UI**: shadcn-svelte components in `src/lib/components/ui/`, Tailwind CSS v4 (inlined by the Vite plugin, only emits utilities used in source).
- **Standalone scripts** (`src/scripts/seed.ts`): run with `tsx`, use `dotenv/config` + `process.env` directly rather than the SvelteKit env system.