import { defineConfig } from "drizzle-kit";

try {
  process.loadEnvFile(".env.local");
} catch {
  // no .env.local (e.g. CI): rely on real environment variables
}

const url = process.env.DATABASE_URL;
if (!url) throw new Error("DATABASE_URL is not set in .env.local");

export default defineConfig({
  schema: "./src/db/schema.ts",
  out: "./drizzle",
  dialect: "postgresql",
  casing: "snake_case",
  dbCredentials: { url },
  // Manage RLS policies from schema.ts; Supabase's built-in roles already exist.
  entities: { roles: { provider: "supabase" } },
  schemaFilter: ["public"],
});
