// Public env vars. Must be referenced literally so Next.js inlines them in the browser bundle.
function required(name: string, value: string | undefined): string {
  if (!value) throw new Error(`Missing env var ${name} (see .env.example)`);
  return value;
}

export const SUPABASE_URL = required(
  "NEXT_PUBLIC_SUPABASE_URL",
  process.env.NEXT_PUBLIC_SUPABASE_URL,
);
export const SUPABASE_PUBLISHABLE_KEY = required(
  "NEXT_PUBLIC_SUPABASE_PUBLISHABLE_KEY",
  process.env.NEXT_PUBLIC_SUPABASE_PUBLISHABLE_KEY,
);
