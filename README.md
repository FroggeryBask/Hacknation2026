# Hacknation2026

Live: https://hacknation2026-xi.vercel.app

Next.js 16 · TypeScript · Supabase · Drizzle ORM · shadcn/ui + Tailwind · lucide-react · Motion · Vercel

## Setup

**Install once:** Node.js 22+, git, and [uv](https://docs.astral.sh/uv/) (`curl -LsSf https://astral.sh/uv/install.sh | sh`)

```bash
git clone https://github.com/FroggeryBask/Hacknation2026.git
cd Hacknation2026
npm install
cp .env.example .env.local
```

Then:

```bash
npm run check   # should be all green
npm run dev     # http://localhost:3000
```

## Commands

| Command | What it does |
|---|---|
| `npm run dev` | Start the dev server |
| `npm run check` | Lint, types, Python scripts, database security audit |
| `npm run smoke [url]` | Check that key pages respond (defaults to localhost) |
| `npm run db:generate` | Create a migration from `src/db/schema.ts` |
| `npm run db:migrate` | Apply migrations to the database |
| `npm run db:audit` | Check every table is protected by RLS |
| `npx shadcn@latest add <name>` | Add a UI component |

## Rules

- Pushing to `main` deploys to the live site immediately, so work on a branch for anything risky.
- `npm run check` runs automatically before every push and blocks the push if it fails.
- Schema changes: edit `src/db/schema.ts` → `npm run db:generate` → `npm run db:migrate` → `npm run db:audit`. **Never** use `drizzle-kit push`.
- Every new table needs RLS policies (see the `notes` example in `src/db/schema.ts`).
- We share one database: only one person makes schema changes at a time, and always pull `main` before `db:generate`.
- No AI attribution in commits. A git hook rejects them.
- Never commit `.env.local` or paste keys anywhere public.

## Using Claude Code?

The project rules (`CLAUDE.md`), hooks and the `/ship` command load automatically. The first time it asks to connect the Supabase connection in `.mcp.json`, log in with your Supabase account.
