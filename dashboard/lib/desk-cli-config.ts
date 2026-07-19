export type DeskActionVariant = "primary" | "secondary";

export interface DeskAction {
  id: string;
  label: string;
  cliArgs: string[];
  /** Relative path from repo root for script-based jobs (e.g. scripts/run_all_daily_now.py). */
  scriptPath?: string;
  /** Extra CLI flags appended when running scriptPath (e.g. --force). */
  scriptArgs?: string[];
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
      { id: "daily", label: "Daily run", cliArgs: ["swing-daily"], variant: "primary", description: "Full exit at T1, no foreclosure, max 4 open names per sector" },
      { id: "report", label: "Report", cliArgs: ["swing-report"], variant: "secondary" },
    ],
  },
  {
    id: "momentum",
    label: "Momentum Desk",
    actions: [
      { id: "daily", label: "Daily run", cliArgs: ["momentum-daily"], variant: "primary", description: "Full exit at T1, no foreclosure, max 4 open names per sector" },
      { id: "report", label: "Report", cliArgs: ["momentum-report"], variant: "secondary" },
    ],
  },
  {
    id: "nss",
    label: "NSS Desk",
    actions: [
      { id: "daily", label: "Daily run", cliArgs: ["nss-daily"], variant: "primary", description: "Full exit at T1, no foreclosure, max 4 open names per sector" },
      { id: "report", label: "Report", cliArgs: ["nss-report"], variant: "secondary" },
      { id: "diagnostics", label: "Diagnostics", cliArgs: ["nss-diagnostics"], variant: "secondary" },
    ],
  },
  {
    id: "supertrend-rsi",
    label: "SuperTrend RSI Desk",
    actions: [
      { id: "daily", label: "Daily run", cliArgs: ["supertrend-rsi-daily"], variant: "primary", description: "T1 full exit, SELL closes longs, max 4/sector, 20 slots" },
      { id: "report", label: "Report", cliArgs: ["supertrend-rsi-report"], variant: "secondary" },
      { id: "explain", label: "Explain ticker", cliArgs: ["supertrend-rsi-explain"], needsTicker: true, variant: "secondary" },
    ],
  },
  {
    id: "trama",
    label: "TRAMA Desk",
    actions: [
      { id: "daily", label: "Daily run", cliArgs: ["trama-daily"], variant: "primary", description: "T1 full exit, SELL closes longs, max 4/sector, 20 slots" },
      { id: "report", label: "Report", cliArgs: ["trama-report"], variant: "secondary" },
      { id: "explain", label: "Explain ticker", cliArgs: ["trama-explain"], needsTicker: true, variant: "secondary" },
    ],
  },
  {
    id: "gap-fill",
    label: "Gap Fill Desk",
    actions: [
      { id: "daily", label: "Daily run", cliArgs: ["gap-fill-daily"], variant: "primary", description: "T1 full exit, UP closes longs, max 4/sector, 20 slots" },
      { id: "report", label: "Report", cliArgs: ["gap-fill-report"], variant: "secondary" },
      { id: "explain", label: "Explain ticker", cliArgs: ["gap-fill-explain"], needsTicker: true, variant: "secondary" },
    ],
  },
  {
    id: "nw-envelope",
    label: "NW Envelope Desk",
    actions: [
      { id: "daily", label: "Daily run", cliArgs: ["nw-envelope-daily"], variant: "primary", description: "T1 full exit, SELL closes longs, max 4/sector, 20 slots" },
      { id: "report", label: "Report", cliArgs: ["nw-envelope-report"], variant: "secondary" },
      { id: "explain", label: "Explain ticker", cliArgs: ["nw-envelope-explain"], needsTicker: true, variant: "secondary" },
    ],
  },
  {
    id: "pattern-forecast",
    label: "Pattern Forecast Desk",
    actions: [
      { id: "daily", label: "Daily run", cliArgs: ["pattern-forecast-daily"], variant: "primary", description: "Target full exit, max 4/sector, 20 slots, 5d hold" },
      { id: "report", label: "Report", cliArgs: ["pattern-forecast-report"], variant: "secondary" },
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
          "Read latest shared tech_reports for the current watchlist. Path 5: Tech Desk Trader (R:R) then script assemble opens/waits — no daily LLM PM. Weekly review manages opens. New entries watchlist-only; pending on Tech Desk book.",
      },
      {
        id: "daily",
        label: "Daily run",
        cliArgs: ["tech-desk-daily"],
        variant: "primary",
        group: "desk",
        description:
          "Rules-only daily job: stop loss, targets, time exits, and pending zone fills. No LLM cost — run each day after the close.",
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
    id: "chart-patterns",
    label: "Chart Patterns",
    actions: [],
  },
  {
    id: "candlesticks",
    label: "Candlesticks",
    actions: [
      {
        id: "screen",
        label: "Screen candlesticks",
        cliArgs: ["candlesticks"],
        variant: "primary",
        description:
          "Scan NSE universe for confirmed daily candlesticks (hammer, engulfing, doji). Also runs inside Sync now.",
      },
    ],
  },
  {
    id: "positions",
    label: "RS Desk",
    actions: [
      {
        id: "screen",
        label: "Screen + MA + PM",
        cliArgs: ["screen", "--yes"],
        variant: "primary",
        requiresApiKey: true,
        description:
          "RS shortlist → Market Analyst on top 10 (writes shared tech_reports/) → RS Desk PM opens/waits on the rs_desk book.",
      },
      {
        id: "process",
        label: "Process zones",
        cliArgs: ["rs-desk-process"],
        variant: "secondary",
        requiresApiKey: true,
        description:
          "Re-run RS Path 5 (Trader + script assemble) on latest shared reports for last screen ∪ open/pending (no new MA). No daily LLM PM. Pending on RS Desk book only.",
      },
      {
        id: "daily",
        label: "Daily run",
        cliArgs: ["rs-desk-daily"],
        variant: "primary",
        description:
          "Rules-only: stop / target / time exits and pending zone fills on the RS Desk book. No LLM.",
      },
      {
        id: "positions",
        label: "CLI positions",
        cliArgs: ["rs-desk-positions"],
        variant: "secondary",
        description: "Print RS Desk open positions and pending zones in the terminal.",
      },
    ],
  },
  {
    id: "screens",
    label: "Screen History",
    actions: [
      {
        id: "screen",
        label: "Screen + MA + PM",
        cliArgs: ["screen", "--yes"],
        variant: "primary",
        requiresApiKey: true,
        description:
          "RS shortlist → MA top 10 → RS Desk PM. History listed here; blotter on RS Desk (/positions).",
      },
      {
        id: "preview",
        label: "Preview screen (free)",
        cliArgs: ["screen", "--preview", "--yes"],
        variant: "secondary",
        description: "Ranked RS picks only — no Market Analyst, no PM, no token cost.",
      },
    ],
  },
  {
    id: "control-center",
    label: "Command Center",
    actions: [
      {
        id: "eod-sync-now",
        label: "Sync now",
        cliArgs: [],
        scriptPath: "scripts/run_eod_pipeline.py",
        scriptArgs: ["--force"],
        variant: "primary",
        description:
          "Manual full sync: refresh prices through last trading day, run all desk screeners and dailies",
      },
      {
        id: "eod-pipeline",
        label: "Run EOD pipeline",
        cliArgs: [],
        scriptPath: "scripts/run_eod_pipeline.py",
        variant: "secondary",
        supportsForce: true,
        description:
          "Same pipeline as Sync now, but skips price re-sync if already completed today",
      },
      {
        id: "all-dailies",
        label: "Run all dailies",
        cliArgs: [],
        scriptPath: "scripts/run_all_daily_now.py",
        variant: "secondary",
        description: "Shared download then sync all strategy paper books",
      },
      {
        id: "custom-ticker-add",
        label: "Add custom ticker",
        cliArgs: ["custom-ticker", "add"],
        needsTicker: true,
        variant: "secondary",
        description: "Add a ticker to the custom price-sync list and cache it",
      },
      {
        id: "rs-screen",
        label: "RS screen + MA + PM",
        cliArgs: ["screen", "--yes"],
        variant: "primary",
        requiresApiKey: true,
        description:
          "RS shortlist → MA top 10 (shared tech_reports) → RS Desk PM (separate book)",
      },
      {
        id: "rs-desk-daily",
        label: "RS Desk daily",
        cliArgs: ["rs-desk-daily"],
        variant: "secondary",
        description: "RS Desk rules-only exits and zone fills",
      },
    ],
  },
];

const PORTFOLIO_DESK_IDS = [
  "swing",
  "momentum",
  "nss",
  "supertrend-rsi",
  "trama",
  "gap-fill",
  "nw-envelope",
  "pattern-forecast",
  "positions",
  "tech-desk",
] as const;

export function listDeskConfigs(): DeskConfig[] {
  return DESK_CONFIGS;
}

export function listPortfolioDesks(): DeskConfig[] {
  return DESK_CONFIGS.filter((d) =>
    (PORTFOLIO_DESK_IDS as readonly string[]).includes(d.id),
  );
}

export function getDeskConfig(deskId: string): DeskConfig | undefined {
  return DESK_CONFIGS.find((d) => d.id === deskId);
}

export function getDeskActionLabel(deskId: string, actionId: string): string {
  const action = getDeskAction(deskId, actionId);
  const desk = getDeskConfig(deskId);
  if (action?.label && desk?.label) return `${desk.label} · ${action.label}`;
  return action?.label ?? `${deskId}/${actionId}`;
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
