import fs from "fs";
import os from "os";
import path from "path";

import { getPortfolioDeskSummaries } from "@/lib/command-center-server";
import { checkLlmApiKey } from "@/lib/env-server";
import { readCustomTickers } from "@/lib/custom-tickers-server";
import { gapFillBookPath, readGapFillBook } from "@/lib/gap-fill-server";
import { readGapScreenerSnapshot } from "@/lib/gap-screener-server";
import { listRecentJobs } from "@/lib/desk-cli-server";
import { getLatestPaper, getLatestScreen, paperSnapshotPath, screensPath } from "@/lib/paper-server";
import {
  countStaleSymbols,
  describeSyncGap,
  expectedCompletedSessionIst,
  maxLastBarFromManifest,
  pricesDbPath,
  readLatestEodReport,
  readManifest,
} from "@/lib/price-sync-status";
import { swingBookPath } from "@/lib/swing-server";
import { techDeskBookPath } from "@/lib/tech-desk-server";

export interface DataHealthRow {
  id: string;
  label: string;
  path: string;
  exists: boolean;
  updatedAt: string | null;
  detail: string;
}

export interface CrossDeskPnl {
  deskId: string;
  label: string;
  href: string;
  openCount: number;
  closedCount: number;
  realizedPnl: number | null;
}

function fileMtime(filePath: string): string | null {
  try {
    if (!fs.existsSync(filePath)) return null;
    return new Date(fs.statSync(filePath).mtimeMs).toISOString();
  } catch {
    return null;
  }
}

export function getDataHealthRows(): DataHealthRow[] {
  const home = process.env.TRADINGAGENTS_HOME ?? path.join(os.homedir(), ".tradingagents");
  const cacheDir = process.env.TRADINGAGENTS_CACHE_DIR ?? path.join(home, "cache");
  const pricesDb = pricesDbPath();
  const manifestPath = path.join(cacheDir, "manifest.json");
  const manifest = readManifest();
  const expectedSession = expectedCompletedSessionIst();
  const staleCount = countStaleSymbols(manifest);
  const maxLastBar = maxLastBarFromManifest(manifest);
  const latestEod = readLatestEodReport();
  const syncWarning = describeSyncGap(maxLastBar, expectedSession, latestEod?.sync);
  const customTickers = readCustomTickers();

  const paper = getLatestPaper();
  const screen = getLatestScreen();
  const gapSnap = readGapScreenerSnapshot();
  const gapBook = readGapFillBook();

  const rows: DataHealthRow[] = [
    {
      id: "paper",
      label: "RS paper snapshot",
      path: paperSnapshotPath(),
      exists: Boolean(paper),
      updatedAt: paper?.created_at ?? null,
      detail: paper ? `${paper.data.stats?.open_positions ?? 0} open` : "Missing",
    },
    {
      id: "screen",
      label: "Latest RS screen",
      path: screensPath(),
      exists: Boolean(screen),
      updatedAt: screen?.created_at ?? null,
      detail: screen ? `${screen.data.candidates.length} candidates` : "Missing",
    },
    {
      id: "swing",
      label: "Swing book",
      path: swingBookPath(),
      exists: fs.existsSync(swingBookPath()),
      updatedAt: fileMtime(swingBookPath()),
      detail: "Portfolio desk",
    },
    {
      id: "tech-desk",
      label: "Tech Desk book",
      path: techDeskBookPath(),
      exists: fs.existsSync(techDeskBookPath()),
      updatedAt: fileMtime(techDeskBookPath()),
      detail: "LLM desk",
    },
    {
      id: "gap-fill",
      label: "Gap Fill desk",
      path: gapFillBookPath(),
      exists: Boolean(gapBook) || Boolean(gapSnap),
      updatedAt: gapBook?.updated_at ?? gapSnap?.updated_at ?? null,
      detail: [
        gapSnap ? `${gapSnap.picks.length} screener picks` : "no screener snapshot",
        gapBook
          ? `${gapBook.positions.filter((p) => p.status === "open").length} open in book`
          : "no book",
      ].join(" · "),
    },
    {
      id: "desk-cli",
      label: "Desk CLI jobs",
      path: path.join(home, "desk_cli", "jobs"),
      exists: fs.existsSync(path.join(home, "desk_cli", "jobs")),
      updatedAt: null,
      detail: `${listRecentJobs(50).length} recent job(s)`,
    },
    {
      id: "prices-db",
      label: "prices.db (SQLite)",
      path: pricesDb,
      exists: fs.existsSync(pricesDb),
      updatedAt: fileMtime(pricesDb),
      detail: maxLastBar
        ? `Latest bar ${maxLastBar} · ${Object.keys(manifest.symbols ?? {}).length} symbols in manifest`
        : `${Object.keys(manifest.symbols ?? {}).length} symbols in manifest`,
    },
    {
      id: "eod-run",
      label: "Last EOD pipeline",
      path: manifestPath,
      exists: Boolean(manifest.last_eod_run),
      updatedAt: manifest.last_eod_run ?? null,
      detail: manifest.last_eod_run
        ? latestEod?.sync && typeof latestEod.sync.synced === "number"
          ? `Ran ${manifest.last_eod_run} · sync ${latestEod.sync.synced} ok / ${latestEod.sync.skipped} skip / ${latestEod.sync.failed ?? 0} fail`
          : `Ran ${manifest.last_eod_run}`
        : "Not run today",
    },
    {
      id: "custom-tickers",
      label: "Custom tickers",
      path: customTickers.path,
      exists: fs.existsSync(customTickers.path),
      updatedAt: fileMtime(customTickers.path),
      detail: `${customTickers.symbols.length} symbol(s)`,
    },
    {
      id: "stale-prices",
      label: "Stale price symbols",
      path: manifestPath,
      exists: fs.existsSync(manifestPath),
      updatedAt: fileMtime(manifestPath),
      detail: `${staleCount} symbol(s) >2 days behind`,
    },
    ...(syncWarning
      ? [
          {
            id: "price-sync-gap",
            label: "Price sync gap",
            path: latestEod?.path ?? manifestPath,
            exists: true,
            updatedAt: latestEod?.completed_at ?? null,
            detail: syncWarning,
          } satisfies DataHealthRow,
        ]
      : []),
  ];

  return rows;
}

export function getCrossDeskPnl(): CrossDeskPnl[] {
  return getPortfolioDeskSummaries().map((d) => {
    // Summaries only have open count — read closed from books via command-center readers
    return {
      deskId: d.id,
      label: d.label,
      href: d.href,
      openCount: d.openCount ?? 0,
      closedCount: 0,
      realizedPnl: null,
    };
  });
}

export function getDataHealthMeta() {
  return {
    apiKey: checkLlmApiKey(),
    tradingagentsHome:
      process.env.TRADINGAGENTS_HOME ?? path.join(os.homedir(), ".tradingagents"),
  };
}
