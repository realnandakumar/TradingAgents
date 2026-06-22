import { createClient, SupabaseClient } from "@supabase/supabase-js";

// Reads use the public anon key (safe to expose). The Python side uses the
// service key to write. Returns null when env vars are missing so the UI can
// render a friendly setup screen instead of crashing.
// Accept the new publishable key name (sb_publishable_...) or the legacy anon key.
function publicKey(): string | undefined {
  return (
    process.env.NEXT_PUBLIC_SUPABASE_PUBLISHABLE_KEY ||
    process.env.NEXT_PUBLIC_SUPABASE_ANON_KEY
  );
}

export function getSupabase(): SupabaseClient | null {
  const url = process.env.NEXT_PUBLIC_SUPABASE_URL;
  const key = publicKey();
  if (!url || !key) return null;
  return createClient(url, key, { auth: { persistSession: false } });
}

export const isConfigured = () =>
  Boolean(process.env.NEXT_PUBLIC_SUPABASE_URL && publicKey());
