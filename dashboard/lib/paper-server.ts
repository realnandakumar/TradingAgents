import os from "os";
import path from "path";

import type { PaperSnapshot, ScreenSnapshot, SnapshotRow } from "./types";
import { readJsonFile } from "@/lib/parse-book-json";

const HOME = path.join(os.homedir(), ".tradingagents", "paper");
const DEFAULT_PAPER = path.join(HOME, "paper_snapshot.json");
const DEFAULT_SCREENS = path.join(HOME, "screens.json");

export function paperSnapshotPath(): string {
  return process.env.PAPER_SNAPSHOT_PATH ?? process.env.TRADINGAGENTS_PAPER_SNAPSHOT_PATH ?? DEFAULT_PAPER;
}

export function screensPath(): string {
  return process.env.PAPER_SCREENS_PATH ?? process.env.TRADINGAGENTS_PAPER_SCREENS_PATH ?? DEFAULT_SCREENS;
}

function readJson<T>(filePath: string): T | null {
  return readJsonFile<T>(filePath);
}

export function getLatestPaper(): SnapshotRow<PaperSnapshot> | null {
  return readJson<SnapshotRow<PaperSnapshot>>(paperSnapshotPath());
}

export function getScreens(limit = 30): SnapshotRow<ScreenSnapshot>[] {
  const rows = readJson<SnapshotRow<ScreenSnapshot>[]>(screensPath());
  if (!Array.isArray(rows)) return [];
  return rows.slice(0, limit);
}

export function getLatestScreen(): SnapshotRow<ScreenSnapshot> | null {
  return getScreens(1)[0] ?? null;
}
