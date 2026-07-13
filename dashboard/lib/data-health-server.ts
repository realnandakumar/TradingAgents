import fs from "fs";
import os from "os";
import path from "path";

import { getPortfolioDeskSummaries } from "@/lib/command-center-server";
import { checkLlmApiKey } from "@/lib/env-server";
import { gapFillBookPath, readGapFillBook } from "@/lib/gap-fill-server";
import { readGapScreenerSnapshot } from "@/lib/gap-screener-server";
import { listRecentJobs } from "@/lib/desk-cli-server";
import { getLatestPaper, getLatestScreen, paperSnapshotPath, screensPath } from "@/lib/paper-server";
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
