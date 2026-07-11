"use client";

import { inr } from "@/lib/format";
import {
  daysInTrade,
  entryDate,
  purchaseNotional,
  slotBudget,
  withinBudget,
  type DeskPositionMeta,
} from "@/lib/desk-position";

/** Standard open-position meta columns: entry date, days, qty, purchase, budget, OK */
export function deskOpenMetaHeaders(): string[] {
  return ["ENT", "DAYS", "QTY", "BUY", "SLOT", "OK"];
}

export function DeskOpenMetaCells({ p }: { p: DeskPositionMeta }) {
  const ok = withinBudget(p);
  return (
    <>
      <td className="py-2 px-2 text-right tabular-nums text-muted whitespace-nowrap">{entryDate(p)}</td>
      <td className="py-2 px-2 text-right tabular-nums">{daysInTrade(p)}</td>
      <td className="py-2 px-2 text-right tabular-nums">{p.shares ?? "—"}</td>
      <td className="py-2 px-2 text-right tabular-nums">{inr(purchaseNotional(p))}</td>
      <td className="py-2 px-2 text-right tabular-nums text-muted">
        {slotBudget(p) ? inr(slotBudget(p)) : "—"}
      </td>
      <td
        className={`py-2 px-2 text-center text-[10px] whitespace-nowrap ${
          ok ? "text-bull" : "text-bear font-semibold"
        }`}
      >
        {ok ? "OK" : "OVER"}
      </td>
    </>
  );
}
