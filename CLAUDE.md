# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Monorepo layout

- `web/` — SvelteKit 3 app (moved from repo root; all paths below are relative to `web/`)
- `api/` — FastAPI + MongoDB service (Python, managed with **uv**: `uv sync --project api`, lockfile `api/uv.lock` committed)
- Single `.env` at the **repo root**, shared by all three consumers: web (via `sveltekit({ env: { dir: '..' } })` in `web/vite.config.ts`), api (pydantic-settings, `env_file` resolved from the file's location — cwd-independent), and the seed script (dotenv via `import.meta.url`). Real environment variables override `.env` values in both stacks.

## Commands (run from the repo root)

- `pnpm dev` — web dev server on 5173 (forwards to `pnpm -C web dev`)
- `pnpm dev:api` — FastAPI on 8000 (`cd api && uv run uvicorn app.main:app --reload`); endpoints: `/health`, `/api/docs`, `GET/POST /api/items`
- `pnpm api:sync` — install/sync Python deps into `api/.venv`
- `pnpm build` / `pnpm preview` — production build / preview of the web app
- `pnpm check` — `svelte-kit sync` + `svelte-check` (type-check; this repo has no test suite or linter)
- `pnpm seed` — clears `items` collection and inserts 3 seed documents via `tsx src/scripts/seed.ts` (loads the root `.env`, bypassing SvelteKit)

MongoDB runs as a local Docker container on port 27017 (name `mongodb`, restart policy `always`), created manually via `docker run` — there is no compose file in the repo.

## Critical: `#lib`, not `$lib`

This SvelteKit 3 scaffold has **no `$lib` alias** and no `svelte.config.js`. Kit 3 configuration lives in `web/vite.config.ts` (passed to the `sveltekit()` plugin). The path alias is `#lib`, mapped in `web/package.json` `imports`, and server-module imports need the `.js` extension:

```ts
import { getDb } from '#lib/server/db.js';        // works
import { getDb } from '#lib/server/db';            // FAILS (extensionless)
import { getDb } from '$lib/server/db.js';         // FAILS (no $lib alias in this scaffold)
```

Root cause: `tsconfig.json` extends `$app/tsconfig` (shim at `web/node_modules/$app/tsconfig.json`) whose `paths` is `{}`, so TS only resolves `#lib` via the `imports` field (`moduleResolution: "bundler"`). Verify import changes with `pnpm check`.

## Environment variables

Declared in `web/src/env.ts` via `defineEnvVars` from `@sveltejs/kit/env` (Kit 3 style). Server code reads them from `$app/env/private` — NOT from `process.env` (see `web/src/lib/server/db.ts`). Values come from the repo-root `.env` (gitignored; `.env.example` documents the four keys: `ATLAS_URI`, `ATLAS_DB`, `MONGODB_URI`, `MONGODB_DB`). Atlas is used if `ATLAS_URI` is non-empty, otherwise local; missing both throws at module load. **All four vars need an optional-value schema in `env.ts`** (e.g. `schema: (value) => value?.trim() || undefined`) — an un-schema'd var is required and a missing/empty value fails startup with `kit/env_invalid`. Kit 3 ignores Vite's `envDir`; use Kit's own `env: { dir: '..' }` inside the `sveltekit()` call. Restart `pnpm dev` after `.env` changes.

## Architecture

- **Web → API**: in dev the browser reaches the Python API same-origin — `server.proxy` maps `/api/*` to `http://127.0.0.1:8000` in `web/vite.config.ts`. This is dev-only; an adapter-auto build does not proxy (needs a reverse proxy in production).
- **DB access** (`web/src/lib/server/db.ts`): module-load singleton `MongoClient` cached on `globalThis._mongoClientPromise` so the connection survives Vite HMR in dev. `resolveDbConfig()` runs at import time. Mirrored in Python by `api/app/config.py` (`resolve_db_config()`) and `api/app/db.py` (motor client at module load — fails fast on missing env).
- **Data flow** (`web/src/routes/+page.server.ts`): form actions (`?/create`) validate with zod and return `fail(400, { errors, name })` on failure; the `+page.svelte` `form` prop reads errors to render messages and repopulate the input. `load` queries `items` (latest 10); Mongo `_id` ObjectIds are stringified before returning because SvelteKit cannot serialize them. Same shape in FastAPI: `api/app/items.py` returns `{"_id": str(...), "name", "createdAt"}` dicts (FastAPI can't JSON-encode ObjectId; always pass a limit to `to_list()`).
- **Item shape**: `{ _id, name, createdAt }` in the `items` collection of `root-cause_db`.
- **UI**: shadcn-svelte components in `web/src/lib/components/ui/`, Tailwind CSS v4 (inlined by the Vite plugin, only emits utilities used in source).
- **Standalone scripts** (`web/src/scripts/seed.ts`): run with `tsx`, use dotenv + `process.env` directly rather than the SvelteKit env system (loads the repo-root `.env` via `import.meta.url`, so it works from any cwd).
- **Python service** (`api/app/`): FastAPI with a lifespan that closes the motor client; pydantic-settings resolved from the settings file's location, not the CWD; no CORS middleware needed in dev (same-origin via the proxy).
