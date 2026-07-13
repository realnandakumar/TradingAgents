import fs from "fs";
import os from "os";
import path from "path";

import type { ReplacementCandidate } from "@/lib/desk-replacements-types";

const TRADINGAGENTS_HOME =
  process.env.TRADINGAGENTS_HOME ?? path.join(os.homedir(), ".tradingagents");

interface PendingProposalRow {
  id?: string;
  proposed_at?: string;
  close_ticker?: string;
  close_stock_name?: string;
  close_reason?: string;
  close_score?: number;
  new_ticker?: string;
  new_stock_name?: string;
  approved?: boolean;
}

interface TechPendingRow {
  id?: string;
  foreclose?: string;
  open?: string;
  foreclose_entry?: number;
  foreclose_confidence?: number;
}

const PORTFOLIO_PENDING_PATHS: Record<string, string> = {
  swing: path.join(TRADINGAGENTS_HOME, "swing", "pending_replacements.json"),
  momentum: path.join(TRADINGAGENTS_HOME, "momentum", "pending_replacements.json"),
  nss: path.join(TRADINGAGENTS_HOME, "nss", "pending_replacements.json"),
  "supertrend-rsi": path.join(TRADINGAGENTS_HOME, "supertrend_rsi", "pending_replacements.json"),
  trama: path.join(TRADINGAGENTS_HOME, "trama", "pending_replacements.json"),
  "gap-fill": path.join(TRADINGAGENTS_HOME, "gap_fill", "pending_replacements.json"),
  "nw-envelope": path.join(TRADINGAGENTS_HOME, "nw_envelope", "pending_replacements.json"),
  "pattern-forecast": path.join(
    TRADINGAGENTS_HOME,
    "pattern_forecast",
    "pending_replacements.json",
  ),
};

function readJsonFile<T>(filePath: string): T | null {
  try {
    return JSON.parse(fs.readFileSync(filePath, "utf-8")) as T;
  } catch {
    return null;
  }
}

function mapPortfolioProposal(row: PendingProposalRow): ReplacementCandidate | null {
  if (!row.id || row.approved) return null;
  if (!row.close_ticker || !row.new_ticker) return null;
  return {
    id: row.id,
    closeTicker: row.close_ticker,
    closeName: row.close_stock_name ?? row.close_ticker,
    newTicker: row.new_ticker,
    newName: row.new_stock_name ?? row.new_ticker,
    proposedAt: row.proposed_at,
    closeReason: row.close_reason,
    closeScore: row.close_score,
  };
}

function listPortfolioPending(deskId: string): ReplacementCandidate[] {
  const filePath = PORTFOLIO_PENDING_PATHS[deskId];
  if (!filePath) return [];
  const data = readJsonFile<{ proposals?: PendingProposalRow[] }>(filePath);
  if (!data?.proposals?.length) return [];
  return data.proposals
    .map(mapPortfolioProposal)
    .filter((row): row is ReplacementCandidate => row !== null);
}

function latestTechProcessLog(): { date: string; log: Record<string, unknown> } | null {
  const processDir = path.join(TRADINGAGENTS_HOME, "tech_desk", "process");
  if (!fs.existsSync(processDir)) return null;
  const files = fs
    .readdirSync(processDir)
    .filter((f) => f.endsWith(".json") && !f.startsWith("review_"))
    .sort()
    .reverse();
  if (files.length === 0) return null;
  const date = files[0]!.replace(".json", "");
  const log = readJsonFile<Record<string, unknown>>(path.join(processDir, files[0]!));
  if (!log) return null;
  return { date, log };
}

function listTechDeskPending(): ReplacementCandidate[] {
  const latest = latestTechProcessLog();
  if (!latest) return [];
  const pending = latest.log.pending_replacements;
  if (!Array.isArray(pending) || pending.length === 0) return [];

  return (pending as TechPendingRow[])
    .map((row): ReplacementCandidate | null => {
      const foreclose = row.foreclose ?? "";
      const openTicker = row.open ?? "";
      if (!foreclose || !openTicker) return null;
      const id = row.id ?? `${foreclose}->${openTicker}`;
      return {
        id,
        closeTicker: foreclose,
        closeName: foreclose,
        newTicker: openTicker,
        newName: openTicker,
        processDate: latest.date,
        closeScore: row.foreclose_confidence,
      };
    })
    .filter((row): row is ReplacementCandidate => row !== null);
}

export function listPendingReplacements(deskId: string): ReplacementCandidate[] {
  if (deskId === "tech-desk") return listTechDeskPending();
  return listPortfolioPending(deskId);
}
