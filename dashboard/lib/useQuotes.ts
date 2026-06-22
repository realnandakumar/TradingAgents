"use client";

import { useEffect, useState } from "react";

export interface Quote {
  price: number | null;
  prevClose: number | null;
  changePct: number | null;
}

export type QuoteMap = Record<string, Quote>;

// Poll /api/quotes for the given symbols. Empty list → no fetch (so callers can
// call this unconditionally and pass [] to disable, keeping hook rules happy).
export function useQuotes(symbols: string[], intervalMs = 45000) {
  const [quotes, setQuotes] = useState<QuoteMap>({});
  const [loading, setLoading] = useState(false);
  const key = symbols.join(",");

  useEffect(() => {
    if (!key) {
      setQuotes({});
      return;
    }
    let active = true;
    const load = async () => {
      setLoading(true);
      try {
        const res = await fetch(`/api/quotes?symbols=${encodeURIComponent(key)}`, {
          cache: "no-store",
        });
        if (active && res.ok) setQuotes(await res.json());
      } catch {
        /* keep last good values */
      } finally {
        if (active) setLoading(false);
      }
    };
    load();
    const id = setInterval(load, intervalMs);
    return () => {
      active = false;
      clearInterval(id);
    };
  }, [key, intervalMs]);

  return { quotes, loading };
}
