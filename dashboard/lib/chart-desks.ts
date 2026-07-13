export interface ChartDeskMeta {
  id: string;
  label: string;
  color: string;
  href: string;
}

export const CHART_DESK_META: ChartDeskMeta[] = [
  { id: "swing", label: "Swing", color: "#5b8cff", href: "/swing" },
  { id: "momentum", label: "Momentum", color: "#f59e0b", href: "/momentum" },
  { id: "nss", label: "NSS", color: "#a78bfa", href: "/nss" },
  { id: "supertrend-rsi", label: "ST+RSI", color: "#22d3ee", href: "/supertrend-rsi" },
  { id: "trama", label: "TRAMA", color: "#34d399", href: "/trama" },
  { id: "gap-fill", label: "Gap fill", color: "#fb923c", href: "/gap-fill" },
  { id: "nw-envelope", label: "NW Env", color: "#e879f9", href: "/nw-envelope" },
  { id: "pattern-forecast", label: "Pattern", color: "#94a3b8", href: "/pattern-forecast" },
  { id: "chart-patterns", label: "Patterns", color: "#fbbf24", href: "/chart-patterns" },
  { id: "tech-desk", label: "Tech Desk", color: "#818cf8", href: "/tech-desk" },
];
