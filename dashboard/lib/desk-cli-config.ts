export type DeskActionVariant = "primary" | "secondary";

export interface DeskAction {
  id: string;
  label: string;
  cliArgs: string[];
  needsTicker?: boolean;
  /** Pass ticker as `--flag VALUE` (e.g. tech-analyze --ticker). */
  tickerAsOption?: boolean;
  tickerFlag?: string;
  description?: string;
  variant?: DeskActionVariant;
  requiresApiKey?: boolean;
  destructive?: boolean;
  supportsForce?: boolean;
  /** UI grouping for Tech Desk panel. */
  group?: "analyze" | "desk";
}

export interface DeskConfig {
  id: string;
  label: string;
  actions: DeskAction[];
}

const DESK_CONFIGS: DeskConfig[] = [
  {
    id: "swing",
    label: "Swing Desk",
    actions: [
      { id: "screener", label: "Run screener", cliArgs: ["swing"], variant: "secondary", description: "Screen swing candidates" },
      { id: "daily", label: "Daily run", cliArgs: ["swing-daily", "--yes"], variant: "primary", description: "Exits, opens, and daily portfolio job" },
      { id: "report", label: "Report", cliArgs: ["swing-report"], variant: "secondary" },
      { id: "approve", label: "Approve replacements", cliArgs: ["swing-approve", "--yes"], variant: "secondary" },
    ],
  },
  {
    id: "momentum",
    label: "Momentum Desk",
    actions: [
      { id: "screener", label: "Run screener", cliArgs: ["momentum"], variant: "secondary" },
      { id: "daily", label: "Daily run", cliArgs: ["momentum-daily", "--yes"], variant: "primary" },
      { id: "report", label: "Report", cliArgs: ["momentum-report"], variant: "secondary" },
      { id: "approve", label: "Approve replacements", cliArgs: ["momentum-approve", "--yes"], variant: "secondary" },
    ],
  },
  {
    id: "nss",
    label: "NSS Desk",
    actions: [
      { id: "screener", label: "Run screener", cliArgs: ["nss"], variant: "secondary" },
      { id: "daily", label: "Daily run", cliArgs: ["nss-daily", "--yes"], variant: "primary" },
      { id: "report", label: "Report", cliArgs: ["nss-report"], variant: "secondary" },
      { id: "approve", label: "Approve replacements", cliArgs: ["nss-approve", "--yes"], variant: "secondary" },
      { id: "diagnostics", label: "Diagnostics", cliArgs: ["nss-diagnostics"], variant: "secondary" },
    ],
  },
  {
    id: "supertrend-rsi",
    label: "SuperTrend RSI Desk",
    actions: [
      { id: "screener", label: "Run screener", cliArgs: ["supertrend-rsi"], variant: "secondary" },
      { id: "daily", label: "Daily run", cliArgs: ["supertrend-rsi-daily", "--yes"], variant: "primary" },
      { id: "report", label: "Report", cliArgs: ["supertrend-rsi-report"], variant: "secondary" },
      { id: "approve", label: "Approve replacements", cliArgs: ["supertrend-rsi-approve", "--yes"], variant: "secondary" },
      { id: "explain", label: "Explain ticker", cliArgs: ["supertrend-rsi-explain"], needsTicker: true, variant: "secondary" },
    ],
  },
  {
    id: "trama",
    label: "TRAMA Desk",
    actions: [
      { id: "screener", label: "Run screener", cliArgs: ["trama"], variant: "secondary" },
      { id: "daily", label: "Daily run", cliArgs: ["trama-daily", "--yes"], variant: "primary" },
      { id: "report", label: "Report", cliArgs: ["trama-report"], variant: "secondary" },
      { id: "approve", label: "Approve replacements", cliArgs: ["trama-approve", "--yes"], variant: "secondary" },
      { id: "explain", label: "Explain ticker", cliArgs: ["trama-explain"], needsTicker: true, variant: "secondary" },
    ],
  },
  {
    id: "gap-fill",
    label: "Gap Fill Desk",
    actions: [
      { id: "screener", label: "Run screener", cliArgs: ["gap-fill"], variant: "secondary" },
      { id: "daily", label: "Daily run", cliArgs: ["gap-fill-daily", "--yes"], variant: "primary" },
      { id: "report", label: "Report", cliArgs: ["gap-fill-report"], variant: "secondary" },
      { id: "approve", label: "Approve replacements", cliArgs: ["gap-fill-approve", "--yes"], variant: "secondary" },
      { id: "explain", label: "Explain ticker", cliArgs: ["gap-fill-explain"], needsTicker: true, variant: "secondary" },
    ],
  },
  {
    id: "nw-envelope",
    label: "NW Envelope Desk",
    actions: [
      { id: "screener", label: "Run screener", cliArgs: ["nw-envelope"], variant: "secondary" },
      { id: "daily", label: "Daily run", cliArgs: ["nw-envelope-daily", "--yes"], variant: "primary" },
      { id: "report", label: "Report", cliArgs: ["nw-envelope-report"], variant: "secondary" },
      { id: "approve", label: "Approve replacements", cliArgs: ["nw-envelope-approve", "--yes"], variant: "secondary" },
      { id: "explain", label: "Explain ticker", cliArgs: ["nw-envelope-explain"], needsTicker: true, variant: "secondary" },
    ],
  },
  {
    id: "pattern-forecast",
    label: "Pattern Forecast Desk",
    actions: [
      { id: "screener", label: "Run screener", cliArgs: ["pattern-forecast"], variant: "secondary" },
      { id: "daily", label: "Daily run", cliArgs: ["pattern-forecast-daily", "--yes"], variant: "primary" },
      { id: "report", label: "Report", cliArgs: ["pattern-forecast-report"], variant: "secondary" },
      { id: "approve", label: "Approve replacements", cliArgs: ["pattern-forecast-approve", "--yes"], variant: "secondary" },
    ],
  },
  {
    id: "tech-desk",
    label: "Tech Desk",
    actions: [
      {
        id: "analyze-watchlist",
        label: "Analyze entire watchlist",
        cliArgs: ["tech-analyze", "--watchlist"],
        variant: "secondary",
        description:
          "Run quick technical analysis (Market Analyst only) for every ticker in your watchlist. Saves reports under tech_reports/TICKER/DATE/. Uses API credits (~1–2 min per ticker).",
        requiresApiKey: true,
        group: "analyze",
      },
      {
        id: "analyze-stale",
        label: "Analyze stale & missing",
        cliArgs: [],
        variant: "secondary",
        description:
          "Re-run tech-analyze only for watchlist tickers whose saved report is missing or older than 14 days. Does not add tickers to the watchlist.",
        requiresApiKey: true,
        group: "analyze",
      },
      {
        id: "analyze-ticker",
        label: "Analyze one ticker",
        cliArgs: ["tech-analyze"],
        tickerAsOption: true,
        tickerFlag: "--ticker",
        needsTicker: true,
        variant: "secondary",
        description:
          "Same as watchlist analyze but for a single symbol you enter below. Saves one report to tech_reports/. Does not add the ticker to your watchlist.",
        requiresApiKey: true,
        group: "analyze",
      },
      {
        id: "process",
        label: "Process zones",
        cliArgs: ["tech-desk-process"],
        variant: "secondary",
        requiresApiKey: true,
        group: "desk",
        description:
          "Read saved tech-analyze reports for watchlist tickers (≤14 days old), run the AI portfolio manager, open new trades or queue pullback zones. Portfolio replacements require explicit Apply.",
      },
      {
        id: "process-apply",
        label: "Apply replacements",
        cliArgs: ["tech-desk-apply-process"],
        variant: "secondary",
        destructive: true,
        requiresApiKey: false,
        group: "desk",
        description:
          "Execute queued portfolio replacements from the latest Process run (foreclose weakest + open stronger). Review the process log first.",
      },
      {
        id: "daily",
        label: "Daily run",
        cliArgs: ["tech-desk-daily"],
        variant: "primary",
        supportsForce: true,
        group: "desk",
        description:
          "Rules-only daily job: stop loss, targets, time exits, and pending zone fills. No LLM cost — run on each trading day after the close.",
      },
      {
        id: "review",
        label: "Review (read only)",
        cliArgs: ["tech-desk-review"],
        variant: "secondary",
        requiresApiKey: true,
        group: "desk",
        description:
          "Weekly LLM review memo on open positions. Shows recommendations only — does not change the book.",
      },
      {
        id: "review-apply",
        label: "Review & apply",
        cliArgs: ["tech-desk-review", "--apply"],
        variant: "secondary",
        requiresApiKey: true,
        destructive: true,
        group: "desk",
        description:
          "Run the weekly review and execute its closes and stop raises on the paper book. Read the memo first before applying.",
      },
      {
        id: "report",
        label: "Portfolio report",
        cliArgs: ["tech-desk-report"],
        variant: "secondary",
        group: "desk",
        description:
          "Print closed-trade stats (win rate, avg R, P&L by exit type) and summaries from the latest process and daily logs.",
      },
    ],
  },
  {
    id: "gap-screener",
    label: "Gap Screener",
    actions: [
      { id: "refresh", label: "Refresh screener", cliArgs: ["gap-fill"], variant: "primary", description: "Run gap-fill screener snapshot" },
    ],
  },
  {
    id: "chart-patterns",
    label: "Chart Patterns",
    actions: [
      { id: "refresh", label: "Refresh screener", cliArgs: ["chart-patterns"], variant: "primary" },
    ],
  },
  {
    id: "positions",
    label: "RS Paper Positions",
    actions: [
      { id: "screen", label: "Run screen", cliArgs: ["screen", "--yes"], variant: "primary", description: "Screen and paper-trade top picks" },
      { id: "paper", label: "Refresh positions", cliArgs: ["paper"], variant: "secondary", description: "Mark to market and refresh snapshot" },
    ],
  },
  {
    id: "screens",
    label: "Screen History",
    actions: [
      { id: "screen", label: "Run screen", cliArgs: ["screen", "--yes"], variant: "primary", description: "Screen and paper-trade top picks" },
    ],
  },
];

export function getDeskConfig(deskId: string): DeskConfig | undefined {
  return DESK_CONFIGS.find((d) => d.id === deskId);
}

export function getDeskAction(deskId: string, actionId: string): DeskAction | undefined {
  return getDeskConfig(deskId)?.actions.find((a) => a.id === actionId);
}

export function formatCliCommand(
  cliArgs: string[],
  ticker?: string,
  opts?: { tickerAsOption?: boolean; tickerFlag?: string; force?: boolean },
): string {
  const parts = ["tradingagents", ...cliArgs];
  if (opts?.force) parts.push("--force");
  if (ticker?.trim()) {
    if (opts?.tickerAsOption) {
      parts.push(opts.tickerFlag ?? "--ticker", ticker.trim().toUpperCase());
    } else {
      parts.push(ticker.trim().toUpperCase());
    }
  }
  return parts.join(" ");
}
