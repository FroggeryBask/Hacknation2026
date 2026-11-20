# Decisions (current only)

<!-- One line per decision: `- [area] decision (why)`. When a decision changes, EDIT or DELETE
     its line; don't append a correction. Git history is the archive. Keep under ~40 lines. -->

- [stack] Next.js + Supabase + Drizzle + shadcn/Tailwind + Motion (one TS codebase, fast deploy on Vercel)
- [db] Supabase project settings: auto-RLS + auto-grant on new tables (tables are locked until a policy exists)
- [db] Drizzle for schema/migrations and trusted server queries; Supabase client for user-scoped access (RLS)
- [db] Schema changes via `db:generate` + `db:migrate` only; `drizzle-kit push` is banned (v0.45 created policies without conditions = open to all logged-in users)
- [auth] Email/password only, email confirmation on, anonymous sign-ins off
- [tooling] Biome (not ESLint/Prettier); Python scripts via uv in `scripts/`; lefthook git hooks
- [git] No AI attribution in commits/PRs (team rule): disabled in .claude/settings.json, blocked by lefthook commit-msg hook
