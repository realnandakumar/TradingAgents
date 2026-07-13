import { TickMarkType, type Time } from "lightweight-charts";

export const MARKET_TIMEZONE = "Asia/Kolkata";
export const CHART_LOCALE = "en-IN";

/** Map LW chart time to a Date anchored in IST (NSE session calendar). */
export function timeToMarketDate(time: Time): Date {
  if (typeof time === "number") {
    return new Date(time * 1000);
  }
  if (typeof time === "string") {
    return new Date(`${time}T12:00:00+05:30`);
  }
  const { year, month, day } = time;
  const m = String(month).padStart(2, "0");
  const d = String(day).padStart(2, "0");
  return new Date(`${year}-${m}-${d}T12:00:00+05:30`);
}

function istFormat(
  options: Intl.DateTimeFormatOptions,
  date: Date,
): string {
  return new Intl.DateTimeFormat(CHART_LOCALE, {
    timeZone: MARKET_TIMEZONE,
    ...options,
  }).format(date);
}

export function formatChartCrosshairTime(time: Time, intraday: boolean): string {
  const d = timeToMarketDate(time);
  if (intraday && typeof time === "number") {
    return istFormat(
      { day: "numeric", month: "short", hour: "2-digit", minute: "2-digit", hour12: false },
      d,
    );
  }
  return istFormat({ day: "numeric", month: "short", year: "numeric" }, d);
}

export function formatChartTickMark(
  time: Time,
  tickMarkType: TickMarkType,
  intraday: boolean,
): string | null {
  const d = timeToMarketDate(time);

  if (intraday && typeof time === "number") {
    switch (tickMarkType) {
      case TickMarkType.Year:
        return istFormat({ year: "numeric" }, d);
      case TickMarkType.Month:
        return istFormat({ month: "short" }, d);
      case TickMarkType.DayOfMonth:
        return istFormat({ day: "numeric", month: "short" }, d);
      case TickMarkType.Time:
      case TickMarkType.TimeWithSeconds:
      default:
        return istFormat({ hour: "2-digit", minute: "2-digit", hour12: false }, d);
    }
  }

  switch (tickMarkType) {
    case TickMarkType.Year:
      return istFormat({ year: "numeric" }, d);
    case TickMarkType.Month:
      return istFormat({ month: "short", year: "2-digit" }, d);
    default:
      return istFormat({ day: "numeric", month: "short" }, d);
  }
}

export function chartTimeLocaleOptions(intraday: boolean) {
  return {
    localization: {
      locale: CHART_LOCALE,
      timeFormatter: (time: Time) => formatChartCrosshairTime(time, intraday),
      dateFormat: intraday ? "dd MMM HH:mm" : "dd MMM yyyy",
    },
    timeScale: {
      tickMarkFormatter: (time: Time, tickMarkType: TickMarkType) =>
        formatChartTickMark(time, tickMarkType, intraday),
    },
  };
}
