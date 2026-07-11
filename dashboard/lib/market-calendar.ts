/** IST calendar helpers for Tech Desk daily ops (weekday = trading day, same as Python is_nse_trading_day). */

export function todayIstIso(): string {
  return new Date().toLocaleDateString("en-CA", { timeZone: "Asia/Kolkata" });
}

export function isTradingDayIst(): boolean {
  const wd = new Date().toLocaleDateString("en-US", {
    timeZone: "Asia/Kolkata",
    weekday: "short",
  });
  return wd !== "Sat" && wd !== "Sun";
}

export function formatIstWhen(iso: string | null): string {
  if (!iso) return "Never";
  try {
    return new Date(iso).toLocaleString("en-IN", { timeZone: "Asia/Kolkata" });
  } catch {
    return iso;
  }
}
