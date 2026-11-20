# Hackathon app

Next.js 16 (App Router, `src/`) · TypeScript · Supabase (Postgres + Auth) · Drizzle ORM · shadcn/ui + Tailwind · lucide-react · Motion · Python (uv) for check scripts · Vercel.

## Commands
- `npm run dev`: start the dev server
- `npm run check`: everything (biome, tsc, ruff, Supabase RLS audit). Add `-- --build` for a full build. Must pass before commit.
- `npm run smoke [url]`: hit key routes (add new routes to `scripts/smoke_test.py`)
- `npm run db:generate` then `npm run db:migrate`: the ONLY way to change the schema. Never `drizzle-kit push` (it drops RLS policy conditions). Run `npm run db:audit` after every migration.
- `npx shadcn@latest add <component>`: add UI components (never hand-write what shadcn has)

## Rules
- Data access: user-facing reads/writes go through the Supabase client (`src/lib/supabase/{server,client}.ts`) so RLS applies. `src/db` (Drizzle) connects as `postgres` and BYPASSES RLS: server-only, check permissions yourself.
- Every new table: RLS policies in `src/db/schema.ts` (see `notes` example), one per operation, `to authenticated`. Never authorize from `user_metadata`.
- Secrets (`DATABASE_URL`, `ANTHROPIC_API_KEY`) are server-only: never `NEXT_PUBLIC_`, never imported in `"use client"` files.
- Env vars: add to `.env.example` and `src/lib/env.ts`.
- Animations: `motion/react`. Icons: `lucide-react`.
- Keep it simple: no new dependencies or abstractions without a reason in decisions.md.
- Git (all agents and tools): never mention AI in commits, PRs, branch names, tags or comments. No `Co-Authored-By` trailers, no "Generated with ..." lines, no AI names or emoji signatures. Author is the human committing.

## Decisions
@docs/decisions.md
