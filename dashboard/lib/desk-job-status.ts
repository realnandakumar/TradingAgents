import { getDeskAction, getDeskConfig } from "@/lib/desk-cli-config";
import type { DeskCliJobProgress } from "@/lib/desk-cli-server";

export type JobPhase = "idle" | "running" | "success" | "failed";

export interface PlainJobStatus {
  phase: JobPhase;
  headline: string;
  detail: string;
  percent: number;
}

const ACTION_START_MESSAGES: Record<string, string> = {
  daily: "Running the end-of-day portfolio job — checking exits, opens, and pending replacements",
  screener: "Screening the NSE universe for trade candidates",
  approve: "Approving queued portfolio replacement proposals",
  report: "Generating portfolio report",
  diagnostics: "Running NSS health diagnostics",
  explain: "Explaining screener signal for the ticker",
  refresh: "Refreshing screener snapshot",
  screen: "Screening relative-strength picks and opening paper trades",
  paper: "Refreshing RS paper positions and mark-to-market",
  "all-dailies": "Downloading shared price data and syncing every strategy paper book",
  "all-screeners": "Downloading shared price data and running all technical screeners",
  "rs-screen": "Screening top relative-strength NSE picks for paper trading",
  "rs-paper": "Updating RS paper book with latest prices",
  "analyze-watchlist": "Running AI technical analysis on your entire watchlist",
  "analyze-stale": "Re-analyzing watchlist tickers with stale or missing reports",
  "analyze-ticker": "Running AI technical analysis on one ticker",
  process: "AI portfolio manager reading reports and opening trades or zone orders",
  "process-apply": "Applying queued portfolio replacements on the Tech Desk book",
  review: "Running weekly LLM review on open Tech Desk positions",
  "review-apply": "Applying review recommendations — closes and stop updates",
};

const LINE_HINTS: [RegExp, string][] = [
  [/Downloading .* history/i, "Downloading market price data for the NSE universe"],
  [/Got usable history/i, "Price download complete — starting desk workflows"],
  [/Syncing paper books/i, "Updating strategy paper portfolios"],
  [/Running .* screener/i, "Screening stocks for candidates"],
  [/Running .* daily/i, "Running daily portfolio update"],
  [/Tech Desk daily/i, "Checking stop exits, targets, and pullback zone fills"],
  [/screening/i, "Scanning charts and ranking candidates"],
  [/exits?:/i, "Processing position exits"],
  [/opened:/i, "Opening new paper positions"],
  [/pending/i, "Queueing replacement proposals for your approval"],
  [/approve/i, "Processing replacement approvals"],
  [/analyze/i, "Running technical analysis reports"],
  [/NSE Swing/i, "Swing desk workflow in progress"],
  [/pattern-forecast/i, "Pattern forecast desk workflow in progress"],
  [/Done\./i, "Wrapping up"],
];

function lastOutputLine(lines: string[]): string | null {
  for (let i = lines.length - 1; i >= 0; i--) {
    const line = lines[i].replace(/^\[err\]\s*/, "").trim();
    if (line.length > 0) return line;
  }
  return null;
}

function friendlyLine(raw: string): string {
  for (const [pattern, message] of LINE_HINTS) {
    if (pattern.test(raw)) return message;
  }
  if (raw.length > 120) return `${raw.slice(0, 117)}…`;
  return raw;
}

function defaultStartMessage(deskId: string, actionId: string): string {
  const action = getDeskAction(deskId, actionId);
  const desk = getDeskConfig(deskId);
  const preset = ACTION_START_MESSAGES[actionId];
  if (preset) return preset;
  if (action?.description) return action.description;
  const label = action?.label ?? actionId;
  const deskLabel = desk?.label ?? deskId;
  return `${label} on ${deskLabel}`;
}

export function describeDeskJob(
  deskId: string,
  actionId: string,
  progress: DeskCliJobProgress | null | undefined,
): PlainJobStatus {
  const action = getDeskAction(deskId, actionId);
  const desk = getDeskConfig(deskId);
  const actionLabel = action?.label ?? actionId;
  const deskLabel = desk?.label ?? deskId;

  if (!progress || progress.status === "pending") {
    return {
      phase: "running",
      headline: `${deskLabel} — ${actionLabel}`,
      detail: defaultStartMessage(deskId, actionId),
      percent: progress?.percent ?? 2,
    };
  }

  if (progress.status === "completed") {
    const tail = lastOutputLine(progress.lines);
    return {
      phase: "success",
      headline: `${actionLabel} finished`,
      detail: tail ? friendlyLine(tail) : `${deskLabel} job completed successfully`,
      percent: 100,
    };
  }

  if (progress.status === "failed") {
    return {
      phase: "failed",
      headline: `${actionLabel} failed`,
      detail:
        progress.error?.trim() ||
        (lastOutputLine(progress.lines)
          ? friendlyLine(lastOutputLine(progress.lines)!)
          : "The command exited with an error"),
      percent: 100,
    };
  }

  const tail = lastOutputLine(progress.lines);
  return {
    phase: "running",
    headline: `${deskLabel} — ${actionLabel}`,
    detail: tail ? friendlyLine(tail) : defaultStartMessage(deskId, actionId),
    percent: progress.percent,
  };
}
