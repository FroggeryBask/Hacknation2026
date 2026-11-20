import "server-only";
import { drizzle } from "drizzle-orm/postgres-js";
import postgres from "postgres";
import * as schema from "./schema";

// SERVER ONLY. This connects as the `postgres` role, which BYPASSES RLS.
// Check permissions yourself before every query here, or use the Supabase
// client (src/lib/supabase/server.ts) for user-scoped reads/writes so RLS applies.
const url = process.env.DATABASE_URL;
if (!url) throw new Error("DATABASE_URL is not set (see .env.example)");

// prepare: false is required for Supabase's transaction pooler (port 6543).
const client = postgres(url, { prepare: false });
export const db = drizzle(client, { schema, casing: "snake_case" });
