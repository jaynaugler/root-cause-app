# root-cause-app

A hackathon monorepo: SvelteKit 5 web app (`web/`) plus a FastAPI + MongoDB service (`api/`). shadcn-svelte UI, Tailwind CSS v4, zod-validated form actions, and a Dockerized local MongoDB. The UI calls the Python API through a same-origin `/api/*` proxy in dev.

## Requirements

- Node.js (>= 22) and [pnpm](https://pnpm.io)
- [uv](https://docs.astral.sh/uv) (for the Python service)
- Docker (for the local MongoDB container)

## Setup

1. Install dependencies:

   ```sh
   pnpm install     # web app
   pnpm api:sync    # Python service (api/.venv)
   ```

2. Start MongoDB in Docker (data persists across container recreation via the named volume):

   ```sh
   docker run -d --name mongodb --restart always -p 27017:27017 \
     -v mongodb-data:/data/db mongo:8.0.4
   ```

3. Configure the database connection (single `.env` at the repo root, shared by web + api + the seed script):

   ```sh
   cp .env.example .env
   ```

   Then fill in either a local URI (`MONGODB_URI="mongodb://localhost:27017/"`) or a MongoDB Atlas connection string (`ATLAS_URI`). Atlas takes precedence when both are set. No `docker run` needed if you use an Atlas URI.

4. (Optional) Seed the `items` collection with demo data:

   ```sh
   pnpm seed
   ```

   ⚠️ This clears the collection first.

5. Start the dev servers (two terminals, or background one of them):

   ```sh
   pnpm dev        # web app     → http://localhost:5173
   pnpm dev:api    # FastAPI API → http://localhost:8000
   ```

   The web app proxies `/api/*` to the API, so the browser can call it same-origin (docs are also served at `/api/docs` through the proxy, or directly at `http://localhost:8000/docs`).

## Commands

| Command         | What it does                                                        |
| --------------- | ------------------------------------------------------------------- |
| `pnpm dev`      | Start the web app dev server (port 5173)                            |
| `pnpm dev:api`  | Start the FastAPI service with reload (port 8000)                   |
| `pnpm build`    | Production build of the web app                                     |
| `pnpm preview`  | Preview the production build locally                                |
| `pnpm check`    | Type-check the web app with `svelte-check` (no test suite yet)      |
| `pnpm seed`     | Clear and re-seed the `items` collection                            |
| `pnpm api:sync` | Install/sync Python deps for the api from `uv.lock` into `api/.venv` |

## Project structure

- `web/src/routes/` — SvelteKit pages: `+page.server.ts` (load + form actions with zod validation), `+page.svelte` (UI)
- `web/src/lib/server/db.ts` — MongoDB client singleton (Atlas-first fallback to local)
- `web/src/env.ts` — Kit 3 environment variable declarations; read via `$app/env/private`
- `web/src/lib/components/ui/` — shadcn-svelte components
- `web/src/scripts/seed.ts` — standalone seeding script (`tsx` + `dotenv`, independent of SvelteKit)
- `web/vite.config.ts` — Kit 3 configuration (inline: no `svelte.config.js`) incl. the `/api` dev proxy
- `api/app/main.py` — FastAPI app (`/health`, `/api/docs`)
- `api/app/items.py` — `GET|POST /api/items` starter resource over the shared `items` collection
- `api/app/config.py` / `api/app/db.py` — settings (root `.env`, cwd-independent) and motor client singleton

## Notes

- Imports use the `#lib` alias (not `$lib`):
  `import { getDb } from '#lib/server/db.js';`
- To deploy, replace `@sveltejs/adapter-auto` in `web/vite.config.ts` with the adapter for your target platform (Node, Vercel, etc.). The `/api/*` proxy is dev-only — production needs a reverse proxy in front of the two services.
