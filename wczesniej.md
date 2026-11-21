# Zrobione przed hackathonem

Stan na commit `2f872d7`. Sam szkielet projektu i konfiguracja, bez logiki aplikacji (strona główna to domyślny ekran Create Next App).

## Technologie
- Next.js 16 (App Router, `src/`), React 19, TypeScript
- Tailwind CSS 4 + shadcn/ui (na razie tylko `button`), lucide-react, Motion
- Supabase (Postgres + Auth: tylko email/hasło, z potwierdzeniem maila)
- Drizzle ORM + drizzle-kit (migracje)
- Python (uv) do skryptów sprawdzających, Biome (lint/format), lefthook (git hooki)
- Deploy na Vercel

## Konfiguracja
- Klienty Supabase (server/client/middleware) w `src/lib/supabase/`, walidacja env w `src/lib/env.ts`, `.env.example`
- Drizzle: `src/db/`, przykładowa tabela `notes` z politykami RLS, migracja `drizzle/0000_init.sql`
- Endpoint `GET /api/health`
- Skrypty: `npm run check` (biome, tsc, ruff, audyt RLS), `smoke`, `db:audit`, `db:generate`/`db:migrate`
- Git hooki: biome/ruff przy commicie, `check` przed pushem, blokada atrybucji AI w commitach
- Claude Code: `CLAUDE.md`, `docs/decisions.md`, agent `reviewer`, komenda `/ship`, hook weryfikujący, MCP Supabase
- README z instrukcją konfiguracji dla zespołu
