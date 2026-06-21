import { getSupabase } from "./supabase";
import type { PaperSnapshot, ScreenSnapshot, SnapshotRow } from "./types";

// Always fetch fresh — the dashboard is low-traffic and data updates out-of-band.
export const revalidate = 0;

export async function getLatestPaper(): Promise<SnapshotRow<PaperSnapshot> | null> {
  const sb = getSupabase();
  if (!sb) return null;
  const { data, error } = await sb
    .from("snapshots")
    .select("id, kind, created_at, data")
    .eq("kind", "paper")
    .order("created_at", { ascending: false })
    .limit(1);
  if (error || !data || data.length === 0) return null;
  return data[0] as SnapshotRow<PaperSnapshot>;
}

export async function getScreens(limit = 30): Promise<SnapshotRow<ScreenSnapshot>[]> {
  const sb = getSupabase();
  if (!sb) return [];
  const { data, error } = await sb
    .from("snapshots")
    .select("id, kind, created_at, data")
    .eq("kind", "screen")
    .order("created_at", { ascending: false })
    .limit(limit);
  if (error || !data) return [];
  return data as SnapshotRow<ScreenSnapshot>[];
}

export async function getLatestScreen(): Promise<SnapshotRow<ScreenSnapshot> | null> {
  const screens = await getScreens(1);
  return screens[0] ?? null;
}
