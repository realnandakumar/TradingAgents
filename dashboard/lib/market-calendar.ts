/** IST calendar helpers for Tech Desk daily ops — weekends + NSE holidays. */

import { isNseHolidayIso } from "@/lib/nse-holidays";

export function todayIstIso(): string {
  return new Date().toLocaleDateString("en-CA", { timeZone: "Asia/Kolkata" });
}

export function isTradingDayIst(isoDate?: string): boolean {
  const iso =
    isoDate ??
    new Date().toLocaleDateString("en-CA", { timeZone: "Asia/Kolkata" });
  const wd = new Date(`${iso}T12:00:00+05:30`).toLocaleDateString("en-US", {
    timeZone: "Asia/Kolkata",
    weekday: "short",
  });
  if (wd === "Sat" || wd === "Sun") return false;
  return !isNseHolidayIso(iso);
}

export function formatIstWhen(iso: string | null): string {
  if (!iso) return "Never";
  try {
    return new Date(iso).toLocaleString("en-IN", { timeZone: "Asia/Kolkata" });
  } catch {
    return iso;
  }
}
