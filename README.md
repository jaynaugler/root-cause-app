# root-cause-app

A SvelteKit 5 + MongoDB starter built for a hackathon: shadcn-svelte UI, Tailwind CSS v4, zod-validated form actions, and a Dockerized local MongoDB.

## Requirements

- Node.js (>= 22) and [pnpm](https://pnpm.io)
- Docker (for the local MongoDB container)

## Setup

1. Install dependencies:

   ```sh
   pnpm install
   ```

2. Start MongoDB in Docker (data persists across container recreation via the named volume):

   ```sh
   docker run -d --name mongodb --restart always -p 27017:27017 \
     -v mongodb-data:/data/db mongo:8.0.4
   ```

3. Configure the database connection:

   ```sh
   cp .env.example .env
   ```

   Then fill in either a local URI (`MONGODB_URI="mongodb://localhost:27017/"`) or a MongoDB Atlas connection string (`ATLAS_URI`). Atlas takes precedence when both are set. No `docker run` needed if you use an Atlas URI.

4. (Optional) Seed the `items` collection with demo data:

   ```sh
   pnpm seed
   ```

   ⚠️ This clears the collection first.

5. Start the dev server:

   ```sh
   pnpm dev
   ```

## Commands

| Command             | What it does                                                     |
| ------------------- | ---------------------------------------------------------------- |
| `pnpm dev`          | Start the dev server                                             |
| `pnpm build`        | Production build                                                 |
| `pnpm preview`      | Preview the production build locally                             |
| `pnpm check`        | Type-check the project with `svelte-check` (no test suite yet)   |
| `pnpm seed`         | Clear and re-seed the `items` collection                         |

## Project structure

- `src/routes/` — SvelteKit pages: `+page.server.ts` (load + form actions with zod validation), `+page.svelte` (UI)
- `src/lib/server/db.ts` — MongoDB client singleton (Atlas-first fallback to local)
- `src/env.ts` — Kit 3 environment variable declarations; read via `$app/env/private`
- `src/lib/components/ui/` — shadcn-svelte components
- `src/scripts/seed.ts` — standalone seeding script (`tsx` + `dotenv`, independent of SvelteKit)

## Notes

- Imports use the `#lib` alias (not `$lib`):
  `import { getDb } from '#lib/server/db.js';`
- To deploy, replace `@sveltejs/adapter-auto` in `vite.config.ts` with the adapter for your target platform (Node, Vercel, etc.).